"""
Modèle OTP (One-Time Password)
Stocke les codes temporaires pour :
  - Vérification d'email lors de l'inscription
  - Réinitialisation de mot de passe
"""

from sqlalchemy import Column, String, DateTime, Enum, Boolean
from datetime import datetime, timezone
import enum
import uuid

from app.db.base import Base


def generate_uuid():
    return str(uuid.uuid4())


class OTPPurposeEnum(str, enum.Enum):
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    PASSWORD_RESET = "PASSWORD_RESET"


class OTPCode(Base):
    __tablename__ = "otp_codes"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)

    # Email auquel l'OTP est lié (clé de recherche)
    email = Column(String, nullable=False, index=True)

    # Code OTP à 6 chiffres (hashé)
    code = Column(String, nullable=False)

    # Objet de l'OTP
    purpose = Column(Enum(OTPPurposeEnum), nullable=False)

    # OTP utilisé ?
    is_used = Column(Boolean, default=False, nullable=False)

    # Dates
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)
