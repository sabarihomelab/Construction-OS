from uuid import uuid4

from app.modules.authentication.web_router import router
from app.modules.authentication.web_schemas import WebSessionResponse


def test_web_session_response_does_not_expose_session_secrets() -> None:
    response = WebSessionResponse(membership_id=uuid4())
    body = response.model_dump()
    assert body["status"] == "authenticated"
    assert body["membership_id"]
    assert "access_token" not in body
    assert "csrf_token" not in body


def test_web_authentication_routes_are_registered() -> None:
    paths = {route.path for route in router.routes}
    assert "/auth/web/providers" in paths
    assert "/auth/web/authenticate" in paths
    assert "/auth/web/select-membership" in paths
