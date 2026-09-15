from dataclasses import dataclass
from datetime import date


class ContractCompatibilityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ContractSpec:
    key: str
    current_version: int
    minimum_supported_version: int
    deprecated_before: int | None = None
    sunset_date: date | None = None

    def supports(self, version: int) -> bool:
        return self.minimum_supported_version <= version <= self.current_version

    def require_supported(self, version: int) -> None:
        if not self.supports(version):
            raise ContractCompatibilityError(
                f"{self.key} version {version} is unsupported; supported range is "
                f"{self.minimum_supported_version}..{self.current_version}"
            )


class ContractRegistry:
    def __init__(self) -> None:
        self._contracts: dict[str, ContractSpec] = {}

    def register(self, contract: ContractSpec) -> None:
        if not contract.key.strip():
            raise ValueError("Contract key is required")
        if contract.minimum_supported_version < 1:
            raise ValueError("Minimum supported contract version must be at least 1")
        if contract.current_version < contract.minimum_supported_version:
            raise ValueError("Current contract version cannot precede minimum supported version")
        if contract.deprecated_before is not None and not (
            contract.minimum_supported_version <= contract.deprecated_before <= contract.current_version
        ):
            raise ValueError("deprecated_before must be inside the supported version range")
        if contract.key in self._contracts:
            raise ValueError(f"Contract already registered: {contract.key}")
        self._contracts[contract.key] = contract

    def get(self, key: str) -> ContractSpec:
        try:
            return self._contracts[key]
        except KeyError as exc:
            raise ContractCompatibilityError(f"Unknown contract: {key}") from exc


PLATFORM_CONTRACTS = ContractRegistry()
PLATFORM_CONTRACTS.register(
    ContractSpec(key="api.v1", current_version=1, minimum_supported_version=1)
)
PLATFORM_CONTRACTS.register(
    ContractSpec(key="realtime.event", current_version=1, minimum_supported_version=1)
)
PLATFORM_CONTRACTS.register(
    ContractSpec(key="background_job.payload", current_version=1, minimum_supported_version=1)
)
PLATFORM_CONTRACTS.register(
    ContractSpec(key="tenant_export.manifest", current_version=1, minimum_supported_version=1)
)
PLATFORM_CONTRACTS.register(
    ContractSpec(key="offline.mutation", current_version=1, minimum_supported_version=1)
)
