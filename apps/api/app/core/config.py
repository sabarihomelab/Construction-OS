from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Construction OS API"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://construction:construction@localhost:5432/construction_os"
    web_origin: str = "http://localhost:3000"
    jwt_secret: str = "replace-me"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
