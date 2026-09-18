from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.projects.access import project_permission_is_allowed
from app.modules.sessions.deps import CurrentSession
from app.modules.submittals.models import (
    Submittal,
    SubmittalHistoryEvent,
    SubmittalReference,
    SubmittalReview,
    SubmittalRevision,
)
from app.modules.submittals.schemas import (
    SubmittalBallInCourtUpdate,
    SubmittalCreate,
    SubmittalHistoryRead,
    SubmittalRead,
    SubmittalReferenceCreate,
    SubmittalReferenceRead,
    SubmittalReviewCreate,
    SubmittalReviewRead,
    SubmittalRevisionCreate,
    SubmittalRevisionRead,
    SubmittalRevisionSubmit,
    SubmittalUpdate,
    SubmittalVersionAction,
    SubmittalVoidRequest,
)
from app.modules.submittals.service import (
    SubmittalConflictError,
    SubmittalValidationError,
    add_reference,
    add_review,
    add_revision,
    close_submittal,
    create_submittal,
    open_submittal,
    set_ball_in_court,
    submit_revision,
    update_submittal,
    void_submittal,
)

router = APIRouter(prefix="/projects/{project_id}/submittals", tags=["submittals"])


def _require_project_permission(context, project_id: UUID, permission_key: str) -> None:
    project_permissions = {
        key: set(values) for key, values in context.project_permissions.items()
    }
    if not project_permission_is_allowed(
        permission_key,
        project_id=project_id,
        organization_permissions=set(context.permissions),
        project_permissions=project_permissions,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _raise_domain_error(exc: Exception) -> None:
    if isinstance(exc, SubmittalConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


async def _load_submittal_or_404(
    db: DbSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    submittal_id: UUID,
) -> Submittal:
    submittal = await db.scalar(
        select(Submittal).where(
            Submittal.id == submittal_id,
            Submittal.organization_id == organization_id,
            Submittal.project_id == project_id,
        )
    )
    if submittal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submittal not found")
    return submittal


async def _load_revision_or_404(
    db: DbSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    submittal_id: UUID,
    revision_id: UUID,
) -> SubmittalRevision:
    revision = await db.scalar(
        select(SubmittalRevision)
        .join(Submittal, Submittal.id == SubmittalRevision.submittal_id)
        .where(
            SubmittalRevision.id == revision_id,
            SubmittalRevision.organization_id == organization_id,
            Submittal.id == submittal_id,
            Submittal.organization_id == organization_id,
            Submittal.project_id == project_id,
        )
    )
    if revision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submittal revision not found",
        )
    return revision


@router.get("", response_model=list[SubmittalRead])
async def list_submittals(
    project_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[Submittal]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "submittals.submittal.view")
    rows = await db.scalars(
        select(Submittal)
        .where(
            Submittal.organization_id == context.organization_id,
            Submittal.project_id == project_id,
        )
        .order_by(Submittal.number.desc())
    )
    return list(rows.all())


@router.post("", response_model=SubmittalRead, status_code=status.HTTP_201_CREATED)
async def create_submittal_route(
    project_id: UUID,
    payload: SubmittalCreate,
    db: DbSession,
    session: CurrentSession,
) -> Submittal:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "submittals.submittal.create")
    try:
        submittal = await create_submittal(
            db,
            organization_id=context.organization_id,
            project_id=project_id,
            actor_user_id=session.user_id,
            **payload.model_dump(),
        )
        await db.commit()
        await db.refresh(submittal)
        return submittal
    except (SubmittalValidationError, SubmittalConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get("/{submittal_id}", response_model=SubmittalRead)
async def get_submittal(
    project_id: UUID,
    submittal_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> Submittal:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "submittals.submittal.view")
    return await _load_submittal_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        submittal_id=submittal_id,
    )


