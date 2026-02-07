"""
Application Configuration
Centralized configuration management using Pydantic Settings.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Application
    app_name: str = Field(default="Voice-to-Task", description="Application name")
    app_env: str = Field(default="development", description="Environment")
    debug: bool = Field(default=False, description="Debug mode")
    secret_key: str = Field(default="change-me-in-production", description="Secret key")
    api_version: str = Field(default="v1", description="API version")
    
    # Database
    postgres_user: str = Field(default="voicetask")
    postgres_password: str = Field(default="voicetask_secret")
    postgres_db: str = Field(default="voice_to_task")
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    database_url: Optional[str] = Field(default=None)
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker_url: str = Field(default="redis://localhost:6379/0")
    celery_result_backend: str = Field(default="redis://localhost:6379/0")
    
    # OpenAI
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o", description="OpenAI model")
    whisper_model: str = Field(default="base", description="Whisper model")
    
    # JWT
    jwt_secret_key: str = Field(default="jwt-secret-change-me")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=30)
    jwt_refresh_token_expire_days: int = Field(default=7)
    
    # Integrations
    asana_client_id: Optional[str] = Field(default=None)
    asana_client_secret: Optional[str] = Field(default=None)
    asana_redirect_uri: Optional[str] = Field(default=None)
    asana_personal_access_token: Optional[str] = Field(default=None)
    
    trello_api_key: Optional[str] = Field(default=None)
    trello_api_secret: Optional[str] = Field(default=None)
    trello_redirect_uri: Optional[str] = Field(default=None)
    
    jira_domain: Optional[str] = Field(default=None)
    jira_email: Optional[str] = Field(default=None)
    jira_api_token: Optional[str] = Field(default=None)
    
    # File Upload
    max_upload_size_mb: int = Field(default=500)
    allowed_audio_formats: str = Field(default="wav,mp3,m4a,ogg,flac,webm")
    upload_dir: str = Field(default="./uploads")
    
    # Audio Processing
    audio_chunk_duration_seconds: int = Field(default=600)
    audio_sample_rate: int = Field(default=16000)
    enable_diarization: bool = Field(default=True)
    
    # CORS
    cors_origins: str = Field(default="http://localhost:3000")
    cors_allow_credentials: bool = Field(default=True)
    
    # Logging
    log_level: str = Field(default="INFO")
    sentry_dsn: Optional[str] = Field(default=None)
    
    # Rate Limiting
    rate_limit_requests: int = Field(default=100)
    rate_limit_period_seconds: int = Field(default=60)
    
    # HuggingFace
    hf_auth_token: Optional[str] = Field(default=None)
    
    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL."""
        if self.database_url:
            return self.database_url.replace("+asyncpg", "")
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def database_url_async(self) -> str:
        """Get asynchronous database URL."""
        if self.database_url:
            if "+asyncpg" not in self.database_url:
                return self.database_url.replace("postgresql://", "postgresql+asyncpg://")
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def allowed_audio_formats_list(self) -> List[str]:
        """Parse allowed audio formats into a list."""
        return [fmt.strip().lower() for fmt in self.allowed_audio_formats.split(",")]
    
    @property
    def max_upload_size_bytes(self) -> int:
        """Get max upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Export settings instance for convenience
settings = get_settings()
