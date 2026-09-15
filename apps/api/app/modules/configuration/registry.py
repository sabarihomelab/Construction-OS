from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID

from app.modules.configuration.models import ConfigurationChangeClass, ConfigurationScopeType
from app.modules.configuration.module_definitions import MODULE_CONFIGURATION_DEFINITIONS


class ConfigurationValueType(StrEnum):
    BOOLEAN = "boolean"
    INTEGER = "integer"
    DECIMAL = "decimal"
    STRING = "string"
    STRING_LIST = "string_list"
    UUID = "uuid"
    JSON = "json"


class ConfigurationMutability(StrEnum):
    PROTECTED = "protected"
    BUSINESS = "business"
    USER_PREFERENCE = "user_preference"


@dataclass(frozen=True, slots=True)
class ConfigurationDefinition:
    key: str
    module_key: str
    value_type: ConfigurationValueType
    default: object
    change_class: ConfigurationChangeClass
    mutability: ConfigurationMutability
    allowed_scopes: tuple[ConfigurationScopeType, ...] = ()
    allowed_values: tuple[str, ...] = ()
    min_value: int | Decimal | None = None
    max_value: int | Decimal | None = None
    max_length: int | None = None
    sensitive: bool = False
    description: str = ""

    @property
    def configurable(self) -> bool:
        return self.mutability != ConfigurationMutability.PROTECTED


BUSINESS_SCOPES = (
    ConfigurationScopeType.COMPANY,
    ConfigurationScopeType.PROJECT_TEMPLATE,
    ConfigurationScopeType.PROJECT,
)

DAILY_REPORT_SECTIONS = (
    "weather",
    "crew",
    "work",
    "equipment",
    "deliveries",
    "production",
    "delays",
    "safety",
    "photos",
    "notes",
)

WORKFORCE_WORKER_FIELDS = (
    "worker_number",
    "first_name",
    "last_name",
    "preferred_name",
    "email",
    "phone",
    "job_title",
    "trade",
    "classification",
    "hire_date",
)

WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


