"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings sourced from .env file."""

    database_url: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
