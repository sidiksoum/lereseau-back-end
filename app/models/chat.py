from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
import enum
import uuid
from datetime import datetime, timezone
from app.db.base import Base

class MessageTypeEnum(str, enum.Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    DOCUMENT = "DOCUMENT"

class MessageStatusEnum(str, enum.Enum):
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"

def generate_uuid():
    return str(uuid.uuid4())

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    participants = Column(JSON, nullable=False)
    lastMessageText = Column(String, nullable=True)
    lastMessageAt = Column(DateTime(timezone=True), nullable=True)
    unreadCount = Column(JSON, nullable=True)

    messages = relationship("Message", back_populates="conversation")

class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    conversationId = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    senderId = Column(String, ForeignKey("users.id"), nullable=False)
    
    content = Column(String, nullable=False)
    type = Column(Enum(MessageTypeEnum), default=MessageTypeEnum.TEXT)
    status = Column(Enum(MessageStatusEnum), default=MessageStatusEnum.SENT)
    
    createdAt = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User")
