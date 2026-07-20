from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.dependencies.auth import get_db, get_current_active_user
from app.models.user import User
from app.models.network import Connection, ConnectionTypeEnum, ConnectionStatusEnum

router = APIRouter()

@router.post("/request/{to_user_id}")
async def send_connection_request(
    to_user_id: str,
    type: ConnectionTypeEnum,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.services.notifications import NotificationService
    from app.models.notification import NotificationTypeEnum
    
    if to_user_id == current_user.id:
        raise HTTPException(400, "Impossible de s'envoyer une demande.")
    
    target = db.query(User).filter(User.id == to_user_id).first()
    if not target: raise HTTPException(404, "Utilisateur introuvable.")

    conn = Connection(
        requesterId=current_user.id,
        addresseeId=to_user_id,
        type=type,
        status=ConnectionStatusEnum.PENDING
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    
    await NotificationService.push_notification(
        db=db,
        user_id=to_user_id,
        type=NotificationTypeEnum.FRIEND_REQUEST,
        message=f"{current_user.firstName} vous a envoyé une demande de connexion.",
        data={"connectionId": conn.id}
    )
    
    return conn

@router.put("/accept/{connection_id}")
def accept_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if not conn or conn.addresseeId != current_user.id:
        raise HTTPException(404, "Demande introuvable ou vous n'êtes pas destinataire.")
    
    conn.status = ConnectionStatusEnum.ACCEPTED
    db.commit()
    db.refresh(conn)
    return conn

@router.put("/reject/{connection_id}")
@router.delete("/reject/{connection_id}")
def reject_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if not conn:
        raise HTTPException(404, "Demande introuvable.")
        
    if current_user.id not in [conn.addresseeId, conn.requesterId]:
        raise HTTPException(403, "Non autorisé à modifier cette demande.")
    
    if current_user.id == conn.requesterId:
        # Si c'est l'expéditeur qui annule sa demande, on la supprime
        db.delete(conn)
    else:
        # Si c'est le destinataire qui refuse
        conn.status = ConnectionStatusEnum.REJECTED
        
    db.commit()
    return {"ok": True}

@router.post("/follow/{institution_id}")
def follow_institution(
    institution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    target = db.query(User).filter(User.id == institution_id, User.roleType == "institution").first()
    if not target: raise HTTPException(404, "Institution introuvable.")

    existing = db.query(Connection).filter(
        Connection.requesterId == current_user.id, 
        Connection.addresseeId == institution_id,
        Connection.type == ConnectionTypeEnum.FOLLOWING
    ).first()
    if existing: return existing

    conn = Connection(
        requesterId=current_user.id,
        addresseeId=institution_id,
        type=ConnectionTypeEnum.FOLLOWING,
        status=ConnectionStatusEnum.ACCEPTED # Following is one-way
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn

@router.get("/")
def get_my_network(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    conns = db.query(Connection).filter(
        (Connection.requesterId == current_user.id) | (Connection.addresseeId == current_user.id)
    ).all()
    
    res = []
    for c in conns:
        d = c.__dict__.copy()
        
        # Identifier la cible de la relation (L'autre personne)
        target = c.addressee if c.requesterId == current_user.id else c.requester
        if target:
            d['targetUser'] = {
                "id": target.id,
                "firstName": target.firstName,
                "lastName": target.lastName,
                "avatarUrl": target.avatarUrl,
                "roleType": target.roleType.value if target.roleType else None,
                "jobTitle": target.jobTitle,
                "studyDomain": target.studyDomain
            }
            
        d.pop('_sa_instance_state', None)
        res.append(d)
        
    return res

@router.get("/outgoing")
def get_outgoing_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Demandes envoyées (PENDING ou ACCEPTED)
    conns = db.query(Connection).filter(
        Connection.requesterId == current_user.id,
        Connection.status.in_([ConnectionStatusEnum.PENDING, ConnectionStatusEnum.ACCEPTED])
    ).all()
    
    res = []
    for c in conns:
        d = c.__dict__.copy()
        if c.addressee:
            d['addresseeDetails'] = {
                "id": c.addressee.id,
                "firstName": c.addressee.firstName,
                "lastName": c.addressee.lastName,
                "avatarUrl": c.addressee.avatarUrl,
                "roleType": c.addressee.roleType.value if c.addressee.roleType else None,
                "jobTitle": c.addressee.jobTitle,
                "studyDomain": c.addressee.studyDomain
            }
        d.pop('_sa_instance_state', None)
        res.append(d)
        
    return res

@router.get("/incoming")
def get_incoming_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Demandes reçues (en attente d'une réponse de notre part)
    conns = db.query(Connection).filter(
        Connection.addresseeId == current_user.id,
        Connection.status == ConnectionStatusEnum.PENDING
    ).all()
    
    res = []
    for c in conns:
        d = c.__dict__.copy()
        if c.requester:
            d['requesterDetails'] = {
                "id": c.requester.id,
                "firstName": c.requester.firstName,
                "lastName": c.requester.lastName,
                "avatarUrl": c.requester.avatarUrl,
                "roleType": c.requester.roleType.value if c.requester.roleType else None,
                "jobTitle": c.requester.jobTitle,
                "studyDomain": c.requester.studyDomain
            }
        d.pop('_sa_instance_state', None)
        res.append(d)
        
    return res

@router.get("/accepted")
def get_accepted_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Toutes les connexions acceptées (Amis / Contacts mutuels)
    conns = db.query(Connection).filter(
        (Connection.requesterId == current_user.id) | (Connection.addresseeId == current_user.id),
        Connection.status == ConnectionStatusEnum.ACCEPTED
    ).all()
    
    res = []
    for c in conns:
        d = c.__dict__.copy()
        target = c.addressee if c.requesterId == current_user.id else c.requester
        if target:
            d['targetUser'] = {
                "id": target.id,
                "firstName": target.firstName,
                "lastName": target.lastName,
                "avatarUrl": target.avatarUrl,
                "roleType": target.roleType.value if target.roleType else None,
                "jobTitle": target.jobTitle,
                "studyDomain": target.studyDomain
            }
        d.pop('_sa_instance_state', None)
        res.append(d)
        
    return res

@router.get("/accepted/professionals")
def get_accepted_professionals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    conns = db.query(Connection).filter(
        (Connection.requesterId == current_user.id) | (Connection.addresseeId == current_user.id),
        Connection.status == ConnectionStatusEnum.ACCEPTED
    ).all()
    
    res = []
    for c in conns:
        target = c.addressee if c.requesterId == current_user.id else c.requester
        if target and target.roleType and target.roleType.value == "professional":
            d = c.__dict__.copy()
            d['targetUser'] = {
                "id": target.id,
                "firstName": target.firstName,
                "lastName": target.lastName,
                "avatarUrl": target.avatarUrl,
                "roleType": target.roleType.value,
                "jobTitle": target.jobTitle,
                "studyDomain": target.studyDomain
            }
            d.pop('_sa_instance_state', None)
            res.append(d)
            
    return res

@router.get("/accepted/mentors")
def get_accepted_mentors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Les mentors sont les relations de type MENTORSHIP ou les professionnels
    conns = db.query(Connection).filter(
        (Connection.requesterId == current_user.id) | (Connection.addresseeId == current_user.id),
        Connection.status == ConnectionStatusEnum.ACCEPTED,
        Connection.type == ConnectionTypeEnum.MENTORSHIP
    ).all()
    
    res = []
    for c in conns:
        target = c.addressee if c.requesterId == current_user.id else c.requester
        if target:
            d = c.__dict__.copy()
            d['targetUser'] = {
                "id": target.id,
                "firstName": target.firstName,
                "lastName": target.lastName,
                "avatarUrl": target.avatarUrl,
                "roleType": target.roleType.value if target.roleType else None,
                "jobTitle": target.jobTitle,
                "studyDomain": target.studyDomain
            }
            d.pop('_sa_instance_state', None)
            res.append(d)
            
    return res
