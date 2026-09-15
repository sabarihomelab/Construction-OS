import csv
import io
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import (
    BOQ,
    BOQItem,
    BOQRevision,
    BOQStatus,
    RecordStatus,
    WBSCode,
)
from app.modules.events.service import enqueue_event
from app.modules.projects.models import Project
from app.modules.search.service import schedule_search_index


class BOQValidationError(ValueError):
    pass


class BOQConflictError(ValueError):
    pass


MONEY_QUANT = Decimal("0.01")
MAX_IMPORT_ROWS = 5000
CSV_REQUIRED_FIELDS = {
    "line_number",
    "item_code",
    "description",
    "unit_code",
    "quantity",
    "rate",
}
CSV_OPTIONAL_FIELDS = {"wbs_code", "hsn_sac", "notes"}
CSV_FIELDS = (
    "line_number",
    "item_code",
    "description",
    "unit_code",
    "quantity",
    "rate",
    "wbs_code",
    "hsn_sac",
    "notes",
)


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _decimal_places(value: Decimal) -> int:
    exponent = value.as_tuple().exponent
    return max(0, -exponent)


async def _require_project(db: AsyncSession, organization_id: UUID, project_id: UUID) -> None:
    project = await db.scalar(
        select(Project.id).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise BOQValidationError("Project was not found")


async def _load_boq(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    boq_id: UUID,
    for_update: bool = False,
) -> BOQ:
    statement = select(BOQ).where(
        BOQ.id == boq_id,
        BOQ.organization_id == organization_id,
        BOQ.project_id == project_id,
    )
    if for_update:
        statement = statement.with_for_update()
    boq = await db.scalar(statement)
    if boq is None:
        raise BOQValidationError("BOQ was not found")
    return boq


async def _load_draft_boq(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    boq_id: UUID,
    for_update: bool = True,
) -> BOQ:
    boq = await _load_boq(
        db,
        organization_id=organization_id,
        project_id=project_id,
        boq_id=boq_id,
        for_update=for_update,
    )
    if boq.status != BOQStatus.DRAFT:
        raise BOQValidationError("Only a draft BOQ can be edited")
    return boq


async def _require_active_wbs(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    wbs_code_id: UUID | None,
) -> WBSCode | None:
    if wbs_code_id is None:
        return None
    row = await db.scalar(
        select(WBSCode).where(
            WBSCode.id == wbs_code_id,
            WBSCode.organization_id == organization_id,
            WBSCode.project_id == project_id,
        )
    )
    if row is None:
        raise BOQValidationError("WBS code was not found in this project")
    if row.status != RecordStatus.ACTIVE:
        raise BOQValidationError("BOQ items can only be mapped to an active WBS code")
    return row


def _boq_item_reference_columns():
    from app.db import model_registry as _model_registry  # noqa: F401

    for table in Base.metadata.tables.values():
        if table.name == "project_boq_items":
            continue
        for column in table.c:
            if any(
                foreign_key.column.table.name == "project_boq_items"
                for foreign_key in column.foreign_keys
            ):
                yield table, column


async def _boq_item_usage_count(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    item_id: UUID,
) -> int:
    count = 0
    for table, column in _boq_item_reference_columns():
        filters = [column == item_id]
        if "organization_id" in table.c:
            filters.append(table.c.organization_id == organization_id)
        if "project_id" in table.c:
            filters.append(table.c.project_id == project_id)
        count += int(await db.scalar(select(func.count()).select_from(table).where(*filters)) or 0)
    return count


def _boq_reference_columns():
    from app.db import model_registry as _model_registry  # noqa: F401

    owned_tables = {"project_boq_items", "project_boq_revisions"}
    for table in Base.metadata.tables.values():
        if table.name in owned_tables or table.name == "project_boqs":
            continue
        for column in table.c:
            if any(foreign_key.column.table.name == "project_boqs" for foreign_key in column.foreign_keys):
                yield table, column


async def _boq_downstream_usage_count(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    boq_id: UUID,
) -> int:
    count = 0
    for table, column in _boq_reference_columns():
        filters = [column == boq_id]
        if "organization_id" in table.c:
            filters.append(table.c.organization_id == organization_id)
        if "project_id" in table.c:
            filters.append(table.c.project_id == project_id)
        count += int(await db.scalar(select(func.count()).select_from(table).where(*filters)) or 0)

    item_ids = list(
        (
            await db.scalars(
                select(BOQItem.id).where(
                    BOQItem.organization_id == organization_id,
                    BOQItem.project_id == project_id,
                    BOQItem.boq_id == boq_id,
                )
            )
        ).all()
    )
    for item_id in item_ids:
        count += await _boq_item_usage_count(
            db,
            organization_id=organization_id,
            project_id=project_id,
            item_id=item_id,
        )
    return count


async def _publish_change(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    event_type: str,
    entity_id: UUID,
    entity_version: int,
    actor_user_id: UUID,
    session_id: UUID | None,
) -> None:
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type=event_type,
        entity_type="boq",
        entity_id=entity_id,
        entity_version=entity_version,
        required_permission_key="commercial.boq.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": entity_version},
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type="boq",
        entity_id=entity_id,
        entity_version=entity_version,
    )


