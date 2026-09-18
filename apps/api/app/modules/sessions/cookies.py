from fastapi import Response

from app.core.config import get_settings
from app.modules.sessions.service import IssuedSession


def set_session_cookies(response: Response, issued: IssuedSession) -> None:
    settings = get_settings()
    common = {
        "secure": settings.session_cookie_secure,
        "samesite": settings.session_cookie_samesite,
        "path": "/",
        "max_age": settings.session_absolute_timeout_seconds,
    }
    response.set_cookie(
        key=settings.session_cookie_name,
        value=issued.token,
        httponly=True,
        **common,
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=issued.csrf_token,
        httponly=False,
        **common,
    )


def clear_session_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
    )
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
    )
