from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

# FeedPost
class FeedPostCreate(BaseModel):
    title: str
    content: str
    type: str = "TEXT" # "IMAGE", "VIDEO", "GALLERY" (will map to IMAGE array)
    attachments: Optional[List[dict]] = None

# Opportunity
class OpportunityCreate(BaseModel):
    title: str
    organization: str
    domain: Optional[str] = None
    amount: str
    deadline: str
    fundingSource: Optional[str] = None
    targetAudience: Optional[str] = None
    description: Optional[str] = None
    eligibilityRequirements: Optional[str] = None
    applicationProcess: Optional[str] = None
    selectionCriteria: Optional[str] = None
    contactEmail: str
    contactPerson: Optional[str] = None
    applyUrl: Optional[str] = None
    bannerImg: Optional[dict] = None

# Document / Library
class DocumentCreate(BaseModel):
    title: str
    domain: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    pagesCount: Optional[int] = None
    format: Optional[str] = None
    author: Optional[str] = None
    publicationYear: Optional[int] = None
    publisher: Optional[str] = None
    associatedCourse: Optional[str] = None
    edition: Optional[str] = None
    referenceKey: Optional[str] = None
    tags: Optional[str] = None
    toc: Optional[str] = None
    fileData: Optional[dict] = None
