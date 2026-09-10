from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.configuration.models import (
    ConfigurationChangeClass,
    ConfigurationScopeRevision,
    ConfigurationScopeType,
    ConfigurationValue,
    ConfigurationValueVersion,
    MembershipPreference,
    MembershipPreferenceState,
    OrganizationConfigurationState,
    PreferenceContextType,
)
from app.modules.configuration.registry import (
    CONFIGURATION_BY_KEY,
    ConfigurationDefinition,
    ConfigurationMutability,
    definitions_for_module,
    normalize_configuration_value,
)
from app.modules.configuration.schemas import (
    EffectiveConfigurationRead,
    EffectiveLocalizationContext,
    ResolvedConfigurationSetting,
)
from app.modules.events.service import enqueue_event
from app.modules.identity.models import OrganizationMembership, UserPreference
from app.modules.organizations.models import OrganizationSettings
from app.modules.projects.models import Project
from app.modules.setup.models import (
    ConfigurationTemplate,
    ConfigurationTemplateVersion,
    TemplateVersionStatus,
)


class ConfigurationValidationError(ValueError):
    pass


class ConfigurationConflictError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ScopeTarget:
    scope_type: ConfigurationScopeType
    scope_id: UUID


async def _validate_scope_target(
    db: AsyncSession,
    *,
    organization_id: UUID,
    scope_type: ConfigurationScopeType,
    scope_id: UUID,
) -> None:
    if scope_type == ConfigurationScopeType.COMPANY:
        if scope_id != organization_id:
            raise ConfigurationValidationError("Company configuration scope must match the company")
        return

    if scope_type == ConfigurationScopeType.PROJECT:
        project_id = await db.scalar(
            select(Project.id).where(
                Project.id == scope_id,
                Project.organization_id == organization_id,
            )
        )
        if project_id is None:
            raise ConfigurationValidationError("Project configuration scope was not found")
        return

    version = await db.scalar(
        select(ConfigurationTemplateVersion)
        .join(ConfigurationTemplate, ConfigurationTemplate.id == ConfigurationTemplateVersion.template_id)
        .where(
            ConfigurationTemplateVersion.id == scope_id,
            ConfigurationTemplateVersion.organization_id == organization_id,
            ConfigurationTemplate.organization_id == organization_id,
            ConfigurationTemplate.target_type.in_(("project", "project_configuration")),
        )
    )
    if version is None:
        raise ConfigurationValidationError("Project-template configuration scope was not found")


async def _bump_organization_revision(
    db: AsyncSession,
    *,
    organization_id: UUID,
) -> int:
    statement = (
        pg_insert(OrganizationConfigurationState)
        .values(organization_id=organization_id, revision=1)
        .on_conflict_do_update(
            index_elements=["organization_id"],
            set_={
                "revision": OrganizationConfigurationState.revision + 1,
                "updated_at": func.now(),
            },
        )
        .returning(OrganizationConfigurationState.revision)
    )
    revision = await db.scalar(statement)
    if revision is None:
        raise RuntimeError("Organization configuration revision could not be updated")
    return revision


async def _bump_scope_revision(
    db: AsyncSession,
    *,
    organization_id: UUID,
    module_key: str,
    scope_type: ConfigurationScopeType,
    scope_id: UUID,
) -> int:
    statement = (
        pg_insert(ConfigurationScopeRevision)
        .values(
            organization_id=organization_id,
            module_key=module_key,
            scope_type=scope_type,
            scope_id=scope_id,
            revision=1,
        )
        .on_conflict_do_update(
            index_elements=["organization_id", "module_key", "scope_type", "scope_id"],
            set_={
                "revision": ConfigurationScopeRevision.revision + 1,
                "updated_at": func.now(),
            },
        )
        .returning(ConfigurationScopeRevision.revision)
    )
    revision = await db.scalar(statement)
    if revision is None:
        raise RuntimeError("Configuration revision could not be updated")
    return revision


async def _bump_preference_revision(
    db: AsyncSession,
    *,
    organization_id: UUID,
    membership_id: UUID,
) -> int:
    statement = (
        pg_insert(MembershipPreferenceState)
        .values(
            organization_id=organization_id,
            membership_id=membership_id,
            revision=1,
        )
        .on_conflict_do_update(
            index_elements=["membership_id"],
            set_={
                "revision": MembershipPreferenceState.revision + 1,
                "updated_at": func.now(),
            },
        )
        .returning(MembershipPreferenceState.revision)
    )
    revision = await db.scalar(statement)
    if revision is None:
        raise RuntimeError("Preference revision could not be updated")
    return revision


