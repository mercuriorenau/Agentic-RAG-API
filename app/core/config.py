from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MAX_QUERY_LENGTH = 600


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ragdb"
    secret_key: str = "change-me-in-production"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    tavily_api_key: str = ""
    llm_provider: str = "openai"
    access_token_expire_minutes: int = 1440
    upload_dir: str = "./uploads"
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4.1"
    anthropic_chat_model: str = "claude-sonnet-4-5"
    chunk_size: int = 800
    chunk_overlap: int = 100
    top_k: int = 5
    top_k_max: int = 8
    adaptive_top_k: bool = True
    candidate_multiplier: int = 4
    retrieval_min_score: float = 0.25
    rerank_enabled: bool = True
    rerank_model: str = "gpt-4o-mini"
    self_rag_enabled: bool = True
    self_rag_max_retries: int = 2
    agent_max_tool_rounds: int = 5
    conversation_history_max_turns: int = 6
    rate_limit_auth: str = "10/minute"
    rate_limit_query: str = "10/day"
    # When true, query rate limits are off for everyone (toggle in Railway while testing).
    rate_limit_disabled: bool = False
    # Comma-separated emails that skip query rate limits (your own accounts).
    rate_limit_bypass_emails: str = ""
    max_query_length: int = DEFAULT_MAX_QUERY_LENGTH
    log_level: str = "INFO"
    max_upload_size_mb: int = 10
    static_dir: str = "./frontend/dist"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"
    app_public_url: str = "http://localhost:8000"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Agentic RAG"
    email_verification_expire_minutes: int = 10

    @field_validator("smtp_password", mode="before")
    @classmethod
    def normalize_smtp_password(cls, value: object) -> object:
        # Gmail App Passwords are often copied as "xxxx xxxx xxxx xxxx".
        if isinstance(value, str):
            return value.replace(" ", "").strip()
        return value

    @field_validator("smtp_username", "smtp_from_email", mode="before")
    @classmethod
    def strip_smtp_identity(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def async_database_url(self) -> str:
        url = self.database_url.strip()
        # Railway / Heroku-style schemes → SQLAlchemy asyncpg.
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]
        # asyncpg understands ssl=…; many providers still ship sslmode=….
        url = url.replace("sslmode=require", "ssl=require")
        url = url.replace("sslmode=verify-full", "ssl=require")
        url = url.replace("sslmode=prefer", "ssl=prefer")
        url = url.replace("sslmode=disable", "ssl=disable")
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
