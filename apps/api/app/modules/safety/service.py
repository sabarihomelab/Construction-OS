from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.configuration.schemas import EffectiveConfigurationRead
from app.modules.configuration.service import resolve_effective_configuration
from app.modules.events.service import enqueue_event
from app.modules.projects.models import ProjectMembership, ProjectMembershipStatus
from app.modules.safety.models import (
    CorrectiveActionStatus,
    InspectionResult,
    InspectionResultStatus,
    InspectionRun,
    InspectionRunStatus,
    InspectionTemplate,
    InspectionTemplateVersion,
    InspectionTemplateVersionStatus,
    PunchItem,
    PunchItemStatus,
    SafetyCorrectiveAction,
    SafetyProjectCounter,
    SafetyRecord,
    SafetyRecordStatus,
    SafetyRecordType,
    SafetySeverity,
)
from app.modules.search.service import schedule_search_index
from app.modules.workflows.service import (
    WorkflowConflictError,
    WorkflowPermissionError,
    WorkflowValidationError,
    execute_transition,
    start_workflow_instance,
)


class SafetyValidationError(ValueError):
    pass


class SafetyConflictError(ValueError):
    pass


_COUNTER_FIELDS = {
    "record": "next_record_number",
    "inspection": "next_inspection_number",
    "punch": "next_punch_number",
}


def _setting(config: EffectiveConfigurationRead, key: str, default: object) -> object:
    for setting in config.settings:
        if setting.key == key:
            return setting.value
    return default


def _string_list(value: object, *, key: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SafetyValidationError(f"Configuration {key} must be a list of strings")
    return list(dict.fromkeys(value))


async def _require_project_member(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
) -> None:
    membership = await db.scalar(
        select(ProjectMembership.id).where(
            ProjectMembership.organization_id == organization_id,
            ProjectMembership.project_id == project_id,
            ProjectMembership.organization_membership_id == membership_id,
            ProjectMembership.status == ProjectMembershipStatus.ACTIVE,
        )
    )
    if membership is None:
        raise SafetyValidationError("An active project membership is required")


async def _allocate_number(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    counter: str,
) -> int:
    field_name = _COUNTER_FIELDS[counter]
    column = getattr(SafetyProjectCounter, field_name)
    values = {
        "organization_id": organization_id,
        "project_id": project_id,
        "next_record_number": 1,
        "next_inspection_number": 1,
        "next_punch_number": 1,
        field_name: 2,
    }
    statement = (
        insert(SafetyProjectCounter)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[
                SafetyProjectCounter.organization_id,
                SafetyProjectCounter.project_id,
            ],
            set_={field_name: column + 1},
        )
        .returning(column)
    )
    next_value = await db.scalar(statement)
    if next_value is None:
        raise SafetyValidationError("Unable to allocate project number")
    return int(next_value) - 1


async def _publish_project_change(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    entity_type: str,
    entity_id: UUID,
    entity_version: int,
    event_type: str,
    permission_key: str,
    actor_user_id: UUID,
    session_id: UUID | None,
    payload: dict[str, object],
) -> None:
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_version=entity_version,
        required_permission_key=permission_key,
        scope_type="project",
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload=payload,
    )
    await schedule_search_index(
        db,
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_version=entity_version,
    )


async def create_safety_record(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    values: Mapping[str, object],
    session_id: UUID | None = None,
) -> SafetyRecord:
    await _require_project_member(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    config = await resolve_effective_configuration(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        module_key="safety",
        project_id=project_id,
    )
    record_type = SafetyRecordType(str(values["record_type"]))
    enabled_types = _string_list(
        _setting(
            config,
            "safety.records.types.enabled",
            [item.value for item in SafetyRecordType],
        ),
        key="safety.records.types.enabled",
    )
    if record_type.value not in enabled_types:
        raise SafetyValidationError(f"Safety record type is disabled: {record_type.value}")

    number = await _allocate_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        counter="record",
    )
    data = dict(values)
    data.pop("record_type", None)
    record = SafetyRecord(
        organization_id=organization_id,
        project_id=project_id,
        number=number,
        record_type=record_type,
        reported_by_membership_id=membership_id,
        configuration_context={
            "configuration_revisions": config.configuration_revisions,
            "project_template_version_id": (
                str(config.project_template_version_id)
                if config.project_template_version_id
                else None
            ),
        },
        **data,
    )
    db.add(record)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="safety.record.created",
        target_type="safety_record",
        target_id=str(record.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH if record.severity == SafetySeverity.CRITICAL else AuditRisk.MEDIUM,
        changes={"number": number, "type": record.record_type.value, "severity": record.severity.value},
    )
    await _publish_project_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        entity_type="safety_record",
        entity_id=record.id,
        entity_version=record.revision,
        event_type="safety.record.created",
        permission_key="safety.record.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"number": number, "severity": record.severity.value},
    )
    return record


