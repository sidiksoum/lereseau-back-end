"""
Routes d'authentification — LeRéseau
Inclut :
  - Inscription avec envoi OTP email
  - Vérification OTP (activation du compte)
  - Connexion (réservée aux comptes vérifiés)
  - Refresh / Logout
  - Mot de passe oublié : demande OTP → vérification → reset
"""

from datetime import timedelta, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_db, get_current_user
from app.core import security
from app.core.config import settings
from app.models.user import User
from app.models.otp import OTPCode, OTPPurposeEnum
from app.schemas.user import UserCreate, UserResponse, Token
from app.schemas.otp import (
    OTPVerifyRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    OTPVerifyResetRequest,
)
from app.services.email import (
    send_otp_verification_email,
    send_password_reset_email,
    generate_otp,
    hash_otp,
    verify_otp_hash,
    compute_expiry,
)

router = APIRouter()


# ─── Helpers internes ──────────────────────────────────────────────────────────

def _invalidate_previous_otps(db: Session, email: str, purpose: OTPPurposeEnum) -> None:
    """Marque tous les OTPs précédents du même email/purpose comme utilisés."""
    db.query(OTPCode).filter(
        OTPCode.email == email,
        OTPCode.purpose == purpose,
        OTPCode.is_used == False,
    ).update({"is_used": True})
    db.commit()


def _create_otp_record(db: Session, email: str, purpose: OTPPurposeEnum) -> str:
    """Génère, hash et persiste un nouvel OTP. Retourne le code en clair."""
    plain_otp = generate_otp()
    otp_record = OTPCode(
        email=email,
        code=hash_otp(plain_otp),
        purpose=purpose,
        expires_at=compute_expiry(),
    )
    db.add(otp_record)
    db.commit()
    return plain_otp


def _validate_otp(db: Session, email: str, plain_otp: str, purpose: OTPPurposeEnum) -> OTPCode:
    """
    Vérifie qu'un OTP valide (non expiré, non utilisé) existe pour cet email.
    Lève HTTPException 400 si invalide/expiré.
    """
    records = (
        db.query(OTPCode)
        .filter(
            OTPCode.email == email,
            OTPCode.purpose == purpose,
            OTPCode.is_used == False,
        )
        .order_by(OTPCode.created_at.desc())
        .all()
    )

    for record in records:
        # Vérifier expiration
        exp = record.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > exp:
            continue
        # Vérifier le hash
        if verify_otp_hash(plain_otp, record.code):
            return record

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Code OTP invalide ou expiré. Veuillez en demander un nouveau.",
    )


# ─── 1. Inscription ────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Crée un compte (non vérifié) et envoie un OTP à 6 chiffres par email.
    Le compte reste inaccessible jusqu'à la vérification OTP.
    """
    # Vérifier doublon
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un utilisateur avec cet email existe déjà.",
        )

    # Créer l'utilisateur (non vérifié)
    hashed_password = security.get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email,
        passwordHash=hashed_password,
        firstName=user_in.firstName,
        lastName=user_in.lastName,
        phone=user_in.phone,
        roleType=user_in.roleType,
        isEmailVerified=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Invalider les éventuels anciens OTP et créer le nouveau
    _invalidate_previous_otps(db, user_in.email, OTPPurposeEnum.EMAIL_VERIFICATION)
    plain_otp = _create_otp_record(db, user_in.email, OTPPurposeEnum.EMAIL_VERIFICATION)

    # Envoi asynchrone en arrière-plan
    background_tasks.add_task(
        send_otp_verification_email,
        to_email=user_in.email,
        first_name=user_in.firstName or "Utilisateur",
        otp_code=plain_otp,
    )

    return {
        "detail": "Compte créé avec succès. Un code de vérification a été envoyé à votre adresse email.",
        "email": user_in.email,
        "next_step": "Veuillez vérifier votre email et saisir votre code OTP.",
    }


# ─── 2. Vérification OTP (activation du compte) ────────────────────────────────

@router.post("/verify-email", status_code=status.HTTP_200_OK)
def verify_email(payload: OTPVerifyRequest, db: Session = Depends(get_db)):
    """
    Vérifie l'OTP reçu par email après l'inscription.
    Active le compte si le code est valide.
    """
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Aucun compte trouvé pour cet email.")

    if user.isEmailVerified:
        return {"detail": "Votre email est déjà vérifié. Vous pouvez vous connecter."}

    otp_record = _validate_otp(db, payload.email, payload.otp_code, OTPPurposeEnum.EMAIL_VERIFICATION)

    # Marquer OTP comme utilisé + activer le compte
    otp_record.is_used = True
    user.isEmailVerified = True
    db.commit()

    return {
        "detail": "Email vérifié avec succès ! Vous pouvez maintenant vous connecter.",
        "email": payload.email,
    }


# ─── 3. Renvoi OTP (si l'utilisateur n'a pas reçu le code) ────────────────────

@router.post("/resend-otp", status_code=status.HTTP_200_OK)
async def resend_otp(
    payload: ForgotPasswordRequest,  # contient juste `email`
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Renvoie un nouveau code OTP de vérification d'email.
    Invalide l'ancien OTP.
    """
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        # Sécurité : ne pas révéler si l'email existe ou non
        return {"detail": "Si cet email est enregistré, un nouveau code a été envoyé."}

    if user.isEmailVerified:
        raise HTTPException(status_code=400, detail="Cet email est déjà vérifié.")

    _invalidate_previous_otps(db, payload.email, OTPPurposeEnum.EMAIL_VERIFICATION)
    plain_otp = _create_otp_record(db, payload.email, OTPPurposeEnum.EMAIL_VERIFICATION)

    background_tasks.add_task(
        send_otp_verification_email,
        to_email=payload.email,
        first_name=user.firstName or "Utilisateur",
        otp_code=plain_otp,
    )

    return {"detail": "Un nouveau code de vérification a été envoyé à votre adresse email."}


