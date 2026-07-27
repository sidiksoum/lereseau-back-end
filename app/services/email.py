"""
Service Email — LeRéseau
Gère l'envoi des emails transactionnels via MailerSend API ou SMTP.
Utilise httpx pour l'API MailerSend et fastapi-mail pour le SMTP de secours.
"""

import random
import string
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
import httpx

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from jinja2 import Environment, FileSystemLoader

from app.core.config import settings

# ─── Configuration SMTP (Secours) ───────────────────────────────────────────
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


# ─── MailerSend API Client ───────────────────────────────────────────────────

async def send_email_api(to_email: str, to_name: str, subject: str, html_body: str) -> bool:
    """
    Envoie un email en utilisant l'API HTTPS de MailerSend (évite le blocage des ports SMTP).
    """
    url = "https://api.mailersend.com/v1/email"
    headers = {
        "Authorization": f"Bearer {settings.MAILERSEND_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": {
            "email": settings.MAIL_FROM,
            "name": settings.MAIL_FROM_NAME
        },
        "to": [
            {
                "email": to_email,
                "name": to_name
            }
        ],
        "subject": subject,
        "html": html_body
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=10.0)
            if response.status_code in [200, 202]:
                print(f"[MAILERSEND] Email envoyé avec succès à {to_email} (Status: {response.status_code})")
                return True
            else:
                print(f"[MAILERSEND ERROR] Échec de l'envoi à {to_email} : {response.status_code} - {response.text}")
                return False
    except Exception as e:
        print(f"[MAILERSEND ERROR] Erreur lors de l'envoi de l'email : {e}")
        return False


# ─── Envoi d'emails (Fonctions globales appelées par l'API) ───────────────────

async def send_otp_verification_email(
    to_email: str,
    first_name: str,
    otp_code: str,
) -> None:
    """
    Envoie l'email de vérification OTP après création de compte.
    """
    template = jinja_env.get_template("otp_verification.html")
    first_name_str = first_name or "Utilisateur"
    html_body = template.render(
        first_name=first_name_str,
        otp_code=otp_code,
        expire_minutes=settings.OTP_EXPIRE_MINUTES,
    )
    
    subject = "🔐 Votre code de vérification LeRéseau"

    # Si la clé API de MailerSend est configurée, on l'utilise en priorité
    if settings.MAILERSEND_API_KEY and settings.MAILERSEND_API_KEY.strip():
        await send_email_api(to_email, first_name_str, subject, html_body)
    else:
        # Fallback sur l'envoi SMTP (utile pour les tests locaux)
        print("[EMAIL] MailerSend non configuré, utilisation du fallback SMTP...")
        message = MessageSchema(
            subject=subject,
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
    first_name_str = first_name or "Utilisateur"
    html_body = template.render(
        first_name=first_name_str,
        email=to_email,
        otp_code=otp_code,
        expire_minutes=settings.OTP_EXPIRE_MINUTES,
    )
    
    subject = "🔑 Réinitialisation de votre mot de passe LeRéseau"

    if settings.MAILERSEND_API_KEY and settings.MAILERSEND_API_KEY.strip():
        await send_email_api(to_email, first_name_str, subject, html_body)
    else:
        print("[EMAIL] MailerSend non configuré, utilisation du fallback SMTP...")
        message = MessageSchema(
            subject=subject,
            recipients=[to_email],
            body=html_body,
            subtype=MessageType.html,
        )
        fm = FastMail(conf)
        await fm.send_message(message)
