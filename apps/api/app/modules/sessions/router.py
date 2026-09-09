from fastapi import APIRouter, Response, status

from app.core.deps import DbSession
from app.modules.features.schemas import AccessContext
from app.modules.features.service import build_access_context
from app.modules.sessions.cookies import clear_session_cookies
from app.modules.sessions.deps import CsrfProtected, CurrentSession
from app.modules.sessions.service import revoke_session

router = APIRouter(prefix="/session", tags=["session"])


@router.get("/context", response_model=AccessContext)
async def get_session_context(db: DbSession, session: CurrentSession) -> AccessContext:
    return await build_access_context(db, session.membership_id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> None:
    await revoke_session(db, session, "logout")
    await db.commit()
    clear_session_cookies(response)
