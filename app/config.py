from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    whatsapp_token: str = "test-token"
    whatsapp_phone_number_id: str = "000000000000000"
    whatsapp_app_secret: str = "test-secret"
    whatsapp_verify_token: str = "verify-me"
    graph_api_version: str = "v21.0"
    graph_api_base: str = "https://graph.facebook.com"

    database_url: str = "sqlite:///./bot.db"
    business_name: str = "Acme Store"
    business_hours: str = "Mon-Sat, 9:00 to 18:00 (PKT)"


@lru_cache
def get_settings() -> Settings:
    return Settings()