def _definition_for_write(module_key: str, configuration_key: str) -> ConfigurationDefinition:
    definition = CONFIGURATION_BY_KEY.get(configuration_key)
    if definition is None or definition.module_key != module_key:
        raise ConfigurationValidationError("Unknown configuration key for this module")
    return definition


async def set_configuration_override(
    db: AsyncSession,
    *,
    organization_id: UUID,
    module_key: str,
    configuration_key: str,
    scope_type: ConfigurationScopeType,
    scope_id: UUID,
    value: object | None,
    inherit: bool,
    expected_version: int | None,
    effective_from: datetime | None,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> ConfigurationValueVersion:
    definition = _definition_for_write(module_key, configuration_key)
    if definition.mutability != ConfigurationMutability.BUSINESS:
        raise ConfigurationValidationError("This configuration key is not company-configurable")
    if scope_type not in definition.allowed_scopes:
        raise ConfigurationValidationError("This configuration key cannot be overridden at this scope")
    await _validate_scope_target(
        db,
        organization_id=organization_id,
        scope_type=scope_type,
        scope_id=scope_id,
    )

    normalized = None if inherit else normalize_configuration_value(definition, value)
    effective = effective_from or datetime.now(UTC)
    if effective.tzinfo is None or effective.utcoffset() is None:
        raise ConfigurationValidationError("Configuration effective time must include a timezone")

    row = await db.scalar(
        select(ConfigurationValue)
        .where(
            ConfigurationValue.organization_id == organization_id,
            ConfigurationValue.module_key == module_key,
            ConfigurationValue.configuration_key == configuration_key,
            ConfigurationValue.scope_type == scope_type,
            ConfigurationValue.scope_id == scope_id,
        )
        .with_for_update()
    )

    if row is None:
        if expected_version is not None:
            raise ConfigurationConflictError("Configuration does not exist; reload before saving")
        row = ConfigurationValue(
            organization_id=organization_id,
            module_key=module_key,
            configuration_key=configuration_key,
            scope_type=scope_type,
            scope_id=scope_id,
            current_version=1,
        )
        db.add(row)
        await db.flush()
        version_number = 1
    else:
        if expected_version != row.current_version:
            raise ConfigurationConflictError("Configuration changed; reload before saving")
        row.current_version += 1
        version_number = row.current_version

    version = ConfigurationValueVersion(
        organization_id=organization_id,
        configuration_value_id=row.id,
        version=version_number,
        value=normalized,
        enabled=not inherit,
        change_class=definition.change_class,
        effective_from=effective,
        changed_by_user_id=actor_user_id,
        reason=reason,
    )
    db.add(version)
    scope_revision = await _bump_scope_revision(
        db,
        organization_id=organization_id,
        module_key=module_key,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    organization_revision = await _bump_organization_revision(
        db,
        organization_id=organization_id,
    )
    await db.flush()

    changes: dict[str, object] = {
        "configuration_key": configuration_key,
        "scope_type": scope_type.value,
        "scope_id": str(scope_id),
        "version": version_number,
        "effective_from": effective,
        "enabled": not inherit,
        "change_class": definition.change_class.value,
    }
    if not definition.sensitive and not inherit:
        changes["value"] = normalized

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="configuration.override.changed",
        target_type="configuration_value",
        target_id=str(row.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=(
            AuditRisk.CRITICAL
            if definition.change_class in {
                ConfigurationChangeClass.FINANCIAL,
                ConfigurationChangeClass.SECURITY,
            }
            else AuditRisk.MEDIUM
        ),
        reason=reason,
        changes=changes,
    )

    project_scope = scope_type == ConfigurationScopeType.PROJECT
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="configuration.changed",
        entity_type="configuration",
        entity_id=configuration_key,
        entity_version=organization_revision,
        scope_type="project" if project_scope else None,
        scope_id=scope_id if project_scope else None,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={
            "module_key": module_key,
            "configuration_key": configuration_key,
            "scope_type": scope_type.value,
            "scope_id": str(scope_id),
            "configuration_revision": scope_revision,
            "organization_configuration_revision": organization_revision,
        },
    )
    return version


async def set_membership_preference(
    db: AsyncSession,
    *,
    organization_id: UUID,
    membership_id: UUID,
    module_key: str,
    preference_key: str,
    context_type: PreferenceContextType,
    project_id: UUID | None,
    value: object,
    expected_version: int | None,
    actor_user_id: UUID,
    session_id: UUID | None = None,
) -> MembershipPreference:
    definition = _definition_for_write(module_key, preference_key)
    if definition.mutability != ConfigurationMutability.USER_PREFERENCE:
        raise ConfigurationValidationError("This key is not a user preference")
    normalized = normalize_configuration_value(definition, value)

    if context_type == PreferenceContextType.COMPANY:
        if project_id is not None:
            raise ConfigurationValidationError("Company preference cannot include a project")
        context_id = organization_id
    else:
        if project_id is None:
            raise ConfigurationValidationError("Project preference requires a project")
        project_exists = await db.scalar(
            select(Project.id).where(
                Project.id == project_id,
                Project.organization_id == organization_id,
            )
        )
        if project_exists is None:
            raise ConfigurationValidationError("Project was not found")
        context_id = project_id

    row = await db.scalar(
        select(MembershipPreference)
        .where(
            MembershipPreference.organization_id == organization_id,
            MembershipPreference.membership_id == membership_id,
            MembershipPreference.module_key == module_key,
            MembershipPreference.preference_key == preference_key,
            MembershipPreference.context_type == context_type,
            MembershipPreference.context_id == context_id,
        )
        .with_for_update()
    )
    if row is None:
        if expected_version is not None:
            raise ConfigurationConflictError("Preference does not exist; reload before saving")
        row = MembershipPreference(
            organization_id=organization_id,
            membership_id=membership_id,
            module_key=module_key,
            preference_key=preference_key,
            context_type=context_type,
            context_id=context_id,
            project_id=project_id,
            value=normalized,
            version=1,
            updated_by_user_id=actor_user_id,
        )
        db.add(row)
    else:
        if expected_version != row.version:
            raise ConfigurationConflictError("Preference changed; reload before saving")
        row.value = normalized
        row.version += 1
        row.updated_by_user_id = actor_user_id

    preference_revision = await _bump_preference_revision(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
    )
    await db.flush()
    await enqueue_event(
        db,
        organization_id=organization_id,
        recipient_membership_id=membership_id,
        event_type="configuration.preference.changed",
        entity_type="membership_preference",
        entity_id=preference_key,
        entity_version=preference_revision,
        scope_type="project" if project_id is not None else None,
        scope_id=project_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={
            "module_key": module_key,
            "preference_key": preference_key,
            "preference_revision": preference_revision,
        },
    )
    return row


async def assign_project_configuration_template(
    db: AsyncSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    template_version_id: UUID | None,
    expected_project_revision: int,
    actor_user_id: UUID,
    session_id: UUID | None = None,
    reason: str | None = None,
) -> Project:
    project = await db.scalar(
        select(Project)
        .where(Project.id == project_id, Project.organization_id == organization_id)
        .with_for_update()
    )
    if project is None:
        raise ConfigurationValidationError("Project was not found")
    if project.revision != expected_project_revision:
        raise ConfigurationConflictError("Project changed; reload before changing its template")

    if template_version_id is not None:
        template = await db.scalar(
            select(ConfigurationTemplateVersion)
            .join(ConfigurationTemplate, ConfigurationTemplate.id == ConfigurationTemplateVersion.template_id)
            .where(
                ConfigurationTemplateVersion.id == template_version_id,
                ConfigurationTemplateVersion.organization_id == organization_id,
                ConfigurationTemplateVersion.status == TemplateVersionStatus.ACTIVE,
                ConfigurationTemplate.organization_id == organization_id,
                ConfigurationTemplate.target_type.in_(("project", "project_configuration")),
            )
        )
        if template is None:
            raise ConfigurationValidationError("Published project configuration template was not found")

    before = project.configuration_template_version_id
    project.configuration_template_version_id = template_version_id
    project.revision += 1

    affected_modules = {
        definition.module_key
        for definition in CONFIGURATION_BY_KEY.values()
        if ConfigurationScopeType.PROJECT_TEMPLATE in definition.allowed_scopes
    }
    revisions: dict[str, int] = {}
    for module_key in sorted(affected_modules):
        revisions[module_key] = await _bump_scope_revision(
            db,
            organization_id=organization_id,
            module_key=module_key,
            scope_type=ConfigurationScopeType.PROJECT,
            scope_id=project_id,
        )
    organization_revision = await _bump_organization_revision(
        db,
        organization_id=organization_id,
    )
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        action="configuration.project_template.changed",
        target_type="project",
        target_id=str(project.id),
        actor_type=AuditActorType.USER,
        actor_user_id=actor_user_id,
        session_id=session_id,
        risk=AuditRisk.HIGH,
        reason=reason,
        changes={
            "before_template_version_id": str(before) if before else None,
            "after_template_version_id": str(template_version_id) if template_version_id else None,
            "project_revision": project.revision,
        },
    )
    await enqueue_event(
        db,
        organization_id=organization_id,
        event_type="configuration.project_template.changed",
        entity_type="project",
        entity_id=project.id,
        entity_version=organization_revision,
        scope_type="project",
        scope_id=project.id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        payload={
            "module_key": "*",
            "configuration_revisions": revisions,
            "organization_configuration_revision": organization_revision,
        },
    )
    return project


