import hmac
from collections.abc import Mapping
from datetime import UTC, datetime

from app.modules.authentication.providers import AuthenticationAssertion
from app.modules.sessions.models import AuthenticationLevel, AuthenticationMethod


class DevelopmentAuthenticationProvider:
    provider_key = "development"
    allow_verified_email_lookup = True

    def __init__(self, shared_secret: str) -> None:
        secret = shared_secret.strip()
        if len(secret) < 16:
            raise ValueError("Development authentication secret must be at least 16 characters")
        self._shared_secret = secret

    async def authenticate(self, payload: Mapping[str, object]) -> AuthenticationAssertion:
        supplied_secret = payload.get("secret")
        email = payload.get("email")
        display_name = payload.get("display_name")

        if not isinstance(supplied_secret, str) or not hmac.compare_digest(
            supplied_secret,
            self._shared_secret,
        ):
            raise ValueError("Development authentication failed")
        if not isinstance(email, str):
            raise TypeError("Development authentication email is required")

        normalized_email = email.strip().lower()
        if not normalized_email or "@" not in normalized_email:
            raise ValueError("Development authentication email is invalid")

        if display_name is None:
            normalized_display_name = normalized_email.split("@", 1)[0]
        elif isinstance(display_name, str) and display_name.strip():
            normalized_display_name = display_name.strip()
        else:
            raise ValueError("Development authentication display name is invalid")

        authenticated_at = datetime.now(UTC)
        return AuthenticationAssertion(
            provider_key=self.provider_key,
            subject=f"dev:{normalized_email}",
            email=normalized_email,
            email_verified=True,
            display_name=normalized_display_name,
            method=AuthenticationMethod.LOCAL_PASSWORD,
            level=AuthenticationLevel.SINGLE_FACTOR,
            authenticated_at=authenticated_at,
        )