async def update_safety_record(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    record_id: UUID,
    expected_revision: int,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> SafetyRecord:
    record = await db.scalar(
        select(SafetyRecord)
        .where(
            SafetyRecord.id == record_id,
            SafetyRecord.organization_id == organization_id,
            SafetyRecord.project_id == project_id,
        )
        .with_for_update()
    )
    if record is None:
        raise SafetyValidationError("Safety record was not found")
    if record.revision != expected_revision:
        raise SafetyConflictError("Safety record changed; refresh before saving")
    if record.status in {SafetyRecordStatus.CLOSED, SafetyRecordStatus.VOID}:
        raise SafetyValidationError("Closed or void safety records cannot be edited")

    before = {"status": record.status.value, "severity": record.severity.value, "title": record.title}
    mutable = {"severity", "title", "description", "location", "occurred_at"}
    for key, value in changes.items():
        if key in mutable:
            setattr(record, key, value)
    record.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="safety.record.updated",
        target_type="safety_record",
        target_id=str(record.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={
            "before": before,
            "after": {"status": record.status.value, "severity": record.severity.value, "title": record.title},
        },
    )
    await _publish_project_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        entity_type="safety_record",
        entity_id=record.id,
        entity_version=record.revision,
        event_type="safety.record.updated",
        permission_key="safety.record.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": record.revision, "severity": record.severity.value},
    )
    return record


async def add_corrective_action(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    record_id: UUID,
    actor_user_id: UUID,
    values: Mapping[str, object],
    session_id: UUID | None = None,
) -> SafetyCorrectiveAction:
    record = await db.scalar(
        select(SafetyRecord)
        .where(
            SafetyRecord.id == record_id,
            SafetyRecord.organization_id == organization_id,
            SafetyRecord.project_id == project_id,
        )
        .with_for_update()
    )
    if record is None or record.status in {SafetyRecordStatus.CLOSED, SafetyRecordStatus.VOID}:
        raise SafetyValidationError("Open safety record was not found")
    assignee = values.get("assigned_to_membership_id")
    if isinstance(assignee, UUID):
        await _require_project_member(
            db,
            organization_id=organization_id,
            project_id=project_id,
            membership_id=assignee,
        )
    sequence = int(
        await db.scalar(
            select(func.coalesce(func.max(SafetyCorrectiveAction.sequence), 0)).where(
                SafetyCorrectiveAction.organization_id == organization_id,
                SafetyCorrectiveAction.safety_record_id == record_id,
            )
        )
        or 0
    ) + 1
    action = SafetyCorrectiveAction(
        organization_id=organization_id,
        project_id=project_id,
        safety_record_id=record_id,
        sequence=sequence,
        **dict(values),
    )
    db.add(action)
    await db.flush()
    record.revision += 1
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="safety.corrective_action.created",
        target_type="safety_record",
        target_id=str(record.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"action_id": action.id, "sequence": sequence},
    )
    await _publish_project_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        entity_type="safety_record",
        entity_id=record.id,
        entity_version=record.revision,
        event_type="safety.corrective_action.created",
        permission_key="safety.record.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": record.revision, "corrective_action_id": str(action.id)},
    )
    return action


