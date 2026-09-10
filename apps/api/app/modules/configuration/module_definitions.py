from dataclasses import dataclass
from decimal import Decimal

from app.modules.configuration.models import ConfigurationChangeClass


@dataclass(frozen=True, slots=True)
class ModuleConfigurationDefinition:
    key: str
    module_key: str
    value_type: str
    default: object
    change_class: ConfigurationChangeClass
    mutability: str = "business"
    business_scoped: bool = True
    allowed_values: tuple[str, ...] = ()
    min_value: int | Decimal | None = None
    max_value: int | Decimal | None = None
    max_length: int | None = None
    description: str = ""


MODULE_CONFIGURATION_DEFINITIONS: tuple[ModuleConfigurationDefinition, ...] = (
    ModuleConfigurationDefinition(
        key="safety.records.types.enabled",
        module_key="safety",
        value_type="string_list",
        default=["hazard", "observation", "incident", "near_miss", "toolbox_talk"],
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        allowed_values=("hazard", "observation", "incident", "near_miss", "toolbox_talk"),
        description="Safety record types available for new project records.",
    ),
    ModuleConfigurationDefinition(
        key="safety.records.corrective_action_required_severities",
        module_key="safety",
        value_type="string_list",
        default=["high", "critical"],
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        allowed_values=("low", "medium", "high", "critical"),
        description="Safety severities that require at least one corrective action before closure.",
    ),
    ModuleConfigurationDefinition(
        key="safety.inspections.approval.required",
        module_key="safety",
        value_type="boolean",
        default=False,
        change_class=ConfigurationChangeClass.WORKFLOW,
        description="Whether submitted inspections require shared Workflow review.",
    ),
    ModuleConfigurationDefinition(
        key="safety.inspections.workflow.definition_key",
        module_key="safety",
        value_type="string",
        default="",
        change_class=ConfigurationChangeClass.WORKFLOW,
        max_length=160,
        description="Published shared Workflow definition used for inspection review.",
    ),
    ModuleConfigurationDefinition(
        key="safety.inspections.workflow.approve_transition_key",
        module_key="safety",
        value_type="string",
        default="",
        change_class=ConfigurationChangeClass.WORKFLOW,
        max_length=160,
        description="Shared Workflow transition used to approve an inspection.",
    ),
    ModuleConfigurationDefinition(
        key="safety.inspections.workflow.reject_transition_key",
        module_key="safety",
        value_type="string",
        default="",
        change_class=ConfigurationChangeClass.WORKFLOW,
        max_length=160,
        description="Shared Workflow transition used to reject an inspection.",
    ),
    ModuleConfigurationDefinition(
        key="safety.punch.require_assignee",
        module_key="safety",
        value_type="boolean",
        default=False,
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        description="Require a project member to be assigned when a Punch item is created.",
    ),
    ModuleConfigurationDefinition(
        key="safety.punch.default_due_days",
        module_key="safety",
        value_type="integer",
        default=7,
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        min_value=0,
        max_value=3650,
        description="Default due-date offset applied to new Punch items without an explicit due date.",
    ),
    ModuleConfigurationDefinition(
        key="meetings.external_attendees.enabled",
        module_key="meetings",
        value_type="boolean",
        default=True,
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        description="Allow purpose-scoped external attendees to be recorded on project meetings.",
    ),
    ModuleConfigurationDefinition(
        key="meetings.actions.default_due_days",
        module_key="meetings",
        value_type="integer",
        default=7,
        change_class=ConfigurationChangeClass.BUSINESS_RULE,
        min_value=0,
        max_value=3650,
        description="Default due-date offset for meeting action items.",
    ),
    ModuleConfigurationDefinition(
        key="meetings.minutes.approval.required",
        module_key="meetings",
        value_type="boolean",
        default=False,
        change_class=ConfigurationChangeClass.WORKFLOW,
        description="Whether final meeting minutes require shared Workflow review.",
    ),
    ModuleConfigurationDefinition(
        key="meetings.minutes.workflow.definition_key",
        module_key="meetings",
        value_type="string",
        default="",
        change_class=ConfigurationChangeClass.WORKFLOW,
        max_length=160,
        description="Published shared Workflow definition used for meeting-minutes approval.",
    ),
    ModuleConfigurationDefinition(
        key="meetings.minutes.workflow.approve_transition_key",
        module_key="meetings",
        value_type="string",
        default="",
        change_class=ConfigurationChangeClass.WORKFLOW,
        max_length=160,
        description="Shared Workflow transition used to approve meeting minutes.",
    ),
    ModuleConfigurationDefinition(
        key="meetings.minutes.workflow.reject_transition_key",
        module_key="meetings",
        value_type="string",
        default="",
        change_class=ConfigurationChangeClass.WORKFLOW,
        max_length=160,
        description="Shared Workflow transition used to reject meeting minutes for correction.",
    ),
)
