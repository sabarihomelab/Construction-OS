import json
from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.commercial.models import (
    BOQ,
    BOQItem,
    BOQRevision,
    BOQStatus,
    MeasurementEntry,
    MeasurementStatus,
    Party,
    ProjectPartyAssignment,
    RABill,
    RABillLine,
    RABillMeasurement,
    RABillStatus,
    WBSCode,
)
from app.modules.events.service import enqueue_event
from app.modules.projects.models import Project
from app.modules.search.service import schedule_search_index


class CommercialValidationError(ValueError):
    pass


class CommercialConflictError(ValueError):
    pass


MONEY_QUANT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


async def _require_project(db: AsyncSession, organization_id: UUID, project_id: UUID) -> Project:
    project = await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
    )
    if project is None:
        raise CommercialValidationError("Project was not found")
    return project


async def _publish_change(
    db: AsyncSession,
    *,
    organization_id: UUID,
    event_type: str,
    entity_type: str,
    entity_id: UUID,
    entity_version: int,
    required_permission_key: str,
    actor_user_id: UUID,
    session_id: UUID | None,
    project_id: UUID | None = None,
    correlation_id: UUID | None = None,
) -> None:
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_version=entity_version,
        required_permission_key=required_permission_key,
        scope_type="project" if project_id is not None else None,
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        payload={"revision": entity_version},
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_version=entity_version,
        correlation_id=correlation_id,
    )


async def create_party(
    db: AsyncSession,
    *,
    organization_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
) -> Party:
    data = dict(values)
    data.pop("organization_id", None)
    code = str(data.get("code") or "").strip().upper()
    name = str(data.get("name") or "").strip()
    if not code or not name:
        raise CommercialValidationError("Party code and name are required")
    duplicate = await db.scalar(
        select(Party.id).where(Party.organization_id == organization_id, Party.code == code)
    )
    if duplicate is not None:
        raise CommercialConflictError("Party code already exists in this company")
    data["code"] = code
    data["name"] = name
    for key in ("gstin", "pan", "state_code"):
        if data.get(key):
            data[key] = str(data[key]).strip().upper()

    party = Party(organization_id=organization_id, **data)
    db.add(party)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="commercial.party.created",
        target_type="commercial_party",
        target_id=str(party.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.MEDIUM,
        changes={
            "after": {
                "code": party.code,
                "name": party.name,
                "party_type": party.party_type.value,
                "status": party.status.value,
                "revision": party.revision,
            }
        },
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        event_type="commercial.party.created",
        entity_type="commercial_party",
        entity_id=party.id,
        entity_version=party.revision,
        required_permission_key="commercial.party.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
    )
    return party


async def update_party(
    db: AsyncSession,
    *,
    organization_id: UUID,
    party_id: UUID,
    expected_revision: int,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
    reason: str | None = None,
) -> Party:
    party = await db.scalar(
        select(Party)
        .where(Party.id == party_id, Party.organization_id == organization_id)
        .with_for_update()
    )
    if party is None:
        raise CommercialValidationError("Party was not found")
    if party.revision != expected_revision:
        raise CommercialConflictError("Party changed; refresh before saving")
    before = {
        "name": party.name,
        "party_type": party.party_type.value,
        "status": party.status.value,
        "revision": party.revision,
    }
    mutable = {
        "name",
        "legal_name",
        "party_type",
        "status",
        "gstin",
        "pan",
        "email",
        "phone",
        "address_line_1",
        "address_line_2",
        "locality",
        "state_name",
        "state_code",
        "postal_code",
        "payment_terms_days",
        "notes",
    }
    for key, value in changes.items():
        if key not in mutable:
            continue
        if key == "name" and isinstance(value, str):
            value = value.strip()
            if not value:
                raise CommercialValidationError("Party name cannot be blank")
        if key in {"gstin", "pan", "state_code"} and isinstance(value, str):
            value = value.strip().upper()
        setattr(party, key, value)
    party.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="commercial.party.updated",
        target_type="commercial_party",
        target_id=str(party.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={
            "before": before,
            "after": {
                "name": party.name,
                "party_type": party.party_type.value,
                "status": party.status.value,
                "revision": party.revision,
            },
        },
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        event_type="commercial.party.updated",
        entity_type="commercial_party",
        entity_id=party.id,
        entity_version=party.revision,
        required_permission_key="commercial.party.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
    )
    return party


