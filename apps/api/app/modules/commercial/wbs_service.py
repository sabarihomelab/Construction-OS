from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import RecordStatus, WBSCode
from app.modules.events.service import enqueue_event
from app.modules.projects.models import Project
from app.modules.search.service import schedule_search_index


class WBSValidationError(ValueError):
    pass


class WBSConflictError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class WBSUsageSummary:
    direct_count: int
    subtree_count: int
    usage_areas: tuple[str, ...]


_USAGE_LABELS = {
    "project_boq_items": "BOQ items",
    "estimate_items": "estimate items",
    "project_budget_lines": "budget lines",
    "purchase_requisition_lines": "purchase requisitions",
    "purchase_order_lines": "purchase orders",
    "material_consumptions": "material consumption",
    "equipment_usages": "equipment usage",
    "subcontract_lines": "subcontracts",
    "job_cost_entries": "job cost",
    "vendor_bill_lines": "vendor bills",
}


def _usage_label(table_name: str) -> str:
    return _USAGE_LABELS.get(table_name, table_name.replace("_", " "))


async def _require_project(db: AsyncSession, organization_id: UUID, project_id: UUID) -> None:
    project = await db.scalar(
        select(Project.id).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise WBSValidationError("Project was not found")


async def _load_project_rows(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> list[WBSCode]:
    rows = await db.scalars(
        select(WBSCode).where(
            WBSCode.organization_id == organization_id,
            WBSCode.project_id == project_id,
        )
    )
    return list(rows.all())


def _children_by_parent(rows: Iterable[WBSCode]) -> dict[UUID | None, list[WBSCode]]:
    grouped: dict[UUID | None, list[WBSCode]] = defaultdict(list)
    for row in rows:
        grouped[row.parent_id].append(row)
    for children in grouped.values():
        children.sort(key=lambda item: (item.code, item.name, str(item.id)))
    return grouped


def _descendant_ids(rows: Iterable[WBSCode], root_id: UUID) -> set[UUID]:
    children = _children_by_parent(rows)
    descendants: set[UUID] = set()
    stack = list(children.get(root_id, ()))
    while stack:
        row = stack.pop()
        if row.id in descendants:
            continue
        descendants.add(row.id)
        stack.extend(children.get(row.id, ()))
    return descendants


def _path_rows(rows: Iterable[WBSCode], row: WBSCode) -> list[WBSCode]:
    by_id = {item.id: item for item in rows}
    path: list[WBSCode] = [row]
    seen = {row.id}
    cursor = row.parent_id
    while cursor is not None:
        parent = by_id.get(cursor)
        if parent is None or parent.id in seen:
            break
        path.append(parent)
        seen.add(parent.id)
        cursor = parent.parent_id
    path.reverse()
    return path


def flatten_wbs_tree(rows: Iterable[WBSCode]) -> list[tuple[WBSCode, int, tuple[str, ...], int]]:
    materialized = list(rows)
    children = _children_by_parent(materialized)
    flattened: list[tuple[WBSCode, int, tuple[str, ...], int]] = []

    def walk(parent_id: UUID | None, depth: int, path_codes: tuple[str, ...]) -> None:
        for row in children.get(parent_id, ()):
            current_path = (*path_codes, row.code)
            flattened.append((row, depth, current_path, len(children.get(row.id, ()))))
            walk(row.id, depth + 1, current_path)

    walk(None, 0, ())
    return flattened


async def _validate_parent(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    parent_id: UUID | None,
    current_id: UUID | None = None,
    require_active_chain: bool = True,
) -> WBSCode | None:
    if parent_id is None:
        return None

    seen = {current_id} if current_id is not None else set()
    cursor = parent_id
    parent: WBSCode | None = None
    while cursor is not None:
        if cursor in seen:
            raise WBSValidationError("WBS hierarchy cannot contain a cycle")
        seen.add(cursor)
        row = await db.scalar(
            select(WBSCode).where(
                WBSCode.id == cursor,
                WBSCode.organization_id == organization_id,
                WBSCode.project_id == project_id,
            )
        )
        if row is None:
            raise WBSValidationError("WBS parent was not found in this project")
        if parent is None:
            parent = row
        if require_active_chain and row.status != RecordStatus.ACTIVE:
            raise WBSValidationError("WBS parent hierarchy must be active")
        cursor = row.parent_id
    return parent


def _wbs_reference_tables():
    # Importing the model registry here keeps normal runtime module loading lightweight,
    # while structural edits can still discover every currently supported WBS consumer.
    from app.db import model_registry as _model_registry  # noqa: F401

    for table in Base.metadata.tables.values():
        if table.name == "project_wbs_codes" or "wbs_code_id" not in table.c:
            continue
        column = table.c.wbs_code_id
        if any(foreign_key.column.table.name == "project_wbs_codes" for foreign_key in column.foreign_keys):
            yield table


async def _usage_summary(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    direct_id: UUID,
    subtree_ids: set[UUID],
) -> WBSUsageSummary:
    direct_count = 0
    subtree_count = 0
    areas: set[str] = set()
    all_ids = {direct_id, *subtree_ids}

    for table in _wbs_reference_tables():
        filters = [table.c.wbs_code_id.in_(all_ids)]
        if "organization_id" in table.c:
            filters.append(table.c.organization_id == organization_id)
        if "project_id" in table.c:
            filters.append(table.c.project_id == project_id)
        count = int(await db.scalar(select(func.count()).select_from(table).where(*filters)) or 0)
        if not count:
            continue
        subtree_count += count
        areas.add(_usage_label(table.name))

        direct_filters = [table.c.wbs_code_id == direct_id]
        if "organization_id" in table.c:
            direct_filters.append(table.c.organization_id == organization_id)
        if "project_id" in table.c:
            direct_filters.append(table.c.project_id == project_id)
        direct_count += int(
            await db.scalar(select(func.count()).select_from(table).where(*direct_filters)) or 0
        )

    return WBSUsageSummary(
        direct_count=direct_count,
        subtree_count=subtree_count,
        usage_areas=tuple(sorted(areas)),
    )


async def _publish_change(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    row: WBSCode,
    event_type: str,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> None:
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type=event_type,
        entity_type="wbs_code",
        entity_id=row.id,
        entity_version=row.revision,
        required_permission_key="commercial.wbs.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": row.revision},
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type="wbs_code",
        entity_id=row.id,
        entity_version=row.revision,
    )


async def list_wbs_codes(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> list[WBSCode]:
    await _require_project(db, organization_id, project_id)
    rows = await _load_project_rows(
        db,
        organization_id=organization_id,
        project_id=project_id,
    )
    return [item[0] for item in flatten_wbs_tree(rows)]


async def create_wbs_code(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> WBSCode:
    await _require_project(db, organization_id, project_id)
    data = dict(values)
    code = str(data.get("code") or "").strip().upper()
    name = str(data.get("name") or "").strip()
    if not code or not name:
        raise WBSValidationError("WBS code and name are required")

    duplicate = await db.scalar(
        select(WBSCode.id).where(
            WBSCode.organization_id == organization_id,
            WBSCode.project_id == project_id,
            WBSCode.code == code,
        )
    )
    if duplicate is not None:
        raise WBSConflictError("WBS code already exists in this project")

    parent_id = data.get("parent_id")
    if parent_id is not None and not isinstance(parent_id, UUID):
        raise WBSValidationError("WBS parent identifier is invalid")
    await _validate_parent(
        db,
        organization_id=organization_id,
        project_id=project_id,
        parent_id=parent_id,
    )

    description = data.get("description")
    data["code"] = code
    data["name"] = name
    data["description"] = (
        str(description).strip() if description is not None and str(description).strip() else None
    )
    row = WBSCode(organization_id=organization_id, project_id=project_id, **data)
    db.add(row)
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="commercial.wbs.created",
        target_type="wbs_code",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={
            "after": {
                "project_id": str(project_id),
                "code": row.code,
                "name": row.name,
                "kind": row.kind.value,
                "parent_id": str(row.parent_id) if row.parent_id else None,
                "status": row.status.value,
                "revision": row.revision,
            }
        },
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        row=row,
        event_type="commercial.wbs.created",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def update_wbs_code(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    wbs_id: UUID,
    expected_revision: int,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> WBSCode:
    row = await db.scalar(
        select(WBSCode)
        .where(
            WBSCode.id == wbs_id,
            WBSCode.organization_id == organization_id,
            WBSCode.project_id == project_id,
        )
        .with_for_update()
    )
    if row is None:
        raise WBSValidationError("WBS code was not found")
    if row.revision != expected_revision:
        raise WBSConflictError("WBS code changed; refresh before saving")

    project_rows = await _load_project_rows(
        db,
        organization_id=organization_id,
        project_id=project_id,
    )
    descendants = _descendant_ids(project_rows, row.id)
    before = {
        "name": row.name,
        "kind": row.kind.value,
        "parent_id": str(row.parent_id) if row.parent_id else None,
        "status": row.status.value,
        "description": row.description,
        "revision": row.revision,
    }

    next_parent_id = changes.get("parent_id", row.parent_id)
    if next_parent_id is not None and not isinstance(next_parent_id, UUID):
        raise WBSValidationError("WBS parent identifier is invalid")
    parent_changed = "parent_id" in changes and next_parent_id != row.parent_id
    kind_changed = "kind" in changes and changes.get("kind") != row.kind

    if parent_changed:
        await _validate_parent(
            db,
            organization_id=organization_id,
            project_id=project_id,
            parent_id=next_parent_id,
            current_id=row.id,
        )

    if parent_changed or kind_changed:
        usage = await _usage_summary(
            db,
            organization_id=organization_id,
            project_id=project_id,
            direct_id=row.id,
            subtree_ids=descendants,
        )
        if usage.subtree_count:
            raise WBSValidationError(
                "WBS structure is already used by project records; parent and type can no longer change"
            )

    next_status = changes.get("status", row.status)
    if next_status == RecordStatus.INACTIVE and row.status != RecordStatus.INACTIVE:
        active_descendants = [
            item for item in project_rows if item.id in descendants and item.status == RecordStatus.ACTIVE
        ]
        if active_descendants:
            raise WBSValidationError("Deactivate child WBS codes before deactivating their parent")
    if next_status == RecordStatus.ACTIVE and row.status != RecordStatus.ACTIVE:
        await _validate_parent(
            db,
            organization_id=organization_id,
            project_id=project_id,
            parent_id=next_parent_id,
        )

    if "name" in changes:
        name = str(changes.get("name") or "").strip()
        if not name:
            raise WBSValidationError("WBS name cannot be blank")
        row.name = name
    if "description" in changes:
        description = changes.get("description")
        row.description = (
            str(description).strip()
            if description is not None and str(description).strip()
            else None
        )
    if parent_changed:
        row.parent_id = next_parent_id
    if kind_changed:
        row.kind = changes["kind"]
    if "status" in changes:
        row.status = changes["status"]

    row.revision += 1
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="commercial.wbs.updated",
        target_type="wbs_code",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH if parent_changed or kind_changed else AuditRisk.MEDIUM,
        reason=reason,
        changes={
            "before": before,
            "after": {
                "name": row.name,
                "kind": row.kind.value,
                "parent_id": str(row.parent_id) if row.parent_id else None,
                "status": row.status.value,
                "description": row.description,
                "revision": row.revision,
            },
        },
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        row=row,
        event_type="commercial.wbs.updated",
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return row


async def get_wbs_context(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    wbs_id: UUID,
) -> tuple[WBSCode, list[WBSCode], set[UUID], WBSUsageSummary]:
    row = await db.scalar(
        select(WBSCode).where(
            WBSCode.id == wbs_id,
            WBSCode.organization_id == organization_id,
            WBSCode.project_id == project_id,
        )
    )
    if row is None:
        raise WBSValidationError("WBS code was not found")
    project_rows = await _load_project_rows(
        db,
        organization_id=organization_id,
        project_id=project_id,
    )
    descendants = _descendant_ids(project_rows, row.id)
    usage = await _usage_summary(
        db,
        organization_id=organization_id,
        project_id=project_id,
        direct_id=row.id,
        subtree_ids=descendants,
    )
    return row, _path_rows(project_rows, row), descendants, usage


async def get_wbs_tree_context(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> list[tuple[WBSCode, int, tuple[str, ...], int]]:
    await _require_project(db, organization_id, project_id)
    rows = await _load_project_rows(
        db,
        organization_id=organization_id,
        project_id=project_id,
    )
    return flatten_wbs_tree(rows)
