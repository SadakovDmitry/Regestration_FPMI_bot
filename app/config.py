from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(default="TEST_TOKEN", alias="BOT_TOKEN")
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5433/hb_bot",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    admin_ids: list[int] = Field(default_factory=list, alias="ADMIN_IDS")
    super_admin_ids: list[int] = Field(default_factory=list, alias="SUPER_ADMIN_IDS")
    timezone: str = Field(default="Europe/Moscow", alias="TIMEZONE")
    channel_id: int | None = Field(default=None, alias="CHANNEL_ID")
    pd_consent_version: str = Field(default="v1", alias="PD_CONSENT_VERSION")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("admin_ids", "super_admin_ids", mode="before")
    @classmethod
    def _parse_ids(cls, value: str | list[int] | None) -> list[int]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if not value:
            return []
        return [int(x.strip()) for x in str(value).split(",") if x.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
