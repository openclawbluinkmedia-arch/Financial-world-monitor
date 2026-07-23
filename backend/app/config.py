from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class DeploymentMode(str, Enum):
    DEV = "dev"
    CUSTOMER = "customer"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    DEPLOYMENT_MODE: DeploymentMode = DeploymentMode.DEV

    # ── Reasoning LLM ──────────────────────────────────────────
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL_SLUG: str = "qwen/qwen3.5-397b-a17b"

    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL_SLUG: str = "qwen/qwen3.7-plus"

    VLLM_BASE_URL: str = "http://vllm:8000/v1"
    VLLM_MODEL_SLUG: str = "qwen/qwen3.5-397b-a17b"

    # ── Embeddings (remote via NIM) ────────────────────────────
    EMBEDDING_API_URL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "nvidia/nv-embedqa-e5-v5"
    EMBEDDING_DIM: int = 1024

    # ── Database ───────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://fios:fios_secret@localhost:5432/fios"
    DATABASE_SSL: str = ""

    # ── Redis (optional — leave empty to disable) ──────────────
    REDIS_URL: str = ""

    # ── CORS ───────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000"

    # ── Auth ───────────────────────────────────────────────────
    SECRET_KEY: str = "insecure-default-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── Ingest API guard ───────────────────────────────────────
    INGEST_TOKEN: str = ""

    # ── Scheduler ──────────────────────────────────────────────
    ENABLE_SCHEDULER: bool = True

    # ── Logging ────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    STRUCTURED_LOG: bool = True

    @property
    def is_dev(self) -> bool:
        return self.DEPLOYMENT_MODE == DeploymentMode.DEV

    @property
    def is_customer(self) -> bool:
        return self.DEPLOYMENT_MODE == DeploymentMode.CUSTOMER

    @property
    def has_secure_secret(self) -> bool:
        return self.SECRET_KEY not in ("insecure-default-change-me", "", "change-me")

    @property
    def effective_embedding_api_url(self) -> str:
        return (self.EMBEDDING_API_URL or self.NVIDIA_BASE_URL).rstrip("/")

    @property
    def effective_embedding_api_key(self) -> str:
        return self.EMBEDDING_API_KEY or self.NVIDIA_API_KEY


@lru_cache()
def get_settings() -> Settings:
    return Settings()
