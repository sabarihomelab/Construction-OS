from pydantic import BaseModel, Field

from app.modules.features.registry import FeatureKind, FeatureReleaseState, FeatureSensitivity


class VisibleFeature(BaseModel):
    key: str
    name: str
    kind: FeatureKind
    parent_key: str | None
    route: str | None
    sensitivity: FeatureSensitivity
    display_order: int
    mobile_enabled: bool
    offline_enabled: bool
    help_topic: str | None


class AccessContext(BaseModel):
    organization_id: str
    membership_id: str
    authorization_revision: int = Field(ge=1)
    permissions: list[str]
    features: list[VisibleFeature]


class FeatureRegistryEntry(BaseModel):
    key: str
    name: str
    kind: FeatureKind
    parent_key: str | None
    route: str | None
    required_permissions: list[str]
    tenant_configurable: bool
    enabled_by_default: bool
    release_state: FeatureReleaseState
    sensitivity: FeatureSensitivity
    display_order: int
    mobile_enabled: bool
    offline_enabled: bool
    help_topic: str | None
