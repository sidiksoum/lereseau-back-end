from sqlalchemy.orm import Session
from app.models.notification import Notification, NotificationTypeEnum
from app.sockets.server import sio

class NotificationService:
    @staticmethod
    async def push_notification(
        db: Session,
        user_id: str,
        type: NotificationTypeEnum,
        message: str,
        data: dict = None
    ) -> Notification:
        """
        Crée une notification en base de données et la pousse sur le websocket.
        """
        # 1. Sauvegarde en Base
        notif = Notification(
            userId=user_id,
            type=type,
            message=message,
            data=data or {}
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        
        # Get sender details if fromUserId or authorId is in data
        sender_details = None
        if data:
            sender_id = data.get("fromUserId") or data.get("authorId")
            if sender_id:
                from app.models.user import User
                sender = db.query(User).filter(User.id == sender_id).first()
                if sender:
                    sender_details = {
                        "id": sender.id,
                        "firstName": sender.firstName,
                        "lastName": sender.lastName,
                        "avatarUrl": sender.avatarUrl
                    }

        # 2. Push temps réel
        # Émet l'événement sur la room "user_{user_id}"
        await sio.emit("new_notification", {
            "id": notif.id,
            "type": notif.type.value,
            "message": notif.message,
            "data": notif.data,
            "senderDetails": sender_details
        }, room=f"user_{user_id}")
        
        return notif