async def update_corrective_action(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    action_id: UUID,
    expected_revision: int,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> SafetyCorrectiveAction:
    action = await db.scalar(
        select(SafetyCorrectiveAction)
        .where(
            SafetyCorrectiveAction.id == action_id,
            SafetyCorrectiveAction.organization_id == organization_id,
            SafetyCorrectiveAction.project_id == project_id,
        )
        .with_for_update()
    )
    if action is None:
        raise SafetyValidationError("Corrective action was not found")
    if action.revision != expected_revision:
        raise SafetyConflictError("Corrective action changed; refresh before saving")
    assignee = changes.get("assigned_to_membership_id")
    if isinstance(assignee, UUID):
        await _require_project_member(
            db,
            organization_id=organization_id,
            project_id=project_id,
            membership_id=assignee,
        )
    mutable = {"description", "assigned_to_membership_id", "due_date", "status"}
    for key, value in changes.items():
        if key in mutable:
            setattr(action, key, value)
    if action.status == CorrectiveActionStatus.COMPLETED and action.completed_at is None:
        action.completed_at = datetime.now(UTC)
    elif action.status != CorrectiveActionStatus.COMPLETED:
        action.completed_at = None
    action.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="safety.corrective_action.updated",
        target_type="safety_corrective_action",
        target_id=str(action.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"status": action.status.value, "revision": action.revision},
    )
    return action


async def close_safety_record(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    record_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> SafetyRecord:
    record = await db.scalar(
        select(SafetyRecord)
        .where(
            SafetyRecord.id == record_id,
            SafetyRecord.organization_id == organization_id,
            SafetyRecord.project_id == project_id,
        )
        .with_for_update()
    )
    if record is None:
        raise SafetyValidationError("Safety record was not found")
    if record.revision != expected_revision:
        raise SafetyConflictError("Safety record changed; refresh before closing")
    if record.status == SafetyRecordStatus.CLOSED:
        return record
    if record.status == SafetyRecordStatus.VOID:
        raise SafetyValidationError("Void safety records cannot be closed")

    config = await resolve_effective_configuration(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        module_key="safety",
        project_id=project_id,
    )
    required_severities = _string_list(
        _setting(config, "safety.records.corrective_action_required_severities", ["high", "critical"]),
        key="safety.records.corrective_action_required_severities",
    )
    actions = list(
        (
            await db.scalars(
                select(SafetyCorrectiveAction).where(
                    SafetyCorrectiveAction.organization_id == organization_id,
                    SafetyCorrectiveAction.safety_record_id == record.id,
                )
            )
        ).all()
    )
    if record.severity.value in required_severities and not actions:
        raise SafetyValidationError("A corrective action is required before closing this record")
    open_actions = [
        action for action in actions if action.status not in {CorrectiveActionStatus.COMPLETED, CorrectiveActionStatus.CANCELLED}
    ]
    if open_actions:
        raise SafetyValidationError("Complete or cancel all corrective actions before closing")

    record.status = SafetyRecordStatus.CLOSED
    record.closed_at = datetime.now(UTC)
    record.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="safety.record.closed",
        target_type="safety_record",
        target_id=str(record.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": record.status.value, "revision": record.revision},
    )
    await _publish_project_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        entity_type="safety_record",
        entity_id=record.id,
        entity_version=record.revision,
        event_type="safety.record.closed",
        permission_key="safety.record.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": record.revision, "status": record.status.value},
    )
    return record


async def create_inspection_template(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    values: Mapping[str, object],
    session_id: UUID | None = None,
) -> InspectionTemplate:
    key = str(values["key"]).strip().lower()
    duplicate = await db.scalar(
        select(InspectionTemplate.id).where(
            InspectionTemplate.organization_id == organization_id,
            InspectionTemplate.key == key,
        )
    )
    if duplicate is not None:
        raise SafetyConflictError("Inspection template key already exists")
    data = dict(values)
    data["key"] = key
    template = InspectionTemplate(organization_id=organization_id, **data)
    db.add(template)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="safety.inspection_template.created",
        target_type="inspection_template",
        target_id=str(template.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"key": key, "name": template.name},
    )
    return template


async def create_inspection_template_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    template_id: UUID,
    checklist: list[dict[str, object]],
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> InspectionTemplateVersion:
    template = await db.scalar(
        select(InspectionTemplate)
        .where(
            InspectionTemplate.id == template_id,
            InspectionTemplate.organization_id == organization_id,
            InspectionTemplate.active.is_(True),
        )
        .with_for_update()
    )
    if template is None:
        raise SafetyValidationError("Active inspection template was not found")
    latest = int(
        await db.scalar(
            select(func.coalesce(func.max(InspectionTemplateVersion.version), 0)).where(
                InspectionTemplateVersion.organization_id == organization_id,
                InspectionTemplateVersion.template_id == template_id,
            )
        )
        or 0
    )
    version = InspectionTemplateVersion(
        organization_id=organization_id,
        template_id=template_id,
        version=latest + 1,
        checklist=checklist,
    )
    db.add(version)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="safety.inspection_template.version.created",
        target_type="inspection_template",
        target_id=str(template.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"version": version.version},
    )
    return version


