import os
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Application settings loaded from environment variables with defaults."""

    mongo_uri: str = Field(default_factory=lambda: os.getenv("MONGO_URI", "mongodb://mongodb:27017"))
    mongo_db: str = Field(default_factory=lambda: os.getenv("MONGO_DB", "sentiment_stream"))
    model_path: str = Field(default_factory=lambda: os.getenv("MODEL_PATH", "/app/model"))
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


settings = Settings()
