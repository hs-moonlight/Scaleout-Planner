"""App configuration, loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Market-data API keys (see .env.example)
    alpha_vantage_api_key: str = ""
    fmp_api_key: str = ""

    # Persistence. Step 2 uses local SQLite; Step 3 swaps this for Azure PostgreSQL.
    database_url: str = "sqlite:///./scaleout.db"

    # Default trailing-stop percentage for the strategy.
    default_stop_pct: float = 6.0

    # CORS origins allowed to call the API (the front end / artifact).
    cors_origins: str = "*"


settings = Settings()
