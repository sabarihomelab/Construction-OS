import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from pydantic import AnyUrl, EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.authorization.models import Permission
from app.modules.metadata.models import (
    CustomFieldDefinition,
    CustomFieldDefinitionRevision,
    CustomFieldOption,
    CustomFieldType,
    CustomFieldValue,
)
from app.modules.metadata.schemas import (
    CustomFieldDefinitionCreate,
    CustomFieldDefinitionUpdate,
    CustomFieldOptionCreate,
)

CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
SELECT_FIELD_TYPES = {CustomFieldType.SINGLE_SELECT, CustomFieldType.MULTI_SELECT}
REFERENCE_FIELD_TYPES = {
    CustomFieldType.USER,
    CustomFieldType.COMPANY,
    CustomFieldType.PROJECT,
    CustomFieldType.ATTACHMENT,
}


class MetadataConflictError(ValueError):
    pass


class MetadataValidationError(ValueError):
    pass


@dataclass(slots=True)
class TypedCustomValue:
    text_value: str | None = None
    numeric_value: Decimal | None = None
    boolean_value: bool | None = None
    date_value: date | None = None
    datetime_value: datetime | None = None
    uuid_value: UUID | None = None
    json_value: object | None = None
    currency_code: str | None = None
    unit_code: str | None = None


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool):
        raise MetadataValidationError("Boolean values cannot be used as numbers")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MetadataValidationError("Value must be numeric") from exc
    if not result.is_finite():
        raise MetadataValidationError("Numeric values must be finite")
    return result


def normalize_custom_value(field_type: CustomFieldType, value: object) -> TypedCustomValue:
    if value is None:
        return TypedCustomValue()

    if field_type in {CustomFieldType.TEXT, CustomFieldType.LONG_TEXT, CustomFieldType.PHONE}:
        if not isinstance(value, str):
            raise MetadataValidationError("Value must be text")
        return TypedCustomValue(text_value=value)

    if field_type == CustomFieldType.EMAIL:
        try:
            email = TypeAdapter(EmailStr).validate_python(value)
        except ValidationError as exc:
            raise MetadataValidationError("Value must be a valid email address") from exc
        return TypedCustomValue(text_value=str(email).lower())

    if field_type == CustomFieldType.URL:
        try:
            url = TypeAdapter(AnyUrl).validate_python(value)
        except ValidationError as exc:
            raise MetadataValidationError("Value must be a valid URL") from exc
        return TypedCustomValue(text_value=str(url))

    if field_type == CustomFieldType.INTEGER:
        number = _decimal(value)
        if number != number.to_integral_value():
            raise MetadataValidationError("Value must be an integer")
        return TypedCustomValue(numeric_value=number)

    if field_type == CustomFieldType.DECIMAL:
        return TypedCustomValue(numeric_value=_decimal(value))

    if field_type == CustomFieldType.CURRENCY:
        if not isinstance(value, Mapping):
            raise MetadataValidationError("Currency values require amount and currency")
        amount = _decimal(value.get("amount"))
        currency = str(value.get("currency", "")).upper()
        if not CURRENCY_PATTERN.fullmatch(currency):
            raise MetadataValidationError("Currency must be a three-letter ISO code")
        return TypedCustomValue(numeric_value=amount, currency_code=currency)

    if field_type == CustomFieldType.MEASUREMENT:
        if not isinstance(value, Mapping):
            raise MetadataValidationError("Measurement values require value and unit")
        amount = _decimal(value.get("value"))
        unit = str(value.get("unit", "")).strip()
        if not unit or len(unit) > 32:
            raise MetadataValidationError("Measurement unit is required")
        return TypedCustomValue(numeric_value=amount, unit_code=unit)

    if field_type == CustomFieldType.BOOLEAN:
        if not isinstance(value, bool):
            raise MetadataValidationError("Value must be true or false")
        return TypedCustomValue(boolean_value=value)

    if field_type == CustomFieldType.DATE:
        if isinstance(value, datetime):
            raise MetadataValidationError("Date values must not include a time")
        try:
            parsed = TypeAdapter(date).validate_python(value)
        except ValidationError as exc:
            raise MetadataValidationError("Value must be a valid date") from exc
        return TypedCustomValue(date_value=parsed)

    if field_type == CustomFieldType.DATETIME:
        try:
            parsed = TypeAdapter(datetime).validate_python(value)
        except ValidationError as exc:
            raise MetadataValidationError("Value must be a valid datetime") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise MetadataValidationError("Datetime values must include a timezone")
        return TypedCustomValue(datetime_value=parsed)

    if field_type in REFERENCE_FIELD_TYPES:
        try:
            parsed = TypeAdapter(UUID).validate_python(value)
        except ValidationError as exc:
            raise MetadataValidationError("Reference values must be UUIDs") from exc
        return TypedCustomValue(uuid_value=parsed)

    if field_type == CustomFieldType.SINGLE_SELECT:
        if not isinstance(value, str) or not value:
            raise MetadataValidationError("Single-select value must be an option key")
        return TypedCustomValue(text_value=value)

    if field_type == CustomFieldType.MULTI_SELECT:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise MetadataValidationError("Multi-select value must be a list of option keys")
        option_keys = [str(item) for item in value]
        if len(option_keys) != len(set(option_keys)):
            raise MetadataValidationError("Multi-select values cannot contain duplicates")
        return TypedCustomValue(json_value=option_keys)

    raise MetadataValidationError(f"Unsupported custom field type: {field_type}")


