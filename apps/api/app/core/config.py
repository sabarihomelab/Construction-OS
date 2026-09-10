from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> Path | str:
    candidates = [Path.cwd(), *Path(__file__).resolve().parents]
    seen: set[Path] = set()
    for directory in candidates:
        candidate = directory / ".env"
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file():
            return candidate
    return ".env"


_ENV_FILE = _find_env_file()


class Settings(BaseSettings):
    app_name: str = "Construction OS API"
    environment: str = "development"
    environment_name: str = "India Local Development"
    database_url: str = "postgresql+asyncpg://construction:construction@localhost:5432/construction_os"
    web_origin: str = "http://localhost:3000"

    product_market: Literal["IN"] = "IN"
    default_locale: str = "en-IN"
    default_timezone: str = "Asia/Kolkata"
    default_currency: str = "INR"
    default_unit_system: Literal["metric", "mixed", "imperial"] = "metric"

    deployment_profile: Literal["development", "single_server", "split"] = "development"
    database_mode: Literal["local", "external"] = "local"
    storage_provider: str = "local"
    runtime_modules: str = "default"
    worker_profiles: str = "auto"

    ai_assistant_enabled: bool = False
    ai_provider: Literal["disabled", "ollama", "openai_compatible"] = "disabled"
    ai_base_url: str = ""
    ai_model: str = ""
    ai_api_key: str = ""
    ai_allow_tenant_knowledge: bool = True
    ai_allow_upgrade_guidance: bool = True

    session_cookie_name: str = "construction_os_session"
    csrf_cookie_name: str = "construction_os_csrf"
    session_cookie_secure: bool = True
    session_cookie_samesite: Literal["lax", "strict"] = "lax"
    session_idle_timeout_seconds: int = Field(default=180, ge=60)
    session_absolute_timeout_seconds: int = Field(default=28800, ge=300)
    session_touch_interval_seconds: int = Field(default=30, ge=10)

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        if self.session_absolute_timeout_seconds <= self.session_idle_timeout_seconds:
            raise ValueError("Absolute session timeout must exceed the idle timeout")
        if self.session_touch_interval_seconds >= self.session_idle_timeout_seconds:
            raise ValueError("Session touch interval must be shorter than the idle timeout")
        if self.environment.lower() == "production" and not self.session_cookie_secure:
            raise ValueError("Secure session cookies are required in production")
        if not self.environment_name.strip():
            raise ValueError("ENVIRONMENT_NAME cannot be empty")
        if not self.storage_provider.strip():
            raise ValueError("STORAGE_PROVIDER cannot be empty")
        if self.default_currency.upper() != self.default_currency or len(self.default_currency) != 3:
            raise ValueError("DEFAULT_CURRENCY must be a three-letter uppercase currency code")
        if not self.default_locale.strip() or not self.default_timezone.strip():
            raise ValueError("India localization defaults cannot be empty")
        if self.ai_assistant_enabled:
            if self.ai_provider == "disabled":
                raise ValueError("AI_PROVIDER must be configured when AI_ASSISTANT_ENABLED=true")
            if not self.ai_model.strip():
                raise ValueError("AI_MODEL is required when the assistant is enabled")
            if not self.ai_base_url.strip():
                raise ValueError("AI_BASE_URL is required when the assistant is enabled")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