_BASE_CONFIGURATION_DEFINITIONS: tuple[ConfigurationDefinition, ...] = (
    ConfigurationDefinition(
        key="core.audit.enabled",
        module_key="core",
        value_type=ConfigurationValueType.BOOLEAN,
        default=True,
        change_class=ConfigurationChangeClass.SECURITY,
        mutability=ConfigurationMutability.PROTECTED,
        description="Audit enforcement is protected platform behavior.",
    ),
    ConfigurationDefinition(
        key="core.sync.integrity_enabled",
        module_key="core",
        value_type=ConfigurationValueType.BOOLEAN,
        default=True,
        change_class=ConfigurationChangeClass.SECURITY,
        mutability=ConfigurationMutability.PROTECTED,
        description="Offline idempotency and conflict enforcement cannot be disabled by tenants.",
    ),
    ConfigurationDefinition(
        key="core.terminology.overrides",
        module_key="core",
        value_type=ConfigurationValueType.JSON,
        default={},
        change_class=ConfigurationChangeClass.PRESENTATION,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        description="Controlled company/project terminology overrides keyed by canonical term.",
    ),
    ConfigurationDefinition(
        key="core.dashboard.compact_mode",
        module_key="core",
        value_type=ConfigurationValueType.BOOLEAN,
        default=False,
        change_class=ConfigurationChangeClass.PRESENTATION,
        mutability=ConfigurationMutability.USER_PREFERENCE,
        description="Personal preference for denser dashboard presentation.",
    ),
    ConfigurationDefinition(
        key="rfis.default_due_days",
        module_key="rfis",
        value_type=ConfigurationValueType.INTEGER,
        default=7,
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        min_value=0,
        max_value=3650,
        description="Default due-date offset for new RFIs; existing RFIs retain their own due date.",
    ),
    ConfigurationDefinition(
        key="rfis.numbering.prefix",
        module_key="rfis",
        value_type=ConfigurationValueType.STRING,
        default="RFI",
        change_class=ConfigurationChangeClass.METADATA,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        max_length=24,
        description="Display prefix for RFI numbering; stable numeric identity remains protected.",
    ),
    ConfigurationDefinition(
        key="drawings.allow_field_markup",
        module_key="drawings",
        value_type=ConfigurationValueType.BOOLEAN,
        default=True,
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        description="Whether authorized field users may create drawing markups.",
    ),
    ConfigurationDefinition(
        key="field.daily_reports.sections.enabled",
        module_key="field",
        value_type=ConfigurationValueType.STRING_LIST,
        default=["crew", "work", "photos", "notes"],
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        allowed_values=DAILY_REPORT_SECTIONS,
        description="Standard Daily Report sections shown for this company/project.",
    ),
    ConfigurationDefinition(
        key="field.daily_reports.sections.required",
        module_key="field",
        value_type=ConfigurationValueType.STRING_LIST,
        default=["work"],
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        allowed_values=DAILY_REPORT_SECTIONS,
        description="Enabled Daily Report sections that must contain data before submission.",
    ),
    ConfigurationDefinition(
        key="field.daily_reports.approval.required",
        module_key="field",
        value_type=ConfigurationValueType.BOOLEAN,
        default=False,
        change_class=ConfigurationChangeClass.WORKFLOW,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        description="Whether a submitted Daily Report starts the configured shared approval workflow.",
    ),
    ConfigurationDefinition(
        key="field.daily_reports.workflow.definition_key",
        module_key="field",
        value_type=ConfigurationValueType.STRING,
        default="",
        change_class=ConfigurationChangeClass.WORKFLOW,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        max_length=160,
        description="Published shared Workflow definition key used when Daily Report approval is required.",
    ),
    ConfigurationDefinition(
        key="field.daily_reports.carry_forward.enabled",
        module_key="field",
        value_type=ConfigurationValueType.BOOLEAN,
        default=True,
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        description="Allow supported draft sections to be carried forward into a new report.",
    ),
    ConfigurationDefinition(
        key="field.daily_reports.default_shift",
        module_key="field",
        value_type=ConfigurationValueType.STRING,
        default="day",
        change_class=ConfigurationChangeClass.METADATA,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        max_length=40,
        description="Default shift code proposed when a new Daily Report is created.",
    ),
    ConfigurationDefinition(
        key="field.daily_reports.compact_entry",
        module_key="field",
        value_type=ConfigurationValueType.BOOLEAN,
        default=True,
        change_class=ConfigurationChangeClass.PRESENTATION,
        mutability=ConfigurationMutability.USER_PREFERENCE,
        description="Use the compact field-first Daily Report entry experience when available.",
    ),
    ConfigurationDefinition(
        key="field.daily_reports.visible_columns",
        module_key="field",
        value_type=ConfigurationValueType.STRING_LIST,
        default=["report_date", "shift_code", "status"],
        change_class=ConfigurationChangeClass.PRESENTATION,
        mutability=ConfigurationMutability.USER_PREFERENCE,
        description="Personal Daily Report list columns; this does not change business rules.",
    ),
    ConfigurationDefinition(
        key="workforce.workers.fields.enabled",
        module_key="workforce",
        value_type=ConfigurationValueType.STRING_LIST,
        default=list(WORKFORCE_WORKER_FIELDS),
        change_class=ConfigurationChangeClass.METADATA,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        allowed_values=WORKFORCE_WORKER_FIELDS,
        description="Standard Worker attributes shown by this company/project; protected identity remains stored.",
    ),
    ConfigurationDefinition(
        key="workforce.workers.fields.required",
        module_key="workforce",
        value_type=ConfigurationValueType.STRING_LIST,
        default=["worker_number", "first_name", "last_name"],
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        allowed_values=WORKFORCE_WORKER_FIELDS,
        description="Enabled standard Worker attributes required by business configuration.",
    ),
    ConfigurationDefinition(
        key="workforce.timecards.week_start_day",
        module_key="workforce",
        value_type=ConfigurationValueType.STRING,
        default="monday",
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        allowed_values=WEEKDAYS,
        description="Day used to begin a project timecard week.",
    ),
    ConfigurationDefinition(
        key="workforce.timecards.require_cost_code",
        module_key="workforce",
        value_type=ConfigurationValueType.BOOLEAN,
        default=False,
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        description="Require a cost code on every submitted time entry.",
    ),
    ConfigurationDefinition(
        key="workforce.timecards.overtime.enabled",
        module_key="workforce",
        value_type=ConfigurationValueType.BOOLEAN,
        default=True,
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        description="Allow overtime hours to be entered for project timecards.",
    ),
    ConfigurationDefinition(
        key="workforce.timecards.double_time.enabled",
        module_key="workforce",
        value_type=ConfigurationValueType.BOOLEAN,
        default=False,
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        description="Allow double-time hours to be entered for project timecards.",
    ),
    ConfigurationDefinition(
        key="workforce.timecards.max_daily_hours",
        module_key="workforce",
        value_type=ConfigurationValueType.DECIMAL,
        default="24",
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        min_value=Decimal("0.25"),
        max_value=Decimal("24"),
        description="Maximum combined regular/overtime/double-time hours allowed for one calendar day.",
    ),
    ConfigurationDefinition(
        key="workforce.timecards.approval.required",
        module_key="workforce",
        value_type=ConfigurationValueType.BOOLEAN,
        default=False,
        change_class=ConfigurationChangeClass.WORKFLOW,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        description="Whether submitted timecards require the shared Workflow engine.",
    ),
    ConfigurationDefinition(
        key="workforce.timecards.workflow.definition_key",
        module_key="workforce",
        value_type=ConfigurationValueType.STRING,
        default="",
        change_class=ConfigurationChangeClass.WORKFLOW,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        max_length=160,
        description="Published shared Workflow definition key used for timecard approval.",
    ),
    ConfigurationDefinition(
        key="workforce.timecards.workflow.approve_transition_key",
        module_key="workforce",
        value_type=ConfigurationValueType.STRING,
        default="",
        change_class=ConfigurationChangeClass.WORKFLOW,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        max_length=160,
        description="Shared Workflow transition that completes an approved timecard.",
    ),
    ConfigurationDefinition(
        key="workforce.timecards.workflow.reject_transition_key",
        module_key="workforce",
        value_type=ConfigurationValueType.STRING,
        default="",
        change_class=ConfigurationChangeClass.WORKFLOW,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        max_length=160,
        description="Shared Workflow transition used when a reviewer rejects a timecard.",
    ),
    ConfigurationDefinition(
        key="workforce.timecards.workflow.resubmit_transition_key",
        module_key="workforce",
        value_type=ConfigurationValueType.STRING,
        default="",
        change_class=ConfigurationChangeClass.WORKFLOW,
        mutability=ConfigurationMutability.BUSINESS,
        allowed_scopes=BUSINESS_SCOPES,
        max_length=160,
        description="Shared Workflow transition used to resubmit a corrected rejected timecard.",
    ),
    ConfigurationDefinition(
        key="workforce.timecards.visible_columns",
        module_key="workforce",
        value_type=ConfigurationValueType.STRING_LIST,
        default=["worker", "week_start", "status", "total_hours"],
        change_class=ConfigurationChangeClass.PRESENTATION,
        mutability=ConfigurationMutability.USER_PREFERENCE,
        description="Personal timecard list columns; this does not change business rules.",
    ),
)

