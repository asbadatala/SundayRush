from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://sundayrush:sundayrush@localhost:5442/sundayrush"
    session_secret: str = "dev-session-secret-change-me"
    # Fernet key (urlsafe base64, 32 bytes). Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    token_encryption_key: str = ""

    web_base_url: str = "https://localhost:3000"
    cookie_secure: bool = True

    yahoo_client_id: str = ""
    yahoo_client_secret: str = ""
    yahoo_redirect_uri: str = "https://localhost:3000/api/providers/yahoo/auth/callback"

    # Swaps in fixture-backed NFL data + a fake Yahoo OAuth/API for tests and E2E.
    fixture_mode: bool = False
    fixture_dir: str = ""

    log_level: str = "INFO"
    log_json: bool = True

    # Rate limits (slowapi syntax)
    rate_limit_import: str = "20/minute"
    rate_limit_search: str = "120/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()
