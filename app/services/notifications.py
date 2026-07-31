from sqlalchemy.orm import Session
from app.models.notification import Notification, NotificationTypeEnum
from app.sockets.server import sio

def _send_webpush_sync(endpoint: str, p256dh: str, auth: str, payload_str: str, private_key: str):
    from pywebpush import webpush, WebPushException
    try:
        webpush(
            subscription_info={
                "endpoint": endpoint,
                "keys": {
                    "p256dh": p256dh,
                    "auth": auth
                }
            },
            data=payload_str,
            vapid_private_key=private_key,
            vapid_claims={"sub": "mailto:noreply@lereseau.com"}
        )
        return True, None
    except WebPushException as ex:
        status_code = ex.response.status_code if ex.response is not None else None
        return False, status_code
    except Exception as ex:
        return False, None

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

        # 2. Push temps réel via WebSockets
        await sio.emit("new_notification", {
            "id": notif.id,
            "type": notif.type.value,
            "message": notif.message,
            "data": notif.data,
            "senderDetails": sender_details
        }, room=f"user_{user_id}")
        
        # 3. Web Push System (Tâche de fond non bloquante)
        from app.models.notification import PushSubscription
        from app.core.config import settings
        import json
        import asyncio

        subs = db.query(PushSubscription).filter(PushSubscription.userId == user_id).all()
        if subs:
            target_url = "/feed"
            if data:
                if data.get("postId"):
                    target_url = "/feed"
                elif data.get("connectionId"):
                    target_url = "/network"
                elif data.get("topicId"):
                    target_url = "/forum"
                    
            payload_str = json.dumps({
                "title": "LeRéseau",
                "body": message,
                "url": target_url
            })
            
            for sub in subs:
                async def run_push(s=sub):
                    success, status_code = await asyncio.to_thread(
                        _send_webpush_sync,
                        s.endpoint,
                        s.p256dh,
                        s.auth,
                        payload_str,
                        settings.VAPID_PRIVATE_KEY
                    )
                    if not success and status_code in [404, 410]:
                        try:
                            from app.db.session import SessionLocal
                            with SessionLocal() as db_session:
                                expired_sub = db_session.query(PushSubscription).filter(PushSubscription.id == s.id).first()
                                if expired_sub:
                                    db_session.delete(expired_sub)
                                    db_session.commit()
                        except Exception as e:
                            print(f"Error deleting expired subscription: {e}")
                
                asyncio.create_task(run_push())

        return notif
