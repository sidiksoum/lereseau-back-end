from datetime import datetime
from time import perf_counter
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from app.api.dependencies.auth import get_db, get_current_active_user
from app.models.feed import FeedPost, FeedLike, FeedComment, FeedPostStatusEnum
from app.models.user import User
from app.models.notification import NotificationTypeEnum
from app.services.notifications import NotificationService
from app.services.recommendations import score_feed_post_match
from app.services.cache import cache, make_jsonable
from app.services.metrics import metrics
from app.services.logging import logger
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class CommentCreate(BaseModel):
    content: str
    parentId: Optional[str] = None


@router.post("/{post_id}/like")
async def toggle_like_post(post_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    post = db.query(FeedPost).filter(FeedPost.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post introuvable")

    existing_like = db.query(FeedLike).filter(FeedLike.postId == post_id, FeedLike.userId == current_user.id).first()

    if existing_like:
        db.delete(existing_like)
        post.likesCount -= 1
        db.commit()
        return make_jsonable({"liked": False, "likesCount": post.likesCount})

    new_like = FeedLike(postId=post_id, userId=current_user.id)
    db.add(new_like)
    post.likesCount += 1
    db.commit()

    if post.authorId != current_user.id:
        await NotificationService.push_notification(
            db=db,
            user_id=post.authorId,
            type=NotificationTypeEnum.FEED_LIKE,
            message=f"{current_user.firstName} a aimé votre publication.",
            data={"postId": post.id, "fromUserId": current_user.id},
        )

    return make_jsonable({"liked": True, "likesCount": post.likesCount})


@router.post("/{post_id}/repost")
async def repost_feed(post_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    original_post = db.query(FeedPost).filter(FeedPost.id == post_id).first()
    if not original_post:
        raise HTTPException(404, "Post original introuvable")

    repost = FeedPost(authorId=current_user.id, originalPostId=original_post.id, status=FeedPostStatusEnum.APPROVED)
    db.add(repost)
    db.commit()
    return make_jsonable(repost)


@router.post("/{post_id}/comments")
async def create_comment(post_id: str, comment_in: CommentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    post = db.query(FeedPost).filter(FeedPost.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post introuvable")

    comment = FeedComment(
        postId=post_id,
        authorId=current_user.id,
        parentId=comment_in.parentId if comment_in.parentId and comment_in.parentId.lower() != "string" else None,
        content=comment_in.content,
    )
    db.add(comment)
    post.commentsCount += 1
    db.commit()
    db.refresh(comment)

    if post.authorId != current_user.id:
        await NotificationService.push_notification(
            db=db,
            user_id=post.authorId,
            type=NotificationTypeEnum.FEED_COMMENT,
            message=f"{current_user.firstName} a commenté votre publication.",
            data={"postId": post.id, "fromUserId": current_user.id},
        )

    d = comment.__dict__.copy()
    d["authorDetails"] = {
        "firstName": current_user.firstName,
        "lastName": current_user.lastName,
        "avatarUrl": current_user.avatarUrl,
    }
    d.pop("_sa_instance_state", None)
    return make_jsonable(d)


@router.get("/{post_id}/comments")
def get_comments(post_id: str, db: Session = Depends(get_db)):
    comments = db.query(FeedComment).filter(FeedComment.postId == post_id).order_by(FeedComment.createdAt).all()
    res = []
    for c in comments:
        d = c.__dict__.copy()
        d["authorDetails"] = {"firstName": c.author.firstName, "lastName": c.author.lastName, "avatarUrl": c.author.avatarUrl}
        d.pop("_sa_instance_state", None)
        res.append(d)
    return make_jsonable(res)


@router.get("/")
def get_feed(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    q: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
):
    started = perf_counter()
    cache_key = f"feed:{current_user.id}:{q or ''}:{type or ''}:{limit}:{cursor or ''}"
    cached = cache.get(cache_key)
    if cached is not None:
        metrics.increment("feed_cache_hits")
        return make_jsonable(cached)

    query = db.query(FeedPost).filter(FeedPost.status == FeedPostStatusEnum.APPROVED)

    if q:
        like_q = f"%{q}%"
        query = query.filter(or_(FeedPost.title.ilike(like_q), FeedPost.content.ilike(like_q)))
    if type:
        query = query.filter(FeedPost.type == type)
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(400, detail="cursor invalide") from exc
        query = query.filter(FeedPost.createdAt < cursor_dt)

    posts = query.order_by(desc(FeedPost.createdAt)).limit(limit + 1).all()
    has_more = len(posts) > limit
    items = posts[:limit]

    post_ids = [p.id for p in items]
    liked_post_ids = set()
    if post_ids and current_user:
        likes = db.query(FeedLike.postId).filter(FeedLike.postId.in_(post_ids), FeedLike.userId == current_user.id).all()
        liked_post_ids = {l.postId for l in likes}

    serialized = []
    for post in items:
        d = post.__dict__.copy()
        d["authorDetails"] = {"firstName": post.author.firstName, "lastName": post.author.lastName, "avatarUrl": post.author.avatarUrl}
        d["liked"] = post.id in liked_post_ids
        d["recommendationScore"] = score_feed_post_match(current_user, post)
        if post.originalPost:
            orig = post.originalPost.__dict__.copy()
            orig["authorDetails"] = {"firstName": post.originalPost.author.firstName, "lastName": post.originalPost.author.lastName, "avatarUrl": post.originalPost.author.avatarUrl}
            orig.pop("_sa_instance_state", None)
            d["originalPost"] = orig
        d.pop("_sa_instance_state", None)
        serialized.append(d)

    serialized.sort(key=lambda item: item.get("recommendationScore", 0), reverse=True)
    serialized = make_jsonable(serialized)
    cache.set(cache_key, serialized, ttl=60)
    metrics.increment("feed_cache_misses")
    metrics.observe("feed_latency_ms", (perf_counter() - started) * 1000)
    logger.info("feed_served", extra={"request_id": str(current_user.id), "limit": limit})
    return serialized
