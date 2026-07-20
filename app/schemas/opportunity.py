from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from app.models.opportunity import OpportunityTypeEnum

class Attachment(BaseModel):
    type: str
    url: str
    name: Optional[str] = None
    order: Optional[int] = None

class OpportunityBase(BaseModel):
    type: OpportunityTypeEnum
    title: str
    organization: str
    fundingSource: Optional[str] = None
    targetAudience: Optional[str] = None
    
    attachments: Optional[List[Attachment]] = None
    location: Optional[str] = None
    amount: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None
    
    missions: Optional[Any] = None
    benefits: Optional[Any] = None
    fundingDetails: Optional[Any] = None
    eligibilityRequirements: Optional[Any] = None
    selectionCriteria: Optional[Any] = None
    applicationProcess: Optional[Any] = None
    importantDates: Optional[Any] = None
    contactPerson: Optional[Any] = None
    requiredDocuments: Optional[Any] = None
    requirements: Optional[Any] = None
    
    domain: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    
    deadline: Optional[datetime] = None
    contactInfo: Optional[str] = None
    applyUrl: Optional[str] = None

class OpportunityCreate(OpportunityBase):
    isPremiumOnly: Optional[bool] = False
    isBoosted: Optional[bool] = False
    isActive: Optional[bool] = True

class OpportunityResponse(OpportunityBase):
    id: str
    authorId: Optional[str] = None
    isPremiumOnly: bool
    isBoosted: bool
    isActive: bool
    createdAt: datetime
    aiMatchScore: Optional[int] = None

    class Config:
        from_attributes = True
