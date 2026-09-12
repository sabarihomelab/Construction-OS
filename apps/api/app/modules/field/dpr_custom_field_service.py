from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.events.service import enqueue_event
from app.modules.field.dpr_custom_field_schemas import (
    DPRCustomFieldDefinitionRead,
    DPRCustomFieldOptionRead,
    DPRCustomFieldValueRead,
    DPRCustomFieldValueWrite,
    DPRCustomFieldValuesRead,
)
from app.modules.field.dpr_service import DPRConflictError, DPRValidationError
from app.modules.field.models import (
    DailyReport,
    DailyReportHistoryEvent,
    DailyReportHistoryType,
    DailyReportStatus,
)
from app.modules.metadata.models import (
    CustomFieldDefinition,
    CustomFieldOption,
    CustomFieldValue,
)
from app.modules.metadata.service import MetadataValidationError, write_custom_field_value
from app.modules.search.service import schedule_search_index

_ENTITY_TYPE = "daily_report"


def _definition_is_visible(definition: CustomFieldDefinition, permission_keys: set[str]) -> bool:
    return definition.view_permission_key is None or definition.view_permission_key in permission_keys


def _definition_is_editable(definition: CustomFieldDefinition, permission_keys: set[str]) -> bool:
    if not definition.editable:
        return False
    return definition.edit_permission_key is None or definition.edit_permission_key in permission_keys


def _typed_json_to_value(value: dict[str, object] | None) -> object:
    if value is None:
        return None
    if "text" in value:
        return value["text"]
    if "number" in value:
        if "currency" in value:
            return {"amount": value["number"], "currency": value["currency"]}
        if "unit" in value:
            return {"value": value["number"], "unit": value["unit"]}
        return value["number"]
    if "boolean" in value:
        return value["boolean"]
    if "date" in value:
        return value["date"]
    if "datetime" in value:
        return value["datetime"]
    if "uuid" in value:
        return value["uuid"]
    if "json" in value:
        return value["json"]
    return None


def _stored_value(row: CustomFieldValue) -> object:
    if row.text_value is not None:
        return row.text_value
    if row.numeric_value is not None:
        number = format(row.numeric_value, "f")
        if row.currency_code:
            return {"amount": number, "currency": row.currency_code}
        if row.unit_code:
            return {"value": number, "unit": row.unit_code}
        return number
    if row.boolean_value is not None:
        return row.boolean_value
    if row.date_value is not None:
        return row.date_value.isoformat()
    if row.datetime_value is not None:
        return row.datetime_value.isoformat()
    if row.uuid_value is not None:
        return str(row.uuid_value)
    return row.json_value


def _row_has_value(row: CustomFieldValue) -> bool:
    return any(
        value is not None
        for value in (
            row.text_value,
            row.numeric_value,
            row.boolean_value,
            row.date_value,
            row.datetime_value,
            row.uuid_value,
            row.json_value,
        )
    )


async def _definitions(
    db: AsyncSession,
    *,
    organization_id: UUID,
) -> list[CustomFieldDefinition]:
    rows = await db.scalars(
        select(CustomFieldDefinition)
        .where(
            CustomFieldDefinition.organization_id == organization_id,
            CustomFieldDefinition.entity_type == _ENTITY_TYPE,
            CustomFieldDefinition.active.is_(True),
            CustomFieldDefinition.visible.is_(True),
        )
        .order_by(CustomFieldDefinition.display_order, CustomFieldDefinition.key)
    )
    return list(rows.all())


async def list_dpr_custom_field_definitions(
    db: AsyncSession,
    *,
    organization_id: UUID,
    permission_keys: set[str],
) -> list[DPRCustomFieldDefinitionRead]:
    definitions = [
        row for row in await _definitions(db, organization_id=organization_id)
        if _definition_is_visible(row, permission_keys)
    ]
    definition_ids = [row.id for row in definitions]
    options_by_definition: dict[UUID, list[DPRCustomFieldOptionRead]] = {
        definition_id: [] for definition_id in definition_ids
    }
    if definition_ids:
        options = await db.scalars(
            select(CustomFieldOption)
            .where(
                CustomFieldOption.definition_id.in_(definition_ids),
                CustomFieldOption.active.is_(True),
            )
            .order_by(
                CustomFieldOption.definition_id,
                CustomFieldOption.display_order,
                CustomFieldOption.key,
            )
        )
        for option in options.all():
            options_by_definition.setdefault(option.definition_id, []).append(
                DPRCustomFieldOptionRead(key=option.key, label=option.label)
            )
    return [
        DPRCustomFieldDefinitionRead(
            definition_id=definition.id,
            key=definition.key,
            label=definition.label,
            description=definition.description,
            field_type=definition.field_type.value,
            required=definition.required,
            editable=_definition_is_editable(definition, permission_keys),
            display_order=definition.display_order,
            default_value=_typed_json_to_value(definition.default_value),
            options=options_by_definition.get(definition.id, []),
        )
        for definition in definitions
    ]


async def _load_report(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
) -> DailyReport:
    report = await db.scalar(
        select(DailyReport).where(
            DailyReport.id == report_id,
            DailyReport.organization_id == organization_id,
            DailyReport.project_id == project_id,
        )
    )
    if report is None:
        raise DPRValidationError("Daily Progress Report was not found")
    return report


