# app/core/config.py
from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --- App Info ---
    PROJECT_NAME: str = "CAN 2025 Assistant"
    ENVIRONMENT: Literal["dev", "stage", "prod"] = "dev"
    LOG_LEVEL: str = "INFO"

    # --- Database (PostgreSQL) ---
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:"
            f"{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --- Redis (Cache & Sessions) ---
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    # --- LLM Configuration (LiteLLM) ---
    # LLM_MODEL_FAST: For intent classification / routing
    # LLM_MODEL_SMART: For complex reasoning / RAG
    LLM_API_KEY: str
    LLM_MODEL_FAST: str = "gpt-5-nano"
    LLM_MODEL_SMART: str = "gpt-5-nano"

    # --- External Services ---
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    GOOGLE_SEARCH_API_KEY: Optional[str] = None
    GOOGLE_CSE_ID: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )


settings = Settings()  # type: ignore
