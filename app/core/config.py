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

    # Object storage was here — removed for now, see
    # plan/backend/phase-2b-storage-and-workers.md. Uploaded bytes are held in
    # memory for one request/background-task and then discarded.

    max_upload_mb: int = 25

    # Vector search (Pinecone serverless).
    pinecone_api_key: str = ""
    pinecone_index: str = "enterprise-rag"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    # Embeddings.
    embedding_provider: str = "openai"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # Chunking.
    chunk_strategy: str = "structural"
    chunk_target_tokens: int = 512
    chunk_overlap_tokens: int = 64
    max_chunk_metadata_chars: int = 4000

    # LLM (Phase 4) — server-wide default, used when a user hasn't set their own.
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # Symmetric key (Fernet, urlsafe-base64, 32 raw bytes) used to encrypt
    # per-workspace LLM API keys at rest. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Required before a workspace can save its own LLM config.
    secrets_encryption_key: str = ""

    rag_top_k: int = 5

    # Later phases add their own keys here (query rewriting, reranking, ...).

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

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
