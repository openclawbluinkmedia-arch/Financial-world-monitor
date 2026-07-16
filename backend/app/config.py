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

    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL_SLUG: str = "qwen/qwen3.5-397b-a17b"

    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL_SLUG: str = "qwen/qwen3.7-plus"

    VLLM_BASE_URL: str = "http://vllm:8000/v1"
    VLLM_MODEL_SLUG: str = "qwen/qwen3.5-397b-a17b"

    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIM: int = 1024

    DATABASE_URL: str = "postgresql+asyncpg://fios:fios_secret@localhost:5432/fios"
    REDIS_URL: str = "redis://localhost:6379/0"

    CORS_ORIGINS: str = "http://localhost:3000"

    SECRET_KEY: str = "insecure-default-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

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


@lru_cache()
def get_settings() -> Settings:
    return Settings()
