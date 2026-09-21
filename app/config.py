"""App configuration, loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Market-data API keys (see .env.example) ---
    alpha_vantage_api_key: str = ""
    fmp_api_key: str = ""
    finnhub_api_key: str = ""

    # --- Provider order per capability (comma-separated names) ---
    # Dispatcher tries these left-to-right, returns the first that answers.
    # quote: FMP first (rich: price + 50/200 MA + 52wk range); AV covers
    # FMP-gated symbols; Finnhub is a broad price-only backstop.
    quote_providers: str = "fmp,alpha_vantage,finnhub"
    # analyst: FMP has counts + price targets; Finnhub has counts only.
    analyst_providers: str = "fmp,finnhub"
    # weekly OHLC series: only Alpha Vantage gives what we need for ATR/40wk SMA.
    series_providers: str = "alpha_vantage"

    # --- In-memory cache TTLs (seconds); 0 disables caching for that capability ---
    cache_ttl_quote: int = 300       # 5 min: prices move, but not per-keystroke
    cache_ttl_analyst: int = 21600   # 6 h: consensus changes slowly
    cache_ttl_series: int = 21600    # 6 h: weekly bars change at most weekly

    # Persistence. Step 2 uses local SQLite; Step 3 swaps this for Azure PostgreSQL.
    database_url: str = "sqlite:///./scaleout.db"

    # Default trailing-stop percentage for the strategy.
    default_stop_pct: float = 6.0

    # CORS origins allowed to call the API (the front end / artifact).
    cors_origins: str = "*"


settings = Settings()
