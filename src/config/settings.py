"""Configuration management using Pydantic settings."""

import os
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with validation."""

    # Telegram Bot Configuration
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    telegram_bot_username: Optional[str] = Field(None, env="TELEGRAM_BOT_USERNAME")

    # Google AI Configuration  
    google_api_key: str = Field(..., env="GOOGLE_API_KEY")
    gemini_model: str = Field("google-gla:gemini-1.5-flash", env="GEMINI_MODEL")

    # AI Agent Configuration
    system_prompt: str = Field(
        "You are a helpful AI assistant integrated with a Telegram bot. "
        "Respond to user messages in a friendly and informative way. "
        "Keep responses concise but helpful.",
        env="SYSTEM_PROMPT"
    )
    max_response_length: int = Field(4096, env="MAX_RESPONSE_LENGTH")

    # Application Configuration
    log_level: str = Field("INFO", env="LOG_LEVEL")
    polling_interval: int = Field(1, env="POLLING_INTERVAL")  # seconds

    # Rate Limiting
    max_requests_per_minute: int = Field(60, env="MAX_REQUESTS_PER_MINUTE")
    request_timeout: int = Field(30, env="REQUEST_TIMEOUT")  # seconds
    
    # Conversation Persistence Configuration
    persistence_enabled: bool = Field(True, env="PERSISTENCE_ENABLED")
    persistence_type: str = Field("json", env="PERSISTENCE_TYPE")  # "json" or "database"
    
    # JSON Storage Configuration
    json_storage_dir: str = Field("data/conversations", env="JSON_STORAGE_DIR")
    
    # Database Configuration
    database_url: str = Field("sqlite:///data/conversations.db", env="DATABASE_URL")
    
    # Conversation Management
    max_conversations_per_user: int = Field(100, env="MAX_CONVERSATIONS_PER_USER")
    context_window_size: int = Field(10, env="CONTEXT_WINDOW_SIZE")
    auto_summarize_threshold: int = Field(50, env="AUTO_SUMMARIZE_THRESHOLD")
    cleanup_old_data_days: int = Field(30, env="CLEANUP_OLD_DATA_DAYS")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"  # Allow extra fields in .env file
    }

    @field_validator("telegram_bot_token")
    @classmethod
    def validate_telegram_token(cls, v):
        """Validate Telegram bot token format."""
        if not v or ":" not in v:
            raise ValueError("Invalid Telegram bot token format")
        return v

    @field_validator("google_api_key")
    @classmethod
    def validate_google_api_key(cls, v):
        """Validate Google API key format."""
        if not v or len(v) < 20:
            raise ValueError("Invalid Google API key")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()
    
    @field_validator("persistence_type")
    @classmethod
    def validate_persistence_type(cls, v):
        """Validate persistence type."""
        valid_types = ["json", "database"]
        if v.lower() not in valid_types:
            raise ValueError(f"Persistence type must be one of: {valid_types}")
        return v.lower()

    def get_log_level(self) -> int:
        """Get logging level as integer."""
        import logging
        return getattr(logging, self.log_level)

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return os.getenv("ENVIRONMENT", "").lower() == "production"


# Global settings instance
settings = Settings()
