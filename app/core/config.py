from functools import lru_cache
from urllib.parse import quote_plus, urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    # Base URI without credentials (e.g. mongodb+srv://cluster0.xxx.mongodb.net).
    # When username/password are set they are URL-encoded and injected at runtime,
    # so secrets never have to live inside the URI string.
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_username: str = ""
    mongodb_password: str = ""
    mongodb_db: str = "enterprise_rag"

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 60 * 24

    # Later phases add their own keys here (Pinecone, LLM, object storage, ...).

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def mongo_dsn(self) -> str:
        """Connection URI with credentials injected (any already in the URI are replaced)."""
        if not self.mongodb_username:
            return self.mongodb_uri
        parts = urlsplit(self.mongodb_uri)
        userinfo = f"{quote_plus(self.mongodb_username)}:{quote_plus(self.mongodb_password)}"
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"
        netloc = f"{userinfo}@{host}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
