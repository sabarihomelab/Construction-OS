from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core.config import get_settings
from app.core.deps import DbSession
from app.modules.sessions.models import Session
from app.modules.sessions.service import SessionValidationError, load_active_session, validate_csrf_token


async def get_current_session(request: Request, db: DbSession) -> Session:
    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    try:
        return await load_active_session(db, raw_token)
    except SessionValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired",
        ) from exc


CurrentSession = Annotated[Session, Depends(get_current_session)]


async def require_csrf(request: Request, session: CurrentSession) -> None:
    csrf_token = request.headers.get("X-CSRF-Token")
    if not csrf_token or not validate_csrf_token(session, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


CsrfProtected = Annotated[None, Depends(require_csrf)]