def typed_value_to_json(value: TypedCustomValue) -> dict[str, object]:
    result: dict[str, object] = {}
    if value.text_value is not None:
        result["text"] = value.text_value
    if value.numeric_value is not None:
        result["number"] = str(value.numeric_value)
    if value.boolean_value is not None:
        result["boolean"] = value.boolean_value
    if value.date_value is not None:
        result["date"] = value.date_value.isoformat()
    if value.datetime_value is not None:
        result["datetime"] = value.datetime_value.isoformat()
    if value.uuid_value is not None:
        result["uuid"] = str(value.uuid_value)
    if value.json_value is not None:
        result["json"] = value.json_value
    if value.currency_code is not None:
        result["currency"] = value.currency_code
    if value.unit_code is not None:
        result["unit"] = value.unit_code
    return result


def _ensure_json_compatible(value: object, name: str) -> None:
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise MetadataValidationError(f"{name} must be JSON-compatible") from exc


async def _validate_permission_keys(
    db: AsyncSession,
    permission_keys: Sequence[str | None],
) -> None:
    keys = {key for key in permission_keys if key}
    if not keys:
        return
    existing = set(
        (
            await db.scalars(
                select(Permission.key).where(Permission.key.in_(keys), Permission.is_active.is_(True))
            )
        ).all()
    )
    missing = keys - existing
    if missing:
        raise MetadataValidationError(f"Unknown permission keys: {', '.join(sorted(missing))}")


async def _definition_snapshot(
    db: AsyncSession,
    definition: CustomFieldDefinition,
) -> dict[str, object]:
    options = (
        await db.scalars(
            select(CustomFieldOption)
            .where(CustomFieldOption.definition_id == definition.id)
            .order_by(CustomFieldOption.display_order, CustomFieldOption.key)
        )
    ).all()
    return {
        "entity_type": definition.entity_type,
        "key": definition.key,
        "label": definition.label,
        "description": definition.description,
        "field_type": definition.field_type.value,
        "required": definition.required,
        "default_value": definition.default_value,
        "validation_rules": definition.validation_rules,
        "configuration": definition.configuration,
        "searchable": definition.searchable,
        "filterable": definition.filterable,
        "reportable": definition.reportable,
        "visible": definition.visible,
        "editable": definition.editable,
        "view_permission_key": definition.view_permission_key,
        "edit_permission_key": definition.edit_permission_key,
        "display_order": definition.display_order,
        "active": definition.active,
        "version": definition.version,
        "options": [
            {
                "key": option.key,
                "label": option.label,
                "display_order": option.display_order,
                "active": option.active,
                "version": option.version,
            }
            for option in options
        ],
    }


async def _add_definition_revision(
    db: AsyncSession,
    definition: CustomFieldDefinition,
    *,
    actor_user_id: UUID | None,
    reason: str | None,
) -> dict[str, object]:
    snapshot = await _definition_snapshot(db, definition)
    db.add(
        CustomFieldDefinitionRevision(
            definition_id=definition.id,
            version=definition.version,
            organization_id=definition.organization_id,
            snapshot=snapshot,
            changed_by_user_id=actor_user_id,
            reason=reason,
        )
    )
    await db.flush()
    return snapshot


