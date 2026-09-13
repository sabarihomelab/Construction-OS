from fastapi import APIRouter, HTTPException, Response, status

from app.core.deps import DbSession
from app.modules.authentication.native_service import (
    PendingMembershipSelection,
    begin_native_authentication,
    complete_native_membership_selection,
)
from app.modules.authentication.providers import AUTHENTICATION_PROVIDERS
from app.modules.authentication.web_schemas import (
    WebAuthenticationRequest,
    WebMembershipOption,
    WebMembershipSelectionRequest,
    WebMembershipSelectionResponse,
    WebProviderListResponse,
    WebSessionResponse,
)
from app.modules.sessions.cookies import set_session_cookies
from app.modules.sessions.service import IssuedSession

router = APIRouter(prefix="/auth/web", tags=["authentication"])


def _session_response(issued: IssuedSession) -> WebSessionResponse:
    return WebSessionResponse(membership_id=issued.session.membership_id)


def _selection_response(
    pending: PendingMembershipSelection,
) -> WebMembershipSelectionResponse:
    return WebMembershipSelectionResponse(
        grant_token=pending.grant_token,
        memberships=[
            WebMembershipOption(
                membership_id=item.membership_id,
                organization_id=item.organization_id,
                organization_name=item.organization_name,
            )
            for item in pending.memberships
        ],
    )


@router.get("/providers", response_model=WebProviderListResponse)
async def list_web_authentication_providers() -> WebProviderListResponse:
    return WebProviderListResponse(providers=list(AUTHENTICATION_PROVIDERS.keys()))


@router.post(
    "/authenticate",
    response_model=WebSessionResponse | WebMembershipSelectionResponse,
)
async def authenticate_web_client(
    payload: WebAuthenticationRequest,
    response: Response,
    db: DbSession,
) -> WebSessionResponse | WebMembershipSelectionResponse:
    try:
        provider = AUTHENTICATION_PROVIDERS.get(payload.provider_key)
        assertion = await provider.authenticate(payload.payload)
        if assertion.provider_key != provider.provider_key:
            raise ValueError("Authentication provider returned an invalid assertion")
        result = await begin_native_authentication(
            db,
            assertion,
            allow_verified_email_lookup=bool(
                getattr(provider, "allow_verified_email_lookup", False)
            ),
        )
        await db.commit()
    except (TypeError, ValueError) as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        ) from exc

    if isinstance(result, IssuedSession):
        set_session_cookies(response, result)
        return _session_response(result)
    return _selection_response(result)


@router.post("/select-membership", response_model=WebSessionResponse)
async def select_web_membership(
    payload: WebMembershipSelectionRequest,
    response: Response,
    db: DbSession,
) -> WebSessionResponse:
    try:
        issued = await complete_native_membership_selection(
            db,
            raw_grant_token=payload.grant_token,
            membership_id=payload.membership_id,
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication grant is invalid or expired",
        ) from exc

    set_session_cookies(response, issued)
    return _session_response(issued)