async def assign_party_to_project(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    party_id: UUID,
    role: object,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> ProjectPartyAssignment:
    await _require_project(db, organization_id, project_id)
    party = await db.scalar(
        select(Party).where(Party.id == party_id, Party.organization_id == organization_id)
    )
    if party is None or party.status.value != "active":
        raise CommercialValidationError("Active party was not found")
    existing = await db.scalar(
        select(ProjectPartyAssignment).where(
            ProjectPartyAssignment.organization_id == organization_id,
            ProjectPartyAssignment.project_id == project_id,
            ProjectPartyAssignment.party_id == party_id,
            ProjectPartyAssignment.role == role,
        )
    )
    if existing is not None:
        if not existing.active:
            existing.active = True
            await db.flush()
        return existing
    assignment = ProjectPartyAssignment(
        organization_id=organization_id,
        project_id=project_id,
        party_id=party_id,
        role=role,
    )
    db.add(assignment)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="commercial.project_party.assigned",
        target_type="project_party_assignment",
        target_id=str(assignment.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"party_id": str(party_id), "project_id": str(project_id), "role": str(role)},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="commercial.project_party.assigned",
        entity_type="project_party_assignment",
        entity_id=assignment.id,
        entity_version=1,
        required_permission_key="commercial.party.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"party_id": str(party_id)},
    )
    return assignment


async def _validate_wbs_parent(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    parent_id: UUID | None,
    current_id: UUID | None = None,
) -> None:
    seen = {current_id} if current_id is not None else set()
    cursor = parent_id
    while cursor is not None:
        if cursor in seen:
            raise CommercialValidationError("WBS hierarchy cannot contain a cycle")
        seen.add(cursor)
        row = await db.scalar(
            select(WBSCode).where(
                WBSCode.id == cursor,
                WBSCode.organization_id == organization_id,
                WBSCode.project_id == project_id,
            )
        )
        if row is None:
            raise CommercialValidationError("WBS parent was not found in this project")
        cursor = row.parent_id


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
        raise CommercialValidationError("WBS code and name are required")
    duplicate = await db.scalar(
        select(WBSCode.id).where(WBSCode.project_id == project_id, WBSCode.code == code)
    )
    if duplicate is not None:
        raise CommercialConflictError("WBS code already exists in this project")
    await _validate_wbs_parent(
        db,
        organization_id=organization_id,
        project_id=project_id,
        parent_id=data.get("parent_id") if isinstance(data.get("parent_id"), UUID) else None,
    )
    data["code"] = code
    data["name"] = name
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
        changes={"code": row.code, "name": row.name, "kind": row.kind.value},
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        event_type="commercial.wbs.created",
        entity_type="wbs_code",
        entity_id=row.id,
        entity_version=row.revision,
        required_permission_key="commercial.wbs.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        project_id=project_id,
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
        raise CommercialValidationError("WBS code was not found")
    if row.revision != expected_revision:
        raise CommercialConflictError("WBS code changed; refresh before saving")
    if "parent_id" in changes:
        parent_id = changes.get("parent_id")
        await _validate_wbs_parent(
            db,
            organization_id=organization_id,
            project_id=project_id,
            parent_id=parent_id if isinstance(parent_id, UUID) else None,
            current_id=wbs_id,
        )
    for key in ("parent_id", "name", "kind", "status", "description"):
        if key in changes:
            setattr(row, key, changes[key])
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
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"code": row.code, "revision": row.revision, "status": row.status.value},
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        event_type="commercial.wbs.updated",
        entity_type="wbs_code",
        entity_id=row.id,
        entity_version=row.revision,
        required_permission_key="commercial.wbs.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        project_id=project_id,
    )
    return row


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
    code = str(data.get("code") or "").strip().upper()
    name = str(data.get("name") or "").strip()
    if not code or not name:
        raise CommercialValidationError("BOQ code and name are required")
    duplicate = await db.scalar(
        select(BOQ.id).where(BOQ.project_id == project_id, BOQ.code == code)
    )
    if duplicate is not None:
        raise CommercialConflictError("BOQ code already exists in this project")
    data["code"] = code
    data["name"] = name
    data["currency_code"] = str(data.get("currency_code") or "INR").upper()
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
        changes={"code": boq.code, "name": boq.name, "currency": boq.currency_code},
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        event_type="commercial.boq.created",
        entity_type="boq",
        entity_id=boq.id,
        entity_version=boq.revision,
        required_permission_key="commercial.boq.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        project_id=project_id,
    )
    return boq


