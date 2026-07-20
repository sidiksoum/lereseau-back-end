from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
import enum
import uuid
from datetime import datetime, timezone
from app.db.base import Base

class DocumentStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

def generate_uuid():
    return str(uuid.uuid4())

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    authorId = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    title = Column(String, nullable=False)
    category = Column(String, nullable=False)
    description = Column(String, nullable=True)
    
    authorDetails = Column(JSON, nullable=True)
    publicationYear = Column(Integer, nullable=True)
    publisher = Column(String, nullable=True)
    edition = Column(String, nullable=True)
    referenceKey = Column(String, nullable=True)
    associatedCourse = Column(String, nullable=True)
    
    tags = Column(JSON, nullable=True)
    pagesCount = Column(Integer, nullable=True)
    language = Column(String, default="Français")
    format = Column(String, default="PDF")
    tableOfContents = Column(JSON, nullable=True)
    
    fileUrl = Column(String, nullable=True)
    previewUrl = Column(String, nullable=True)
    
    isPremium = Column(Boolean, default=True)
    price = Column(Float, nullable=True)
    downloadsCount = Column(Integer, default=0)
    rating = Column(Float, default=0.0)
    
    status = Column(Enum(DocumentStatusEnum), default=DocumentStatusEnum.PENDING)
    createdAt = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    author = relationship("User")
