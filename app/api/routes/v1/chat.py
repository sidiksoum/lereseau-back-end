from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import or_, and_, desc
from app.api.dependencies.auth import get_db, get_current_active_user
from app.models.chat import Conversation, Message, MessageTypeEnum
from app.models.user import User
from app.services.notifications import NotificationService
from app.models.notification import NotificationTypeEnum
from pydantic import BaseModel

router = APIRouter()

class MessageCreate(BaseModel):
    content: str
    recipientId: str

@router.get("/")
def get_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    user_id = current_user.id
    # JSON array lookup logic. If participants has user_id
    # Normally PostgreSQL JSONB uses `@>` but for simplicity we fetch all and filter in Python
    # In production, use JSONB indexing or Association Table for Participants
    all_convos = db.query(Conversation).all()
    my_convos = []
    
    for c in all_convos:
        if user_id in c.participants:
            # fetch other participant details
            other_ids = [p for p in c.participants if p != user_id]
            others = []
            if other_ids:
                users = db.query(User).filter(User.id.in_(other_ids)).all()
                for u in users:
                    others.append({"id": u.id, "firstName": u.firstName, "lastName": u.lastName, "avatarUrl": u.avatarUrl})
            
            d = c.__dict__.copy()
            d['otherParticipants'] = others
            
            if d.get('unreadCount'):
                d['myUnreadCount'] = d['unreadCount'].get(user_id, 0)
            else:
                d['myUnreadCount'] = 0
                
            d.pop('_sa_instance_state', None)
            my_convos.append(d)
            
    my_convos.sort(key=lambda x: x.get('lastMessageAt') or x.get('id'), reverse=True)
    return my_convos

@router.get("/{conversation_id}")
@router.get("/{conversation_id}/messages")
def get_messages(conversation_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not convo or current_user.id not in convo.participants:
        raise HTTPException(403, "Accès refusé")
        
    messages = db.query(Message).filter(Message.conversationId == conversation_id).order_by(Message.createdAt).all()
    
    # Mark messages as read
    if convo.unreadCount and current_user.id in convo.unreadCount:
        convo.unreadCount = {**convo.unreadCount, current_user.id: 0}
        flag_modified(convo, 'unreadCount')
        db.commit()
    
    # Serialization de la conversation avec otherParticipants
    other_ids = [p for p in convo.participants if p != current_user.id]
    others = []
    users = []
    if other_ids:
        users = db.query(User).filter(User.id.in_(other_ids)).all()
        for u in users:
            others.append({"id": u.id, "firstName": u.firstName, "lastName": u.lastName, "avatarUrl": u.avatarUrl, "roleType": u.roleType.value if u.roleType else None})
            
    d_convo = convo.__dict__.copy()
    d_convo['otherParticipants'] = others
    d_convo.pop('_sa_instance_state', None)
    
    res_messages = []
    for msg in messages:
        d_m = {
            "id": msg.id,
            "conversationId": msg.conversationId,
            "senderId": msg.senderId,
            "content": msg.content,
            "type": msg.type,
            "status": msg.status,
            "createdAt": msg.createdAt
        }
        sender = current_user if msg.senderId == current_user.id else next((u for u in users if u.id == msg.senderId), None)
        if sender:
            d_m['senderDetails'] = {
                "id": sender.id,
                "firstName": sender.firstName,
                "lastName": sender.lastName,
                "avatarUrl": sender.avatarUrl
            }
        res_messages.append(d_m)
        
    return {"conversation": d_convo, "messages": res_messages}

@router.post("/")
async def send_message(msg_in: MessageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    from app.models.network import Connection, ConnectionStatusEnum
    
    recipient = db.query(User).filter(User.id == msg_in.recipientId).first()
    if not recipient: raise HTTPException(404, "Destinataire introuvable")
    
    # Check if they are friends
    is_friends = db.query(Connection).filter(
        or_(
            and_(Connection.requesterId == current_user.id, Connection.addresseeId == recipient.id),
            and_(Connection.requesterId == recipient.id, Connection.addresseeId == current_user.id)
        ),
        Connection.status == ConnectionStatusEnum.ACCEPTED
    ).first() is not None
    
    # Search for an existing conversation
    all_convos = db.query(Conversation).all()
    convo = None
    for c in all_convos:
        if current_user.id in c.participants and msg_in.recipientId in c.participants and len(c.participants) == 2:
            convo = c
            break
            
    if not is_friends:
        # If not friends, check if current_user already sent a message
        if convo:
            sent_count = db.query(Message).filter(Message.conversationId == convo.id, Message.senderId == current_user.id).count()
            if sent_count >= 1:
                raise HTTPException(403, "Vous ne pouvez envoyer qu'un seul message de prise de contact avant l'acceptation de votre demande de mise en relation.")
            
    if not convo:
        convo = Conversation(participants=[current_user.id, msg_in.recipientId], unreadCount={current_user.id: 0, msg_in.recipientId: 0})
        db.add(convo)
        db.commit()
        db.refresh(convo)
        
    message = Message(
        conversationId=convo.id,
        senderId=current_user.id,
        content=msg_in.content
    )
    db.add(message)
    
    convo.lastMessageText = msg_in.content
    convo.lastMessageAt = message.createdAt
    
    # Update unread count for recipient
    uc = convo.unreadCount.copy() if convo.unreadCount else {current_user.id: 0, msg_in.recipientId: 0}
    uc[msg_in.recipientId] = uc.get(msg_in.recipientId, 0) + 1
    # Assignment needed to force SQLAlchemy JSON detection
    convo.unreadCount = uc

    db.commit()
    db.refresh(message)
    
    # Push WS and notification
    from app.sockets.server import sio
    await sio.emit("new_message", {"conversationId": convo.id, "message": message.content, "senderId": current_user.id}, room=f"user_{msg_in.recipientId}")
    
    await NotificationService.push_notification(
        db=db,
        user_id=msg_in.recipientId,
        type=NotificationTypeEnum.CHAT_MESSAGE,
        message=f"Nouveau message de {current_user.firstName}",
        data={"conversationId": convo.id, "fromUserId": current_user.id}
    )
    
    d_convo = convo.__dict__.copy()
    other_ids = [p for p in convo.participants if p != current_user.id]
    others = []
    if other_ids:
        users = db.query(User).filter(User.id.in_(other_ids)).all()
        for u in users:
            others.append({"id": u.id, "firstName": u.firstName, "lastName": u.lastName, "avatarUrl": u.avatarUrl, "roleType": u.roleType.value if u.roleType else None})
    d_convo['otherParticipants'] = others
    d_convo.pop('_sa_instance_state', None)

    d_msg = message.__dict__.copy()
    d_msg['senderDetails'] = {
        "id": current_user.id,
        "firstName": current_user.firstName,
        "lastName": current_user.lastName,
        "avatarUrl": current_user.avatarUrl
    }
    d_msg.pop('_sa_instance_state', None)
    
    return {"message": d_msg, "conversation": d_convo}
