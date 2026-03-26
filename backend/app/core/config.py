"""Application configuration using pydantic-settings."""

from pydantic import model_validator
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
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_version: str = "0.1.0"
    cors_origins: str = "http://localhost:3000"

    # Security
    jwt_secret_key: str = ""
    jwt_refresh_secret_key: str = ""
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7
    bcrypt_cost_factor: int = 12
    encryption_key: str = ""

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://smriti:smriti_dev@localhost:5432/smriti"
    database_pool_size: int = 30
    database_max_overflow: int = 20
    database_pool_recycle: int = 1800
    database_pool_timeout: int = 30

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Gemini
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-pro-preview"
    gemini_flash_model: str = "gemini-3-flash-preview"
    gemini_embedding_model: str = "gemini-embedding-2-preview"
    gemini_embedding_dimension: int = 1536
    gemini_context_cache_enabled: bool = True  # [S10]
    gemini_context_cache_ttl: int = 3600  # [S10] seconds

    # Pinecone
    vector_provider: str = "pinecone"
    pinecone_api_key: str = ""
    pinecone_index_name: str = "smriti-legal"
    pinecone_host: str = ""

    # Neo4j
    graph_provider: str = "neo4j"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "smriti_dev"
    neo4j_database: str = "neo4j"

    # Cohere
    reranker_provider: str = "cohere"
    cohere_api_key: str = ""
    cohere_rerank_model: str = "rerank-v4.0-pro"
    cohere_rerank_top_n: int = 10

    # TTS
    tts_provider: str = "mock"
    sarvam_api_key: str = ""

    # Storage
    storage_provider: str = "local"
    local_storage_path: str = "./data/pdfs"
    gcs_bucket_name: str = "smriti-489416-documents"
    gcs_project_id: str = "smriti-489416"

    # Ingestion — local-only SQLite for CLI job tracking (not used in Cloud Run)
    ingestion_tracker_db: str = "./data/ingestion_tracker.db"

    # Search
    search_cache_ttl: int = 300
    search_facet_cache_ttl: int = 900
    search_rrf_k: int = 60  # default / balanced
    search_rrf_k_keyword_heavy: int = 30
    search_rrf_k_vector_heavy: int = 60
    search_vector_top_k: int = 20
    search_fts_top_k: int = 20
    search_rerank_top_n: int = 10
    search_default_page_size: int = 10
    search_max_page_size: int = 50

    # Indian Kanoon API
    ik_api_token: str = ""
    ik_rate_limit: float = 2.0  # requests per second

    # Tavily Web Search
    tavily_api_key: str = ""
    web_search_timeout: int = 10

    # Research Agent
    research_max_refinement_rounds: int = 2
    research_max_chunks_per_case: int = 4
    research_max_snippet_len: int = 1500
    research_max_ratio_len: int = 3000

    # CRAG thresholds
    research_crag_threshold_correct: float = 0.7
    research_crag_threshold_ambiguous: float = 0.3
    research_crag_fallback_ratio: float = 0.5

    # Chat / RAG
    chat_max_history: int = 10
    chat_max_context_results: int = 5
    chat_max_snippet_chars: int = 3000

    # Treatment classification — LLM fallback for ambiguous citation treatment.
    # When enabled, uses Gemini Flash to classify treatment when regex confidence
    # is below threshold. Improves accuracy for overruled/distinguished detection.
    enable_treatment_llm_fallback: bool = False
    treatment_llm_confidence_threshold: float = 0.6

    # Logging
    log_level: str = "INFO"

    # Monitoring
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    sentry_environment: str = ""

    # DPDP
    data_retention_days: int = 365
    user_upload_retention_days: int = 7

    @model_validator(mode="after")
    def validate_critical_settings(self) -> "Settings":
        if self.app_env == "test":
            return self

        secret_fields = {
            "jwt_secret_key": self.jwt_secret_key,
            "jwt_refresh_secret_key": self.jwt_refresh_secret_key,
        }

        if self.app_env == "production":
            # Enforce non-empty and minimum length for JWT secrets
            for name, value in secret_fields.items():
                if not value:
                    raise ValueError(
                        f"{name} must not be empty in production"
                    )
                if len(value) < 32:
                    raise ValueError(
                        f"{name} must be at least 32 characters in production"
                    )
            # Enforce non-empty encryption key
            if not self.encryption_key:
                raise ValueError(
                    "encryption_key must not be empty in production"
                )
            # Enforce encryption key minimum length
            if len(self.encryption_key) < 32:
                raise ValueError(
                    "encryption_key must be at least 32 characters in production"
                )
            # Enforce CORS is not wildcard
            if "*" in self.cors_origins:
                raise ValueError(
                    "CORS origins must not contain '*' in production"
                )
            # Enforce external service API keys are set
            if not self.gemini_api_key:
                raise ValueError(
                    "gemini_api_key must not be empty in production"
                )
            if not self.pinecone_api_key:
                raise ValueError(
                    "pinecone_api_key must not be empty in production"
                )
            if not self.pinecone_host:
                raise ValueError(
                    "pinecone_host must not be empty in production"
                )
            if not self.cohere_api_key:
                raise ValueError(
                    "cohere_api_key must not be empty in production"
                )
            # Enforce no dev defaults in production
            if self.neo4j_password == "smriti_dev":
                raise ValueError(
                    "neo4j_password must not use default 'smriti_dev' in production"
                )
            if "localhost" in self.database_url:
                raise ValueError(
                    "database_url must not contain 'localhost' in production"
                )
            if self.storage_provider == "local":
                raise ValueError(
                    "storage_provider must not be 'local' in production"
                )
            if self.tts_provider == "mock":
                raise ValueError(
                    "tts_provider must not be 'mock' in production"
                )
            if self.app_debug:
                raise ValueError(
                    "app_debug must be False in production"
                )
        else:
            # Development: warn but allow empty
            import warnings

            for name, value in secret_fields.items():
                if not value:
                    warnings.warn(
                        f"{name} is empty — using insecure defaults",
                        stacklevel=2,
                    )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()
