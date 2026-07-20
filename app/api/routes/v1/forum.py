from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.api.dependencies.auth import get_db, get_current_active_user
from app.models.forum import ForumChannel, ForumTopic, ForumReply, ForumChannelMember, ForumTopicStatusEnum
from app.models.user import User, RoleEnum
from pydantic import BaseModel

router = APIRouter()

class TopicCreate(BaseModel):
    title: str
    content: str

class ReplyCreate(BaseModel):
    content: str

@router.get("/channels")
def get_channels(db: Session = Depends(get_db)):
    return db.query(ForumChannel).all()

@router.get("/channels/{channel_id}/memberships")
def get_channel_memberships(channel_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    ext = db.query(ForumChannelMember).filter(ForumChannelMember.channelId == channel_id, ForumChannelMember.userId == current_user.id).first()
    return {"joined": bool(ext)}

@router.post("/channels/{channel_id}/join")
def join_channel(channel_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    channel = db.query(ForumChannel).filter(ForumChannel.id == channel_id).first()
    if not channel: raise HTTPException(404, "Canal introuvable")
    
    ext = db.query(ForumChannelMember).filter(ForumChannelMember.channelId == channel_id, ForumChannelMember.userId == current_user.id).first()
    if ext: # Leave
        db.delete(ext)
        db.commit()
        return {"joined": False}
    else: # Join
        db.add(ForumChannelMember(channelId=channel_id, userId=current_user.id))
        db.commit()
        return {"joined": True}

@router.get("/channels/{channel_id}/topics")
def get_channel_topics(channel_id: str, db: Session = Depends(get_db)):
    topics = db.query(ForumTopic).filter(ForumTopic.channelId == channel_id, ForumTopic.status == ForumTopicStatusEnum.APPROVED).order_by(desc(ForumTopic.createdAt)).all()
    # Serialize authors lightly
    res = []
    for t in topics:
        d = t.__dict__.copy()
        d['authorDetails'] = {"firstName": t.author.firstName, "lastName": t.author.lastName, "avatarUrl": t.author.avatarUrl}
        res.append(d)
    return res

@router.post("/channels/{channel_id}/topics")
def create_topic(channel_id: str, topic_in: TopicCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    channel = db.query(ForumChannel).filter(ForumChannel.id == channel_id).first()
    if not channel: raise HTTPException(404, "Canal introuvable")
    
    topic = ForumTopic(
        channelId=channel_id,
        authorId=current_user.id,
        title=topic_in.title,
        content=topic_in.content,
        status=ForumTopicStatusEnum.PENDING
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic

@router.get("/topics/{topic_id}/replies")
def get_topic_replies(topic_id: str, db: Session = Depends(get_db)):
    replies = db.query(ForumReply).filter(ForumReply.topicId == topic_id).order_by(ForumReply.createdAt).all()
    res = []
    for r in replies:
        d = r.__dict__.copy()
        d['authorDetails'] = {"firstName": r.author.firstName, "lastName": r.author.lastName, "avatarUrl": r.author.avatarUrl}
        res.append(d)
    return res

@router.get("/topics/{topic_id}")
def get_topic(topic_id: str, db: Session = Depends(get_db)):
    topic = db.query(ForumTopic).filter(ForumTopic.id == topic_id).first()
    if not topic: raise HTTPException(404, "Sujet introuvable")
    
    d = topic.__dict__.copy()
    d['authorDetails'] = {"firstName": topic.author.firstName, "lastName": topic.author.lastName, "avatarUrl": topic.author.avatarUrl}
    return d

@router.post("/topics/{topic_id}/view")
def view_topic(topic_id: str, db: Session = Depends(get_db)):
    topic = db.query(ForumTopic).filter(ForumTopic.id == topic_id).first()
    if not topic: raise HTTPException(404, "Sujet introuvable")
    
    topic.viewsCount += 1
    db.commit()
    return {"ok": True, "viewsCount": topic.viewsCount}

@router.post("/topics/{topic_id}/replies")
async def create_reply(topic_id: str, reply_in: ReplyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    from app.services.notifications import NotificationService
    from app.models.notification import NotificationTypeEnum
    
    topic = db.query(ForumTopic).filter(ForumTopic.id == topic_id).first()
    if not topic: raise HTTPException(404, "Sujet introuvable")
    
    reply = ForumReply(
        topicId=topic_id,
        authorId=current_user.id,
        content=reply_in.content
    )
    db.add(reply)
    topic.repliesCount += 1
    db.commit()
    db.refresh(reply)
    
    if topic.authorId != current_user.id:
        await NotificationService.push_notification(
            db=db,
            user_id=topic.authorId,
            type=NotificationTypeEnum.FORUM_REPLY,
            message=f"{current_user.firstName} a répondu à votre sujet '{topic.title}'.",
            data={"topicId": topic.id}
        )
        
    return reply

@router.post("/replies/{reply_id}/replies")
def create_nested_reply(reply_id: str, reply_in: ReplyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    parent_reply = db.query(ForumReply).filter(ForumReply.id == reply_id).first()
    if not parent_reply: raise HTTPException(404, "Message introuvable")
    
    reply = ForumReply(
        topicId=parent_reply.topicId,
        authorId=current_user.id,
        parentId=reply_id,
        content=reply_in.content
    )
    db.add(reply)
    parent_reply.topic.repliesCount += 1
    db.commit()
    db.refresh(reply)
    return reply

@router.post("/replies/{reply_id}/like")
def like_reply(reply_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    reply = db.query(ForumReply).filter(ForumReply.id == reply_id).first()
    if not reply: raise HTTPException(404, "Réponse introuvable")
    
    # Simuler un like (dans un vrai système on vérifierait si l'utilisateur a déjà liké via une table d'association)
    reply.likesCount += 1
    db.commit()
    return {"ok": True, "likesCount": reply.likesCount}

@router.post("/replies/{reply_id}/report")
def report_reply(reply_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    reply = db.query(ForumReply).filter(ForumReply.id == reply_id).first()
    if not reply: raise HTTPException(404, "Réponse introuvable")
    
    # Simuler un signalement
    reply.reportsCount += 1
    db.commit()
    return {"ok": True, "reportsCount": reply.reportsCount}