async def _load_scope_overrides(
    db: AsyncSession,
    *,
    organization_id: UUID,
    module_key: str,
    target: ScopeTarget,
    as_of: datetime,
) -> dict[str, tuple[ConfigurationValueVersion, ConfigurationValue]]:
    rows = await db.execute(
        select(ConfigurationValueVersion, ConfigurationValue)
        .join(
            ConfigurationValue,
            ConfigurationValue.id == ConfigurationValueVersion.configuration_value_id,
        )
        .where(
            ConfigurationValue.organization_id == organization_id,
            ConfigurationValue.module_key == module_key,
            ConfigurationValue.scope_type == target.scope_type,
            ConfigurationValue.scope_id == target.scope_id,
            ConfigurationValue.active.is_(True),
            ConfigurationValueVersion.effective_from <= as_of,
        )
        .order_by(
            ConfigurationValue.id,
            ConfigurationValueVersion.effective_from.desc(),
            ConfigurationValueVersion.version.desc(),
        )
    )
    resolved: dict[str, tuple[ConfigurationValueVersion, ConfigurationValue]] = {}
    seen_ids: set[UUID] = set()
    for version, value_row in rows.all():
        if value_row.id in seen_ids:
            continue
        seen_ids.add(value_row.id)
        resolved[value_row.configuration_key] = (version, value_row)
    return resolved


