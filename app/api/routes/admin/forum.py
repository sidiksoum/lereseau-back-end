from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.dependencies.auth import get_db, require_role
from app.models.forum import ForumChannel, ForumTopic, ForumTopicStatusEnum, ForumReply
from app.models.user import User
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import desc

import re
import unicodedata

router = APIRouter()

class ChannelCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None

def generate_unique_slug(db: Session, text: str, model_class) -> str:
    # 1. Nettoyage basique (slugify)
    value = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    base_slug = re.sub(r'[-\s]+', '-', value).strip('-_')
    
    if not base_slug:
        base_slug = "channel"
        
    # 2. Vérification d'unicité
    slug = base_slug
    counter = 1
    while db.query(model_class).filter(model_class.slug == slug).first() is not None:
        slug = f"{base_slug}-{counter}"
        counter += 1
        
    return slug

@router.get("/topics")
def get_pending_topics(db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    return db.query(ForumTopic).filter(ForumTopic.status == ForumTopicStatusEnum.PENDING).order_by(desc(ForumTopic.createdAt)).all()

@router.get("/topics/reported")
def get_reported_topics(db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    return db.query(ForumTopic).filter(ForumTopic.reportsCount > 0).order_by(desc(ForumTopic.reportsCount)).all()

@router.get("/replies/reported")
def get_reported_replies(db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    return db.query(ForumReply).filter(ForumReply.reportsCount > 0).order_by(desc(ForumReply.reportsCount)).all()

@router.get("/topics")
def get_pending_topics(db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    """Retrieve all forum topics pending validation (Admin only)"""
    return db.query(ForumTopic).filter(ForumTopic.status == ForumTopicStatusEnum.PENDING).order_by(desc(ForumTopic.createdAt)).all()

@router.get("/channels")
def get_channels(db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    """Retrieve all forum channels (Admin only)"""
    return db.query(ForumChannel).all()

@router.post("/channels")
def create_channel(channel_in: ChannelCreate, db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    data = channel_in.model_dump()
    if not data.get("slug") or data.get("slug") == "string":
        data["slug"] = generate_unique_slug(db, data["name"], ForumChannel)
        
    channel = ForumChannel(**data)
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel

@router.put("/channels/{id}")
def update_channel(id: str, channel_in: ChannelCreate, db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    channel = db.query(ForumChannel).filter(ForumChannel.id == id).first()
    if not channel: raise HTTPException(404, "Canal non trouvé")
    
    data = channel_in.model_dump()
    if not data.get("slug") or data.get("slug") == "string":
        if data["name"] != channel.name:
            # Nouveau nom -> On regénère le slug
            data["slug"] = generate_unique_slug(db, data["name"], ForumChannel)
        else:
            # Même nom -> on garde l'ancien slug
            data["slug"] = channel.slug
            
    for key, value in data.items():
        setattr(channel, key, value)
    db.commit()
    return channel

@router.delete("/channels/{id}")
def delete_channel(id: str, db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    channel = db.query(ForumChannel).filter(ForumChannel.id == id).first()
    if not channel: raise HTTPException(404, "Canal non trouvé")
    db.delete(channel)
    db.commit()
    return {"ok": True}

@router.delete("/topics/{id}")
def delete_topic(id: str, db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    topic = db.query(ForumTopic).filter(ForumTopic.id == id).first()
    if not topic: raise HTTPException(404, "Sujet non trouvé")
    db.delete(topic)
    db.commit()
    return {"ok": True}

@router.patch("/topics/{id}/authorize")
def authorize_topic(id: str, db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    topic = db.query(ForumTopic).filter(ForumTopic.id == id).first()
    if not topic: raise HTTPException(404, "Sujet non trouvé")
    topic.status = ForumTopicStatusEnum.APPROVED
    db.commit()
    return {"ok": True, "status": "APPROVED"}

@router.delete("/replies/{id}")
def delete_reply(id: str, db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    reply = db.query(ForumReply).filter(ForumReply.id == id).first()
    if not reply: raise HTTPException(404, "Réponse non trouvée")
    
    # Optionally update topic repliesCount if needed
    topic = reply.topic
    if topic and topic.repliesCount > 0:
        topic.repliesCount -= 1
        
    db.delete(reply)
    db.commit()
    return {"ok": True}

@router.patch("/replies/{id}/ignore-report")
def ignore_reply_report(id: str, db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    reply = db.query(ForumReply).filter(ForumReply.id == id).first()
    if not reply: raise HTTPException(404, "Réponse non trouvée")
    
    reply.reportsCount = 0
    db.commit()
    return {"ok": True, "reportsCount": 0}
