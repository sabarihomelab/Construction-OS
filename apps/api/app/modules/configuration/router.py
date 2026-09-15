from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.modules.configuration.models import ConfigurationScopeType
from app.modules.configuration.registry import definitions_for_module
from app.modules.configuration.schemas import (
    ConfigurationDefinitionRead,
    ConfigurationOverrideRead,
    ConfigurationOverrideWrite,
    EffectiveConfigurationRead,
    MembershipPreferenceRead,
    MembershipPreferenceWrite,
    ProjectTemplateAssignmentWrite,
)
from app.modules.configuration.service import (
    ConfigurationConflictError,
    ConfigurationValidationError,
    assign_project_configuration_template,
    resolve_effective_configuration,
    set_configuration_override,
    set_membership_preference,
)
from app.modules.features.registry import FEATURES_BY_KEY, FeatureReleaseState
from app.modules.features.schemas import AccessContext
from app.modules.features.service import build_access_context
from app.modules.projects.access import effective_project_permissions
from app.modules.projects.schemas import ProjectRead
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(prefix="/configuration", tags=["configuration"])


def _require_organization_permission(context: AccessContext, permission_key: str) -> None:
    if permission_key not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _require_project_access(context: AccessContext, project_id: UUID) -> None:
    permissions = effective_project_permissions(
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions={key: set(value) for key, value in context.project_permissions.items()},
    )
    if "projects.project.view" not in permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project access denied")


def _require_module_access(
    context: AccessContext,
    module_key: str,
    *,
    project_id: UUID | None = None,
) -> None:
    if "admin.configuration.view" in context.permissions:
        return
    if module_key == "core":
        return
    feature = FEATURES_BY_KEY.get(module_key)
    if feature is None or feature.release_state not in {
        FeatureReleaseState.AVAILABLE,
        FeatureReleaseState.PREVIEW,
    }:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not available")
    permissions = set(context.permissions)
    if project_id is not None:
        permissions = effective_project_permissions(
            project_id=project_id,
            organization_permissions=permissions,
            project_permissions={key: set(value) for key, value in context.project_permissions.items()},
        )
    if not set(feature.required_permissions).issubset(permissions):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Module access denied")


def _handle_configuration_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ConfigurationConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get(
    "/modules/{module_key}/definitions",
    response_model=list[ConfigurationDefinitionRead],
)
async def list_configuration_definitions(
    module_key: str,
    db: DbSession,
    session: CurrentSession,
) -> list[ConfigurationDefinitionRead]:
    context = await build_access_context(db, session.membership_id)
    _require_organization_permission(context, "admin.configuration.view")
    definitions = definitions_for_module(module_key)
    if not definitions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown module")
    return [
        ConfigurationDefinitionRead(
            key=definition.key,
            module_key=definition.module_key,
            value_type=definition.value_type,
            default=definition.default,
            change_class=definition.change_class,
            mutability=definition.mutability,
            allowed_scopes=list(definition.allowed_scopes),
            allowed_values=list(definition.allowed_values),
            sensitive=definition.sensitive,
            description=definition.description,
        )
        for definition in definitions
    ]


