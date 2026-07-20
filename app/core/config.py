from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "LeRéseau API"
    VERSION: str = "3.0.0"
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    JWT_EXPIRATION: Optional[str] = None
    
    # Database
    DATABASE_URL: str
    
    # AWS / S3 (For documents)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = None
    AWS_S3_BUCKET_NAME: Optional[str] = None
    
    # Cloudinary (Alternative storage)
    CLOUDINARY_CLOUD_NAME: Optional[str] = None
    CLOUDINARY_API_KEY: Optional[str] = None
    CLOUDINARY_API_SECRET: Optional[str] = None
    CLOUDINARY_URL: Optional[str] = None
    
    # Stripe (Premium)
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    # Local Payment Gateways
    CINETPAY_APIKEY: Optional[str] = None
    CINETPAY_SITE_ID: Optional[str] = None

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ]
    
    # OpenRouter API (Chatbot)
    OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "meta-llama/llama-3.1-8b-instruct:free"

    # ─── SMTP — Email noreply ──────────────────────────────────────────────────
    MAIL_USERNAME: str = "lereseau2026@gmail.com"
    MAIL_PASSWORD: str = "VOTRE_APP_PASSWORD_ICI"
    MAIL_FROM: str = "lereseau2026@gmail.com"
    MAIL_FROM_NAME: str = "LeRéseau — No Reply"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True
    OTP_EXPIRE_MINUTES: int = 10

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

settings = Settings()