async def create_field_definition(
    db: AsyncSession,
    organization_id: UUID,
    payload: CustomFieldDefinitionCreate,
    *,
    actor_user_id: UUID | None,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
    reason: str | None = None,
) -> CustomFieldDefinition:
    duplicate = await db.scalar(
        select(CustomFieldDefinition.id).where(
            CustomFieldDefinition.organization_id == organization_id,
            CustomFieldDefinition.entity_type == payload.entity_type,
            CustomFieldDefinition.key == payload.key,
        )
    )
    if duplicate is not None:
        raise MetadataConflictError("Custom field key already exists for this entity type")

    await _validate_permission_keys(db, [payload.view_permission_key, payload.edit_permission_key])
    _ensure_json_compatible(payload.validation_rules, "Validation rules")
    _ensure_json_compatible(payload.configuration, "Configuration")

    default_value = None
    if payload.default_value is not None:
        default_value = typed_value_to_json(
            normalize_custom_value(payload.field_type, payload.default_value)
        )

    definition = CustomFieldDefinition(
        organization_id=organization_id,
        entity_type=payload.entity_type,
        key=payload.key,
        label=payload.label,
        description=payload.description,
        field_type=payload.field_type,
        required=payload.required,
        default_value=default_value,
        validation_rules=payload.validation_rules,
        configuration=payload.configuration,
        searchable=payload.searchable,
        filterable=payload.filterable,
        reportable=payload.reportable,
        visible=payload.visible,
        editable=payload.editable,
        view_permission_key=payload.view_permission_key,
        edit_permission_key=payload.edit_permission_key,
        display_order=payload.display_order,
    )
    db.add(definition)
    await db.flush()
    snapshot = await _add_definition_revision(
        db, definition, actor_user_id=actor_user_id, reason=reason
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="metadata.custom_field.created",
        target_type="custom_field_definition",
        target_id=str(definition.id),
        actor_type=AuditActorType.USER if actor_user_id is not None else AuditActorType.SYSTEM,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"after": snapshot},
    )
    return definition


async def update_field_definition(
    db: AsyncSession,
    organization_id: UUID,
    definition_id: UUID,
    payload: CustomFieldDefinitionUpdate,
    *,
    actor_user_id: UUID | None,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
    reason: str | None = None,
) -> CustomFieldDefinition:
    definition = await db.scalar(
        select(CustomFieldDefinition).where(
            CustomFieldDefinition.id == definition_id,
            CustomFieldDefinition.organization_id == organization_id,
        )
    )
    if definition is None:
        raise MetadataValidationError("Custom field definition was not found")
    if definition.version != payload.expected_version:
        raise MetadataConflictError("Custom field definition changed; reload before saving")

    before = await _definition_snapshot(db, definition)
    fields = payload.model_fields_set - {"expected_version"}
    non_nullable = {
        "label",
        "required",
        "searchable",
        "filterable",
        "reportable",
        "visible",
        "editable",
        "display_order",
        "active",
    }
    for field_name in fields:
        field_value = getattr(payload, field_name)
        if field_name in non_nullable and field_value is None:
            raise MetadataValidationError(f"{field_name} cannot be null")

    if "validation_rules" in fields:
        rules = payload.validation_rules or {}
        _ensure_json_compatible(rules, "Validation rules")
        definition.validation_rules = rules
    if "configuration" in fields:
        configuration = payload.configuration or {}
        _ensure_json_compatible(configuration, "Configuration")
        definition.configuration = configuration
    if "default_value" in fields:
        definition.default_value = (
            None
            if payload.default_value is None
            else typed_value_to_json(
                normalize_custom_value(definition.field_type, payload.default_value)
            )
        )

    permission_fields = {"view_permission_key", "edit_permission_key"} & fields
    if permission_fields:
        await _validate_permission_keys(
            db,
            [payload.view_permission_key, payload.edit_permission_key],
        )

    direct_fields = fields - {"validation_rules", "configuration", "default_value"}
    for field_name in direct_fields:
        setattr(definition, field_name, getattr(payload, field_name))

    definition.version += 1
    await db.flush()
    after = await _add_definition_revision(
        db, definition, actor_user_id=actor_user_id, reason=reason
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="metadata.custom_field.changed",
        target_type="custom_field_definition",
        target_id=str(definition.id),
        actor_type=AuditActorType.USER if actor_user_id is not None else AuditActorType.SYSTEM,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"before": before, "after": after},
    )
    return definition


