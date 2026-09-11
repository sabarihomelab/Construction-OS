from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.modules.features.schemas import AccessContext
from app.modules.sessions.router import router as session_router


def test_bearer_session_can_load_existing_session_context(monkeypatch) -> None:
    membership_id = uuid4()
    organization_id = uuid4()
    seen: dict[str, object] = {}

    async def override_db():
        yield object()

    async def fake_load_active_session(db, raw_token: str):
        seen["token"] = raw_token
        return SimpleNamespace(membership_id=membership_id)

    async def fake_build_access_context(db, requested_membership_id):
        seen["membership_id"] = requested_membership_id
        return AccessContext(
            organization_id=organization_id,
            membership_id=membership_id,
            authorization_revision=1,
            configuration_revision=1,
            permissions=["workforce.attendance.view"],
            scopes={},
            project_permissions={},
            features=[],
        )

    monkeypatch.setattr(
        "app.modules.sessions.deps.load_active_session",
        fake_load_active_session,
    )
    monkeypatch.setattr(
        "app.modules.sessions.router.build_access_context",
        fake_build_access_context,
    )

    app = FastAPI()
    app.include_router(session_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/session/context",
            headers={"Authorization": "Bearer native-session-token"},
        )

    assert response.status_code == 200
    assert response.json()["membership_id"] == str(membership_id)
    assert seen["token"] == "native-session-token"
    assert seen["membership_id"] == membership_id