async def update_inspection_template_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    version_id: UUID,
    expected_revision: int,
    checklist: list[dict[str, object]],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> InspectionTemplateVersion:
    version = await db.scalar(
        select(InspectionTemplateVersion)
        .where(
            InspectionTemplateVersion.id == version_id,
            InspectionTemplateVersion.organization_id == organization_id,
        )
        .with_for_update()
    )
    if version is None:
        raise SafetyValidationError("Inspection template version was not found")
    if version.revision != expected_revision:
        raise SafetyConflictError("Inspection template version changed; refresh before saving")
    if version.status != InspectionTemplateVersionStatus.DRAFT:
        raise SafetyValidationError("Published inspection template versions are immutable")
    version.checklist = checklist
    version.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="safety.inspection_template.version.updated",
        target_type="inspection_template_version",
        target_id=str(version.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"revision": version.revision},
    )
    return version


async def publish_inspection_template_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    version_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> InspectionTemplateVersion:
    version = await db.scalar(
        select(InspectionTemplateVersion)
        .where(
            InspectionTemplateVersion.id == version_id,
            InspectionTemplateVersion.organization_id == organization_id,
        )
        .with_for_update()
    )
    if version is None:
        raise SafetyValidationError("Inspection template version was not found")
    if version.revision != expected_revision:
        raise SafetyConflictError("Inspection template version changed; refresh before publishing")
    if version.status != InspectionTemplateVersionStatus.DRAFT:
        raise SafetyValidationError("Only draft inspection template versions can be published")
    if not version.checklist:
        raise SafetyValidationError("Inspection template must contain checklist items")
    keys = [str(item.get("key", "")) for item in version.checklist]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise SafetyValidationError("Inspection checklist item keys must be non-empty and unique")

    template = await db.scalar(
        select(InspectionTemplate)
        .where(
            InspectionTemplate.id == version.template_id,
            InspectionTemplate.organization_id == organization_id,
        )
        .with_for_update()
    )
    if template is None or not template.active:
        raise SafetyValidationError("Active inspection template was not found")
    prior_versions = list(
        (
            await db.scalars(
                select(InspectionTemplateVersion).where(
                    InspectionTemplateVersion.organization_id == organization_id,
                    InspectionTemplateVersion.template_id == template.id,
                    InspectionTemplateVersion.status == InspectionTemplateVersionStatus.PUBLISHED,
                )
            )
        ).all()
    )
    for prior in prior_versions:
        prior.status = InspectionTemplateVersionStatus.RETIRED
    now = datetime.now(UTC)
    version.status = InspectionTemplateVersionStatus.PUBLISHED
    version.published_at = now
    version.effective_from = now
    version.revision += 1
    template.current_version = version.version
    template.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="safety.inspection_template.version.published",
        target_type="inspection_template",
        target_id=str(template.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        changes={"published_version": version.version},
    )
    return version


async def create_inspection_run(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    values: Mapping[str, object],
    session_id: UUID | None = None,
) -> InspectionRun:
    await _require_project_member(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    template_version_id = values["template_version_id"]
    if not isinstance(template_version_id, UUID):
        raise SafetyValidationError("template_version_id is required")
    template_version = await db.scalar(
        select(InspectionTemplateVersion).where(
            InspectionTemplateVersion.id == template_version_id,
            InspectionTemplateVersion.organization_id == organization_id,
            InspectionTemplateVersion.status == InspectionTemplateVersionStatus.PUBLISHED,
        )
    )
    if template_version is None:
        raise SafetyValidationError("Published inspection template version was not found")
    number = await _allocate_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        counter="inspection",
    )
    run = InspectionRun(
        organization_id=organization_id,
        project_id=project_id,
        number=number,
        inspector_membership_id=membership_id,
        status=InspectionRunStatus.IN_PROGRESS,
        started_at=datetime.now(UTC),
        **dict(values),
    )
    db.add(run)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="safety.inspection.created",
        target_type="inspection_run",
        target_id=str(run.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"number": number, "template_version_id": template_version_id},
    )
    await _publish_project_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        entity_type="inspection_run",
        entity_id=run.id,
        entity_version=run.revision,
        event_type="safety.inspection.created",
        permission_key="safety.inspection.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"number": number, "status": run.status.value},
    )
    return run


