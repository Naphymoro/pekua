from functools import lru_cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PEKUA_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: SecretStr = SecretStr("postgresql+asyncpg://pekua:pekua@localhost:5432/pekua")
    object_store_endpoint: str = "http://localhost:9000"
    object_store_bucket: str = "pekua-documents"
    object_store_access_key: SecretStr = SecretStr("development-only")
    object_store_secret_key: SecretStr = SecretStr("development-only")
    neo4j_uri: str | None = None
    neo4j_user: str | None = None
    neo4j_password: SecretStr | None = None
    vault_provider: str = "environment"
    log_level: str = "INFO"

    @model_validator(mode="after")
    def reject_development_secrets_in_production(self) -> "Settings":
        if self.environment.lower() != "production":
            return self
        forbidden = {"development-only", "pekua", "change-me", ""}
        secret_values = {
            self.object_store_access_key.get_secret_value(),
            self.object_store_secret_key.get_secret_value(),
        }
        if secret_values & forbidden:
            raise ValueError("development object-store credentials are forbidden in production")
        if self.vault_provider == "environment":
            raise ValueError("the environment vault provider is forbidden in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
