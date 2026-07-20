from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.api.dependencies.auth import get_db, require_role
from app.models.user import User, StatusEnum, RoleEnum, RoleTypeEnum
from app.schemas.user import UserResponse, UserCreate
from app.core import security
from sqlalchemy import desc

router = APIRouter()

@router.get("/", response_model=List[UserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
    role: Optional[str] = None,
    current_admin: User = Depends(require_role("ADMIN"))
):
    query = db.query(User).order_by(desc(User.reportsCount))
    if role:
        query = query.filter(User.roleType == role)
    return query.offset(skip).limit(limit).all()

@router.post("/create", response_model=UserResponse)
def create_admin_user(
    user_in: UserCreate,
    role: RoleEnum,
    db: Session = Depends(get_db),
    current_super_admin: User = Depends(require_role("SUPER_ADMIN"))
):
    user_exists = db.query(User).filter(User.email == user_in.email).first()
    if user_exists:
        raise HTTPException(status_code=400, detail="User already exists")
        
    hashed_password = security.get_password_hash(user_in.password)
    
    new_user = User(
        email=user_in.email,
        passwordHash=hashed_password,
        firstName=user_in.firstName,
        lastName=user_in.lastName,
        roleType=user_in.roleType,
        role=role,
        status=StatusEnum.VERIFIED
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.patch("/{id}/status", response_model=UserResponse)
def change_user_status(
    id: str,
    new_status: StatusEnum,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("ADMIN"))
):
    user = db.query(User).filter(User.id == id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    
    user.status = new_status
    db.commit()
    db.refresh(user)
    return user

@router.delete("/{id}")
def delete_user(
    id: str,
    db: Session = Depends(get_db),
    current_super_admin: User = Depends(require_role("SUPER_ADMIN"))
):
    user = db.query(User).filter(User.id == id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()
    return {"ok": True}

@router.get("/stats")
def get_user_stats(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("ADMIN"))
):
    total_users = db.query(User).count()
    total_students = db.query(User).filter(User.roleType == RoleTypeEnum.student).count()
    total_professionals = db.query(User).filter(User.roleType == RoleTypeEnum.professional).count()
    total_institutions = db.query(User).filter(User.roleType == RoleTypeEnum.institution).count()
    
    # A certified mentor is a professional with nineaUploaded == True
    total_certified_mentors = db.query(User).filter(
        User.roleType == RoleTypeEnum.professional, 
        User.nineaUploaded == True
    ).count()
    
    return {
        "totalUsers": total_users,
        "totalStudents": total_students,
        "totalProfessionals": total_professionals,
        "totalInstitutions": total_institutions,
        "totalCertifiedMentors": total_certified_mentors
    }

# --- Certifications (Mentors & Institutions) ---
@router.get("/certifications/pending", response_model=List[UserResponse])
def get_pending_certifications(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("ADMIN"))
):
    # kycDocumentUrl is "PENDING_REQUEST" AND nineaUploaded is False means pending request
    return db.query(User).filter(
        User.kycDocumentUrl == "PENDING_REQUEST",
        User.nineaUploaded == False
    ).order_by(desc(User.createdAt)).all()

@router.patch("/certifications/{user_id}/approve")
def approve_certification(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("ADMIN"))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "Utilisateur introuvable")
    
    if user.kycDocumentUrl != "PENDING_REQUEST":
        raise HTTPException(400, "Cet utilisateur n'a pas de demande de certification en attente.")
        
    user.nineaUploaded = True # Means Approved
    user.kycDocumentUrl = "APPROVED"
    db.commit()
    return {"ok": True, "message": "Certification approuvée"}

@router.patch("/certifications/{user_id}/reject")
def reject_certification(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("ADMIN"))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "Utilisateur introuvable")
    
    # We allow revoking an already active certification OR rejecting a pending request
    user.kycDocumentUrl = None
    user.nineaUploaded = False
    db.commit()
    return {"ok": True, "message": "Certification rejetée"}

# --- Premium Management ---
@router.get("/premium/pending", response_model=List[UserResponse])
def get_pending_premium_requests(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("ADMIN"))
):
    return db.query(User).filter(
        User.premiumPaymentMethod == "PENDING_REQUEST",
        User.isPremium == False
    ).order_by(desc(User.createdAt)).all()

@router.patch("/premium/{user_id}/approve")
def approve_premium(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("ADMIN"))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "Utilisateur introuvable")
    
    if user.premiumPaymentMethod != "PENDING_REQUEST":
        raise HTTPException(400, "Cet utilisateur n'a pas de demande en attente.")
        
    user.isPremium = True
    user.premiumPaymentMethod = "APPROVED"
    db.commit()
    return {"ok": True, "message": "Compte Premium activé."}

@router.patch("/premium/{user_id}/reject")
def reject_premium(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("ADMIN"))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "Utilisateur introuvable")
    
    # We allow revoking an already active premium OR rejecting a pending request
    user.isPremium = False
    user.premiumPaymentMethod = None
    db.commit()
    return {"ok": True, "message": "Compte Premium refusé ou désactivé."}