async def list_boqs(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> list[BOQ]:
    await _require_project(db, organization_id, project_id)
    rows = await db.scalars(
        select(BOQ)
        .where(BOQ.organization_id == organization_id, BOQ.project_id == project_id)
        .order_by(BOQ.created_at.desc(), BOQ.code)
    )
    return list(rows.all())


async def get_boq_context(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    boq_id: UUID,
) -> tuple[BOQ, list[BOQItem], int]:
    boq = await _load_boq(
        db,
        organization_id=organization_id,
        project_id=project_id,
        boq_id=boq_id,
    )
    items = list(
        (
            await db.scalars(
                select(BOQItem)
                .where(
                    BOQItem.organization_id == organization_id,
                    BOQItem.project_id == project_id,
                    BOQItem.boq_id == boq_id,
                )
                .order_by(BOQItem.line_number, BOQItem.item_code)
            )
        ).all()
    )
    revision_count = int(
        await db.scalar(
            select(func.count(BOQRevision.id)).where(
                BOQRevision.organization_id == organization_id,
                BOQRevision.project_id == project_id,
                BOQRevision.boq_id == boq_id,
            )
        )
        or 0
    )
    return boq, items, revision_count


async def create_boq(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> BOQ:
    await _require_project(db, organization_id, project_id)
    data = dict(values)
    data.pop("organization_id", None)
    data.pop("project_id", None)
    code = str(data.get("code") or "").strip().upper()
    name = str(data.get("name") or "").strip()
    currency = str(data.get("currency_code") or "INR").strip().upper()
    if not code or not name:
        raise BOQValidationError("BOQ code and name are required")
    if len(currency) != 3 or not currency.isalpha():
        raise BOQValidationError("BOQ currency must be a three-letter currency code")
    duplicate = await db.scalar(
        select(BOQ.id).where(
            BOQ.organization_id == organization_id,
            BOQ.project_id == project_id,
            BOQ.code == code,
        )
    )
    if duplicate is not None:
        raise BOQConflictError("BOQ code already exists in this project")
    data["code"] = code
    data["name"] = name
    data["currency_code"] = currency
    boq = BOQ(organization_id=organization_id, project_id=project_id, **data)
    db.add(boq)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="commercial.boq.created",
        target_type="boq",
        target_id=str(boq.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"code": boq.code, "name": boq.name, "currency_code": boq.currency_code},
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="commercial.boq.created",
        entity_id=boq.id,
        entity_version=boq.revision,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return boq


async def update_boq(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    boq_id: UUID,
    expected_revision: int,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> BOQ:
    boq = await _load_draft_boq(
        db,
        organization_id=organization_id,
        project_id=project_id,
        boq_id=boq_id,
    )
    if boq.revision != expected_revision:
        raise BOQConflictError("BOQ changed; refresh before saving")
    before = {
        "name": boq.name,
        "description": boq.description,
        "currency_code": boq.currency_code,
        "revision": boq.revision,
    }
    if "name" in changes:
        name = str(changes.get("name") or "").strip()
        if not name:
            raise BOQValidationError("BOQ name cannot be blank")
        boq.name = name
    if "description" in changes:
        description = changes.get("description")
        boq.description = str(description).strip() if isinstance(description, str) else None
    if "currency_code" in changes and changes.get("currency_code") is not None:
        currency = str(changes["currency_code"]).strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise BOQValidationError("BOQ currency must be a three-letter currency code")
        if currency != boq.currency_code:
            item_count = int(
                await db.scalar(select(func.count(BOQItem.id)).where(BOQItem.boq_id == boq.id)) or 0
            )
            if item_count:
                raise BOQValidationError("Currency cannot change after BOQ items have been added")
            boq.currency_code = currency
    boq.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="commercial.boq.updated",
        target_type="boq",
        target_id=str(boq.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={
            "before": before,
            "after": {
                "name": boq.name,
                "description": boq.description,
                "currency_code": boq.currency_code,
                "revision": boq.revision,
            },
        },
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="commercial.boq.updated",
        entity_id=boq.id,
        entity_version=boq.revision,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return boq


async def _ensure_unique_item_identity(
    db: AsyncSession,
    *,
    boq_id: UUID,
    line_number: int,
    item_code: str,
    current_item_id: UUID | None = None,
) -> None:
    statement = select(BOQItem.id).where(
        BOQItem.boq_id == boq_id,
        (BOQItem.line_number == line_number) | (BOQItem.item_code == item_code),
    )
    if current_item_id is not None:
        statement = statement.where(BOQItem.id != current_item_id)
    duplicate = await db.scalar(statement)
    if duplicate is not None:
        raise BOQConflictError("BOQ line number or item code already exists")


async def add_boq_item(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    boq_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> BOQItem:
    boq = await _load_draft_boq(
        db,
        organization_id=organization_id,
        project_id=project_id,
        boq_id=boq_id,
    )
    expected_boq_revision = values.get("expected_boq_revision")
    if isinstance(expected_boq_revision, int) and boq.revision != expected_boq_revision:
        raise BOQConflictError("BOQ changed; refresh before adding an item")
    data = dict(values)
    data.pop("expected_boq_revision", None)
    data.pop("organization_id", None)
    data.pop("project_id", None)
    data.pop("boq_id", None)
    line_number = int(data["line_number"])
    item_code = str(data.get("item_code") or "").strip().upper()
    description = str(data.get("description") or "").strip()
    unit_code = str(data.get("unit_code") or "").strip().upper()
    quantity = Decimal(str(data["quantity"]))
    rate = Decimal(str(data["rate"]))
    if not item_code or not description or not unit_code:
        raise BOQValidationError("Item code, description and unit are required")
    await _ensure_unique_item_identity(
        db,
        boq_id=boq_id,
        line_number=line_number,
        item_code=item_code,
    )
    wbs = await _require_active_wbs(
        db,
        organization_id=organization_id,
        project_id=project_id,
        wbs_code_id=data.get("wbs_code_id") if isinstance(data.get("wbs_code_id"), UUID) else None,
    )
    data["line_number"] = line_number
    data["item_code"] = item_code
    data["description"] = description
    data["unit_code"] = unit_code
    data["quantity"] = quantity
    data["rate"] = money(rate)
    data["amount"] = money(quantity * rate)
    data["wbs_code_id"] = wbs.id if wbs is not None else None
    if isinstance(data.get("hsn_sac"), str):
        data["hsn_sac"] = str(data["hsn_sac"]).strip().upper() or None
    item = BOQItem(
        organization_id=organization_id,
        project_id=project_id,
        boq_id=boq_id,
        **data,
    )
    db.add(item)
    boq.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="commercial.boq_item.created",
        target_type="boq_item",
        target_id=str(item.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "boq_id": str(boq.id),
            "line_number": item.line_number,
            "item_code": item.item_code,
            "amount": str(item.amount),
            "wbs_code_id": str(item.wbs_code_id) if item.wbs_code_id else None,
        },
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="commercial.boq.updated",
        entity_id=boq.id,
        entity_version=boq.revision,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return item


async def update_boq_item(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    boq_id: UUID,
    item_id: UUID,
    expected_revision: int,
    expected_boq_revision: int | None,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> BOQItem:
    boq = await _load_draft_boq(
        db,
        organization_id=organization_id,
        project_id=project_id,
        boq_id=boq_id,
    )
    if expected_boq_revision is not None and boq.revision != expected_boq_revision:
        raise BOQConflictError("BOQ changed; refresh before saving the item")
    item = await db.scalar(
        select(BOQItem)
        .where(
            BOQItem.id == item_id,
            BOQItem.organization_id == organization_id,
            BOQItem.project_id == project_id,
            BOQItem.boq_id == boq_id,
        )
        .with_for_update()
    )
    if item is None:
        raise BOQValidationError("BOQ item was not found")
    if item.revision != expected_revision:
        raise BOQConflictError("BOQ item changed; refresh before saving")
    usage_count = await _boq_item_usage_count(
        db,
        organization_id=organization_id,
        project_id=project_id,
        item_id=item.id,
    )
    if usage_count:
        raise BOQValidationError(
            "This BOQ item is already referenced by downstream records and cannot be edited"
        )

    line_number = int(changes.get("line_number", item.line_number))
    item_code = str(changes.get("item_code", item.item_code)).strip().upper()
    await _ensure_unique_item_identity(
        db,
        boq_id=boq_id,
        line_number=line_number,
        item_code=item_code,
        current_item_id=item.id,
    )
    if "wbs_code_id" in changes:
        raw_wbs = changes.get("wbs_code_id")
        wbs = await _require_active_wbs(
            db,
            organization_id=organization_id,
            project_id=project_id,
            wbs_code_id=raw_wbs if isinstance(raw_wbs, UUID) else None,
        )
        item.wbs_code_id = wbs.id if wbs is not None else None
    if "description" in changes:
        description = str(changes.get("description") or "").strip()
        if not description:
            raise BOQValidationError("BOQ item description cannot be blank")
        item.description = description
    if "unit_code" in changes:
        unit_code = str(changes.get("unit_code") or "").strip().upper()
        if not unit_code:
            raise BOQValidationError("BOQ item unit cannot be blank")
        item.unit_code = unit_code
    if "quantity" in changes and changes.get("quantity") is not None:
        item.quantity = Decimal(str(changes["quantity"]))
    if "rate" in changes and changes.get("rate") is not None:
        item.rate = money(Decimal(str(changes["rate"])))
    if "hsn_sac" in changes:
        hsn = changes.get("hsn_sac")
        item.hsn_sac = str(hsn).strip().upper() if isinstance(hsn, str) and hsn.strip() else None
    if "notes" in changes:
        notes = changes.get("notes")
        item.notes = str(notes).strip() if isinstance(notes, str) and notes.strip() else None
    item.line_number = line_number
    item.item_code = item_code
    item.amount = money(Decimal(item.quantity) * Decimal(item.rate))
    item.revision += 1
    boq.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="commercial.boq_item.updated",
        target_type="boq_item",
        target_id=str(item.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={
            "boq_id": str(boq.id),
            "line_number": item.line_number,
            "item_code": item.item_code,
            "revision": item.revision,
            "amount": str(item.amount),
        },
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="commercial.boq.updated",
        entity_id=boq.id,
        entity_version=boq.revision,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return item


async def delete_boq_item(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    boq_id: UUID,
    item_id: UUID,
    expected_revision: int,
    expected_boq_revision: int | None,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> BOQ:
    boq = await _load_draft_boq(
        db,
        organization_id=organization_id,
        project_id=project_id,
        boq_id=boq_id,
    )
    if expected_boq_revision is not None and boq.revision != expected_boq_revision:
        raise BOQConflictError("BOQ changed; refresh before deleting the item")
    item = await db.scalar(
        select(BOQItem)
        .where(
            BOQItem.id == item_id,
            BOQItem.organization_id == organization_id,
            BOQItem.project_id == project_id,
            BOQItem.boq_id == boq_id,
        )
        .with_for_update()
    )
    if item is None:
        raise BOQValidationError("BOQ item was not found")
    if item.revision != expected_revision:
        raise BOQConflictError("BOQ item changed; refresh before deleting")
    usage_count = await _boq_item_usage_count(
        db,
        organization_id=organization_id,
        project_id=project_id,
        item_id=item.id,
    )
    if usage_count:
        raise BOQValidationError("Referenced BOQ items cannot be deleted")
    item_snapshot = {
        "id": str(item.id),
        "line_number": item.line_number,
        "item_code": item.item_code,
        "amount": str(item.amount),
    }
    await db.delete(item)
    boq.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="commercial.boq_item.deleted",
        target_type="boq_item",
        target_id=str(item_id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"before": item_snapshot, "boq_id": str(boq.id)},
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="commercial.boq.updated",
        entity_id=boq.id,
        entity_version=boq.revision,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return boq


async def approve_boq(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    boq_id: UUID,
    expected_revision: int,
    membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> BOQ:
    boq = await _load_draft_boq(
        db,
        organization_id=organization_id,
        project_id=project_id,
        boq_id=boq_id,
    )
    if boq.revision != expected_revision:
        raise BOQConflictError("BOQ changed; refresh before approval")
    items = list(
        (
            await db.scalars(
                select(BOQItem)
                .where(
                    BOQItem.organization_id == organization_id,
                    BOQItem.project_id == project_id,
                    BOQItem.boq_id == boq.id,
                )
                .order_by(BOQItem.line_number)
            )
        ).all()
    )
    if not items:
        raise BOQValidationError("BOQ cannot be approved without items")
    wbs_ids = {item.wbs_code_id for item in items if item.wbs_code_id is not None}
    wbs_by_id: dict[UUID, WBSCode] = {}
    if wbs_ids:
        wbs_rows = list(
            (
                await db.scalars(
                    select(WBSCode).where(
                        WBSCode.organization_id == organization_id,
                        WBSCode.project_id == project_id,
                        WBSCode.id.in_(wbs_ids),
                    )
                )
            ).all()
        )
        wbs_by_id = {row.id: row for row in wbs_rows}
        if len(wbs_by_id) != len(wbs_ids) or any(
            row.status != RecordStatus.ACTIVE for row in wbs_by_id.values()
        ):
            raise BOQValidationError("All mapped WBS codes must still be active before approval")

    version_number = int(
        await db.scalar(
            select(func.coalesce(func.max(BOQRevision.version_number), 0)).where(
                BOQRevision.organization_id == organization_id,
                BOQRevision.project_id == project_id,
                BOQRevision.boq_id == boq.id,
            )
        )
        or 0
    ) + 1
    approved_at = datetime.now(UTC)
    total_amount = money(sum((Decimal(item.amount) for item in items), start=Decimal("0")))
    snapshot = {
        "boq": {
            "id": str(boq.id),
            "code": boq.code,
            "name": boq.name,
            "description": boq.description,
            "currency_code": boq.currency_code,
            "revision": boq.revision,
            "version_number": version_number,
            "approved_at": approved_at.isoformat(),
            "total_amount": str(total_amount),
        },
        "items": [
            {
                "id": str(item.id),
                "line_number": item.line_number,
                "item_code": item.item_code,
                "wbs_code_id": str(item.wbs_code_id) if item.wbs_code_id else None,
                "wbs_code": wbs_by_id[item.wbs_code_id].code if item.wbs_code_id else None,
                "description": item.description,
                "unit_code": item.unit_code,
                "quantity": str(item.quantity),
                "rate": str(item.rate),
                "amount": str(item.amount),
                "hsn_sac": item.hsn_sac,
                "notes": item.notes,
                "revision": item.revision,
            }
            for item in items
        ],
    }
    revision = BOQRevision(
        organization_id=organization_id,
        project_id=project_id,
        boq_id=boq.id,
        version_number=version_number,
        approved_by_membership_id=membership_id,
        approved_at=approved_at,
        snapshot_json=json.dumps(snapshot, separators=(",", ":"), sort_keys=True),
        reason=reason,
    )
    db.add(revision)
    boq.status = BOQStatus.APPROVED
    boq.approved_by_membership_id = membership_id
    boq.approved_at = approved_at
    boq.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="commercial.boq.approved",
        target_type="boq",
        target_id=str(boq.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.CRITICAL,
        reason=reason,
        changes={
            "status": boq.status.value,
            "revision": boq.revision,
            "version_number": version_number,
            "total_amount": str(total_amount),
        },
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="commercial.boq.approved",
        entity_id=boq.id,
        entity_version=boq.revision,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return boq


async def cancel_boq(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    boq_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> BOQ:
    boq = await _load_draft_boq(
        db,
        organization_id=organization_id,
        project_id=project_id,
        boq_id=boq_id,
    )
    if boq.revision != expected_revision:
        raise BOQConflictError("BOQ changed; refresh before cancellation")
    if not reason or not reason.strip():
        raise BOQValidationError("A reason is required to cancel a BOQ")
    usage_count = await _boq_downstream_usage_count(
        db,
        organization_id=organization_id,
        project_id=project_id,
        boq_id=boq_id,
    )
    if usage_count:
        raise BOQValidationError("A BOQ referenced by downstream records cannot be cancelled")
    boq.status = BOQStatus.CANCELLED
    boq.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="commercial.boq.cancelled",
        target_type="boq",
        target_id=str(boq.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": boq.status.value, "revision": boq.revision},
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="commercial.boq.cancelled",
        entity_id=boq.id,
        entity_version=boq.revision,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return boq


async def list_boq_revisions(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    boq_id: UUID,
) -> list[BOQRevision]:
    await _load_boq(
        db,
        organization_id=organization_id,
        project_id=project_id,
        boq_id=boq_id,
    )
    rows = await db.scalars(
        select(BOQRevision)
        .where(
            BOQRevision.organization_id == organization_id,
            BOQRevision.project_id == project_id,
            BOQRevision.boq_id == boq_id,
        )
        .order_by(BOQRevision.version_number.desc())
    )
    return list(rows.all())


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _parse_decimal(raw: str, *, field: str, max_places: int, errors: list[str]) -> Decimal | None:
    try:
        value = Decimal(raw.strip())
    except (InvalidOperation, ValueError):
        errors.append(f"{field} must be numeric")
        return None
    if value < 0:
        errors.append(f"{field} cannot be negative")
        return None
    if _decimal_places(value) > max_places:
        errors.append(f"{field} supports at most {max_places} decimal places")
        return None
    return value


async def preview_boq_import(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    boq_id: UUID,
    csv_text: str,
    for_update: bool = False,
) -> tuple[BOQ, list[dict[str, object]], Decimal]:
    boq = await _load_draft_boq(
        db,
        organization_id=organization_id,
        project_id=project_id,
        boq_id=boq_id,
        for_update=for_update,
    )
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    if not reader.fieldnames:
        raise BOQValidationError("CSV header row is required")
    header_map = {_normalize_header(name): name for name in reader.fieldnames if name is not None}
    missing = sorted(CSV_REQUIRED_FIELDS - set(header_map))
    if missing:
        raise BOQValidationError(f"CSV is missing required columns: {', '.join(missing)}")

    existing_items = list(
        (
            await db.scalars(
                select(BOQItem).where(
                    BOQItem.organization_id == organization_id,
                    BOQItem.project_id == project_id,
                    BOQItem.boq_id == boq_id,
                )
            )
        ).all()
    )
    existing_lines = {item.line_number for item in existing_items}
    existing_codes = {item.item_code.upper() for item in existing_items}
    wbs_rows = list(
        (
            await db.scalars(
                select(WBSCode).where(
                    WBSCode.organization_id == organization_id,
                    WBSCode.project_id == project_id,
                )
            )
        ).all()
    )
    wbs_by_code = {row.code.upper(): row for row in wbs_rows}
    seen_lines: set[int] = set()
    seen_codes: set[str] = set()
    prepared: list[dict[str, object]] = []
    total = Decimal("0")

    for row_number, raw_row in enumerate(reader, start=2):
        if row_number - 1 > MAX_IMPORT_ROWS:
            raise BOQValidationError(f"CSV import is limited to {MAX_IMPORT_ROWS} data rows")
        if not any(str(value or "").strip() for value in raw_row.values()):
            continue
        errors: list[str] = []

        def cell(name: str) -> str:
            original = header_map.get(name)
            return str(raw_row.get(original, "") or "").strip() if original else ""

        line_number: int | None = None
        line_raw = cell("line_number")
        try:
            line_number = int(line_raw)
            if line_number < 1:
                raise ValueError
        except ValueError:
            errors.append("line_number must be a positive integer")
            line_number = None

        item_code = cell("item_code").upper()
        description = cell("description")
        unit_code = cell("unit_code").upper()
        if not item_code:
            errors.append("item_code is required")
        elif len(item_code) > 80:
            errors.append("item_code exceeds 80 characters")
        if not description:
            errors.append("description is required")
        if not unit_code:
            errors.append("unit_code is required")
        elif len(unit_code) > 24:
            errors.append("unit_code exceeds 24 characters")

        quantity = _parse_decimal(cell("quantity"), field="quantity", max_places=3, errors=errors)
        rate = _parse_decimal(cell("rate"), field="rate", max_places=2, errors=errors)
        amount = money(quantity * rate) if quantity is not None and rate is not None else None

        wbs_code = cell("wbs_code").upper() or None
        wbs_code_id: UUID | None = None
        if wbs_code:
            wbs = wbs_by_code.get(wbs_code)
            if wbs is None:
                errors.append("wbs_code was not found in this project")
            elif wbs.status != RecordStatus.ACTIVE:
                errors.append("wbs_code is inactive")
            else:
                wbs_code_id = wbs.id

        hsn_sac = cell("hsn_sac").upper() or None
        if hsn_sac and len(hsn_sac) > 16:
            errors.append("hsn_sac exceeds 16 characters")
        notes = cell("notes") or None

        if line_number is not None:
            if line_number in existing_lines:
                errors.append("line_number already exists in this BOQ")
            if line_number in seen_lines:
                errors.append("line_number is duplicated in this CSV")
            seen_lines.add(line_number)
        if item_code:
            if item_code in existing_codes:
                errors.append("item_code already exists in this BOQ")
            if item_code in seen_codes:
                errors.append("item_code is duplicated in this CSV")
            seen_codes.add(item_code)

        prepared.append(
            {
                "row_number": row_number,
                "line_number": line_number,
                "item_code": item_code,
                "description": description,
                "unit_code": unit_code,
                "quantity": quantity,
                "rate": rate,
                "amount": amount,
                "wbs_code": wbs_code,
                "wbs_code_id": wbs_code_id,
                "hsn_sac": hsn_sac,
                "notes": notes,
                "errors": errors,
            }
        )
        if amount is not None and not errors:
            total += amount

    if not prepared:
        raise BOQValidationError("CSV contains no data rows")
    return boq, prepared, money(total)


async def apply_boq_import(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    boq_id: UUID,
    expected_revision: int,
    csv_text: str,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> tuple[int, Decimal, BOQ]:
    boq, rows, total = await preview_boq_import(
        db,
        organization_id=organization_id,
        project_id=project_id,
        boq_id=boq_id,
        csv_text=csv_text,
        for_update=True,
    )
    if boq.revision != expected_revision:
        raise BOQConflictError("BOQ changed; refresh and preview the CSV again")
    invalid = [row for row in rows if row["errors"]]
    if invalid:
        raise BOQValidationError(
            f"CSV contains {len(invalid)} invalid row(s); preview and correct them before import"
        )
    for row in rows:
        db.add(
            BOQItem(
                organization_id=organization_id,
                project_id=project_id,
                boq_id=boq_id,
                wbs_code_id=row["wbs_code_id"],
                line_number=int(row["line_number"]),
                item_code=str(row["item_code"]),
                description=str(row["description"]),
                unit_code=str(row["unit_code"]),
                quantity=Decimal(row["quantity"]),
                rate=money(Decimal(row["rate"])),
                amount=money(Decimal(row["amount"])),
                hsn_sac=row["hsn_sac"],
                notes=row["notes"],
            )
        )
    boq.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="commercial.boq.imported",
        target_type="boq",
        target_id=str(boq.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={
            "imported_rows": len(rows),
            "import_total": str(total),
            "revision": boq.revision,
        },
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        event_type="commercial.boq.imported",
        entity_id=boq.id,
        entity_version=boq.revision,
        actor_user_id=actor_user_id,
        session_id=session_id,
    )
    return len(rows), total, boq


def _render_csv_rows(rows: list[dict[str, object]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") if row.get(field) is not None else "" for field in CSV_FIELDS})
    return output.getvalue()


async def export_boq_csv(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    boq_id: UUID,
) -> tuple[str, str]:
    boq, items, _revision_count = await get_boq_context(
        db,
        organization_id=organization_id,
        project_id=project_id,
        boq_id=boq_id,
    )
    wbs_ids = {item.wbs_code_id for item in items if item.wbs_code_id is not None}
    wbs_by_id: dict[UUID, str] = {}
    if wbs_ids:
        rows = await db.execute(
            select(WBSCode.id, WBSCode.code).where(
                WBSCode.organization_id == organization_id,
                WBSCode.project_id == project_id,
                WBSCode.id.in_(wbs_ids),
            )
        )
        wbs_by_id = {row.id: row.code for row in rows}
    csv_rows = [
        {
            "line_number": item.line_number,
            "item_code": item.item_code,
            "description": item.description,
            "unit_code": item.unit_code,
            "quantity": str(item.quantity),
            "rate": str(item.rate),
            "wbs_code": wbs_by_id.get(item.wbs_code_id, "") if item.wbs_code_id else "",
            "hsn_sac": item.hsn_sac or "",
            "notes": item.notes or "",
        }
        for item in items
    ]
    return f"{boq.code}.csv", _render_csv_rows(csv_rows)


async def export_boq_revision_csv(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    boq_id: UUID,
    version_number: int,
) -> tuple[str, str]:
    revision = await db.scalar(
        select(BOQRevision).where(
            BOQRevision.organization_id == organization_id,
            BOQRevision.project_id == project_id,
            BOQRevision.boq_id == boq_id,
            BOQRevision.version_number == version_number,
        )
    )
    if revision is None:
        raise BOQValidationError("BOQ revision was not found")
    snapshot = json.loads(revision.snapshot_json)
    boq = snapshot.get("boq") or {}
    items = snapshot.get("items") or []
    csv_rows = [
        {
            "line_number": item.get("line_number", ""),
            "item_code": item.get("item_code", ""),
            "description": item.get("description", ""),
            "unit_code": item.get("unit_code", ""),
            "quantity": item.get("quantity", ""),
            "rate": item.get("rate", ""),
            "wbs_code": item.get("wbs_code", ""),
            "hsn_sac": item.get("hsn_sac", ""),
            "notes": item.get("notes", ""),
        }
        for item in items
    ]
    code = str(boq.get("code") or "BOQ")
    return f"{code}-approved-v{version_number}.csv", _render_csv_rows(csv_rows)


def boq_csv_template() -> str:
    return _render_csv_rows(
        [
            {
                "line_number": 1,
                "item_code": "CIV-CONC-001",
                "description": "Example concrete work",
                "unit_code": "M3",
                "quantity": "10.000",
                "rate": "7500.00",
                "wbs_code": "",
                "hsn_sac": "",
                "notes": "Delete this example row before import",
            }
        ]
    )
