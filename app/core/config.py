from functools import lru_cache

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
    chat_model: str = "gpt-4o"
    anthropic_chat_model: str = "claude-sonnet-4-20250514"
    chunk_size: int = 800
    chunk_overlap: int = 100
    top_k: int = 5
    agent_max_tool_rounds: int = 3
    conversation_history_max_turns: int = 6
    rate_limit_auth: str = "10/minute"
    rate_limit_query: str = "3/day"
    max_query_length: int = DEFAULT_MAX_QUERY_LENGTH
    log_level: str = "INFO"
    max_upload_size_mb: int = 10
    static_dir: str = "./frontend/dist"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def async_database_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