async def replace_inspection_results(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    run_id: UUID,
    expected_revision: int,
    results: list[Mapping[str, object]],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> InspectionRun:
    run = await db.scalar(
        select(InspectionRun)
        .where(
            InspectionRun.id == run_id,
            InspectionRun.organization_id == organization_id,
            InspectionRun.project_id == project_id,
        )
        .with_for_update()
    )
    if run is None:
        raise SafetyValidationError("Inspection run was not found")
    if run.revision != expected_revision:
        raise SafetyConflictError("Inspection changed; refresh before saving")
    if run.status not in {InspectionRunStatus.DRAFT, InspectionRunStatus.IN_PROGRESS, InspectionRunStatus.REJECTED}:
        raise SafetyValidationError("Inspection results can only be edited before approval")
    template_version = await db.scalar(
        select(InspectionTemplateVersion).where(
            InspectionTemplateVersion.id == run.template_version_id,
            InspectionTemplateVersion.organization_id == organization_id,
        )
    )
    if template_version is None:
        raise SafetyValidationError("Pinned inspection template version was not found")
    allowed_keys = {str(item.get("key")) for item in template_version.checklist}
    supplied_keys = {str(item.get("item_key")) for item in results}
    unknown = sorted(supplied_keys - allowed_keys)
    if unknown:
        raise SafetyValidationError("Inspection contains unknown item keys: " + ", ".join(unknown))

    await db.execute(
        delete(InspectionResult).where(
            InspectionResult.organization_id == organization_id,
            InspectionResult.inspection_run_id == run.id,
        )
    )
    for raw in results:
        db.add(
            InspectionResult(
                organization_id=organization_id,
                inspection_run_id=run.id,
                **dict(raw),
            )
        )
    run.status = InspectionRunStatus.IN_PROGRESS
    run.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="safety.inspection.results.updated",
        target_type="inspection_run",
        target_id=str(run.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"result_count": len(results), "revision": run.revision},
    )
    await _publish_project_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        entity_type="inspection_run",
        entity_id=run.id,
        entity_version=run.revision,
        event_type="safety.inspection.updated",
        permission_key="safety.inspection.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": run.revision, "status": run.status.value},
    )
    return run


async def submit_inspection(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    run_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> InspectionRun:
    run = await db.scalar(
        select(InspectionRun)
        .where(
            InspectionRun.id == run_id,
            InspectionRun.organization_id == organization_id,
            InspectionRun.project_id == project_id,
        )
        .with_for_update()
    )
    if run is None:
        raise SafetyValidationError("Inspection run was not found")
    if run.revision != expected_revision:
        raise SafetyConflictError("Inspection changed; refresh before submitting")
    if run.status not in {InspectionRunStatus.IN_PROGRESS, InspectionRunStatus.REJECTED}:
        raise SafetyValidationError("Only active or rejected inspections can be submitted")
    template_version = await db.scalar(
        select(InspectionTemplateVersion).where(
            InspectionTemplateVersion.id == run.template_version_id,
            InspectionTemplateVersion.organization_id == organization_id,
        )
    )
    if template_version is None:
        raise SafetyValidationError("Pinned inspection template version was not found")
    result_rows = list(
        (
            await db.scalars(
                select(InspectionResult).where(
                    InspectionResult.organization_id == organization_id,
                    InspectionResult.inspection_run_id == run.id,
                )
            )
        ).all()
    )
    by_key = {result.item_key: result for result in result_rows}
    missing_required = [
        str(item.get("key"))
        for item in template_version.checklist
        if bool(item.get("required", True))
        and (
            str(item.get("key")) not in by_key
            or by_key[str(item.get("key"))].result == InspectionResultStatus.NOT_CHECKED
        )
    ]
    if missing_required:
        raise SafetyValidationError(
            "Complete required inspection items before submitting: " + ", ".join(missing_required)
        )

    config = await resolve_effective_configuration(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        module_key="safety",
        project_id=project_id,
    )
    approval_required = bool(_setting(config, "safety.inspections.approval.required", False))
    run.configuration_context = {
        "configuration_revisions": config.configuration_revisions,
        "project_template_version_id": (
            str(config.project_template_version_id) if config.project_template_version_id else None
        ),
        "approval_required": approval_required,
        "template_version_id": str(run.template_version_id),
    }
    now = datetime.now(UTC)
    run.submitted_at = now
    if approval_required:
        definition_key = str(_setting(config, "safety.inspections.workflow.definition_key", "")).strip()
        if not definition_key:
            raise SafetyValidationError("Inspection approval requires a configured Workflow definition")
        try:
            workflow = await start_workflow_instance(
                db,
                organization_id=organization_id,
                definition_key=definition_key,
                entity_type="inspection_run",
                entity_id=run.id,
                actor_user_id=actor_user_id,
            )
        except WorkflowValidationError as exc:
            raise SafetyValidationError(str(exc)) from exc
        run.workflow_instance_id = workflow.id
        run.status = InspectionRunStatus.IN_REVIEW
    else:
        run.status = InspectionRunStatus.APPROVED
        run.completed_at = now
    run.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="safety.inspection.submitted",
        target_type="inspection_run",
        target_id=str(run.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": run.status.value, "approval_required": approval_required},
    )
    await _publish_project_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        entity_type="inspection_run",
        entity_id=run.id,
        entity_version=run.revision,
        event_type="safety.inspection.submitted",
        permission_key="safety.inspection.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": run.revision, "status": run.status.value},
    )
    return run


