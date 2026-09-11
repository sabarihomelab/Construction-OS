from enum import StrEnum
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core.config import get_settings
from app.core.deps import DbSession
from app.modules.sessions.models import Session
from app.modules.sessions.service import (
    SessionValidationError,
    load_active_session,
    validate_csrf_token,
)


class SessionTransport(StrEnum):
    COOKIE = "cookie"
    BEARER = "bearer"


def _authentication_error(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _session_token_from_request(request: Request) -> tuple[str, SessionTransport]:
    authorization = request.headers.get("Authorization")
    if authorization is not None:
        scheme, separator, credentials = authorization.partition(" ")
        if (
            separator != " "
            or scheme.lower() != "bearer"
            or not credentials.strip()
            or " " in credentials.strip()
        ):
            raise _authentication_error("Invalid bearer authorization")
        return credentials.strip(), SessionTransport.BEARER

    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise _authentication_error()
    return raw_token, SessionTransport.COOKIE


async def get_current_session(request: Request, db: DbSession) -> Session:
    raw_token, transport = _session_token_from_request(request)
    try:
        session = await load_active_session(db, raw_token)
    except SessionValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired",
        ) from exc

    request.state.session_transport = transport
    return session


CurrentSession = Annotated[Session, Depends(get_current_session)]


async def require_csrf(request: Request, session: CurrentSession) -> None:
    if getattr(request.state, "session_transport", SessionTransport.COOKIE) == SessionTransport.BEARER:
        return

    csrf_token = request.headers.get("X-CSRF-Token")
    if not csrf_token or not validate_csrf_token(session, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


CsrfProtected = Annotated[None, Depends(require_csrf)]