CONFIGURATION_DEFINITIONS = _BASE_CONFIGURATION_DEFINITIONS + tuple(
    ConfigurationDefinition(
        key=definition.key,
        module_key=definition.module_key,
        value_type=ConfigurationValueType(definition.value_type),
        default=definition.default,
        change_class=definition.change_class,
        mutability=ConfigurationMutability(definition.mutability),
        allowed_scopes=BUSINESS_SCOPES if definition.business_scoped else (),
        allowed_values=definition.allowed_values,
        min_value=definition.min_value,
        max_value=definition.max_value,
        max_length=definition.max_length,
        description=definition.description,
    )
    for definition in MODULE_CONFIGURATION_DEFINITIONS
)

CONFIGURATION_BY_KEY = {definition.key: definition for definition in CONFIGURATION_DEFINITIONS}

if len(CONFIGURATION_BY_KEY) != len(CONFIGURATION_DEFINITIONS):
    raise RuntimeError("Configuration definition keys must be unique")

for definition in CONFIGURATION_DEFINITIONS:
    if not definition.key.startswith(f"{definition.module_key}."):
        raise RuntimeError(f"Configuration key must start with module key: {definition.key}")
    if definition.mutability == ConfigurationMutability.PROTECTED and definition.allowed_scopes:
        raise RuntimeError(f"Protected configuration cannot declare tenant scopes: {definition.key}")
    if (
        definition.mutability == ConfigurationMutability.USER_PREFERENCE
        and definition.change_class != ConfigurationChangeClass.PRESENTATION
    ):
        raise RuntimeError(f"User preferences must be presentation-only: {definition.key}")


