from dataclasses import dataclass
from enum import StrEnum


class ReportScopeKind(StrEnum):
    ORGANIZATION = "organization"
    PROJECT = "project"
    WORKER = "worker"
    EQUIPMENT = "equipment"
    PARTY = "party"
    ENTITY = "entity"


class AttachmentPolicy(StrEnum):
    NOT_SUPPORTED = "not_supported"
    OPTIONAL = "optional"
    REQUIRED = "required"


class LocationStampPolicy(StrEnum):
    NOT_SUPPORTED = "not_supported"
    OPTIONAL = "optional"
    REQUIRED = "required"


class ReportGenerationTrigger(StrEnum):
    MANUAL = "manual"
    ON_SUBMIT = "on_submit"
    ON_APPROVAL = "on_approval"
    ON_ISSUE = "on_issue"
    ON_CLOSE = "on_close"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    PERIOD_CLOSE = "period_close"


@dataclass(frozen=True, slots=True)
class ReportTypeContract:
    key: str
    name: str
    scopes: tuple[ReportScopeKind, ...]
    allowed_triggers: tuple[ReportGenerationTrigger, ...]
    default_trigger: ReportGenerationTrigger
    attachment_policy: AttachmentPolicy = AttachmentPolicy.NOT_SUPPORTED
    location_stamp_policy: LocationStampPolicy = LocationStampPolicy.NOT_SUPPORTED
    supports_photos: bool = False
    supports_signatures: bool = False
    supports_section_selection: bool = True
    stores_issued_output: bool = True
    filename_pattern: str = "{{report.number}}"
    required_permission_key: str | None = None


class ReportTypeRegistry:
    def __init__(self) -> None:
        self._contracts: dict[str, ReportTypeContract] = {}

    def register(self, contract: ReportTypeContract) -> None:
        key = contract.key.strip()
        if not key:
            raise ValueError("Report type key is required")
        if key in self._contracts:
            raise ValueError(f"Report type is already registered: {key}")
        if not contract.scopes:
            raise ValueError("Report type must support at least one scope")
        if not contract.allowed_triggers:
            raise ValueError("Report type must allow at least one generation trigger")
        if contract.default_trigger not in contract.allowed_triggers:
            raise ValueError("Default generation trigger must be allowed by the report type")
        if not contract.filename_pattern.strip():
            raise ValueError("Report filename pattern is required")
        self._contracts[key] = contract

    def get(self, key: str) -> ReportTypeContract:
        try:
            return self._contracts[key]
        except KeyError as exc:
            raise KeyError(f"Unknown report type: {key}") from exc

    def contains(self, key: str) -> bool:
        return key in self._contracts

    def all(self) -> tuple[ReportTypeContract, ...]:
        return tuple(sorted(self._contracts.values(), key=lambda item: item.key))


report_types = ReportTypeRegistry()