async def _load_draft_boq(
    db: AsyncSession,
    organization_id: UUID,
    project_id: UUID,
    boq_id: UUID,
) -> BOQ:
    boq = await db.scalar(
        select(BOQ)
        .where(
            BOQ.id == boq_id,
            BOQ.organization_id == organization_id,
            BOQ.project_id == project_id,
        )
        .with_for_update()
    )
    if boq is None:
        raise CommercialValidationError("BOQ was not found")
    if boq.status != BOQStatus.DRAFT:
        raise CommercialValidationError("Only a draft BOQ can be edited")
    return boq


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
    boq = await _load_draft_boq(db, organization_id, project_id, boq_id)
    data = dict(values)
    wbs_id = data.get("wbs_code_id")
    if isinstance(wbs_id, UUID):
        wbs = await db.scalar(
            select(WBSCode.id).where(
                WBSCode.id == wbs_id,
                WBSCode.organization_id == organization_id,
                WBSCode.project_id == project_id,
            )
        )
        if wbs is None:
            raise CommercialValidationError("WBS code was not found in this project")
    quantity = Decimal(str(data["quantity"]))
    rate = Decimal(str(data["rate"]))
    data["amount"] = money(quantity * rate)
    data["item_code"] = str(data["item_code"]).strip().upper()
    data["unit_code"] = str(data["unit_code"]).strip().upper()
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
            "item_code": item.item_code,
            "quantity": str(item.quantity),
            "rate": str(item.rate),
            "amount": str(item.amount),
        },
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        event_type="commercial.boq.updated",
        entity_type="boq",
        entity_id=boq.id,
        entity_version=boq.revision,
        required_permission_key="commercial.boq.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        project_id=project_id,
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
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> BOQItem:
    boq = await _load_draft_boq(db, organization_id, project_id, boq_id)
    item = await db.scalar(
        select(BOQItem)
        .where(
            BOQItem.id == item_id,
            BOQItem.boq_id == boq_id,
            BOQItem.organization_id == organization_id,
            BOQItem.project_id == project_id,
        )
        .with_for_update()
    )
    if item is None:
        raise CommercialValidationError("BOQ item was not found")
    if item.revision != expected_revision:
        raise CommercialConflictError("BOQ item changed; refresh before saving")
    for key in ("wbs_code_id", "description", "unit_code", "quantity", "rate", "hsn_sac", "notes"):
        if key in changes:
            value = changes[key]
            if key in {"quantity", "rate"} and value is not None:
                value = Decimal(str(value))
            if key == "unit_code" and isinstance(value, str):
                value = value.strip().upper()
            setattr(item, key, value)
    if item.wbs_code_id is not None:
        wbs = await db.scalar(
            select(WBSCode.id).where(
                WBSCode.id == item.wbs_code_id,
                WBSCode.organization_id == organization_id,
                WBSCode.project_id == project_id,
            )
        )
        if wbs is None:
            raise CommercialValidationError("WBS code was not found in this project")
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
        changes={"revision": item.revision, "amount": str(item.amount)},
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        event_type="commercial.boq.updated",
        entity_type="boq",
        entity_id=boq.id,
        entity_version=boq.revision,
        required_permission_key="commercial.boq.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        project_id=project_id,
    )
    return item


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
    boq = await _load_draft_boq(db, organization_id, project_id, boq_id)
    if boq.revision != expected_revision:
        raise CommercialConflictError("BOQ changed; refresh before approval")
    items = list(
        (
            await db.scalars(
                select(BOQItem)
                .where(BOQItem.boq_id == boq.id, BOQItem.organization_id == organization_id)
                .order_by(BOQItem.line_number)
            )
        ).all()
    )
    if not items:
        raise CommercialValidationError("BOQ cannot be approved without items")
    version_number = (
        await db.scalar(
            select(func.coalesce(func.max(BOQRevision.version_number), 0)).where(
                BOQRevision.boq_id == boq.id
            )
        )
        or 0
    ) + 1
    approved_at = datetime.now(UTC)
    snapshot = {
        "boq": {
            "id": str(boq.id),
            "code": boq.code,
            "name": boq.name,
            "currency_code": boq.currency_code,
            "revision": boq.revision,
        },
        "items": [
            {
                "id": str(item.id),
                "line_number": item.line_number,
                "item_code": item.item_code,
                "wbs_code_id": str(item.wbs_code_id) if item.wbs_code_id else None,
                "description": item.description,
                "unit_code": item.unit_code,
                "quantity": str(item.quantity),
                "rate": str(item.rate),
                "amount": str(item.amount),
                "hsn_sac": item.hsn_sac,
                "revision": item.revision,
            }
            for item in items
        ],
    }
    db.add(
        BOQRevision(
            organization_id=organization_id,
            project_id=project_id,
            boq_id=boq.id,
            version_number=version_number,
            approved_by_membership_id=membership_id,
            approved_at=approved_at,
            snapshot_json=json.dumps(snapshot, separators=(",", ":"), sort_keys=True),
            reason=reason,
        )
    )
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
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": boq.status.value, "revision": boq.revision, "version": version_number},
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        event_type="commercial.boq.approved",
        entity_type="boq",
        entity_id=boq.id,
        entity_version=boq.revision,
        required_permission_key="commercial.boq.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        project_id=project_id,
    )
    return boq


