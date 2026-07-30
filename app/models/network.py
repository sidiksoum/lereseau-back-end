from sqlalchemy import Column, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum
import uuid
from datetime import datetime, timezone
from app.db.base import Base

class ConnectionStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"

class ConnectionTypeEnum(str, enum.Enum):
    FRIEND = "FRIEND"
    MENTORSHIP = "MENTORSHIP"
    FOLLOWING = "FOLLOWING"
    FOLLOWER = "FOLLOWER"

def generate_uuid():
    return str(uuid.uuid4())

class Connection(Base):
    __tablename__ = "connections"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    requesterId = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    addresseeId = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    status = Column(Enum(ConnectionStatusEnum), default=ConnectionStatusEnum.PENDING)
    type = Column(Enum(ConnectionTypeEnum), default=ConnectionTypeEnum.FRIEND)
    
    createdAt = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    requester = relationship("User", foreign_keys=[requesterId])
    addressee = relationship("User", foreign_keys=[addresseeId])