@router.patch("/{submittal_id}", response_model=SubmittalRead)
async def patch_submittal(
    project_id: UUID,
    submittal_id: UUID,
    payload: SubmittalUpdate,
    db: DbSession,
    session: CurrentSession,
) -> Submittal:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "submittals.submittal.update")
    await _load_submittal_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        submittal_id=submittal_id,
    )
    try:
        submittal = await update_submittal(
            db,
            organization_id=context.organization_id,
            submittal_id=submittal_id,
            expected_version=payload.expected_version,
            changes=payload.model_dump(exclude={"expected_version"}, exclude_unset=True),
            actor_user_id=session.user_id,
        )
        await db.commit()
        await db.refresh(submittal)
        return submittal
    except (SubmittalValidationError, SubmittalConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post("/{submittal_id}/open", response_model=SubmittalRead)
async def open_submittal_route(
    project_id: UUID,
    submittal_id: UUID,
    payload: SubmittalVersionAction,
    db: DbSession,
    session: CurrentSession,
) -> Submittal:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "submittals.submittal.update")
    await _load_submittal_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        submittal_id=submittal_id,
    )
    try:
        submittal = await open_submittal(
            db,
            organization_id=context.organization_id,
            submittal_id=submittal_id,
            expected_version=payload.expected_version,
            actor_user_id=session.user_id,
        )
        await db.commit()
        await db.refresh(submittal)
        return submittal
    except (SubmittalValidationError, SubmittalConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.put("/{submittal_id}/ball-in-court", response_model=SubmittalRead)
async def update_ball_in_court(
    project_id: UUID,
    submittal_id: UUID,
    payload: SubmittalBallInCourtUpdate,
    db: DbSession,
    session: CurrentSession,
) -> Submittal:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "submittals.submittal.manage")
    await _load_submittal_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        submittal_id=submittal_id,
    )
    try:
        submittal = await set_ball_in_court(
            db,
            organization_id=context.organization_id,
            submittal_id=submittal_id,
            expected_version=payload.expected_version,
            membership_id=payload.membership_id,
            actor_user_id=session.user_id,
        )
        await db.commit()
        await db.refresh(submittal)
        return submittal
    except (SubmittalValidationError, SubmittalConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get("/{submittal_id}/revisions", response_model=list[SubmittalRevisionRead])
async def list_revisions(
    project_id: UUID,
    submittal_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[SubmittalRevision]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "submittals.submittal.view")
    await _load_submittal_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        submittal_id=submittal_id,
    )
    rows = await db.scalars(
        select(SubmittalRevision)
        .where(
            SubmittalRevision.organization_id == context.organization_id,
            SubmittalRevision.submittal_id == submittal_id,
        )
        .order_by(SubmittalRevision.sequence)
    )
    return list(rows.all())


@router.post(
    "/{submittal_id}/revisions",
    response_model=SubmittalRevisionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_revision_route(
    project_id: UUID,
    submittal_id: UUID,
    payload: SubmittalRevisionCreate,
    db: DbSession,
    session: CurrentSession,
) -> SubmittalRevision:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "submittals.submittal.update")
    await _load_submittal_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        submittal_id=submittal_id,
    )
    try:
        revision = await add_revision(
            db,
            organization_id=context.organization_id,
            submittal_id=submittal_id,
            revision_label=payload.revision_label,
            description=payload.description,
            actor_user_id=session.user_id,
        )
        await db.commit()
        await db.refresh(revision)
        return revision
    except (SubmittalValidationError, SubmittalConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post(
    "/{submittal_id}/revisions/{revision_id}/submit",
    response_model=SubmittalRevisionRead,
)
async def submit_revision_route(
    project_id: UUID,
    submittal_id: UUID,
    revision_id: UUID,
    payload: SubmittalRevisionSubmit,
    db: DbSession,
    session: CurrentSession,
) -> SubmittalRevision:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "submittals.submittal.submit")
    await _load_revision_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        submittal_id=submittal_id,
        revision_id=revision_id,
    )
    try:
        revision = await submit_revision(
            db,
            organization_id=context.organization_id,
            revision_id=revision_id,
            reviewer_membership_id=payload.reviewer_membership_id,
            actor_user_id=session.user_id,
        )
        await db.commit()
        await db.refresh(revision)
        return revision
    except (SubmittalValidationError, SubmittalConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get(
    "/{submittal_id}/revisions/{revision_id}/reviews",
    response_model=list[SubmittalReviewRead],
)
async def list_reviews(
    project_id: UUID,
    submittal_id: UUID,
    revision_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[SubmittalReview]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "submittals.submittal.view")
    await _load_revision_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        submittal_id=submittal_id,
        revision_id=revision_id,
    )
    rows = await db.scalars(
        select(SubmittalReview)
        .where(
            SubmittalReview.organization_id == context.organization_id,
            SubmittalReview.submittal_revision_id == revision_id,
        )
        .order_by(SubmittalReview.sequence)
    )
    return list(rows.all())


