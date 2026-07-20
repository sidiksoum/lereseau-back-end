from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum
import uuid
from datetime import datetime, timezone
from app.db.base import Base

class ForumTopicStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

def generate_uuid():
    return str(uuid.uuid4())

class ForumChannel(Base):
    __tablename__ = "forum_channels"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True, index=True)
    description = Column(String, nullable=True)
    
    topics = relationship("ForumTopic", back_populates="channel")
    members = relationship("ForumChannelMember", back_populates="channel")

class ForumChannelMember(Base):
    __tablename__ = "forum_channel_members"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    channelId = Column(String, ForeignKey("forum_channels.id"), nullable=False, index=True)
    userId = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    joinedAt = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    channel = relationship("ForumChannel", back_populates="members")
    user = relationship("User")

class ForumTopic(Base):
    __tablename__ = "forum_topics"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    channelId = Column(String, ForeignKey("forum_channels.id"), nullable=False, index=True)
    authorId = Column(String, ForeignKey("users.id"), nullable=False)
    
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    status = Column(Enum(ForumTopicStatusEnum), default=ForumTopicStatusEnum.APPROVED)
    
    viewsCount = Column(Integer, default=0)
    repliesCount = Column(Integer, default=0)
    reportsCount = Column(Integer, default=0)
    likesCount = Column(Integer, default=0)
    
    createdAt = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    channel = relationship("ForumChannel", back_populates="topics")
    author = relationship("User")
    replies = relationship("ForumReply", back_populates="topic")

class ForumReply(Base):
    __tablename__ = "forum_replies"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    topicId = Column(String, ForeignKey("forum_topics.id"), nullable=False, index=True)
    authorId = Column(String, ForeignKey("users.id"), nullable=False)
    parentId = Column(String, ForeignKey("forum_replies.id"), nullable=True, index=True)
    
    content = Column(String, nullable=False)
    likesCount = Column(Integer, default=0)
    reportsCount = Column(Integer, default=0)
    
    createdAt = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    topic = relationship("ForumTopic", back_populates="replies")
    author = relationship("User")
    
    parent = relationship("ForumReply", remote_side=[id], back_populates="children")
    children = relationship("ForumReply", back_populates="parent", cascade="all, delete-orphan")
