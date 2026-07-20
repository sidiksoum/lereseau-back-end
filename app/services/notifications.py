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
        
        # 2. Push temps réel
        # Émet l'événement sur la room "user_{user_id}"
        await sio.emit("new_notification", {"id": notif.id, "type": notif.type.value, "message": notif.message, "data": notif.data}, room=f"user_{user_id}")
        
        return notif
