from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.api.dependencies.auth import get_db, get_current_active_user, get_current_user
from app.models.opportunity import Opportunity
from app.models.user import User
from app.schemas.opportunity import OpportunityCreate, OpportunityResponse

router = APIRouter()

@router.get("/", response_model=List[OpportunityResponse])
def list_opportunities(
    db: Session = Depends(get_db)
):
    return db.query(Opportunity).filter(Opportunity.isActive == True).order_by(Opportunity.createdAt.desc()).all()

@router.post("/me/publish", response_model=OpportunityResponse)
def publish_opportunity(
    *,
    db: Session = Depends(get_db),
    op_in: OpportunityCreate,
    current_user: User = Depends(get_current_active_user)
):
    if current_user.roleType.value != "institution":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Seules les institutions peuvent publier des bourses directement."
        )
        
    new_op = Opportunity(**op_in.model_dump(), authorId=current_user.id)
    if current_user.isPremium:
        new_op.isBoosted = True
        
    db.add(new_op)
    db.commit()
    db.refresh(new_op)
    return new_op

@router.get("/{id}", response_model=OpportunityResponse)
def get_opportunity(id: str, db: Session = Depends(get_db)):
    op = db.query(Opportunity).filter(Opportunity.id == id).first()
    if not op:
         raise HTTPException(status_code=404, detail="Opportunity not found")
    return op
