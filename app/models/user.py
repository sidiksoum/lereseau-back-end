from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
import enum
import uuid
from datetime import datetime, timezone
from app.db.base import Base

class RoleEnum(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"

class RoleTypeEnum(str, enum.Enum):
    student = "student"
    professional = "professional"
    institution = "institution"

class StatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    BANNED = "BANNED"
    SHADOWBANNED = "SHADOWBANNED"

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    passwordHash = Column(String, nullable=False)
    firstName = Column(String, nullable=True)
    lastName = Column(String, nullable=True)
    
    roleType = Column(Enum(RoleTypeEnum), default=RoleTypeEnum.student)
    role = Column(Enum(RoleEnum), default=RoleEnum.USER)
    
    avatarUrl = Column(String, nullable=True)
    coverUrl = Column(String, nullable=True)
    status = Column(Enum(StatusEnum), default=StatusEnum.VERIFIED)
    about = Column(String, nullable=True)

    # Student specific
    educationLevel = Column(String, nullable=True)
    studyDomain = Column(String, nullable=True)

    # Professional specific
    jobTitle = Column(String, nullable=True)
    workDomain = Column(String, nullable=True)

    # Institution specific
    institutionType = Column(String, nullable=True)
    institutionDetails = Column(String, nullable=True)
    nineaUploaded = Column(Boolean, default=False)

    points = Column(Integer, default=0)
    reportsCount = Column(Integer, default=0)
    
    kycDocumentUrl = Column(String, nullable=True)
    
    # Premium
    isPremium = Column(Boolean, default=False)
    stripeCustomerId = Column(String, nullable=True)
    premiumReceiptUrl = Column(String, nullable=True)
    premiumPaymentMethod = Column(String, nullable=True)
    premiumAmount = Column(String, nullable=True)

    isEmailVerified = Column(Boolean, default=False, nullable=False)
    refreshToken = Column(String, nullable=True)

    skills = Column(JSON, nullable=True)
    location = Column(String, nullable=True)
    linkedin = Column(String, nullable=True)
    
    def default_settings():
        return {
            "emailNotifications": True,
            "darkMode": "dark",
            "profileVisibility": "PUBLIC"
        }

    settings = Column(JSON, nullable=True, default=default_settings)
    
    lastActive = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    createdAt = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    experiences = relationship("Experience", back_populates="user", cascade="all, delete-orphan")
    educations = relationship("Education", back_populates="user", cascade="all, delete-orphan")

class Experience(Base):
    __tablename__ = "experiences"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"))
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    startDate = Column(String, nullable=False)
    endDate = Column(String, nullable=True)
    description = Column(String, nullable=True)

    user = relationship("User", back_populates="experiences")

class Education(Base):
    __tablename__ = "educations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"))
    school = Column(String, nullable=False)
    degree = Column(String, nullable=False)
    startDate = Column(String, nullable=False)
    endDate = Column(String, nullable=True)
    description = Column(String, nullable=True)

    user = relationship("User", back_populates="educations")
