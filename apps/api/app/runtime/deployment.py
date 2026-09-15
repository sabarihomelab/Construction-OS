from dataclasses import dataclass
from enum import StrEnum

from app.core.config import Settings
from app.runtime.modules import ModuleManifest, resolve_runtime_modules


class DeploymentProfile(StrEnum):
    DEVELOPMENT = "development"
    SINGLE_SERVER = "single_server"
    SPLIT = "split"


class DatabaseMode(StrEnum):
    LOCAL = "local"
    EXTERNAL = "external"


@dataclass(frozen=True, slots=True)
class RuntimePlan:
    profile: DeploymentProfile
    database_mode: DatabaseMode
    storage_provider: str
    modules: tuple[ModuleManifest, ...]
    worker_profiles: tuple[str, ...]

    @property
    def module_keys(self) -> frozenset[str]:
        return frozenset(module.key for module in self.modules)

    def module_enabled(self, module_key: str) -> bool:
        return module_key in self.module_keys

    def worker_profile_enabled(self, profile: str) -> bool:
        return profile in self.worker_profiles


def _worker_profiles(raw: str, modules: tuple[ModuleManifest, ...]) -> tuple[str, ...]:
    normalized = raw.strip().lower()
    if not normalized or normalized == "auto":
        profiles = {"general"}
        for module in modules:
            profiles.update(module.worker_profiles)
        return tuple(sorted(profiles))

    profiles = {part.strip() for part in normalized.split(",") if part.strip()}
    profiles.add("general")
    return tuple(sorted(profiles))


def build_runtime_plan(settings: Settings) -> RuntimePlan:
    modules = resolve_runtime_modules(settings.runtime_modules)
    storage_provider = settings.storage_provider.strip().lower()
    if not storage_provider:
        raise ValueError("STORAGE_PROVIDER cannot be empty")

    return RuntimePlan(
        profile=DeploymentProfile(settings.deployment_profile),
        database_mode=DatabaseMode(settings.database_mode),
        storage_provider=storage_provider,
        modules=modules,
        worker_profiles=_worker_profiles(settings.worker_profiles, modules),
    )