@router.post(
    "/{submittal_id}/revisions/{revision_id}/reviews",
    response_model=SubmittalReviewRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_review_route(
    project_id: UUID,
    submittal_id: UUID,
    revision_id: UUID,
    payload: SubmittalReviewCreate,
    db: DbSession,
    session: CurrentSession,
) -> SubmittalReview:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "submittals.submittal.review")
    await _load_revision_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        submittal_id=submittal_id,
        revision_id=revision_id,
    )
    try:
        review = await add_review(
            db,
            organization_id=context.organization_id,
            revision_id=revision_id,
            reviewer_membership_id=session.membership_id,
            decision=payload.decision,
            comments=payload.comments,
            official=payload.official,
            actor_user_id=session.user_id,
        )
        await db.commit()
        await db.refresh(review)
        return review
    except (SubmittalValidationError, SubmittalConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get("/{submittal_id}/references", response_model=list[SubmittalReferenceRead])
async def list_references(
    project_id: UUID,
    submittal_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[SubmittalReference]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "submittals.submittal.view")
    await _load_submittal_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        submittal_id=submittal_id,
    )
    rows = await db.scalars(
        select(SubmittalReference)
        .where(
            SubmittalReference.organization_id == context.organization_id,
            SubmittalReference.submittal_id == submittal_id,
        )
        .order_by(SubmittalReference.created_at, SubmittalReference.id)
    )
    return list(rows.all())


@router.post(
    "/{submittal_id}/references",
    response_model=SubmittalReferenceRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_reference_route(
    project_id: UUID,
    submittal_id: UUID,
    payload: SubmittalReferenceCreate,
    db: DbSession,
    session: CurrentSession,
) -> SubmittalReference:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "submittals.submittal.update")
    await _load_submittal_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        submittal_id=submittal_id,
    )
    try:
        reference = await add_reference(
            db,
            organization_id=context.organization_id,
            submittal_id=submittal_id,
            reference_type=payload.reference_type,
            reference_id=payload.reference_id,
            label=payload.label,
            actor_user_id=session.user_id,
        )
        await db.commit()
        await db.refresh(reference)
        return reference
    except (SubmittalValidationError, SubmittalConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.get("/{submittal_id}/history", response_model=list[SubmittalHistoryRead])
async def list_history(
    project_id: UUID,
    submittal_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> list[SubmittalHistoryEvent]:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "submittals.submittal.view")
    await _load_submittal_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        submittal_id=submittal_id,
    )
    rows = await db.scalars(
        select(SubmittalHistoryEvent)
        .where(
            SubmittalHistoryEvent.organization_id == context.organization_id,
            SubmittalHistoryEvent.submittal_id == submittal_id,
        )
        .order_by(SubmittalHistoryEvent.created_at, SubmittalHistoryEvent.id)
    )
    return list(rows.all())


@router.post("/{submittal_id}/close", response_model=SubmittalRead)
async def close_submittal_route(
    project_id: UUID,
    submittal_id: UUID,
    payload: SubmittalVersionAction,
    db: DbSession,
    session: CurrentSession,
) -> Submittal:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "submittals.submittal.close")
    await _load_submittal_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        submittal_id=submittal_id,
    )
    try:
        submittal = await close_submittal(
            db,
            organization_id=context.organization_id,
            submittal_id=submittal_id,
            expected_version=payload.expected_version,
            actor_user_id=session.user_id,
        )
        await db.commit()
        await db.refresh(submittal)
        return submittal
    except (SubmittalValidationError, SubmittalConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)


@router.post("/{submittal_id}/void", response_model=SubmittalRead)
async def void_submittal_route(
    project_id: UUID,
    submittal_id: UUID,
    payload: SubmittalVoidRequest,
    db: DbSession,
    session: CurrentSession,
) -> Submittal:
    context = await build_access_context(db, session.membership_id)
    _require_project_permission(context, project_id, "submittals.submittal.manage")
    await _load_submittal_or_404(
        db,
        organization_id=context.organization_id,
        project_id=project_id,
        submittal_id=submittal_id,
    )
    try:
        submittal = await void_submittal(
            db,
            organization_id=context.organization_id,
            submittal_id=submittal_id,
            expected_version=payload.expected_version,
            actor_user_id=session.user_id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(submittal)
        return submittal
    except (SubmittalValidationError, SubmittalConflictError) as exc:
        await db.rollback()
        _raise_domain_error(exc)
