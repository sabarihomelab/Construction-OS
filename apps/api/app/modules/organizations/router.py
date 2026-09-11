from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.organizations.schemas import (
    CompanyProfileRead,
    OrganizationProfileUpdate,
    OrganizationRead,
    OrganizationSettingsRead,
    OrganizationSettingsUpdate,
)
from app.modules.organizations.service import (
    OrganizationConflictError,
    OrganizationValidationError,
    get_company_profile,
    update_company_profile,
    update_company_settings,
)
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(prefix="/organization", tags=["organization"])


def _require_permission(context, permission_key: str) -> None:
    if permission_key not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, OrganizationConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("", response_model=CompanyProfileRead)
async def get_current_company(db: DbSession, session: CurrentSession) -> CompanyProfileRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "admin.settings.view")
    try:
        organization, settings = await get_company_profile(
            db,
            organization_id=context.organization_id,
        )
    except OrganizationValidationError as exc:
        _domain_error(exc)
    return CompanyProfileRead(
        organization=OrganizationRead.model_validate(organization),
        settings=OrganizationSettingsRead.model_validate(settings),
    )


@router.patch("", response_model=OrganizationRead)
async def update_current_company(
    payload: OrganizationProfileUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> OrganizationRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "admin.configuration.manage")
    try:
        organization = await update_company_profile(
            db,
            organization_id=context.organization_id,
            expected_updated_at=payload.expected_updated_at,
            changes=payload.model_dump(exclude={"expected_updated_at"}, exclude_unset=True),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(organization)
        return OrganizationRead.model_validate(organization)
    except (OrganizationConflictError, OrganizationValidationError) as exc:
        await db.rollback()
        _domain_error(exc)


@router.patch("/settings", response_model=OrganizationSettingsRead)
async def update_current_company_settings(
    payload: OrganizationSettingsUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> OrganizationSettingsRead:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, "admin.configuration.manage")
    try:
        settings = await update_company_settings(
            db,
            organization_id=context.organization_id,
            expected_settings_version=payload.expected_settings_version,
            changes=payload.model_dump(
                exclude={"expected_settings_version"},
                exclude_unset=True,
            ),
            actor_user_id=session.user_id,
            session_id=session.id,
        )
        await db.commit()
        await db.refresh(settings)
        return OrganizationSettingsRead.model_validate(settings)
    except (OrganizationConflictError, OrganizationValidationError) as exc:
        await db.rollback()
        _domain_error(exc)
