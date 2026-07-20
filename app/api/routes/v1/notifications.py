from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.api.dependencies.auth import get_db, get_current_active_user
from app.models.notification import Notification
from app.models.user import User

router = APIRouter()

@router.get("/")
def get_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    notifs = db.query(Notification).filter(Notification.userId == current_user.id).order_by(desc(Notification.createdAt)).limit(50).all()
    return notifs

@router.patch("/{id}/read")
def mark_as_read(id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    notif = db.query(Notification).filter(Notification.id == id, Notification.userId == current_user.id).first()
    if notif:
        notif.isRead = True
        db.commit()
        return {"ok": True}
    return {"ok": False}
    
@router.post("/read-all")
def mark_all_as_read(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    db.query(Notification).filter(Notification.userId == current_user.id, Notification.isRead == False).update({"isRead": True})
    db.commit()
    return {"ok": True}
