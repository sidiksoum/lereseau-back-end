"""
Service Email — LeRéseau
Gère l'envoi des emails transactionnels via SMTP Gmail (noreply).
Utilise fastapi-mail avec des templates Jinja2.
"""

import random
import string
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from jinja2 import Environment, FileSystemLoader

from app.core.config import settings


# ─── Configuration SMTP ───────────────────────────────────────────────────────
conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=settings.USE_CREDENTIALS,
    VALIDATE_CERTS=settings.VALIDATE_CERTS,
)

# ─── Jinja2 — chargement des templates HTML ───────────────────────────────────
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


# ─── Helpers ──────────────────────────────────────────────────────────────────

def generate_otp(length: int = 6) -> str:
    """Génère un OTP numérique aléatoire à N chiffres."""
    return "".join(random.choices(string.digits, k=length))


def hash_otp(otp: str) -> str:
    """Hash SHA-256 de l'OTP avant stockage en base."""
    return hashlib.sha256(otp.encode()).hexdigest()


def verify_otp_hash(plain_otp: str, hashed_otp: str) -> bool:
    """Vérifie si un OTP saisi correspond au hash stocké."""
    return hashlib.sha256(plain_otp.encode()).hexdigest() == hashed_otp


def compute_expiry() -> datetime:
    """Calcule la date d'expiration de l'OTP (maintenant + OTP_EXPIRE_MINUTES)."""
    return datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)


# ─── Envoi d'emails ───────────────────────────────────────────────────────────

async def send_otp_verification_email(
    to_email: str,
    first_name: str,
    otp_code: str,
) -> None:
    """
    Envoie l'email de vérification OTP après création de compte.
    """
    template = jinja_env.get_template("otp_verification.html")
    html_body = template.render(
        first_name=first_name or "Utilisateur",
        otp_code=otp_code,
        expire_minutes=settings.OTP_EXPIRE_MINUTES,
    )

    message = MessageSchema(
        subject="🔐 Votre code de vérification LeRéseau",
        recipients=[to_email],
        body=html_body,
        subtype=MessageType.html,
    )

    fm = FastMail(conf)
    await fm.send_message(message)


async def send_password_reset_email(
    to_email: str,
    first_name: str,
    otp_code: str,
) -> None:
    """
    Envoie l'email de réinitialisation de mot de passe avec OTP.
    """
    template = jinja_env.get_template("otp_password_reset.html")
    html_body = template.render(
        first_name=first_name or "Utilisateur",
        email=to_email,
        otp_code=otp_code,
        expire_minutes=settings.OTP_EXPIRE_MINUTES,
    )

    message = MessageSchema(
        subject="🔑 Réinitialisation de votre mot de passe LeRéseau",
        recipients=[to_email],
        body=html_body,
        subtype=MessageType.html,
    )

    fm = FastMail(conf)
    await fm.send_message(message)
