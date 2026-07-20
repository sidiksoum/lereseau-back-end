from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.api.dependencies.auth import get_db, get_current_active_user
from app.models.feed import FeedPost, FeedLike, FeedComment, FeedCommentLike, FeedPostStatusEnum
from app.models.user import User
from app.models.notification import NotificationTypeEnum
from app.services.notifications import NotificationService
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class CommentCreate(BaseModel):
    content: str
    parentId: Optional[str] = None

@router.post("/{post_id}/like")
async def toggle_like_post(post_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    post = db.query(FeedPost).filter(FeedPost.id == post_id).first()
    if not post: raise HTTPException(404, "Post introuvable")
    
    existing_like = db.query(FeedLike).filter(FeedLike.postId == post_id, FeedLike.userId == current_user.id).first()
    
    if existing_like:
        db.delete(existing_like)
        post.likesCount -= 1
        db.commit()
        return {"liked": False, "likesCount": post.likesCount}
    else:
        new_like = FeedLike(postId=post_id, userId=current_user.id)
        db.add(new_like)
        post.likesCount += 1
        db.commit()
        
        # Notifier l'auteur du post si ce n'est pas lui-même
        if post.authorId != current_user.id:
            await NotificationService.push_notification(
                db=db,
                user_id=post.authorId,
                type=NotificationTypeEnum.FEED_LIKE,
                message=f"{current_user.firstName} a aimé votre publication.",
                data={"postId": post.id}
            )
            
        return {"liked": True, "likesCount": post.likesCount}

@router.post("/{post_id}/repost")
async def repost_feed(post_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    original_post = db.query(FeedPost).filter(FeedPost.id == post_id).first()
    if not original_post: raise HTTPException(404, "Post original introuvable")
    
    repost = FeedPost(
        authorId=current_user.id,
        originalPostId=original_post.id,
        status=FeedPostStatusEnum.APPROVED
    )
    db.add(repost)
    db.commit()
    return repost

@router.post("/{post_id}/comments")
async def create_comment(post_id: str, comment_in: CommentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    post = db.query(FeedPost).filter(FeedPost.id == post_id).first()
    if not post: raise HTTPException(404, "Post introuvable")
    
    comment = FeedComment(
        postId=post_id,
        authorId=current_user.id,
        parentId=comment_in.parentId if comment_in.parentId and comment_in.parentId.lower() != "string" else None,
        content=comment_in.content
    )
    db.add(comment)
    post.commentsCount += 1
    db.commit()
    db.refresh(comment)
    
    # Notify author
    if post.authorId != current_user.id:
        await NotificationService.push_notification(
            db=db,
            user_id=post.authorId,
            type=NotificationTypeEnum.FEED_COMMENT,
            message=f"{current_user.firstName} a commenté votre publication.",
            data={"postId": post.id}
        )
        
    return comment

@router.get("/{post_id}/comments")
def get_comments(post_id: str, db: Session = Depends(get_db)):
    comments = db.query(FeedComment).filter(FeedComment.postId == post_id).order_by(FeedComment.createdAt).all()
    # Simple serialization
    res = []
    for c in comments:
        d = c.__dict__.copy()
        d['authorDetails'] = {"firstName": c.author.firstName, "lastName": c.author.lastName, "avatarUrl": c.author.avatarUrl}
        d.pop('_sa_instance_state', None)
        res.append(d)
    return res

@router.get("/")
def get_feed(db: Session = Depends(get_db)):
    # Feed simple chronological
    posts = db.query(FeedPost).filter(FeedPost.status == FeedPostStatusEnum.APPROVED).order_by(desc(FeedPost.createdAt)).all()
    
    res = []
    for p in posts:
        d = p.__dict__.copy()
        d['authorDetails'] = {"firstName": p.author.firstName, "lastName": p.author.lastName, "avatarUrl": p.author.avatarUrl}
        if p.originalPost:
            orig = p.originalPost.__dict__.copy()
            orig['authorDetails'] = {"firstName": p.originalPost.author.firstName, "lastName": p.originalPost.author.lastName, "avatarUrl": p.originalPost.author.avatarUrl}
            orig.pop('_sa_instance_state', None)
            d['originalPost'] = orig
            
        d.pop('_sa_instance_state', None)
        res.append(d)
    return res
