from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime
from app.models.user import RoleEnum, RoleTypeEnum, StatusEnum

class ExperienceBase(BaseModel):
    title: str
    company: str
    startDate: str
    endDate: Optional[str] = None
    description: Optional[str] = None

class ExperienceCreate(ExperienceBase):
    pass

class ExperienceUpdate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    description: Optional[str] = None

class ExperienceResource(ExperienceBase):
    id: int
    user_id: str
    
    class Config:
        from_attributes = True

class EducationBase(BaseModel):
    school: str
    degree: str
    startDate: str
    endDate: Optional[str] = None
    description: Optional[str] = None

class EducationCreate(EducationBase):
    pass

class EducationUpdate(BaseModel):
    school: Optional[str] = None
    degree: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    description: Optional[str] = None

class EducationResource(EducationBase):
    id: int
    user_id: str

    class Config:
        from_attributes = True

class UserSettings(BaseModel):
    emailNotifications: bool = True
    darkMode: str = "dark"
    profileVisibility: str = "PUBLIC"

class UserBase(BaseModel):
    email: EmailStr
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    phone: Optional[str] = None
    roleType: RoleTypeEnum = RoleTypeEnum.student

# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str

# Properties to receive via API on update
class UserUpdate(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    phone: Optional[str] = None
    avatarUrl: Optional[str] = None
    coverUrl: Optional[str] = None
    about: Optional[str] = None
    
    educationLevel: Optional[str] = None
    studyDomain: Optional[str] = None
    jobTitle: Optional[str] = None
    workDomain: Optional[str] = None
    institutionType: Optional[str] = None
    institutionDetails: Optional[str] = None
    nineaUploaded: Optional[bool] = None
    
    skills: Optional[Any] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    settings: Optional[UserSettings] = None

class UserInDBBase(UserBase):
    id: str
    role: RoleEnum
    avatarUrl: Optional[str] = None
    coverUrl: Optional[str] = None
    status: StatusEnum
    about: Optional[str] = None
    
    educationLevel: Optional[str] = None
    studyDomain: Optional[str] = None
    jobTitle: Optional[str] = None
    workDomain: Optional[str] = None
    institutionType: Optional[str] = None
    institutionDetails: Optional[str] = None
    nineaUploaded: Optional[bool] = None

    points: Optional[int] = 0
    reportsCount: Optional[int] = 0
    isPremium: bool
    
    kycDocumentUrl: Optional[str] = None
    premiumReceiptUrl: Optional[str] = None
    premiumPaymentMethod: Optional[str] = None
    premiumAmount: Optional[str] = None
    
    skills: Optional[Any] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    settings: Optional[Any] = None
    
    lastActive: datetime
    createdAt: datetime

    class Config:
        from_attributes = True

# Additional properties to return via API
class UserResponse(UserInDBBase):
    experiences: List[ExperienceResource] = []
    educations: List[EducationResource] = []

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None
