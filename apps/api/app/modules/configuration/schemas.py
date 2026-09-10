from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.modules.configuration.models import (
    ConfigurationChangeClass,
    ConfigurationScopeType,
    PreferenceContextType,
)
from app.modules.configuration.registry import (
    ConfigurationMutability,
    ConfigurationValueType,
)


class ConfigurationDefinitionRead(BaseModel):
    key: str
    module_key: str
    value_type: ConfigurationValueType
    default: object
    change_class: ConfigurationChangeClass
    mutability: ConfigurationMutability
    allowed_scopes: list[ConfigurationScopeType]
    allowed_values: list[str]
    sensitive: bool
    description: str


class ConfigurationOverrideWrite(BaseModel):
    expected_version: int | None = Field(default=None, ge=1)
    value: object | None = None
    inherit: bool = False
    effective_from: datetime | None = None
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_inherit_value(self) -> "ConfigurationOverrideWrite":
        if self.inherit and self.value is not None:
            raise ValueError("Inherited configuration cannot include an override value")
        if not self.inherit and self.value is None:
            raise ValueError("A configuration value is required unless inherit is true")
        if self.effective_from is not None:
            if self.effective_from.tzinfo is None or self.effective_from.utcoffset() is None:
                raise ValueError("effective_from must include a timezone")
        return self


class MembershipPreferenceWrite(BaseModel):
    expected_version: int | None = Field(default=None, ge=1)
    context_type: PreferenceContextType = PreferenceContextType.COMPANY
    project_id: UUID | None = None
    value: object

    @model_validator(mode="after")
    def validate_context(self) -> "MembershipPreferenceWrite":
        if self.context_type == PreferenceContextType.COMPANY and self.project_id is not None:
            raise ValueError("Company preference cannot include a project")
        if self.context_type == PreferenceContextType.PROJECT and self.project_id is None:
            raise ValueError("Project preference requires project_id")
        return self


class ProjectTemplateAssignmentWrite(BaseModel):
    expected_project_revision: int = Field(ge=1)
    template_version_id: UUID | None = None
    reason: str | None = Field(default=None, max_length=1000)


class ResolvedConfigurationSetting(BaseModel):
    key: str
    value: object
    source: str
    change_class: ConfigurationChangeClass
    version: int | None = None
    effective_from: datetime | None = None


class EffectiveLocalizationContext(BaseModel):
    business_timezone: str
    presentation_timezone: str
    base_currency: str
    project_currency: str | None = None
    unit_system: str
    locale: str
    time_format: str
    first_day_of_week: int = Field(ge=0, le=6)


class EffectiveConfigurationRead(BaseModel):
    organization_id: UUID
    membership_id: UUID
    project_id: UUID | None = None
    project_template_version_id: UUID | None = None
    module_key: str
    configuration_revisions: dict[str, int] = Field(default_factory=dict)
    preference_revision: int = Field(ge=1)
    localization: EffectiveLocalizationContext
    settings: list[ResolvedConfigurationSetting]


class ConfigurationOverrideRead(BaseModel):
    configuration_key: str
    module_key: str
    scope_type: ConfigurationScopeType
    scope_id: UUID
    version: int
    enabled: bool
    value: object | None
    effective_from: datetime


class MembershipPreferenceRead(BaseModel):
    preference_key: str
    module_key: str
    context_type: PreferenceContextType
    context_id: UUID
    project_id: UUID | None
    version: int
    value: object