async def review_inspection(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    run_id: UUID,
    expected_revision: int,
    approve: bool,
    permission_keys: set[str],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> InspectionRun:
    run = await db.scalar(
        select(InspectionRun)
        .where(
            InspectionRun.id == run_id,
            InspectionRun.organization_id == organization_id,
            InspectionRun.project_id == project_id,
        )
        .with_for_update()
    )
    if run is None:
        raise SafetyValidationError("Inspection run was not found")
    if run.revision != expected_revision:
        raise SafetyConflictError("Inspection changed; refresh before reviewing")
    if run.status != InspectionRunStatus.IN_REVIEW or run.workflow_instance_id is None:
        raise SafetyValidationError("Inspection is not awaiting Workflow review")
    config = await resolve_effective_configuration(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        module_key="safety",
        project_id=project_id,
    )
    key_name = (
        "safety.inspections.workflow.approve_transition_key"
        if approve
        else "safety.inspections.workflow.reject_transition_key"
    )
    transition_key = str(_setting(config, key_name, "")).strip()
    if not transition_key:
        raise SafetyValidationError("Inspection Workflow transition is not configured")
    from app.modules.workflows.models import WorkflowInstance

    workflow = await db.scalar(
        select(WorkflowInstance).where(
            WorkflowInstance.id == run.workflow_instance_id,
            WorkflowInstance.organization_id == organization_id,
        )
    )
    if workflow is None:
        raise SafetyValidationError("Inspection Workflow instance was not found")
    try:
        await execute_transition(
            db,
            workflow_instance_id=workflow.id,
            organization_id=organization_id,
            transition_key=transition_key,
            expected_instance_version=workflow.version,
            permission_keys=permission_keys,
            actor_user_id=actor_user_id,
            reason=reason,
            session_id=session_id,
            event_context={"project_id": str(project_id), "inspection_run_id": str(run.id)},
        )
    except (WorkflowValidationError, WorkflowConflictError, WorkflowPermissionError) as exc:
        raise SafetyValidationError(str(exc)) from exc
    now = datetime.now(UTC)
    if approve:
        run.status = InspectionRunStatus.APPROVED
        run.completed_at = now
    else:
        run.status = InspectionRunStatus.REJECTED
        run.completed_at = None
    run.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="safety.inspection.approved" if approve else "safety.inspection.rejected",
        target_type="inspection_run",
        target_id=str(run.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={"status": run.status.value, "revision": run.revision},
    )
    await _publish_project_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        entity_type="inspection_run",
        entity_id=run.id,
        entity_version=run.revision,
        event_type="safety.inspection.reviewed",
        permission_key="safety.inspection.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": run.revision, "status": run.status.value},
    )
    return run


