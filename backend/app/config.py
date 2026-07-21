"""Application settings.

Secrets come from environment variables only — never hardcoded (foundational
decision D7, ARCHITECTURE-SPINE.md Consistency Conventions). Fields are optional
so the service can boot and serve `/health` without secrets present; presence is
checked where a value is actually used (see `missing_required`).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

# Env vars that must be present for the full system to operate. `/health` does
# not require them; `/health/db` requires DATABASE_URL.
REQUIRED_FOR_FULL_OPERATION = (
    "DATABASE_URL",
    "EDGAR_CONTACT",
    "TIINGO_API_KEY",
    "LLM_API_KEY",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase Postgres 17 connection (async DSN, e.g. postgresql+asyncpg://...).
    database_url: str | None = None
    # SEC EDGAR fair-access identifying contact (AD-9).
    edgar_contact: str | None = None
    # Tiingo free-tier key — Altman market price only (AD-11/AD-14, D7 exception).
    tiingo_api_key: str | None = None
    # LLM key — FR-12 constrained rewrite, default Claude Haiku (AD-21).
    llm_api_key: str | None = None

    def missing_required(self) -> list[str]:
        """Return the REQUIRED_FOR_FULL_OPERATION env vars that are unset."""
        values = {
            "DATABASE_URL": self.database_url,
            "EDGAR_CONTACT": self.edgar_contact,
            "TIINGO_API_KEY": self.tiingo_api_key,
            "LLM_API_KEY": self.llm_api_key,
        }
        return [name for name, value in values.items() if not value]


def get_settings() -> Settings:
    return Settings()
