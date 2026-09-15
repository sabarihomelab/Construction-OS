from app.core.config import Settings
from app.modules.authentication.development_provider import DevelopmentAuthenticationProvider
from app.modules.authentication.providers import AUTHENTICATION_PROVIDERS


def configure_authentication_providers(settings: Settings) -> None:
    AUTHENTICATION_PROVIDERS.clear()
    if settings.native_dev_auth_enabled:
        AUTHENTICATION_PROVIDERS.register(
            DevelopmentAuthenticationProvider(settings.native_dev_auth_secret)
        )