async def create_punch_item(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    membership_id: UUID,
    actor_user_id: UUID,
    values: Mapping[str, object],
    session_id: UUID | None = None,
) -> PunchItem:
    await _require_project_member(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
    )
    config = await resolve_effective_configuration(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        module_key="safety",
        project_id=project_id,
    )
    data = dict(values)
    assignee = data.get("assigned_to_membership_id")
    if isinstance(assignee, UUID):
        await _require_project_member(
            db,
            organization_id=organization_id,
            project_id=project_id,
            membership_id=assignee,
        )
    if bool(_setting(config, "safety.punch.require_assignee", False)) and assignee is None:
        raise SafetyValidationError("Punch item assignee is required by project configuration")
    if data.get("due_date") is None:
        default_days = int(_setting(config, "safety.punch.default_due_days", 7))
        data["due_date"] = date.today() + timedelta(days=default_days)
    number = await _allocate_number(
        db,
        organization_id=organization_id,
        project_id=project_id,
        counter="punch",
    )
    item = PunchItem(
        organization_id=organization_id,
        project_id=project_id,
        number=number,
        configuration_context={"configuration_revisions": config.configuration_revisions},
        **data,
    )
    db.add(item)
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="safety.punch.created",
        target_type="punch_item",
        target_id=str(item.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        changes={"number": number, "priority": item.priority.value},
    )
    await _publish_project_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        entity_type="punch_item",
        entity_id=item.id,
        entity_version=item.revision,
        event_type="safety.punch.created",
        permission_key="safety.punch.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"number": number, "priority": item.priority.value},
    )
    return item


async def update_punch_item(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    item_id: UUID,
    expected_revision: int,
    changes: Mapping[str, object],
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> PunchItem:
    item = await db.scalar(
        select(PunchItem)
        .where(
            PunchItem.id == item_id,
            PunchItem.organization_id == organization_id,
            PunchItem.project_id == project_id,
        )
        .with_for_update()
    )
    if item is None:
        raise SafetyValidationError("Punch item was not found")
    if item.revision != expected_revision:
        raise SafetyConflictError("Punch item changed; refresh before saving")
    if item.status in {PunchItemStatus.CLOSED, PunchItemStatus.VOID}:
        raise SafetyValidationError("Closed or void punch items cannot be edited")
    assignee = changes.get("assigned_to_membership_id")
    if isinstance(assignee, UUID):
        await _require_project_member(
            db,
            organization_id=organization_id,
            project_id=project_id,
            membership_id=assignee,
        )
    mutable = {"title", "description", "location", "priority", "assigned_to_membership_id", "due_date", "status"}
    for key, value in changes.items():
        if key in mutable:
            setattr(item, key, value)
    item.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="safety.punch.updated",
        target_type="punch_item",
        target_id=str(item.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"status": item.status.value, "revision": item.revision},
    )
    await _publish_project_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        entity_type="punch_item",
        entity_id=item.id,
        entity_version=item.revision,
        event_type="safety.punch.updated",
        permission_key="safety.punch.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": item.revision, "status": item.status.value},
    )
    return item


async def close_punch_item(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    item_id: UUID,
    expected_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> PunchItem:
    item = await db.scalar(
        select(PunchItem)
        .where(
            PunchItem.id == item_id,
            PunchItem.organization_id == organization_id,
            PunchItem.project_id == project_id,
        )
        .with_for_update()
    )
    if item is None:
        raise SafetyValidationError("Punch item was not found")
    if item.revision != expected_revision:
        raise SafetyConflictError("Punch item changed; refresh before closing")
    if item.status == PunchItemStatus.CLOSED:
        return item
    if item.status == PunchItemStatus.VOID:
        raise SafetyValidationError("Void punch items cannot be closed")
    item.status = PunchItemStatus.CLOSED
    item.completed_at = datetime.now(UTC)
    item.revision += 1
    await db.flush()
    await record_audit_event(
        db,
        organization_id=organization_id,
        action="safety.punch.closed",
        target_type="punch_item",
        target_id=str(item.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.MEDIUM,
        reason=reason,
        changes={"status": item.status.value, "revision": item.revision},
    )
    await _publish_project_change(
        db,
        organization_id=organization_id,
        project_id=project_id,
        entity_type="punch_item",
        entity_id=item.id,
        entity_version=item.revision,
        event_type="safety.punch.closed",
        permission_key="safety.punch.view",
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={"revision": item.revision, "status": item.status.value},
    )
    return item
