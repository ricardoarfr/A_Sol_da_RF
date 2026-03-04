from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Z-API credentials
    ZAPI_INSTANCE_ID: str = ""
    ZAPI_TOKEN: str = ""
    ZAPI_CLIENT_TOKEN: str = ""

    # Produttivo API
    PRODUTTIVO_BASE_URL: str = "https://app.produttivo.com.br"
    PRODUTTIVO_ACCOUNT_ID: str = "20834"
    PRODUTTIVO_SESSION_COOKIE: str = ""

    # App
    WEBHOOK_SECRET: str = ""
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