async def list_dpr_custom_field_values(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
    permission_keys: set[str],
) -> DPRCustomFieldValuesRead:
    report = await _load_report(
        db,
        organization_id=organization_id,
        project_id=project_id,
        report_id=report_id,
    )
    definitions = [
        row for row in await _definitions(db, organization_id=organization_id)
        if _definition_is_visible(row, permission_keys)
    ]
    definition_ids = [row.id for row in definitions]
    values: dict[UUID, CustomFieldValue] = {}
    if definition_ids:
        rows = await db.scalars(
            select(CustomFieldValue).where(
                CustomFieldValue.organization_id == organization_id,
                CustomFieldValue.entity_id == report.id,
                CustomFieldValue.definition_id.in_(definition_ids),
            )
        )
        values = {row.definition_id: row for row in rows.all()}
    return DPRCustomFieldValuesRead(
        report_id=report.id,
        report_revision=report.revision,
        values=[
            DPRCustomFieldValueRead(
                definition_id=definition.id,
                value=(
                    _stored_value(values[definition.id])
                    if definition.id in values
                    else _typed_json_to_value(definition.default_value)
                ),
            )
            for definition in definitions
        ],
    )


async def replace_dpr_custom_fields(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
    expected_revision: int,
    values: Sequence[DPRCustomFieldValueWrite],
    permission_keys: set[str],
    actor_user_id: UUID,
    session_id: UUID | None,
    reason: str | None,
) -> DailyReport:
    report = await db.scalar(
        select(DailyReport)
        .where(
            DailyReport.id == report_id,
            DailyReport.organization_id == organization_id,
            DailyReport.project_id == project_id,
        )
        .with_for_update()
    )
    if report is None:
        raise DPRValidationError("Daily Progress Report was not found")
    if report.revision != expected_revision:
        raise DPRConflictError(
            f"DPR changed from revision {expected_revision} to {report.revision}; refresh before saving"
        )
    if report.status != DailyReportStatus.DRAFT:
        raise DPRValidationError("Only a draft Daily Report can update custom fields")

    ids = [row.definition_id for row in values]
    if len(ids) != len(set(ids)):
        raise DPRValidationError("A custom field can be supplied only once per save")
    if not ids:
        return report

    rows = await db.scalars(
        select(CustomFieldDefinition).where(
            CustomFieldDefinition.organization_id == organization_id,
            CustomFieldDefinition.entity_type == _ENTITY_TYPE,
            CustomFieldDefinition.id.in_(ids),
            CustomFieldDefinition.active.is_(True),
            CustomFieldDefinition.visible.is_(True),
        )
    )
    definitions = {row.id: row for row in rows.all()}
    if set(ids) != set(definitions):
        raise DPRValidationError("One or more DPR custom fields are unavailable")

    changed_keys: list[str] = []
    try:
        for item in values:
            definition = definitions[item.definition_id]
            if not _definition_is_visible(definition, permission_keys):
                raise DPRValidationError(f"Custom field is not visible: {definition.label}")
            if not _definition_is_editable(definition, permission_keys):
                raise DPRValidationError(f"Custom field is read-only: {definition.label}")
            await write_custom_field_value(
                db,
                organization_id,
                definition.id,
                report.id,
                item.value,
                actor_user_id=actor_user_id,
            )
            changed_keys.append(definition.key)
    except MetadataValidationError as exc:
        raise DPRValidationError(str(exc)) from exc

    report.revision += 1
    db.add(
        DailyReportHistoryEvent(
            organization_id=organization_id,
            daily_report_id=report.id,
            event_type=DailyReportHistoryType.UPDATED,
            report_revision=report.revision,
            actor_user_id=actor_user_id,
            details={"section": "custom_fields", "fields": sorted(changed_keys), "reason": reason},
        )
    )
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="dpr.custom_fields.updated",
        target_type="daily_report",
        target_id=str(report.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"revision": report.revision, "fields": sorted(changed_keys)},
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="daily_report.updated",
        entity_type="daily_report",
        entity_id=report.id,
        entity_version=report.revision,
        required_permission_key="field.daily_report.view",
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": report.revision, "section": "custom_fields"},
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type="daily_report",
        entity_id=report.id,
        entity_version=report.revision,
    )
    return report


async def materialize_and_validate_required_dpr_custom_fields(
    db: AsyncSession,
    *,
    organization_id: UUID,
    report: DailyReport,
    actor_user_id: UUID,
) -> None:
    definitions = [
        row for row in await _definitions(db, organization_id=organization_id)
        if row.required
    ]
    if not definitions:
        return
    ids = [row.id for row in definitions]
    rows = await db.scalars(
        select(CustomFieldValue).where(
            CustomFieldValue.organization_id == organization_id,
            CustomFieldValue.entity_id == report.id,
            CustomFieldValue.definition_id.in_(ids),
        )
    )
    existing = {row.definition_id: row for row in rows.all()}
    missing: list[str] = []
    for definition in definitions:
        current = existing.get(definition.id)
        if current is not None and _row_has_value(current):
            continue
        if current is None and definition.default_value is not None:
            try:
                await write_custom_field_value(
                    db,
                    organization_id,
                    definition.id,
                    report.id,
                    _typed_json_to_value(definition.default_value),
                    actor_user_id=actor_user_id,
                )
            except MetadataValidationError as exc:
                raise DPRValidationError(str(exc)) from exc
            continue
        missing.append(definition.label)
    if missing:
        raise DPRValidationError(
            "Complete the required Daily Report custom fields before submitting: "
            + ", ".join(sorted(missing))
        )
