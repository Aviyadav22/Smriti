"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "smriti"
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_version: str = "0.1.0"
    cors_origins: str = "http://localhost:3000"

    # Security
    jwt_secret_key: str = ""
    jwt_refresh_secret_key: str = ""
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    bcrypt_cost_factor: int = 12
    encryption_key: str = ""

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://smriti:smriti_dev@localhost:5432/smriti"
    database_ssl_mode: str = "disable"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Gemini
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-pro"
    gemini_embedding_model: str = "text-embedding-004"
    gemini_embedding_dimension: int = 768
    gemini_max_tokens: int = 8192
    gemini_temperature: float = 0.1
    gemini_rate_limit_rpm: int = 60

    # Pinecone
    vector_provider: str = "pinecone"
    pinecone_api_key: str = ""
    pinecone_index_name: str = "smriti-legal"
    pinecone_environment: str = "us-east-1"
    pinecone_dimension: int = 768
    pinecone_metric: str = "cosine"
    pinecone_cloud: str = "aws"
    pinecone_top_k: int = 20

    # Neo4j
    graph_provider: str = "neo4j"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "smriti_dev"
    neo4j_database: str = "neo4j"

    # Cohere
    reranker_provider: str = "cohere"
    cohere_api_key: str = ""
    cohere_rerank_model: str = "rerank-v3.5"
    cohere_rerank_top_n: int = 10

    # Storage
    storage_provider: str = "local"
    local_storage_path: str = "./data/pdfs"

    # Ingestion
    ingestion_batch_size: int = 10
    ingestion_concurrency: int = 5
    ingestion_tracker_db: str = "./data/ingestion_tracker.db"

    # Rate Limiting
    rate_limit_default: str = "100/minute"
    rate_limit_search: str = "60/minute"
    rate_limit_chat: str = "10/minute"
    rate_limit_ingest: str = "5/minute"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    log_pii_redaction: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()
