from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
import enum
import uuid
from datetime import datetime, timezone
from app.db.base import Base

class NotificationTypeEnum(str, enum.Enum):
    FRIEND_REQUEST = "FRIEND_REQUEST"
    OPPORTUNITY_MATCH = "OPPORTUNITY_MATCH"
    FORUM_REPLY = "FORUM_REPLY"
    CHAT_MESSAGE = "CHAT_MESSAGE"
    FEED_LIKE = "FEED_LIKE"
    FEED_COMMENT = "FEED_COMMENT"
    MENTION = "MENTION"
    SYSTEM = "SYSTEM"
    FOLLOWER_POST = "FOLLOWER_POST"

def generate_uuid():
    return str(uuid.uuid4())

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    userId = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    type = Column(Enum(NotificationTypeEnum), nullable=False)
    message = Column(String, nullable=False)
    
    # Can contain { postId: "...", fromUserId: "..." } to handle dynamic redirect in frontend
    data = Column(JSON, nullable=True) 
    
    isRead = Column(Boolean, default=False)
    createdAt = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    user = relationship("User")
