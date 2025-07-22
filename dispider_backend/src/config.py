from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings
    """
    APP_TITLE: str = "Dispider"
    APP_DESCRIPTION: str = "Dispider Backend API"
    SECRET_KEY: str
    DEBUG: bool = False
    ALGORITHM: str = "HS256"
    CONTAINER_HOST: str = "http://localhost"

    # Database settings
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    DATABASE_URL: str

    # Redis settings
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_URL: str

    # Docker settings
    DOCKER_SPACE: str
    DOCKER_SPACE_OUTER: str
    # DOCKER_HOST: str
    API_BASE_URL: str
    # Proxy settings
    PROXY_URL: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings() 