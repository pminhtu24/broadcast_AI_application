import logging
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    NEO4J_URI: str
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: SecretStr
    INFINITY_URL: str
    VIETTEL_BASE_URL: str
    VIETTEL_API_KEY: SecretStr
    VIETTEL_MODEL: str


@lru_cache()
def get_settings() -> Settings:
    logger.info("Loading settings...")
    return Settings()  


settings = get_settings()