@router.get("/modules/{module_key}", response_model=EffectiveConfigurationRead)
async def get_company_effective_configuration(
    module_key: str,
    db: DbSession,
    session: CurrentSession,
) -> EffectiveConfigurationRead:
    context = await build_access_context(db, session.membership_id)
    _require_module_access(context, module_key)
    try:
        return await resolve_effective_configuration(
            db,
            organization_id=context.organization_id,
            membership_id=context.membership_id,
            module_key=module_key,
        )
    except ConfigurationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/projects/{project_id}/modules/{module_key}",
    response_model=EffectiveConfigurationRead,
)
async def get_project_effective_configuration(
    project_id: UUID,
    module_key: str,
    db: DbSession,
    session: CurrentSession,
) -> EffectiveConfigurationRead:
    context = await build_access_context(db, session.membership_id)
    _require_project_access(context, project_id)
    _require_module_access(context, module_key, project_id=project_id)
    try:
        return await resolve_effective_configuration(
            db,
            organization_id=context.organization_id,
            membership_id=context.membership_id,
            module_key=module_key,
            project_id=project_id,
        )
    except ConfigurationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put(
    "/modules/{module_key}/{configuration_key:path}",
    response_model=ConfigurationOverrideRead,
)
async def set_company_configuration(
    module_key: str,
    configuration_key: str,
    payload: ConfigurationOverrideWrite,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ConfigurationOverrideRead:
    context = await build_access_context(db, session.membership_id)
    _require_organization_permission(context, "admin.configuration.manage")
    try:
        version = await set_configuration_override(
            db,
            organization_id=context.organization_id,
            module_key=module_key,
            configuration_key=configuration_key,
            scope_type=ConfigurationScopeType.COMPANY,
            scope_id=context.organization_id,
            value=payload.value,
            inherit=payload.inherit,
            expected_version=payload.expected_version,
            effective_from=payload.effective_from,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        return ConfigurationOverrideRead(
            configuration_key=configuration_key,
            module_key=module_key,
            scope_type=ConfigurationScopeType.COMPANY,
            scope_id=context.organization_id,
            version=version.version,
            enabled=version.enabled,
            value=version.value,
            effective_from=version.effective_from,
        )
    except (ConfigurationConflictError, ConfigurationValidationError) as exc:
        await db.rollback()
        raise _handle_configuration_error(exc) from exc


@router.put(
    "/projects/{project_id}/modules/{module_key}/{configuration_key:path}",
    response_model=ConfigurationOverrideRead,
)
async def set_project_configuration(
    project_id: UUID,
    module_key: str,
    configuration_key: str,
    payload: ConfigurationOverrideWrite,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ConfigurationOverrideRead:
    context = await build_access_context(db, session.membership_id)
    _require_organization_permission(context, "admin.configuration.manage")
    _require_project_access(context, project_id)
    try:
        version = await set_configuration_override(
            db,
            organization_id=context.organization_id,
            module_key=module_key,
            configuration_key=configuration_key,
            scope_type=ConfigurationScopeType.PROJECT,
            scope_id=project_id,
            value=payload.value,
            inherit=payload.inherit,
            expected_version=payload.expected_version,
            effective_from=payload.effective_from,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        return ConfigurationOverrideRead(
            configuration_key=configuration_key,
            module_key=module_key,
            scope_type=ConfigurationScopeType.PROJECT,
            scope_id=project_id,
            version=version.version,
            enabled=version.enabled,
            value=version.value,
            effective_from=version.effective_from,
        )
    except (ConfigurationConflictError, ConfigurationValidationError) as exc:
        await db.rollback()
        raise _handle_configuration_error(exc) from exc


@router.put(
    "/project-templates/{template_version_id}/modules/{module_key}/{configuration_key:path}",
    response_model=ConfigurationOverrideRead,
)
async def set_project_template_configuration(
    template_version_id: UUID,
    module_key: str,
    configuration_key: str,
    payload: ConfigurationOverrideWrite,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ConfigurationOverrideRead:
    context = await build_access_context(db, session.membership_id)
    _require_organization_permission(context, "admin.configuration.manage")
    try:
        version = await set_configuration_override(
            db,
            organization_id=context.organization_id,
            module_key=module_key,
            configuration_key=configuration_key,
            scope_type=ConfigurationScopeType.PROJECT_TEMPLATE,
            scope_id=template_version_id,
            value=payload.value,
            inherit=payload.inherit,
            expected_version=payload.expected_version,
            effective_from=payload.effective_from,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        return ConfigurationOverrideRead(
            configuration_key=configuration_key,
            module_key=module_key,
            scope_type=ConfigurationScopeType.PROJECT_TEMPLATE,
            scope_id=template_version_id,
            version=version.version,
            enabled=version.enabled,
            value=version.value,
            effective_from=version.effective_from,
        )
    except (ConfigurationConflictError, ConfigurationValidationError) as exc:
        await db.rollback()
        raise _handle_configuration_error(exc) from exc


@router.put(
    "/preferences/{module_key}/{preference_key:path}",
    response_model=MembershipPreferenceRead,
)
async def set_current_membership_preference(
    module_key: str,
    preference_key: str,
    payload: MembershipPreferenceWrite,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> MembershipPreferenceRead:
    context = await build_access_context(db, session.membership_id)
    if payload.project_id is not None:
        _require_project_access(context, payload.project_id)
    try:
        preference = await set_membership_preference(
            db,
            organization_id=context.organization_id,
            membership_id=context.membership_id,
            module_key=module_key,
            preference_key=preference_key,
            context_type=payload.context_type,
            project_id=payload.project_id,
            value=payload.value,
            expected_version=payload.expected_version,
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        return MembershipPreferenceRead(
            preference_key=preference.preference_key,
            module_key=preference.module_key,
            context_type=preference.context_type,
            context_id=preference.context_id,
            project_id=preference.project_id,
            version=preference.version,
            value=preference.value,
        )
    except (ConfigurationConflictError, ConfigurationValidationError) as exc:
        await db.rollback()
        raise _handle_configuration_error(exc) from exc


@router.put(
    "/projects/{project_id}/template",
    response_model=ProjectRead,
)
async def set_project_template(
    project_id: UUID,
    payload: ProjectTemplateAssignmentWrite,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
):
    context = await build_access_context(db, session.membership_id)
    _require_organization_permission(context, "admin.configuration.manage")
    _require_project_access(context, project_id)
    try:
        project = await assign_project_configuration_template(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            template_version_id=payload.template_version_id,
            expected_project_revision=payload.expected_project_revision,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(project)
        return project
    except (ConfigurationConflictError, ConfigurationValidationError) as exc:
        await db.rollback()
        raise _handle_configuration_error(exc) from exc
