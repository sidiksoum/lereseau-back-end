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
    res = []
    for n in notifs:
        d = n.__dict__.copy()
        d.pop("_sa_instance_state", None)
        
        sender_details = None
        data_dict = n.data
        if data_dict:
            import json
            if isinstance(data_dict, str):
                try:
                    data_dict = json.loads(data_dict)
                except Exception:
                    data_dict = {}
            if isinstance(data_dict, dict):
                sender_id = data_dict.get("fromUserId") or data_dict.get("authorId")
                if sender_id:
                    sender = db.query(User).filter(User.id == sender_id).first()
                    if sender:
                        sender_details = {
                            "id": sender.id,
                            "firstName": sender.firstName,
                            "lastName": sender.lastName,
                            "avatarUrl": sender.avatarUrl
                        }
        
        # Fallback heuristic for old notifications or notifications missing fromUserId
        if not sender_details and n.message:
            words = n.message.split()
            if words:
                first_word = words[0]
                second_word = words[1] if len(words) > 1 else ""
                
                # Check for "Nouveau message de {Name}"
                if n.message.startswith("Nouveau message de "):
                    name_part = n.message[len("Nouveau message de "):].strip()
                    name_words = name_part.split()
                    sender = None
                    if len(name_words) > 1:
                        sender = db.query(User).filter(User.firstName == name_words[0], User.lastName == name_words[1]).first()
                    if not sender:
                        sender = db.query(User).filter(User.firstName == name_words[0]).first()
                    if sender:
                        sender_details = {
                            "id": sender.id,
                            "firstName": sender.firstName,
                            "lastName": sender.lastName,
                            "avatarUrl": sender.avatarUrl
                        }
                elif first_word not in ["Nouveau", "L’institution", "Une", "Votre", "Le", "La"]:
                    sender = None
                    if second_word and second_word not in ["vous", "a", "est", "a/ont", "a-t-elle", "a commenté", "a aimé"]:
                        sender = db.query(User).filter(User.firstName == first_word, User.lastName == second_word).first()
                    if not sender:
                        sender = db.query(User).filter(User.firstName == first_word).first()
                    if sender:
                        sender_details = {
                            "id": sender.id,
                            "firstName": sender.firstName,
                            "lastName": sender.lastName,
                            "avatarUrl": sender.avatarUrl
                        }
                        
        d["senderDetails"] = sender_details
        res.append(d)
    return res

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
