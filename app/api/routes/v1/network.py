from time import perf_counter
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.api.dependencies.auth import get_db, get_current_active_user
from app.models.user import User, StatusEnum, RoleEnum
from app.models.network import Connection, ConnectionTypeEnum, ConnectionStatusEnum
from app.services.recommendations import score_profile_match
from app.services.cache import cache
from app.services.metrics import metrics
from app.services.logging import logger
from typing import Optional

router = APIRouter()


def _summary_for_user(user: User):
    return {
        "id": user.id,
        "firstName": user.firstName,
        "lastName": user.lastName,
        "avatarUrl": user.avatarUrl,
        "roleType": user.roleType.value if user.roleType else None,
        "jobTitle": user.jobTitle,
        "studyDomain": user.studyDomain,
        "location": user.location,
        "workDomain": user.workDomain,
        "institutionType": user.institutionType,
    }


def _connected_user_ids(db: Session, current_user: User) -> set[str]:
    conns = db.query(Connection).filter(
        ((Connection.requesterId == current_user.id) | (Connection.addresseeId == current_user.id))
    ).all()
    blocked = set()
    for conn in conns:
        if conn.requesterId == current_user.id:
            blocked.add(conn.addresseeId)
        else:
            blocked.add(conn.requesterId)
    return blocked


