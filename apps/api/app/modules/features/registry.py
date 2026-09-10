from dataclasses import dataclass
from enum import StrEnum


class FeatureKind(StrEnum):
    MODULE = "module"
    PAGE = "page"
    TILE = "tile"
    ACTION = "action"


class FeatureReleaseState(StrEnum):
    AVAILABLE = "available"
    PREVIEW = "preview"
    PLANNED = "planned"
    RETIRED = "retired"


class FeatureSensitivity(StrEnum):
    STANDARD = "standard"
    SENSITIVE = "sensitive"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    key: str
    name: str
    kind: FeatureKind
    parent_key: str | None = None
    route: str | None = None
    required_permissions: tuple[str, ...] = ()
    tenant_configurable: bool = True
    enabled_by_default: bool = True
    release_state: FeatureReleaseState = FeatureReleaseState.AVAILABLE
    sensitivity: FeatureSensitivity = FeatureSensitivity.STANDARD
    display_order: int = 100
    mobile_enabled: bool = True
    offline_enabled: bool = False
    help_topic: str | None = None


FEATURE_REGISTRY: tuple[FeatureSpec, ...] = (
    FeatureSpec(
        key="home",
        name="Home",
        kind=FeatureKind.PAGE,
        route="/",
        tenant_configurable=False,
        display_order=10,
        help_topic="home",
    ),
    FeatureSpec(
        key="projects",
        name="Projects",
        kind=FeatureKind.MODULE,
        route="/projects",
        required_permissions=("projects.project.view",),
        release_state=FeatureReleaseState.PLANNED,
        display_order=100,
        offline_enabled=True,
        help_topic="projects",
    ),
    FeatureSpec(
        key="documents",
        name="Documents & Specifications",
        kind=FeatureKind.MODULE,
        route="/documents",
        required_permissions=("documents.document.view",),
        release_state=FeatureReleaseState.PLANNED,
        display_order=120,
        offline_enabled=True,
        help_topic="documents",
    ),
    FeatureSpec(
        key="drawings",
        name="Drawings",
        kind=FeatureKind.MODULE,
        route="/drawings",
        required_permissions=("drawings.drawing.view",),
        release_state=FeatureReleaseState.PLANNED,
        display_order=130,
        offline_enabled=True,
        help_topic="drawings",
    ),
    FeatureSpec(
        key="rfis",
        name="RFIs",
        kind=FeatureKind.MODULE,
        route="/rfis",
        required_permissions=("rfis.rfi.view",),
        release_state=FeatureReleaseState.PLANNED,
        display_order=140,
        offline_enabled=True,
        help_topic="rfis",
    ),
    FeatureSpec(
        key="submittals",
        name="Submittals",
        kind=FeatureKind.MODULE,
        route="/submittals",
        required_permissions=("submittals.submittal.view",),
        release_state=FeatureReleaseState.PLANNED,
        display_order=150,
        offline_enabled=True,
        help_topic="submittals",
    ),
    FeatureSpec(
        key="meetings",
        name="Meetings",
        kind=FeatureKind.MODULE,
        route="/meetings",
        required_permissions=("meetings.meeting.view",),
        release_state=FeatureReleaseState.PLANNED,
        display_order=170,
        offline_enabled=True,
        help_topic="meetings",
    ),
    FeatureSpec(
        key="field",
        name="Field Operations",
        kind=FeatureKind.MODULE,
        route="/field",
        required_permissions=("field.daily_report.view",),
        release_state=FeatureReleaseState.PLANNED,
        display_order=200,
        offline_enabled=True,
        help_topic="field",
    ),
    FeatureSpec(
        key="workforce",
        name="Workforce & Time",
        kind=FeatureKind.MODULE,
        route="/workforce",
        required_permissions=("workforce.worker.view",),
        release_state=FeatureReleaseState.PLANNED,
        display_order=220,
        offline_enabled=True,
        help_topic="workforce",
    ),
    FeatureSpec(
        key="safety",
        name="Safety / Inspections / Punch",
        kind=FeatureKind.MODULE,
        route="/safety",
        required_permissions=("safety.module.view",),
        release_state=FeatureReleaseState.PLANNED,
        sensitivity=FeatureSensitivity.SENSITIVE,
        display_order=230,
        offline_enabled=True,
        help_topic="safety",
    ),
    FeatureSpec(
        key="equipment",
        name="Equipment / Materials",
        kind=FeatureKind.MODULE,
        route="/equipment",
        required_permissions=("equipment.module.view",),
        release_state=FeatureReleaseState.PLANNED,
        display_order=240,
        offline_enabled=True,
        help_topic="equipment",
    ),
    FeatureSpec(
        key="financials",
        name="Financials",
        kind=FeatureKind.MODULE,
        route="/financials",
        required_permissions=("finance.budget.view",),
        release_state=FeatureReleaseState.PLANNED,
        sensitivity=FeatureSensitivity.HIGH,
        display_order=500,
        mobile_enabled=False,
        help_topic="financials",
    ),
    FeatureSpec(
        key="admin",
        name="Administration",
        kind=FeatureKind.MODULE,
        required_permissions=("admin.settings.view",),
        tenant_configurable=False,
        display_order=900,
        mobile_enabled=False,
        help_topic="admin",
    ),
    FeatureSpec(
        key="admin.roles_access",
        name="Roles & Access",
        kind=FeatureKind.PAGE,
        parent_key="admin",
        route="/admin/roles-access",
        required_permissions=("security.role.view",),
        tenant_configurable=False,
        sensitivity=FeatureSensitivity.SENSITIVE,
        display_order=910,
        mobile_enabled=False,
        help_topic="admin.roles-access",
    ),
    FeatureSpec(
        key="admin.operations",
        name="Operations Center",
        kind=FeatureKind.PAGE,
        parent_key="admin",
        route="/admin/operations",
        required_permissions=("admin.operations.view",),
        tenant_configurable=False,
        sensitivity=FeatureSensitivity.SENSITIVE,
        display_order=920,
        mobile_enabled=False,
        help_topic="admin.operations",
    ),
    FeatureSpec(
        key="admin.configuration",
        name="Company Configuration",
        kind=FeatureKind.PAGE,
        parent_key="admin",
        route="/admin/configuration",
        required_permissions=("admin.configuration.view",),
        tenant_configurable=False,
        release_state=FeatureReleaseState.PLANNED,
        sensitivity=FeatureSensitivity.SENSITIVE,
        display_order=925,
        mobile_enabled=False,
        help_topic="admin.configuration",
    ),
    FeatureSpec(
        key="admin.custom_fields",
        name="Custom Fields",
        kind=FeatureKind.PAGE,
        parent_key="admin",
        route="/admin/custom-fields",
        required_permissions=("admin.custom_field.view",),
        tenant_configurable=False,
        release_state=FeatureReleaseState.PLANNED,
        sensitivity=FeatureSensitivity.SENSITIVE,
        display_order=930,
        mobile_enabled=False,
        help_topic="admin.custom-fields",
    ),
    FeatureSpec(
        key="help",
        name="Help",
        kind=FeatureKind.MODULE,
        route="/help",
        required_permissions=("help.content.view",),
        tenant_configurable=False,
        display_order=1000,
        help_topic="help",
    ),
    FeatureSpec(
        key="help.assistant",
        name="Construction OS Assistant",
        kind=FeatureKind.PAGE,
        parent_key="help",
        route="/help/assistant",
        required_permissions=("help.assistant.use",),
        tenant_configurable=False,
        release_state=FeatureReleaseState.PLANNED,
        sensitivity=FeatureSensitivity.SENSITIVE,
        display_order=1010,
        help_topic="help.assistant",
    ),
)

FEATURES_BY_KEY = {feature.key: feature for feature in FEATURE_REGISTRY}

if len(FEATURES_BY_KEY) != len(FEATURE_REGISTRY):
    raise RuntimeError("Feature registry keys must be unique")

for feature in FEATURE_REGISTRY:
    if feature.parent_key is not None and feature.parent_key not in FEATURES_BY_KEY:
        raise RuntimeError(f"Unknown parent feature: {feature.parent_key}")

    visited = {feature.key}
    parent_key = feature.parent_key
    while parent_key is not None:
        if parent_key in visited:
            raise RuntimeError(f"Feature registry contains a parent cycle at: {parent_key}")
        visited.add(parent_key)
        parent_key = FEATURES_BY_KEY[parent_key].parent_key
