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

    # WhatsApp service (Baileys/Node.js)
    WHATSAPP_SERVICE_URL: str = "http://localhost:3000"

    # Database
    DATABASE_URL: str = ""

    # App
    WEBHOOK_SECRET: str = ""
    LOG_LEVEL: str = "INFO"
    ADMIN_TOKEN: str = "admin"  # Override in .env with a strong token

    class Config:
        env_file = ".env"


settings = Settings()