@router.post("/request/{to_user_id}")
async def send_connection_request(
    to_user_id: str,
    type: ConnectionTypeEnum,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.services.notifications import NotificationService
    from app.models.notification import NotificationTypeEnum

    if to_user_id == current_user.id:
        raise HTTPException(400, "Impossible de s'envoyer une demande.")

    target = db.query(User).filter(User.id == to_user_id).first()
    if not target:
        raise HTTPException(404, "Utilisateur introuvable.")

    conn = Connection(requesterId=current_user.id, addresseeId=to_user_id, type=type, status=ConnectionStatusEnum.PENDING)
    db.add(conn)
    db.commit()
    db.refresh(conn)

    await NotificationService.push_notification(
        db=db,
        user_id=to_user_id,
        type=NotificationTypeEnum.FRIEND_REQUEST,
        message=f"{current_user.firstName} vous a envoyé une demande de connexion.",
        data={"connectionId": conn.id},
    )

    return conn


@router.put("/accept/{connection_id}")
def accept_connection(connection_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if not conn or conn.addresseeId != current_user.id:
        raise HTTPException(404, "Demande introuvable ou vous n'êtes pas destinataire.")

    conn.status = ConnectionStatusEnum.ACCEPTED
    db.commit()
    db.refresh(conn)
    return conn


@router.put("/reject/{connection_id}")
@router.delete("/reject/{connection_id}")
def reject_connection(connection_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if not conn:
        raise HTTPException(404, "Demande introuvable.")

    if current_user.id not in [conn.addresseeId, conn.requesterId]:
        raise HTTPException(403, "Non autorisé à modifier cette demande.")

    if current_user.id == conn.requesterId:
        db.delete(conn)
    else:
        conn.status = ConnectionStatusEnum.REJECTED

    db.commit()
    return {"ok": True}


@router.post("/follow/{institution_id}")
def follow_institution(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    target = db.query(User).filter(User.id == institution_id, User.roleType == "institution").first()
    if not target:
        raise HTTPException(404, "Institution introuvable.")

    existing = (
        db.query(Connection)
        .filter(
            Connection.requesterId == current_user.id,
            Connection.addresseeId == institution_id,
        )
        .all()
    )
    follow_relation = next((item for item in existing if getattr(item, "type", None) in {ConnectionTypeEnum.FOLLOWER, ConnectionTypeEnum.FOLLOWING}), None)
    if follow_relation:
        if getattr(follow_relation, "type", None) != ConnectionTypeEnum.FOLLOWER:
            follow_relation.type = ConnectionTypeEnum.FOLLOWER
            follow_relation.status = ConnectionStatusEnum.ACCEPTED
            db.commit()
            db.refresh(follow_relation)
        return follow_relation

    conn = Connection(
        requesterId=current_user.id,
        addresseeId=institution_id,
        type=ConnectionTypeEnum.FOLLOWER,
        status=ConnectionStatusEnum.ACCEPTED,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@router.get("/suggestions")
def get_smart_suggestions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    limit: int = Query(default=12, ge=1, le=50),
):
    started = perf_counter()
    cache_key = f"network_suggestions:{current_user.id}:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        metrics.increment("network_cache_hits")
        return cached

    cache.delete(cache_key)

    blocked_ids = _connected_user_ids(db, current_user)
    users = (
        db.query(User)
        .filter(
            User.id != current_user.id,
            User.status != StatusEnum.BANNED,
            User.role != RoleEnum.ADMIN,
            User.role != RoleEnum.SUPER_ADMIN,
        )
        .all()
    )
    scored = []
    for candidate in users:
        if candidate.id in blocked_ids:
            continue
        scored.append((score_profile_match(current_user, candidate), candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    result = [{**_summary_for_user(candidate), "matchScore": score} for score, candidate in scored[:limit]]
    cache.set(cache_key, result, ttl=180)
    metrics.increment("network_cache_misses")
    metrics.observe("network_latency_ms", (perf_counter() - started) * 1000)
    logger.info("network_suggestions_served", extra={"request_id": str(current_user.id), "limit": limit})
    return result


@router.get("/")
def get_my_network(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    conns = db.query(Connection).filter((Connection.requesterId == current_user.id) | (Connection.addresseeId == current_user.id)).order_by(desc(Connection.createdAt)).all()

    res = []
    for c in conns:
        d = c.__dict__.copy()
        target = c.addressee if c.requesterId == current_user.id else c.requester
        if target:
            d["targetUser"] = _summary_for_user(target)
        d.pop("_sa_instance_state", None)
        res.append(d)

    return res


@router.get("/outgoing")
def get_outgoing_requests(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    conns = db.query(Connection).filter(Connection.requesterId == current_user.id, Connection.status.in_([ConnectionStatusEnum.PENDING, ConnectionStatusEnum.ACCEPTED])).all()

    res = []
    for c in conns:
        d = c.__dict__.copy()
        if c.addressee:
            d["addresseeDetails"] = _summary_for_user(c.addressee)
        d.pop("_sa_instance_state", None)
        res.append(d)

    return res


@router.get("/incoming")
def get_incoming_requests(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    conns = db.query(Connection).filter(Connection.addresseeId == current_user.id, Connection.status == ConnectionStatusEnum.PENDING).all()

    res = []
    for c in conns:
        d = c.__dict__.copy()
        if c.requester:
            d["requesterDetails"] = _summary_for_user(c.requester)
        d.pop("_sa_instance_state", None)
        res.append(d)

    return res


@router.get("/accepted")
def get_accepted_connections(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    conns = db.query(Connection).filter(
        ((Connection.requesterId == current_user.id) | (Connection.addresseeId == current_user.id)),
        Connection.status == ConnectionStatusEnum.ACCEPTED,
        Connection.type.notin_([ConnectionTypeEnum.FOLLOWER, ConnectionTypeEnum.FOLLOWING]),
    ).all()

    res = []
    for c in conns:
        d = c.__dict__.copy()
        target = c.addressee if c.requesterId == current_user.id else c.requester
        if target:
            d["targetUser"] = _summary_for_user(target)
        d.pop("_sa_instance_state", None)
        res.append(d)

    return res


@router.get("/accepted/professionals")
def get_accepted_professionals(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    conns = db.query(Connection).filter(
        ((Connection.requesterId == current_user.id) | (Connection.addresseeId == current_user.id)),
        Connection.status == ConnectionStatusEnum.ACCEPTED,
        Connection.type.notin_([ConnectionTypeEnum.FOLLOWER, ConnectionTypeEnum.FOLLOWING]),
    ).all()

    res = []
    for c in conns:
        target = c.addressee if c.requesterId == current_user.id else c.requester
        if target and target.roleType and target.roleType.value == "professional":
            d = c.__dict__.copy()
            d["targetUser"] = _summary_for_user(target)
            d.pop("_sa_instance_state", None)
            res.append(d)

    return res


@router.get("/accepted/mentors")
def get_accepted_mentors(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    conns = db.query(Connection).filter(
        ((Connection.requesterId == current_user.id) | (Connection.addresseeId == current_user.id)),
        Connection.status == ConnectionStatusEnum.ACCEPTED,
        Connection.type == ConnectionTypeEnum.MENTORSHIP,
    ).all()

    res = []
    for c in conns:
        target = c.addressee if c.requesterId == current_user.id else c.requester
        if target:
            d = c.__dict__.copy()
            d["targetUser"] = _summary_for_user(target)
            d.pop("_sa_instance_state", None)
            res.append(d)

    return res
