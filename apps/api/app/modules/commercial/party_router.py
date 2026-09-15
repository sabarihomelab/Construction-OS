from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.modules.commercial.models import Party, ProjectPartyAssignment
from app.modules.commercial.party_lifecycle import (
    get_party,
    list_project_party_assignments,
    set_project_party_assignment_active,
)
from app.modules.commercial.schemas import (
    PartyRead,
    ProjectPartyAssignmentRead,
    ProjectPartyAssignmentUpdate,
)
from app.modules.commercial.service import CommercialConflictError, CommercialValidationError
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["commercial"])


def _org_permission(context, permission_key: str) -> None:
    if permission_key not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _project_permission(context, project_id: UUID, permission_key: str) -> None:
    scoped = {key: set(values) for key, values in context.project_permissions.items()}
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=scoped,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _domain_error(exc: Exception) -> None:
    if isinstance(exc, CommercialConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/commercial/parties/{party_id}", response_model=PartyRead)
async def get_party_route(
    party_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> Party:
    context = await build_access_context(db, session.membership_id)
    _org_permission(context, "commercial.party.view")
    try:
        return await get_party(
            db,
            organization_id=context.organization_id,
            party_id=party_id,
        )
    except CommercialValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/projects/{project_id}/commercial/party-assignments",
    response_model=list[ProjectPartyAssignmentRead],
)
async def list_project_party_assignments_route(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
    party_id: UUID | None = None,
    include_inactive: bool = False,
) -> list[ProjectPartyAssignment]:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.party.view")
    try:
        return await list_project_party_assignments(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            party_id=party_id,
            include_inactive=include_inactive,
        )
    except CommercialValidationError as exc:
        _domain_error(exc)


@router.patch(
    "/projects/{project_id}/commercial/party-assignments/{assignment_id}",
    response_model=ProjectPartyAssignmentRead,
)
async def update_project_party_assignment_route(
    project_id: UUID,
    assignment_id: UUID,
    payload: ProjectPartyAssignmentUpdate,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ProjectPartyAssignment:
    context = await build_access_context(db, session.membership_id)
    _project_permission(context, project_id, "commercial.party.manage")
    try:
        row = await set_project_party_assignment_active(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            assignment_id=assignment_id,
            expected_updated_at=payload.expected_updated_at,
            active=payload.active,
            actor_user_id=session.user_id,
            session_id=session.id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return row
    except (CommercialConflictError, CommercialValidationError) as exc:
        await db.rollback()
        _domain_error(exc)