def definitions_for_module(module_key: str) -> tuple[ConfigurationDefinition, ...]:
    return tuple(
        definition
        for definition in CONFIGURATION_DEFINITIONS
        if definition.module_key == module_key
    )


def normalize_configuration_value(
    definition: ConfigurationDefinition,
    value: object,
) -> object:
    value_type = definition.value_type

    if value_type == ConfigurationValueType.BOOLEAN:
        if not isinstance(value, bool):
            raise ValueError("Value must be true or false")
        normalized: object = value
    elif value_type == ConfigurationValueType.INTEGER:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Value must be an integer")
        normalized = value
    elif value_type == ConfigurationValueType.DECIMAL:
        if isinstance(value, bool):
            raise ValueError("Value must be numeric")
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Value must be numeric") from exc
        if not decimal_value.is_finite():
            raise ValueError("Numeric value must be finite")
        normalized = str(decimal_value)
    elif value_type == ConfigurationValueType.STRING:
        if not isinstance(value, str):
            raise ValueError("Value must be text")
        normalized = value.strip()
        if definition.max_length is not None and len(normalized) > definition.max_length:
            raise ValueError(f"Value cannot exceed {definition.max_length} characters")
    elif value_type == ConfigurationValueType.STRING_LIST:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError("Value must be a list of strings")
        normalized = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        if definition.allowed_values:
            invalid = [item for item in normalized if item not in definition.allowed_values]
            if invalid:
                raise ValueError("List contains unsupported values: " + ", ".join(invalid))
    elif value_type == ConfigurationValueType.UUID:
        try:
            normalized = str(UUID(str(value)))
        except ValueError as exc:
            raise ValueError("Value must be a UUID") from exc
    elif value_type == ConfigurationValueType.JSON:
        if not isinstance(value, (dict, list, str, int, float, bool)) and value is not None:
            raise ValueError("Value must be JSON-compatible")
        normalized = value
    else:
        raise ValueError(f"Unsupported configuration value type: {value_type}")

    if (
        definition.allowed_values
        and value_type != ConfigurationValueType.STRING_LIST
        and str(normalized) not in definition.allowed_values
    ):
        raise ValueError("Value is not in the allowed set")

    if definition.min_value is not None or definition.max_value is not None:
        numeric = Decimal(str(normalized))
        if definition.min_value is not None and numeric < Decimal(str(definition.min_value)):
            raise ValueError(f"Value must be at least {definition.min_value}")
        if definition.max_value is not None and numeric > Decimal(str(definition.max_value)):
            raise ValueError(f"Value must be at most {definition.max_value}")

    return normalized
