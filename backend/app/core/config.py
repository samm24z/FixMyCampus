"""Application Configuration and Settings Module."""

from typing import Any, List, Union
from uuid import uuid4
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


def _is_pooled_host(host: str | None) -> bool:
    """Connection poolers (Neon ``-pooler``, Supabase Supavisor) can't reuse asyncpg prepared statements."""
    host = host or ""
    return "-pooler" in host or "pooler.supabase.com" in host


def _requires_ssl(host: str | None) -> bool:
    return bool(host) and host.endswith((".supabase.com", ".supabase.co", ".neon.tech"))


def normalise_async_url(url: str) -> str:
    """Turn any Postgres URL (Neon, Supabase, Render, local) into one asyncpg accepts.

    Hosted providers (Supabase, Neon, ...) hand out ``postgres://`` or ``postgresql://`` URLs carrying
    libpq-only options (``sslmode``, ``channel_binding``) that asyncpg rejects.
    """
    if not url:
        return url
    parsed = make_url(url)
    query = dict(parsed.query)
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    if sslmode and "ssl" not in query:
        query["ssl"] = sslmode
    if "ssl" not in query and _requires_ssl(parsed.host):
        query["ssl"] = "require"
    if _is_pooled_host(parsed.host):
        query.setdefault("prepared_statement_cache_size", "0")
    driver = "postgresql+asyncpg" if parsed.drivername.split("+")[0] in {"postgres", "postgresql"} else parsed.drivername
    return parsed.set(drivername=driver, query=query).render_as_string(hide_password=False)


def _unique_statement_name() -> str:
    return f"__asyncpg_{uuid4()}__"


def asyncpg_connect_args(url: str) -> dict[str, Any]:
    """Extra asyncpg connect arguments required by the target host.

    Behind a transaction pooler many clients share each server connection, so asyncpg's
    per-connection counter names (``__asyncpg_stmt_7__``) collide. Disable its statement
    cache and give every prepared statement a unique name instead.
    """
    if not _is_pooled_host(make_url(url).host):
        return {}
    return {"statement_cache_size": 0, "prepared_statement_name_func": _unique_statement_name}


class Settings(BaseSettings):
    """Global application settings loaded from environment."""

    PROJECT_NAME: str = "FixMyCampus AI"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Self-signup is limited to these email domains (comma separated, matched exactly: sub-domains and
    # look-alikes are rejected). Empty = no restriction. Applies when an account first appears;
    # accounts an admin creates, and profiles that already exist, are not affected.
    ALLOWED_EMAIL_DOMAINS: str = "mvsrec.edu.in"

    # Supabase Auth: identity (sign-up, login, password reset, sessions) is delegated to it.
    # The backend only verifies the access tokens it issues and keeps roles in its own database.
    SUPABASE_URL: str = ""  # e.g. https://<project-ref>.supabase.co
    SUPABASE_JWT_AUDIENCE: str = "authenticated"
    # Only for legacy projects that sign tokens with a shared secret (HS256). Modern projects
    # sign with asymmetric keys published at <SUPABASE_URL>/auth/v1/.well-known/jwks.json.
    SUPABASE_JWT_SECRET: str = ""
    # Server-side secret ("service_role" / "secret" key) used to create and ban accounts. Never ship to the browser.
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Server settings
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # PostgreSQL & pgvector Database settings
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres_password"
    POSTGRES_DB: str = "fixmycampus_db"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres_password@localhost:5432/fixmycampus_db"
    DB_ECHO: bool = False  # log every SQL statement (includes bound values such as password hashes)
    # Optional direct (non-pooled) URL used only by Alembic; falls back to DATABASE_URL.
    MIGRATION_DATABASE_URL: str = ""

    @field_validator("DATABASE_URL", "MIGRATION_DATABASE_URL")
    @classmethod
    def assemble_database_url(cls, v: str) -> str:
        return normalise_async_url(v)

    @property
    def alembic_database_url(self) -> str:
        return self.MIGRATION_DATABASE_URL or self.DATABASE_URL

    # CORS origins
    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return [str(i) for i in v]
        return v

    # AI Configuration
    AI_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    AI_CLASSIFIER_MODEL: str = "distilbert-base-uncased"
    AI_SIMILARITY_THRESHOLD: float = 0.82
    OPENAI_API_KEY: str = ""

    @property
    def allowed_email_domains(self) -> list[str]:
        return [d.strip().lower().lstrip("@") for d in self.ALLOWED_EMAIL_DOMAINS.split(",") if d.strip()]

    def is_email_allowed(self, email: str) -> bool:
        """True if ``email`` belongs to one of the allowed domains (always true when none are configured)."""
        domains = self.allowed_email_domains
        if not domains:
            return True
        local, at, domain = email.strip().lower().rpartition("@")
        return bool(local) and bool(at) and domain in domains

    @property
    def supabase_issuer(self) -> str:
        return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1"

    @model_validator(mode="after")
    def require_supabase_in_production(self) -> "Settings":
        if self.ENVIRONMENT.lower() == "production" and not self.SUPABASE_URL:
            raise ValueError("SUPABASE_URL must be set when ENVIRONMENT=production")
        return self

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
