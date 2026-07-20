from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
import enum
import uuid
from datetime import datetime, timezone
from app.db.base import Base

class FeedPostTypeEnum(str, enum.Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    PDF = "PDF"
    RECOMMENDED_OPPORTUNITY = "RECOMMENDED_OPPORTUNITY"

class FeedPostStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

def generate_uuid():
    return str(uuid.uuid4())

class FeedPost(Base):
    __tablename__ = "feed_posts"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    authorId = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    originalPostId = Column(String, ForeignKey("feed_posts.id"), nullable=True)
    
    title = Column(String, nullable=True)
    content = Column(String, nullable=True)
    type = Column(Enum(FeedPostTypeEnum), default=FeedPostTypeEnum.TEXT)
    status = Column(Enum(FeedPostStatusEnum), default=FeedPostStatusEnum.APPROVED)
    attachments = Column(JSON, nullable=True)
    
    likesCount = Column(Integer, default=0)
    commentsCount = Column(Integer, default=0)
    
    createdAt = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    author = relationship("User")
    originalPost = relationship("FeedPost", remote_side=[id])

class FeedLike(Base):
    __tablename__ = "feed_likes"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    postId = Column(String, ForeignKey("feed_posts.id"), nullable=False, index=True)
    userId = Column(String, ForeignKey("users.id"), nullable=False)
    createdAt = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class FeedComment(Base):
    __tablename__ = "feed_comments"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    postId = Column(String, ForeignKey("feed_posts.id"), nullable=False, index=True)
    authorId = Column(String, ForeignKey("users.id"), nullable=False)
    parentId = Column(String, ForeignKey("feed_comments.id"), nullable=True, index=True)
    
    content = Column(String, nullable=False)
    likesCount = Column(Integer, default=0)
    
    createdAt = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    author = relationship("User")
    parent = relationship("FeedComment", remote_side=[id], back_populates="children")
    children = relationship("FeedComment", back_populates="parent", cascade="all, delete-orphan")

class FeedCommentLike(Base):
    __tablename__ = "feed_comment_likes"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    commentId = Column(String, ForeignKey("feed_comments.id"), nullable=False, index=True)
    userId = Column(String, ForeignKey("users.id"), nullable=False)
    createdAt = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