# ─── 4. Connexion ──────────────────────────────────────────────────────────────

@router.post("/login")
def login(
    response: Response,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    Connexion utilisateur. Refusée si l'email n'est pas encore vérifié.
    """
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not security.verify_password(form_data.password, user.passwordHash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.isEmailVerified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Veuillez vérifier votre adresse email avant de vous connecter. Consultez votre boîte mail.",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )
    refresh_token = security.create_access_token(
        data={"sub": user.id}, expires_delta=timedelta(days=30)
    )
    user.refreshToken = refresh_token
    db.commit()

    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=True, samesite="lax")
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, samesite="lax")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "roleType": user.roleType,
        },
    }


# ─── 5. Refresh Token ──────────────────────────────────────────────────────────

@router.post("/refresh")
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token manquant")

    try:
        from jose import jwt, JWTError
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.refreshToken != token:
        raise HTTPException(status_code=401, detail="Token expiré ou révoqué")

    new_access_token = security.create_access_token(data={"sub": user.id})
    response.set_cookie(key="access_token", value=new_access_token, httponly=True, secure=True, samesite="lax")

    return {"access_token": new_access_token, "token_type": "bearer"}


# ─── 6. Logout ─────────────────────────────────────────────────────────────────

@router.post("/logout")
def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.refreshToken = None
    db.commit()
    response.delete_cookie("refresh_token")
    response.delete_cookie("access_token")
    return {"detail": "Déconnexion réussie"}


# ═══════════════════════════════════════════════════════════════════════════════
#  MOT DE PASSE OUBLIÉ — Flux en 3 étapes
#  Étape 1 → /forgot-password       : saisie email, envoi OTP
#  Étape 2 → /verify-reset-otp      : vérification OTP, retourne un reset_token
#  Étape 3 → /reset-password        : nouveau mot de passe avec le reset_token
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Étape 1 — Mot de passe oublié.
    L'utilisateur saisit son email. Le système envoie un OTP de réinitialisation.
    (Réponse neutre pour éviter l'énumération d'emails)
    """
    user = db.query(User).filter(User.email == payload.email).first()

    if user:
        _invalidate_previous_otps(db, payload.email, OTPPurposeEnum.PASSWORD_RESET)
        plain_otp = _create_otp_record(db, payload.email, OTPPurposeEnum.PASSWORD_RESET)

        background_tasks.add_task(
            send_password_reset_email,
            to_email=payload.email,
            first_name=user.firstName or "Utilisateur",
            otp_code=plain_otp,
        )

    return {
        "detail": "Si cet email est associé à un compte, un code de réinitialisation a été envoyé.",
    }


@router.post("/verify-reset-otp", status_code=status.HTTP_200_OK)
def verify_reset_otp(payload: OTPVerifyResetRequest, db: Session = Depends(get_db)):
    """
    Étape 2 — Vérification de l'OTP de réinitialisation.
    Retourne un token de session temporaire (reset_token) valable 15 minutes
    pour autoriser le changement de mot de passe.
    """
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Aucun compte trouvé pour cet email.")

    otp_record = _validate_otp(db, payload.email, payload.otp_code, OTPPurposeEnum.PASSWORD_RESET)

    # Marquer OTP comme utilisé
    otp_record.is_used = True
    db.commit()

    # Générer un reset_token JWT valable 15 minutes
    reset_token = security.create_access_token(
        data={"sub": user.id, "purpose": "password_reset"},
        expires_delta=timedelta(minutes=15),
    )

    return {
        "detail": "Code vérifié avec succès. Vous pouvez maintenant choisir un nouveau mot de passe.",
        "reset_token": reset_token,
    }


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Étape 3 — Définition du nouveau mot de passe.
    Nécessite le reset_token obtenu à l'étape 2.
    """
    try:
        from jose import jwt, JWTError
        token_data = jwt.decode(
            payload.reset_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        if token_data.get("purpose") != "password_reset":
            raise HTTPException(status_code=400, detail="Token invalide.")
        user_id: str = token_data.get("sub")
    except JWTError:
        raise HTTPException(status_code=400, detail="Token expiré ou invalide. Recommencez la procédure.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 8 caractères.")

    user.passwordHash = security.get_password_hash(payload.new_password)
    user.refreshToken = None  # Invalider toutes les sessions actives
    db.commit()

    return {"detail": "Mot de passe réinitialisé avec succès. Vous pouvez maintenant vous connecter."}
