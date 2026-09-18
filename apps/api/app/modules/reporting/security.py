from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.metadata.models import CustomFieldDefinition


async def remove_restricted_custom_fields(
    db: AsyncSession,
    *,
    organization_id: UUID,
    source_entity_type: str,
    payload: dict[str, object],
) -> dict[str, object]:
    """Remove permission-gated custom fields from portable report payloads.

    Report generation currently receives a report-level permission rather than the caller's
    complete metadata permission set. The safe default is therefore to exclude any custom field
    with an explicit view permission. Unrestricted reportable fields remain available.
    """

    custom = payload.get("custom_fields")
    if not isinstance(custom, dict):
        return payload

    entity_by_group = {
        "report": source_entity_type,
        "project": "project",
        "company": "organization",
    }
    for group, entity_type in entity_by_group.items():
        values = custom.get(group)
        if not isinstance(values, dict) or not values:
            continue
        restricted = await db.scalars(
            select(CustomFieldDefinition.key).where(
                CustomFieldDefinition.organization_id == organization_id,
                CustomFieldDefinition.entity_type == entity_type,
                CustomFieldDefinition.active.is_(True),
                CustomFieldDefinition.view_permission_key.is_not(None),
            )
        )
        for key in restricted.all():
            values.pop(key, None)
    return payload
