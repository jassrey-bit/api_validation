# config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    API_URL: str
    API_KEY: str

    PROD_BASE_URL: str = "https://msc-sofom.cloudgsf.com/msc-calculation-methods"
    PROD_API_KEY: str = ""
    DEV_BASE_URL: str = "https://dev-msc-sofom.cloudgsf.com/msc-calculation-methods"
    DEV_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Ignora otras variables si existen en el .env
    )


settings = Settings()