async def create_measurement(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> MeasurementEntry:
    await _require_project(db, organization_id, project_id)
    item_id = values.get("boq_item_id")
    if not isinstance(item_id, UUID):
        raise CommercialValidationError("BOQ item is required")
    row = await db.execute(
        select(BOQItem, BOQ)
        .join(BOQ, BOQ.id == BOQItem.boq_id)
        .where(
            BOQItem.id == item_id,
            BOQItem.organization_id == organization_id,
            BOQItem.project_id == project_id,
            BOQ.status == BOQStatus.APPROVED,
        )
    )
    result = row.first()
    if result is None:
        raise CommercialValidationError("Measurement requires an approved BOQ item")
    item, _boq = result
    quantity = Decimal(str(values["quantity"]))
    if quantity <= 0:
        raise CommercialValidationError("Measurement quantity must be greater than zero")
    next_number = (
        await db.scalar(
            select(func.coalesce(func.max(MeasurementEntry.entry_number), 0)).where(
                MeasurementEntry.organization_id == organization_id,
                MeasurementEntry.project_id == project_id,
            )
        )
        or 0
    ) + 1
    measurement = MeasurementEntry(
        organization_id=organization_id,
        project_id=project_id,
        boq_item_id=item.id,
        entry_number=next_number,
        measurement_date=values["measurement_date"],
        location=values.get("location"),
        description=values.get("description"),
        quantity=quantity,
        unit_code=item.unit_code,
        recorded_by_membership_id=membership_id,
    )
    db.add(measurement)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="commercial.measurement.created",
        target_type="measurement_entry",
        target_id=str(measurement.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "entry_number": measurement.entry_number,
            "boq_item_id": str(item.id),
            "quantity": str(measurement.quantity),
            "unit": measurement.unit_code,
        },
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        event_type="commercial.measurement.created",
        entity_type="measurement_entry",
        entity_id=measurement.id,
        entity_version=measurement.revision,
        required_permission_key="commercial.measurement.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        project_id=project_id,
    )
    return measurement


