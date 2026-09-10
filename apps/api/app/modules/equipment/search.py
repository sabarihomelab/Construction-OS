from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.equipment.models import EquipmentAsset, Material, MaterialDelivery
from app.modules.search.providers import search_projection_providers
from app.modules.search.schemas import SearchProjection


async def equipment_asset_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        asset_id = UUID(entity_id)
    except ValueError:
        return None
    asset = await db.scalar(
        select(EquipmentAsset).where(
            EquipmentAsset.id == asset_id,
            EquipmentAsset.organization_id == organization_id,
        )
    )
    if asset is None:
        return None
    body = "\n".join(
        value
        for value in (asset.category, asset.make, asset.model, asset.serial_number, asset.notes)
        if value
    )
    return SearchProjection(
        entity_type="equipment_asset",
        entity_id=str(asset.id),
        entity_version=asset.revision,
        required_permission_key="equipment.asset.view",
        title=asset.name,
        subtitle=asset.asset_number,
        body=body,
        keywords=[asset.asset_number, asset.status.value, asset.ownership.value],
        route_hint=f"/equipment/assets/{asset.id}",
        source_updated_at=asset.updated_at,
    )


async def material_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        material_id = UUID(entity_id)
    except ValueError:
        return None
    material = await db.scalar(
        select(Material).where(
            Material.id == material_id,
            Material.organization_id == organization_id,
        )
    )
    if material is None:
        return None
    return SearchProjection(
        entity_type="material",
        entity_id=str(material.id),
        entity_version=material.revision,
        required_permission_key="materials.material.view",
        title=material.name,
        subtitle=material.code,
        body=material.description or "",
        keywords=[material.code, material.category or "", material.status.value],
        route_hint=f"/materials/{material.id}",
        source_updated_at=material.updated_at,
    )


async def material_delivery_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        delivery_id = UUID(entity_id)
    except ValueError:
        return None
    delivery = await db.scalar(
        select(MaterialDelivery).where(
            MaterialDelivery.id == delivery_id,
            MaterialDelivery.organization_id == organization_id,
        )
    )
    if delivery is None:
        return None
    material = await db.scalar(
        select(Material).where(
            Material.id == delivery.material_id,
            Material.organization_id == organization_id,
        )
    )
    material_name = material.name if material is not None else str(delivery.material_id)
    return SearchProjection(
        entity_type="material_delivery",
        entity_id=str(delivery.id),
        entity_version=delivery.revision,
        required_permission_key="materials.delivery.view",
        scope_type="project",
        scope_id=str(delivery.project_id),
        title=f"{material_name} delivery",
        subtitle=delivery.ticket_number or delivery.status.value,
        body="\n".join(value for value in (delivery.supplier, delivery.location, delivery.notes) if value),
        keywords=[material_name, delivery.status.value, str(delivery.quantity), delivery.unit_code],
        route_hint=f"/projects/{delivery.project_id}/materials/deliveries/{delivery.id}",
        source_updated_at=delivery.updated_at,
    )


for entity_type, provider in (
    ("equipment_asset", equipment_asset_search_projection),
    ("material", material_search_projection),
    ("material_delivery", material_delivery_search_projection),
):
    if not search_projection_providers.contains(entity_type):
        search_projection_providers.register(entity_type, provider)
