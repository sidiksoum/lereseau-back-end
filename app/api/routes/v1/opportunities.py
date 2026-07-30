from datetime import datetime
from time import perf_counter
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from typing import List, Optional
from app.api.dependencies.auth import get_db, get_current_active_user
from app.models.opportunity import Opportunity
from app.models.user import User
from app.schemas.opportunity import OpportunityCreate, OpportunityResponse
from app.services.recommendations import score_opportunity_match
from app.services.cache import cache, make_jsonable
from app.services.metrics import metrics
from app.services.logging import logger

router = APIRouter()


@router.get("/", response_model=List[OpportunityResponse])
def list_opportunities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    q: Optional[str] = Query(default=None),
    domain: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
):
    started = perf_counter()
    cache_key = f"opportunities:{current_user.id}:{q or ''}:{domain or ''}:{limit}:{cursor or ''}"
    cached = cache.get(cache_key)
    if cached is not None:
        metrics.increment("opportunities_cache_hits")
        return make_jsonable(cached)

    query = db.query(Opportunity).filter(Opportunity.isActive == True)
    if q:
        like_q = f"%{q}%"
        query = query.filter(or_(Opportunity.title.ilike(like_q), Opportunity.description.ilike(like_q), Opportunity.organization.ilike(like_q)))
    if domain:
        query = query.filter(Opportunity.domain.ilike(f"%{domain}%"))
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(400, detail="cursor invalide") from exc
        query = query.filter(Opportunity.createdAt < cursor_dt)

    opportunities = query.order_by(desc(Opportunity.createdAt)).limit(limit + 1).all()
    items = opportunities[:limit]
    scored = [(score_opportunity_match(current_user, opp), opp) for opp in items]
    scored.sort(key=lambda item: item[0], reverse=True)
    result = make_jsonable([opp for _, opp in scored])
    cache.set(cache_key, result, ttl=120)
    metrics.increment("opportunities_cache_misses")
    metrics.observe("opportunities_latency_ms", (perf_counter() - started) * 1000)
    logger.info("opportunities_served", extra={"request_id": str(current_user.id), "limit": limit})
    return result


@router.post("/me/publish", response_model=OpportunityResponse)
def publish_opportunity(
    *,
    db: Session = Depends(get_db),
    op_in: OpportunityCreate,
    current_user: User = Depends(get_current_active_user),
):
    if current_user.roleType.value != "institution":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seules les institutions peuvent publier des bourses directement.")

    new_op = Opportunity(**op_in.model_dump(), authorId=current_user.id)
    if current_user.isPremium:
        new_op.isBoosted = True

    db.add(new_op)
    db.commit()
    db.refresh(new_op)
    return make_jsonable(new_op)


@router.get("/{id}", response_model=OpportunityResponse)
def get_opportunity(id: str, db: Session = Depends(get_db)):
    op = db.query(Opportunity).filter(Opportunity.id == id).first()
    if not op:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return make_jsonable(op)