async def _load_revisions(
    db: AsyncSession,
    *,
    organization_id: UUID,
    module_key: str,
    targets: Iterable[ScopeTarget],
) -> dict[str, int]:
    result: dict[str, int] = {}
    for target in targets:
        revision = await db.scalar(
            select(ConfigurationScopeRevision.revision).where(
                ConfigurationScopeRevision.organization_id == organization_id,
                ConfigurationScopeRevision.module_key == module_key,
                ConfigurationScopeRevision.scope_type == target.scope_type,
                ConfigurationScopeRevision.scope_id == target.scope_id,
            )
        )
        result[f"{target.scope_type.value}:{target.scope_id}"] = revision or 1
    return result


async def resolve_effective_configuration(
    db: AsyncSession,
    *,
    organization_id: UUID,
    membership_id: UUID,
    module_key: str,
    project_id: UUID | None = None,
    as_of: datetime | None = None,
) -> EffectiveConfigurationRead:
    definitions = definitions_for_module(module_key)
    if not definitions:
        raise ConfigurationValidationError("Unknown configurable module")

    membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.id == membership_id,
            OrganizationMembership.organization_id == organization_id,
        )
    )
    if membership is None:
        raise ConfigurationValidationError("Organization membership was not found")

    project: Project | None = None
    if project_id is not None:
        project = await db.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id,
            )
        )
        if project is None:
            raise ConfigurationValidationError("Project was not found")

    at = as_of or datetime.now(UTC)
    if at.tzinfo is None or at.utcoffset() is None:
        raise ConfigurationValidationError("Configuration resolution time must include a timezone")

    resolved: dict[str, ResolvedConfigurationSetting] = {
        definition.key: ResolvedConfigurationSetting(
            key=definition.key,
            value=definition.default,
            source="platform_default",
            change_class=definition.change_class,
        )
        for definition in definitions
    }

    targets = [ScopeTarget(ConfigurationScopeType.COMPANY, organization_id)]
    if project is not None and project.configuration_template_version_id is not None:
        targets.append(
            ScopeTarget(
                ConfigurationScopeType.PROJECT_TEMPLATE,
                project.configuration_template_version_id,
            )
        )
    if project is not None:
        targets.append(ScopeTarget(ConfigurationScopeType.PROJECT, project.id))

    for target in targets:
        overrides = await _load_scope_overrides(
            db,
            organization_id=organization_id,
            module_key=module_key,
            target=target,
            as_of=at,
        )
        for key, (version, _) in overrides.items():
            definition = CONFIGURATION_BY_KEY.get(key)
            if definition is None or target.scope_type not in definition.allowed_scopes:
                continue
            if not version.enabled:
                continue
            resolved[key] = ResolvedConfigurationSetting(
                key=key,
                value=version.value,
                source=target.scope_type.value,
                change_class=definition.change_class,
                version=version.version,
                effective_from=version.effective_from,
            )

    preference_contexts = [(PreferenceContextType.COMPANY, organization_id)]
    if project is not None:
        preference_contexts.append((PreferenceContextType.PROJECT, project.id))
    for context_type, context_id in preference_contexts:
        preference_rows = await db.scalars(
            select(MembershipPreference).where(
                MembershipPreference.organization_id == organization_id,
                MembershipPreference.membership_id == membership_id,
                MembershipPreference.module_key == module_key,
                MembershipPreference.context_type == context_type,
                MembershipPreference.context_id == context_id,
            )
        )
        for preference in preference_rows.all():
            definition = CONFIGURATION_BY_KEY.get(preference.preference_key)
            if definition is None or definition.mutability != ConfigurationMutability.USER_PREFERENCE:
                continue
            resolved[preference.preference_key] = ResolvedConfigurationSetting(
                key=preference.preference_key,
                value=preference.value,
                source="user_preference",
                change_class=definition.change_class,
                version=preference.version,
            )

    organization_settings = await db.get(OrganizationSettings, organization_id)
    user_preference = await db.get(UserPreference, membership.user_id)
    business_timezone = (
        project.timezone
        if project is not None and project.timezone
        else organization_settings.timezone if organization_settings else "UTC"
    )
    base_currency = organization_settings.base_currency if organization_settings else "USD"
    project_currency = project.currency_code if project is not None else None
    unit_system = (
        project.unit_system
        if project is not None and project.unit_system
        else organization_settings.unit_system.value if organization_settings else "metric"
    )
    locale = (
        user_preference.locale
        if user_preference is not None and user_preference.locale
        else organization_settings.locale if organization_settings else "en-US"
    )
    presentation_timezone = (
        user_preference.timezone
        if user_preference is not None and user_preference.timezone
        else business_timezone
    )
    time_format = (
        user_preference.time_format
        if user_preference is not None and user_preference.time_format
        else organization_settings.time_format.value if organization_settings else "24h"
    )
    first_day_of_week = organization_settings.first_day_of_week if organization_settings else 1

    preference_revision = await db.scalar(
        select(MembershipPreferenceState.revision).where(
            MembershipPreferenceState.membership_id == membership_id,
            MembershipPreferenceState.organization_id == organization_id,
        )
    )

    return EffectiveConfigurationRead(
        organization_id=organization_id,
        membership_id=membership_id,
        project_id=project.id if project is not None else None,
        project_template_version_id=(
            project.configuration_template_version_id if project is not None else None
        ),
        module_key=module_key,
        configuration_revisions=await _load_revisions(
            db,
            organization_id=organization_id,
            module_key=module_key,
            targets=targets,
        ),
        preference_revision=preference_revision or 1,
        localization=EffectiveLocalizationContext(
            business_timezone=business_timezone,
            presentation_timezone=presentation_timezone,
            base_currency=base_currency,
            project_currency=project_currency,
            unit_system=unit_system,
            locale=locale,
            time_format=time_format,
            first_day_of_week=first_day_of_week,
        ),
        settings=sorted(resolved.values(), key=lambda item: item.key),
    )
