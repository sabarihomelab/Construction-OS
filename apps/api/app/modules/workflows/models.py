from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class WorkflowVersionStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class WorkflowStateKind(StrEnum):
    INITIAL = "initial"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WorkflowInstanceStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TransitionRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXECUTED = "executed"


class ApprovalTaskStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalAssigneeType(StrEnum):
    USER = "user"
    ROLE = "role"
    PROJECT_ROLE = "project_role"
    EXTERNAL = "external"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class WorkflowDefinition(UUIDTimestampMixin, Base):
    __tablename__ = "workflow_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_workflow_definitions_org_key"),
        UniqueConstraint("id", "organization_id", name="uq_workflow_definitions_id_org"),
        CheckConstraint("current_version >= 0", name="ck_workflow_definitions_current_version"),
        Index("ix_workflow_definitions_org_entity", "organization_id", "entity_type"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class WorkflowVersion(UUIDTimestampMixin, Base):
    __tablename__ = "workflow_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["definition_id", "organization_id"],
            ["workflow_definitions.id", "workflow_definitions.organization_id"],
            name="fk_workflow_versions_definition_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "definition_id", "version", name="uq_workflow_versions_definition_version"
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            "definition_id",
            name="uq_workflow_versions_id_org_definition",
        ),
        CheckConstraint("version >= 1", name="ck_workflow_versions_version"),
        Index("ix_workflow_versions_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    definition_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[WorkflowVersionStatus] = mapped_column(
        Enum(WorkflowVersionStatus, native_enum=False, values_callable=enum_values),
        default=WorkflowVersionStatus.DRAFT,
    )
    configuration: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class WorkflowState(UUIDTimestampMixin, Base):
    __tablename__ = "workflow_states"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workflow_version_id", "organization_id"],
            ["workflow_versions.id", "workflow_versions.organization_id"],
            name="fk_workflow_states_version_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "workflow_version_id", "key", name="uq_workflow_states_version_key"
        ),
        UniqueConstraint(
            "workflow_version_id",
            "key",
            "organization_id",
            name="uq_workflow_states_version_key_org",
        ),
        CheckConstraint("display_order >= 0", name="ck_workflow_states_display_order"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    workflow_version_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    key: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(180))
    kind: Mapped[WorkflowStateKind] = mapped_column(
        Enum(WorkflowStateKind, native_enum=False, values_callable=enum_values)
    )
    display_order: Mapped[int] = mapped_column(Integer, default=100)
    configuration: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class WorkflowTransition(UUIDTimestampMixin, Base):
    __tablename__ = "workflow_transitions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workflow_version_id", "organization_id"],
            ["workflow_versions.id", "workflow_versions.organization_id"],
            name="fk_workflow_transitions_version_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workflow_version_id", "from_state_key", "organization_id"],
            [
                "workflow_states.workflow_version_id",
                "workflow_states.key",
                "workflow_states.organization_id",
            ],
            name="fk_workflow_transitions_from_state",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workflow_version_id", "to_state_key", "organization_id"],
            [
                "workflow_states.workflow_version_id",
                "workflow_states.key",
                "workflow_states.organization_id",
            ],
            name="fk_workflow_transitions_to_state",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "workflow_version_id", "key", name="uq_workflow_transitions_version_key"
        ),
        CheckConstraint(
            "from_state_key <> to_state_key", name="ck_workflow_transitions_state_change"
        ),
        Index(
            "ix_workflow_transitions_version_from",
            "workflow_version_id",
            "from_state_key",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    workflow_version_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    key: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(180))
    from_state_key: Mapped[str] = mapped_column(String(100))
    to_state_key: Mapped[str] = mapped_column(String(100))
    required_permission_key: Mapped[str | None] = mapped_column(
        ForeignKey("permissions.key", ondelete="RESTRICT"), nullable=True
    )
    requires_reason: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_step_up_mfa: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_policy: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    conditions: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    assignment_rule: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    due_rule: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkflowInstance(UUIDTimestampMixin, Base):
    __tablename__ = "workflow_instances"
    __table_args__ = (
        ForeignKeyConstraint(
            ["definition_id", "organization_id"],
            ["workflow_definitions.id", "workflow_definitions.organization_id"],
            name="fk_workflow_instances_definition_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workflow_version_id", "organization_id", "definition_id"],
            [
                "workflow_versions.id",
                "workflow_versions.organization_id",
                "workflow_versions.definition_id",
            ],
            name="fk_workflow_instances_version_org_definition",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workflow_version_id", "current_state_key", "organization_id"],
            [
                "workflow_states.workflow_version_id",
                "workflow_states.key",
                "workflow_states.organization_id",
            ],
            name="fk_workflow_instances_current_state",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "definition_id",
            "entity_type",
            "entity_id",
            name="uq_workflow_instances_org_definition_entity",
        ),
        UniqueConstraint("id", "organization_id", name="uq_workflow_instances_id_org"),
        CheckConstraint("version >= 1", name="ck_workflow_instances_version"),
        Index("ix_workflow_instances_org_entity", "organization_id", "entity_type", "entity_id"),
        Index("ix_workflow_instances_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    definition_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    workflow_version_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    current_state_key: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[WorkflowInstanceStatus] = mapped_column(
        Enum(WorkflowInstanceStatus, native_enum=False, values_callable=enum_values),
        default=WorkflowInstanceStatus.ACTIVE,
    )
    version: Mapped[int] = mapped_column(BigInteger, default=1)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class WorkflowTransitionRequest(UUIDTimestampMixin, Base):
    __tablename__ = "workflow_transition_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workflow_instance_id", "organization_id"],
            ["workflow_instances.id", "workflow_instances.organization_id"],
            name="fk_workflow_transition_requests_instance_org",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "expected_instance_version >= 1",
            name="ck_workflow_transition_requests_expected_version",
        ),
        Index(
            "ix_workflow_transition_requests_org_status", "organization_id", "status"
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    workflow_instance_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    transition_key: Mapped[str] = mapped_column(String(100))
    from_state_key: Mapped[str] = mapped_column(String(100))
    to_state_key: Mapped[str] = mapped_column(String(100))
    expected_instance_version: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[TransitionRequestStatus] = mapped_column(
        Enum(TransitionRequestStatus, native_enum=False, values_callable=enum_values),
        default=TransitionRequestStatus.PENDING,
    )
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_context: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkflowApprovalTask(UUIDTimestampMixin, Base):
    __tablename__ = "workflow_approval_tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["transition_request_id", "organization_id"],
            [
                "workflow_transition_requests.id",
                "workflow_transition_requests.organization_id",
            ],
            name="fk_workflow_approval_tasks_request_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "transition_request_id",
            "sequence",
            "assignee_type",
            "assignee_id",
            name="uq_workflow_approval_tasks_request_assignee",
        ),
        CheckConstraint("sequence >= 1", name="ck_workflow_approval_tasks_sequence"),
        Index("ix_workflow_approval_tasks_org_status", "organization_id", "status"),
        Index(
            "ix_workflow_approval_tasks_assignee",
            "organization_id",
            "assignee_type",
            "assignee_id",
            "status",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    transition_request_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=1)
    assignee_type: Mapped[ApprovalAssigneeType] = mapped_column(
        Enum(ApprovalAssigneeType, native_enum=False, values_callable=enum_values)
    )
    assignee_id: Mapped[str] = mapped_column(String(160))
    status: Mapped[ApprovalTaskStatus] = mapped_column(
        Enum(ApprovalTaskStatus, native_enum=False, values_callable=enum_values),
        default=ApprovalTaskStatus.PENDING,
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class WorkflowHistoryEvent(Base):
    __tablename__ = "workflow_history_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workflow_instance_id", "organization_id"],
            ["workflow_instances.id", "workflow_instances.organization_id"],
            name="fk_workflow_history_events_instance_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "workflow_instance_id", "instance_version", name="uq_workflow_history_instance_version"
        ),
        CheckConstraint("instance_version >= 1", name="ck_workflow_history_instance_version"),
        Index("ix_workflow_history_org_occurred", "organization_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    workflow_instance_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    instance_version: Mapped[int] = mapped_column(BigInteger)
    transition_key: Mapped[str] = mapped_column(String(100))
    from_state_key: Mapped[str] = mapped_column(String(100))
    to_state_key: Mapped[str] = mapped_column(String(100))
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    correlation_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    event_context: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
