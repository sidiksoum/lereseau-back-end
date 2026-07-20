"""
Schémas Pydantic pour les opérations OTP
"""

from pydantic import BaseModel, EmailStr, Field


class OTPVerifyRequest(BaseModel):
    """Corps de la requête POST /auth/verify-email"""
    email: EmailStr
    otp_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class OTPVerifyResetRequest(BaseModel):
    """Corps de la requête POST /auth/verify-reset-otp"""
    email: EmailStr
    otp_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class ForgotPasswordRequest(BaseModel):
    """Corps de la requête POST /auth/forgot-password (et /auth/resend-otp)"""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Corps de la requête POST /auth/reset-password"""
    reset_token: str
    new_password: str = Field(..., min_length=8)
