from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.dependencies.auth import get_db, require_role
from app.models.user import User, RoleTypeEnum, StatusEnum

router = APIRouter()

@router.get("/")
def get_pending_certifications(db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    mentors = db.query(User).filter(User.roleType == RoleTypeEnum.professional, User.kycDocumentUrl.isnot(None), User.nineaUploaded == False).all()
    institutions = db.query(User).filter(User.roleType == RoleTypeEnum.institution, User.kycDocumentUrl.isnot(None), User.nineaUploaded == False).all()
    premium = db.query(User).filter(User.premiumReceiptUrl.isnot(None), User.isPremium == False).all()
    
    return {
        "mentors": mentors,
        "institutions": institutions,
        "premium": premium
    }

@router.patch("/{id}/certify")
def certify_user(id: str, is_approved: bool, db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    user = db.query(User).filter(User.id == id).first()
    if not user: raise HTTPException(404, "Utilisateur introuvable")
    
    if is_approved:
        user.nineaUploaded = True
        user.status = StatusEnum.VERIFIED
    else:
        user.kycDocumentUrl = None
        user.nineaUploaded = False
        
    db.commit()
    return {"ok": True, "user_id": user.id, "certified": user.nineaUploaded}

@router.patch("/{id}/premium")
def validate_premium(id: str, is_approved: bool, db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    user = db.query(User).filter(User.id == id).first()
    if not user: raise HTTPException(404, "Utilisateur introuvable")
    
    if is_approved:
        user.isPremium = True
    else:
        user.premiumReceiptUrl = None 
        user.premiumAmount = None
        
    db.commit()
    return {"ok": True, "user_id": user.id, "isPremium": user.isPremium}
