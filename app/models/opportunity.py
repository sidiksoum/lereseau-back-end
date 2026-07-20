from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
import enum
import uuid
from datetime import datetime, timezone
from app.db.base import Base

class OpportunityTypeEnum(str, enum.Enum):
    SCHOLARSHIP = "SCHOLARSHIP"
    INTERNSHIP = "INTERNSHIP"
    JOB = "JOB"

def generate_uuid():
    return str(uuid.uuid4())

class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    authorId = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    
    type = Column(Enum(OpportunityTypeEnum), nullable=False)
    title = Column(String, nullable=False)
    organization = Column(String, nullable=False)
    fundingSource = Column(String, nullable=True)
    targetAudience = Column(String, nullable=True)
    
    attachments = Column(JSON, nullable=True)
    location = Column(String, nullable=True)
    amount = Column(String, nullable=True)
    duration = Column(String, nullable=True)
    description = Column(String, nullable=True)
    
    missions = Column(JSON, nullable=True)
    benefits = Column(JSON, nullable=True)
    fundingDetails = Column(JSON, nullable=True)
    eligibilityRequirements = Column(JSON, nullable=True)
    selectionCriteria = Column(JSON, nullable=True)
    applicationProcess = Column(JSON, nullable=True)
    importantDates = Column(JSON, nullable=True)
    contactPerson = Column(JSON, nullable=True)
    requiredDocuments = Column(JSON, nullable=True)
    requirements = Column(JSON, nullable=True)
    
    domain = Column(String, nullable=True)
    category = Column(String, nullable=True)
    tags = Column(JSON, nullable=True)
    
    deadline = Column(DateTime(timezone=True), nullable=True)
    contactInfo = Column(String, nullable=True)
    applyUrl = Column(String, nullable=True)
    
    isPremiumOnly = Column(Boolean, default=False)
    isBoosted = Column(Boolean, default=False)
    isActive = Column(Boolean, default=True)

    createdAt = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    author = relationship("User")
