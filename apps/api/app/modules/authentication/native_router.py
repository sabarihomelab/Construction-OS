from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.modules.authentication.native_schemas import (
    NativeAuthenticationRequest,
    NativeMembershipOption,
    NativeMembershipSelectionRequest,
    NativeMembershipSelectionResponse,
    NativeProviderListResponse,
    NativeSessionResponse,
)
from app.modules.authentication.native_service import (
    NativeAuthenticationError,
    PendingMembershipSelection,
    begin_native_authentication,
    complete_native_membership_selection,
)
from app.modules.authentication.providers import AUTHENTICATION_PROVIDERS
from app.modules.sessions.service import IssuedSession

router = APIRouter(prefix="/auth/native", tags=["authentication"])


def _session_response(issued: IssuedSession) -> NativeSessionResponse:
    return NativeSessionResponse(
        access_token=issued.token,
        membership_id=issued.session.membership_id,
    )


def _selection_response(
    pending: PendingMembershipSelection,
) -> NativeMembershipSelectionResponse:
    return NativeMembershipSelectionResponse(
        grant_token=pending.grant_token,
        memberships=[
            NativeMembershipOption(
                membership_id=item.membership_id,
                organization_id=item.organization_id,
                organization_name=item.organization_name,
            )
            for item in pending.memberships
        ],
    )


@router.get("/providers", response_model=NativeProviderListResponse)
async def list_native_authentication_providers() -> NativeProviderListResponse:
    return NativeProviderListResponse(providers=list(AUTHENTICATION_PROVIDERS.keys()))


@router.post(
    "/authenticate",
    response_model=NativeSessionResponse | NativeMembershipSelectionResponse,
)
async def authenticate_native_client(
    payload: NativeAuthenticationRequest,
    db: DbSession,
) -> NativeSessionResponse | NativeMembershipSelectionResponse:
    try:
        provider = AUTHENTICATION_PROVIDERS.get(payload.provider_key)
        assertion = await provider.authenticate(payload.payload)
        if assertion.provider_key != provider.provider_key:
            raise NativeAuthenticationError("Authentication provider returned an invalid assertion")
        result = await begin_native_authentication(db, assertion)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        ) from exc

    if isinstance(result, IssuedSession):
        return _session_response(result)
    return _selection_response(result)


@router.post("/select-membership", response_model=NativeSessionResponse)
async def select_native_membership(
    payload: NativeMembershipSelectionRequest,
    db: DbSession,
) -> NativeSessionResponse:
    try:
        issued = await complete_native_membership_selection(
            db,
            raw_grant_token=payload.grant_token,
            membership_id=payload.membership_id,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication grant is invalid or expired",
        ) from exc
    return _session_response(issued)
