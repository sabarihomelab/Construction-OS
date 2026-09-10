from dataclasses import dataclass


class ModuleSelectionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ModuleManifest:
    key: str
    name: str
    dependencies: tuple[str, ...] = ()
    integrates_with: tuple[str, ...] = ()
    api_router: str | None = None
    search_provider_module: str | None = None
    worker_profiles: tuple[str, ...] = ()
    default_enabled: bool = True
    heavy_runtime: bool = False


MODULE_MANIFESTS: tuple[ModuleManifest, ...] = (
    ModuleManifest(
        key="projects",
        name="Projects",
        api_router="app.modules.projects.router:router",
        search_provider_module="app.modules.projects.search",
    ),
    ModuleManifest(
        key="documents",
        name="Documents & Specifications",
        dependencies=("projects",),
        search_provider_module="app.modules.documents.search_provider",
    ),
    ModuleManifest(
        key="drawings",
        name="Drawings",
        dependencies=("projects", "documents"),
        search_provider_module="app.modules.drawings.search",
        worker_profiles=("drawings",),
        heavy_runtime=True,
    ),
    ModuleManifest(
        key="rfis",
        name="RFIs",
        dependencies=("projects",),
        integrates_with=("documents", "drawings"),
        api_router="app.modules.rfis.router:router",
        search_provider_module="app.modules.rfis.search",
    ),
    ModuleManifest(
        key="submittals",
        name="Submittals",
        dependencies=("projects",),
        integrates_with=("documents", "drawings", "rfis"),
        api_router="app.modules.submittals.router:router",
        search_provider_module="app.modules.submittals.search",
    ),
    ModuleManifest(
        key="field",
        name="Field Operations",
        dependencies=("projects",),
        integrates_with=("documents", "drawings", "rfis", "workforce", "equipment", "safety"),
        api_router="app.modules.field.router:router",
        search_provider_module="app.modules.field.search",
    ),
    ModuleManifest(
        key="workforce",
        name="Workforce & Time",
        dependencies=("projects",),
        integrates_with=("field", "equipment", "safety"),
        api_router="app.modules.workforce.api:router",
        search_provider_module="app.modules.workforce.search",
    ),
    ModuleManifest(
        key="safety",
        name="Safety / Inspections / Punch",
        dependencies=("projects",),
        integrates_with=("field", "workforce", "documents", "drawings"),
        api_router="app.modules.safety.router:router",
        search_provider_module="app.modules.safety.search",
    ),
    ModuleManifest(
        key="equipment",
        name="Equipment / Materials",
        dependencies=("projects",),
        integrates_with=("field", "workforce"),
        api_router="app.modules.equipment.router:router",
        search_provider_module="app.modules.equipment.search",
    ),
    ModuleManifest(
        key="meetings",
        name="Meetings",
        dependencies=("projects",),
        integrates_with=("rfis", "submittals", "documents", "drawings"),
        api_router="app.modules.meetings.router:router",
        search_provider_module="app.modules.meetings.search",
    ),
    ModuleManifest(
        key="commercial",
        name="Commercial Controls",
        dependencies=("projects",),
        integrates_with=("field", "workforce", "equipment", "documents", "drawings"),
        api_router="app.modules.commercial.router:router",
        search_provider_module="app.modules.commercial.search",
    ),
)

MODULES_BY_KEY = {manifest.key: manifest for manifest in MODULE_MANIFESTS}

if len(MODULES_BY_KEY) != len(MODULE_MANIFESTS):
    raise RuntimeError("Runtime module keys must be unique")

for manifest in MODULE_MANIFESTS:
    unknown_dependencies = set(manifest.dependencies) - set(MODULES_BY_KEY)
    if unknown_dependencies:
        raise RuntimeError(
            f"Runtime module {manifest.key} has unknown dependencies: "
            f"{sorted(unknown_dependencies)}"
        )
    unknown_integrations = set(manifest.integrates_with) - set(MODULES_BY_KEY)
    if unknown_integrations:
        raise RuntimeError(
            f"Runtime module {manifest.key} has unknown optional integrations: "
            f"{sorted(unknown_integrations)}"
        )
    if manifest.key in manifest.dependencies:
        raise RuntimeError(f"Runtime module cannot depend on itself: {manifest.key}")
    if manifest.key in manifest.integrates_with:
        raise RuntimeError(f"Runtime module cannot integrate with itself: {manifest.key}")


def requested_runtime_module_keys(raw: str) -> frozenset[str]:
    normalized = raw.strip()
    if not normalized or normalized.lower() in {"default", "auto"}:
        return frozenset(
            manifest.key for manifest in MODULE_MANIFESTS if manifest.default_enabled
        )
    if normalized == "*":
        return frozenset(MODULES_BY_KEY)

    keys = {part.strip().lower() for part in normalized.split(",") if part.strip()}
    unknown = keys - set(MODULES_BY_KEY)
    if unknown:
        raise ModuleSelectionError(f"Unknown runtime modules: {', '.join(sorted(unknown))}")
    return frozenset(keys)


def resolve_runtime_modules(raw: str) -> tuple[ModuleManifest, ...]:
    requested = requested_runtime_module_keys(raw)
    resolved = set(requested)
    pending = list(requested)

    while pending:
        key = pending.pop()
        manifest = MODULES_BY_KEY[key]
        for dependency in manifest.dependencies:
            if dependency not in resolved:
                resolved.add(dependency)
                pending.append(dependency)

    return tuple(manifest for manifest in MODULE_MANIFESTS if manifest.key in resolved)