async def create_field_option(
    db: AsyncSession,
    organization_id: UUID,
    definition_id: UUID,
    payload: CustomFieldOptionCreate,
    *,
    actor_user_id: UUID | None,
    session_id: UUID | None = None,
    correlation_id: UUID | None = None,
    reason: str | None = None,
) -> CustomFieldOption:
    definition = await db.scalar(
        select(CustomFieldDefinition).where(
            CustomFieldDefinition.id == definition_id,
            CustomFieldDefinition.organization_id == organization_id,
        )
    )
    if definition is None or not definition.active:
        raise MetadataValidationError("Active custom field definition was not found")
    if definition.field_type not in SELECT_FIELD_TYPES:
        raise MetadataValidationError("Options are allowed only for select fields")

    duplicate = await db.scalar(
        select(CustomFieldOption.id).where(
            CustomFieldOption.definition_id == definition.id,
            CustomFieldOption.key == payload.key,
        )
    )
    if duplicate is not None:
        raise MetadataConflictError("Option key already exists")

    before = await _definition_snapshot(db, definition)
    option = CustomFieldOption(
        definition_id=definition.id,
        key=payload.key,
        label=payload.label,
        display_order=payload.display_order,
    )
    db.add(option)
    definition.version += 1
    await db.flush()
    after = await _add_definition_revision(
        db, definition, actor_user_id=actor_user_id, reason=reason
    )
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="metadata.custom_field.option_created",
        target_type="custom_field_definition",
        target_id=str(definition.id),
        actor_type=AuditActorType.USER if actor_user_id is not None else AuditActorType.SYSTEM,
        actor_user_id=actor_user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"before": before, "after": after},
    )
    return option


async def _validate_select_value(
    db: AsyncSession,
    definition: CustomFieldDefinition,
    typed_value: TypedCustomValue,
) -> None:
    if definition.field_type == CustomFieldType.SINGLE_SELECT:
        keys = {typed_value.text_value} if typed_value.text_value is not None else set()
    elif definition.field_type == CustomFieldType.MULTI_SELECT:
        keys = set(typed_value.json_value or [])
    else:
        return

    if not keys:
        return
    valid_keys = set(
        (
            await db.scalars(
                select(CustomFieldOption.key).where(
                    CustomFieldOption.definition_id == definition.id,
                    CustomFieldOption.key.in_(keys),
                    CustomFieldOption.active.is_(True),
                )
            )
        ).all()
    )
    if valid_keys != keys:
        raise MetadataValidationError("One or more select options are invalid or inactive")


async def write_custom_field_value(
    db: AsyncSession,
    organization_id: UUID,
    definition_id: UUID,
    entity_id: UUID,
    value: object,
    *,
    actor_user_id: UUID | None,
) -> CustomFieldValue:
    definition = await db.scalar(
        select(CustomFieldDefinition).where(
            CustomFieldDefinition.id == definition_id,
            CustomFieldDefinition.organization_id == organization_id,
            CustomFieldDefinition.active.is_(True),
        )
    )
    if definition is None:
        raise MetadataValidationError("Active custom field definition was not found")
    if value is None and definition.required:
        raise MetadataValidationError("This custom field is required")

    typed_value = normalize_custom_value(definition.field_type, value)
    await _validate_select_value(db, definition, typed_value)

    row = await db.scalar(
        select(CustomFieldValue).where(
            CustomFieldValue.organization_id == organization_id,
            CustomFieldValue.definition_id == definition.id,
            CustomFieldValue.entity_id == entity_id,
        )
    )
    if row is None:
        row = CustomFieldValue(
            organization_id=organization_id,
            definition_id=definition.id,
            entity_id=entity_id,
            definition_version=definition.version,
        )
        db.add(row)

    row.definition_version = definition.version
    row.text_value = typed_value.text_value
    row.numeric_value = typed_value.numeric_value
    row.boolean_value = typed_value.boolean_value
    row.date_value = typed_value.date_value
    row.datetime_value = typed_value.datetime_value
    row.uuid_value = typed_value.uuid_value
    row.json_value = typed_value.json_value
    row.currency_code = typed_value.currency_code
    row.unit_code = typed_value.unit_code
    row.updated_by_user_id = actor_user_id
    await db.flush()
    return row
