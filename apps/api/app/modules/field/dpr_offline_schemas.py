from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.modules.field.dpr_custom_field_schemas import DPRCustomFieldReplace
from app.modules.field.dpr_schemas import DPRWorkProgressReplace
from app.modules.field.schemas import (
    DailyReportCreate,
    DailyReportUpdate,
    DailyReportVersionAction,
    DelayEntryWrite,
)
from app.modules.offline.models import SyncMutationStatus


class DailyReportOfflineOperation(StrEnum):
    CREATE_REPORT = "create_report"
    UPDATE_HEADER = "update_header"
    REPLACE_WORK_PROGRESS = "replace_work_progress"
    REPLACE_DELAYS = "replace_delays"
    REPLACE_CUSTOM_FIELDS = "replace_custom_fields"
    SUBMIT = "submit"


class DailyReportDelayReplace(BaseModel):
    expected_revision: int = Field(ge=1)
    rows: list[DelayEntryWrite] = Field(default_factory=list, max_length=1000)
    reason: str | None = Field(default=None, max_length=1000)


class DailyReportOfflineMutationRequest(BaseModel):
    device_id: UUID
    client_mutation_id: UUID
    entity_id: UUID
    operation: DailyReportOfflineOperation
    base_revision: int | None = Field(default=None, ge=1)
    create: DailyReportCreate | None = None
    update: DailyReportUpdate | None = None
    work_progress: DPRWorkProgressReplace | None = None
    delays: DailyReportDelayReplace | None = None
    custom_fields: DPRCustomFieldReplace | None = None
    action: DailyReportVersionAction | None = None

    @model_validator(mode="after")
    def validate_operation_payload(self) -> "DailyReportOfflineMutationRequest":
        supplied = sum(
            item is not None
            for item in (
                self.create,
                self.update,
                self.work_progress,
                self.delays,
                self.custom_fields,
                self.action,
            )
        )
        if supplied != 1:
            raise ValueError("Exactly one Daily Report operation payload is required")

        if self.operation == DailyReportOfflineOperation.CREATE_REPORT:
            if self.create is None or self.base_revision is not None:
                raise ValueError("Create requires create payload and no base_revision")
        elif self.operation == DailyReportOfflineOperation.UPDATE_HEADER:
            if self.update is None or self.base_revision is None:
                raise ValueError("Header update requires update payload and base_revision")
            if self.update.expected_revision != self.base_revision:
                raise ValueError("update.expected_revision must match base_revision")
        elif self.operation == DailyReportOfflineOperation.REPLACE_WORK_PROGRESS:
            if self.work_progress is None or self.base_revision is None:
                raise ValueError("Work progress replacement requires payload and base_revision")
            if self.work_progress.expected_revision != self.base_revision:
                raise ValueError("work_progress.expected_revision must match base_revision")
        elif self.operation == DailyReportOfflineOperation.REPLACE_DELAYS:
            if self.delays is None or self.base_revision is None:
                raise ValueError("Delay replacement requires payload and base_revision")
            if self.delays.expected_revision != self.base_revision:
                raise ValueError("delays.expected_revision must match base_revision")
        elif self.operation == DailyReportOfflineOperation.REPLACE_CUSTOM_FIELDS:
            if self.custom_fields is None or self.base_revision is None:
                raise ValueError("Custom field replacement requires payload and base_revision")
            if self.custom_fields.expected_revision != self.base_revision:
                raise ValueError("custom_fields.expected_revision must match base_revision")
        elif self.operation == DailyReportOfflineOperation.SUBMIT:
            if self.action is None or self.base_revision is None:
                raise ValueError("Submit requires action payload and base_revision")
            if self.action.expected_revision != self.base_revision:
                raise ValueError("action.expected_revision must match base_revision")
        return self


class DailyReportOfflineMutationResponse(BaseModel):
    client_mutation_id: UUID
    entity_id: UUID
    status: SyncMutationStatus
    replayed: bool
    server_revision: int | None = Field(default=None, ge=1)
    result: dict[str, object] = Field(default_factory=dict)
    error_code: str | None = None
