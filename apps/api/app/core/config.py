from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Construction OS API"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://construction:construction@localhost:5432/construction_os"
    web_origin: str = "http://localhost:3000"

    session_cookie_name: str = "construction_os_session"
    session_cookie_secure: bool = True
    session_cookie_samesite: Literal["lax", "strict"] = "lax"
    session_idle_timeout_seconds: int = Field(default=180, ge=60)
    session_absolute_timeout_seconds: int = Field(default=28800, ge=300)
    session_touch_interval_seconds: int = Field(default=30, ge=10)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_session_security(self) -> "Settings":
        if self.session_absolute_timeout_seconds <= self.session_idle_timeout_seconds:
            raise ValueError("Absolute session timeout must exceed the idle timeout")
        if self.session_touch_interval_seconds >= self.session_idle_timeout_seconds:
            raise ValueError("Session touch interval must be shorter than the idle timeout")
        if self.environment.lower() == "production" and not self.session_cookie_secure:
            raise ValueError("Secure session cookies are required in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