async def transition_measurement(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    measurement_id: UUID,
    expected_revision: int,
    target_status: MeasurementStatus,
    membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> MeasurementEntry:
    measurement = await db.scalar(
        select(MeasurementEntry)
        .where(
            MeasurementEntry.id == measurement_id,
            MeasurementEntry.organization_id == organization_id,
            MeasurementEntry.project_id == project_id,
        )
        .with_for_update()
    )
    if measurement is None:
        raise CommercialValidationError("Measurement was not found")
    if measurement.revision != expected_revision:
        raise CommercialConflictError("Measurement changed; refresh before continuing")
    allowed = {
        MeasurementStatus.DRAFT: {MeasurementStatus.SUBMITTED},
        MeasurementStatus.REJECTED: {MeasurementStatus.SUBMITTED},
        MeasurementStatus.SUBMITTED: {MeasurementStatus.CERTIFIED, MeasurementStatus.REJECTED},
        MeasurementStatus.CERTIFIED: set(),
    }
    if target_status not in allowed[measurement.status]:
        raise CommercialValidationError(
            f"Measurement cannot move from {measurement.status.value} to {target_status.value}"
        )
    measurement.status = target_status
    if target_status == MeasurementStatus.CERTIFIED:
        measurement.certified_by_membership_id = membership_id
        measurement.certified_at = datetime.now(UTC)
    elif target_status == MeasurementStatus.REJECTED:
        measurement.certified_by_membership_id = None
        measurement.certified_at = None
    measurement.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action=f"commercial.measurement.{target_status.value}",
        target_type="measurement_entry",
        target_id=str(measurement.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": measurement.status.value, "revision": measurement.revision},
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        event_type=f"commercial.measurement.{target_status.value}",
        entity_type="measurement_entry",
        entity_id=measurement.id,
        entity_version=measurement.revision,
        required_permission_key="commercial.measurement.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        project_id=project_id,
    )
    return measurement


async def create_ra_bill(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    values: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> RABill:
    await _require_project(db, organization_id, project_id)
    counterparty_id = values.get("counterparty_id")
    if not isinstance(counterparty_id, UUID):
        raise CommercialValidationError("RA bill counterparty is required")
    counterparty = await db.scalar(
        select(Party).where(
            Party.id == counterparty_id,
            Party.organization_id == organization_id,
            Party.status == "active",
        )
    )
    if counterparty is None:
        raise CommercialValidationError("Active RA bill counterparty was not found")
    bill_number = str(values.get("bill_number") or "").strip().upper()
    if not bill_number:
        raise CommercialValidationError("RA bill number is required")
    duplicate = await db.scalar(
        select(RABill.id).where(
            RABill.project_id == project_id,
            RABill.bill_number == bill_number,
        )
    )
    if duplicate is not None:
        raise CommercialConflictError("RA bill number already exists in this project")
    period_start = values["period_start"]
    period_end = values["period_end"]
    if period_end < period_start:
        raise CommercialValidationError("RA bill period is invalid")

    billed = select(RABillMeasurement.id).where(
        RABillMeasurement.measurement_entry_id == MeasurementEntry.id
    )
    rows = (
        await db.execute(
            select(MeasurementEntry, BOQItem, BOQ)
            .join(BOQItem, BOQItem.id == MeasurementEntry.boq_item_id)
            .join(BOQ, BOQ.id == BOQItem.boq_id)
            .where(
                MeasurementEntry.organization_id == organization_id,
                MeasurementEntry.project_id == project_id,
                MeasurementEntry.status == MeasurementStatus.CERTIFIED,
                MeasurementEntry.measurement_date >= period_start,
                MeasurementEntry.measurement_date <= period_end,
                ~exists(billed),
            )
            .order_by(MeasurementEntry.entry_number)
        )
    ).all()
    if not rows:
        raise CommercialValidationError(
            "No unbilled certified measurements exist in the selected period"
        )
    currencies = {boq.currency_code for _, _, boq in rows}
    if len(currencies) != 1:
        raise CommercialValidationError("RA bill cannot combine measurements from multiple currencies")

    grouped: dict[UUID, dict[str, object]] = defaultdict(
        lambda: {"quantity": Decimal("0"), "rate": Decimal("0"), "measurements": []}
    )
    for measurement, item, _boq in rows:
        group = grouped[item.id]
        group["quantity"] = Decimal(group["quantity"]) + Decimal(measurement.quantity)
        group["rate"] = Decimal(item.rate)
        group["measurements"].append(measurement)

    retention = money(Decimal(str(values.get("retention_amount") or 0)))
    statutory = money(Decimal(str(values.get("statutory_deduction_amount") or 0)))
    other = money(Decimal(str(values.get("other_deduction_amount") or 0)))
    gross = money(
        sum(
            (
                Decimal(group["quantity"]) * Decimal(group["rate"])
                for group in grouped.values()
            ),
            start=Decimal("0"),
        )
    )
    deductions = retention + statutory + other
    if deductions > gross:
        raise CommercialValidationError("RA bill deductions cannot exceed gross value")

    bill = RABill(
        organization_id=organization_id,
        project_id=project_id,
        counterparty_id=counterparty_id,
        bill_number=bill_number,
        period_start=period_start,
        period_end=period_end,
        currency_code=currencies.pop(),
        gross_amount=gross,
        retention_amount=retention,
        statutory_deduction_amount=statutory,
        other_deduction_amount=other,
        net_payable=money(gross - deductions),
        notes=values.get("notes"),
    )
    db.add(bill)
    await db.flush()
    for item_id, group in grouped.items():
        quantity = Decimal(group["quantity"])
        rate = Decimal(group["rate"])
        db.add(
            RABillLine(
                organization_id=organization_id,
                project_id=project_id,
                ra_bill_id=bill.id,
                boq_item_id=item_id,
                current_quantity=quantity,
                rate=rate,
                gross_amount=money(quantity * rate),
            )
        )
        for measurement in group["measurements"]:
            db.add(
                RABillMeasurement(
                    organization_id=organization_id,
                    project_id=project_id,
                    ra_bill_id=bill.id,
                    measurement_entry_id=measurement.id,
                )
            )
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="commercial.ra_bill.created",
        target_type="ra_bill",
        target_id=str(bill.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={
            "bill_number": bill.bill_number,
            "gross_amount": str(bill.gross_amount),
            "net_payable": str(bill.net_payable),
            "measurement_count": len(rows),
        },
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        event_type="commercial.ra_bill.created",
        entity_type="ra_bill",
        entity_id=bill.id,
        entity_version=bill.revision,
        required_permission_key="commercial.ra_bill.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        project_id=project_id,
    )
    return bill


async def transition_ra_bill(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    bill_id: UUID,
    expected_revision: int,
    target_status: RABillStatus,
    membership_id: UUID,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> RABill:
    bill = await db.scalar(
        select(RABill)
        .where(
            RABill.id == bill_id,
            RABill.organization_id == organization_id,
            RABill.project_id == project_id,
        )
        .with_for_update()
    )
    if bill is None:
        raise CommercialValidationError("RA bill was not found")
    if bill.revision != expected_revision:
        raise CommercialConflictError("RA bill changed; refresh before continuing")
    allowed = {
        RABillStatus.DRAFT: {RABillStatus.SUBMITTED, RABillStatus.CANCELLED},
        RABillStatus.SUBMITTED: {RABillStatus.CERTIFIED, RABillStatus.CANCELLED},
        RABillStatus.CERTIFIED: {RABillStatus.PAID},
        RABillStatus.PAID: set(),
        RABillStatus.CANCELLED: set(),
    }
    if target_status not in allowed[bill.status]:
        raise CommercialValidationError(
            f"RA bill cannot move from {bill.status.value} to {target_status.value}"
        )
    bill.status = target_status
    now = datetime.now(UTC)
    if target_status == RABillStatus.SUBMITTED:
        bill.submitted_at = now
    if target_status == RABillStatus.CERTIFIED:
        bill.certified_by_membership_id = membership_id
        bill.certified_at = now
    bill.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action=f"commercial.ra_bill.{target_status.value}",
        target_type="ra_bill",
        target_id=str(bill.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": bill.status.value, "revision": bill.revision},
    )
    await _publish_change(
        db,
        organization_id=organization_id,
        event_type=f"commercial.ra_bill.{target_status.value}",
        entity_type="ra_bill",
        entity_id=bill.id,
        entity_version=bill.revision,
        required_permission_key="commercial.ra_bill.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        project_id=project_id,
    )
    return bill


async def commercial_dashboard(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
) -> dict[str, object]:
    await _require_project(db, organization_id, project_id)
    boq_value = await db.scalar(
        select(func.coalesce(func.sum(BOQItem.amount), 0))
        .join(BOQ, BOQ.id == BOQItem.boq_id)
        .where(
            BOQItem.organization_id == organization_id,
            BOQItem.project_id == project_id,
            BOQ.status == BOQStatus.APPROVED,
        )
    )
    measurement_value = await db.scalar(
        select(func.coalesce(func.sum(MeasurementEntry.quantity * BOQItem.rate), 0))
        .join(BOQItem, BOQItem.id == MeasurementEntry.boq_item_id)
        .where(
            MeasurementEntry.organization_id == organization_id,
            MeasurementEntry.project_id == project_id,
        )
    )
    certified_measurement_value = await db.scalar(
        select(func.coalesce(func.sum(MeasurementEntry.quantity * BOQItem.rate), 0))
        .join(BOQItem, BOQItem.id == MeasurementEntry.boq_item_id)
        .where(
            MeasurementEntry.organization_id == organization_id,
            MeasurementEntry.project_id == project_id,
            MeasurementEntry.status == MeasurementStatus.CERTIFIED,
        )
    )
    submitted_bill_value = await db.scalar(
        select(func.coalesce(func.sum(RABill.gross_amount), 0)).where(
            RABill.organization_id == organization_id,
            RABill.project_id == project_id,
            RABill.status.in_([RABillStatus.SUBMITTED, RABillStatus.CERTIFIED, RABillStatus.PAID]),
        )
    )
    certified_bill_value = await db.scalar(
        select(func.coalesce(func.sum(RABill.gross_amount), 0)).where(
            RABill.organization_id == organization_id,
            RABill.project_id == project_id,
            RABill.status.in_([RABillStatus.CERTIFIED, RABillStatus.PAID]),
        )
    )
    open_measurements = await db.scalar(
        select(func.count(MeasurementEntry.id)).where(
            MeasurementEntry.organization_id == organization_id,
            MeasurementEntry.project_id == project_id,
            MeasurementEntry.status.in_([MeasurementStatus.DRAFT, MeasurementStatus.SUBMITTED]),
        )
    )
    draft_bills = await db.scalar(
        select(func.count(RABill.id)).where(
            RABill.organization_id == organization_id,
            RABill.project_id == project_id,
            RABill.status == RABillStatus.DRAFT,
        )
    )
    return {
        "project_id": project_id,
        "boq_value": money(Decimal(boq_value or 0)),
        "measured_value": money(Decimal(measurement_value or 0)),
        "certified_measurement_value": money(Decimal(certified_measurement_value or 0)),
        "submitted_bill_value": money(Decimal(submitted_bill_value or 0)),
        "certified_bill_value": money(Decimal(certified_bill_value or 0)),
        "open_measurements": int(open_measurements or 0),
        "draft_bills": int(draft_bills or 0),
    }
