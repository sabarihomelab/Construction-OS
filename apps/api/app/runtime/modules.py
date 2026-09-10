from dataclasses import dataclass


class ModuleSelectionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ModuleManifest:
    key: str
    name: str
    dependencies: tuple[str, ...] = ()
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
        dependencies=("projects", "documents", "drawings"),
        api_router="app.modules.rfis.router:router",
        search_provider_module="app.modules.rfis.search",
    ),
    ModuleManifest(
        key="submittals",
        name="Submittals",
        dependencies=("projects", "documents", "drawings", "rfis"),
        api_router="app.modules.submittals.router:router",
        search_provider_module="app.modules.submittals.search",
    ),
    ModuleManifest(
        key="field",
        name="Field Operations",
        dependencies=("projects",),
        api_router="app.modules.field.router:router",
        search_provider_module="app.modules.field.search",
    ),
)

MODULES_BY_KEY = {manifest.key: manifest for manifest in MODULE_MANIFESTS}

if len(MODULES_BY_KEY) != len(MODULE_MANIFESTS):
    raise RuntimeError("Runtime module keys must be unique")

for manifest in MODULE_MANIFESTS:
    unknown = set(manifest.dependencies) - set(MODULES_BY_KEY)
    if unknown:
        raise RuntimeError(
            f"Runtime module {manifest.key} has unknown dependencies: {sorted(unknown)}"
        )
    if manifest.key in manifest.dependencies:
        raise RuntimeError(f"Runtime module cannot depend on itself: {manifest.key}")


def _requested_keys(raw: str) -> set[str]:
    normalized = raw.strip()
    if not normalized or normalized.lower() in {"default", "auto"}:
        return {manifest.key for manifest in MODULE_MANIFESTS if manifest.default_enabled}
    if normalized == "*":
        return set(MODULES_BY_KEY)

    keys = {part.strip().lower() for part in normalized.split(",") if part.strip()}
    unknown = keys - set(MODULES_BY_KEY)
    if unknown:
        raise ModuleSelectionError(f"Unknown runtime modules: {', '.join(sorted(unknown))}")
    return keys


def resolve_runtime_modules(raw: str) -> tuple[ModuleManifest, ...]:
    requested = _requested_keys(raw)
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
