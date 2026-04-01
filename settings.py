from pydantic_settings import BaseSettings
from pydantic import SecretStr


class Settings(BaseSettings):
    NEO4J_URI: str
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: SecretStr
    INFINITY_URL: str
    VIETTEL_BASE_URL: str
    VIETTEL_API_KEY: SecretStr
    VIETTEL_MODEL: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings() #type: ignore
