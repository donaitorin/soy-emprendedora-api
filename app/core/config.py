from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str

    # Auth
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60 * 24

    # Encryption at rest for Meta access tokens
    fernet_key: str

    # Meta / Facebook Graph API
    meta_app_id: str
    meta_app_secret: str
    meta_redirect_uri: str
    meta_oauth_scopes: str = "pages_show_list,instagram_basic,instagram_manage_insights,business_management"
    meta_graph_api_version: str = "v21.0"

    # CORS
    frontend_url: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
