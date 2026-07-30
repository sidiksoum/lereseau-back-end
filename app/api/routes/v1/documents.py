from datetime import datetime
from time import perf_counter
from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from app.api.dependencies.auth import get_db, get_current_active_user
from app.models.user import User
from app.models.document import Document
from app.services.storage import storage
from app.services.recommendations import score_document_match
from app.services.cache import cache, make_jsonable
from app.services.metrics import metrics
from app.services.logging import logger
from typing import Optional

router = APIRouter()


@router.post("/pro/publish")
async def publish_document(
    title: str = Form(...),
    domain: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    description: Optional[str] = Form(None),
    pagesCount: Optional[int] = Form(None),
    format: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    publicationYear: Optional[int] = Form(None),
    publisher: Optional[str] = Form(None),
    associatedCourse: Optional[str] = Form(None),
    edition: Optional[str] = Form(None),
    referenceKey: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    externalUrl: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    is_mentor = current_user.roleType.value == "professional" and current_user.nineaUploaded
    is_inst = current_user.roleType.value == "institution"

    if not (is_mentor or is_inst):
        raise HTTPException(403, "Seuls les institutions et mentors certifiés peuvent publier.")

    preview_url = ""
    if file:
        preview_url = await storage.upload_document_cover(file, folder="library")

    doc = Document(
        title=title,
        category=domain or "Général",
        price=price,
        description=description,
        pagesCount=pagesCount,
        format=format,
        authorDetails={"name": author} if author else None,
        publicationYear=publicationYear,
        publisher=publisher,
        associatedCourse=associatedCourse,
        edition=edition,
        referenceKey=referenceKey,
        tags=tags.split(',') if tags else None,
        fileUrl=externalUrl or preview_url or "",
        previewUrl=preview_url or externalUrl or "",
        authorId=current_user.id,
        status="APPROVED" if is_inst else "PENDING",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return make_jsonable(doc)


@router.get("/")
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    q: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    isPremium: Optional[bool] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
):
    started = perf_counter()
    cache_key = f"documents:{current_user.id}:{q or ''}:{category or ''}:{str(isPremium) if isPremium is not None else ''}:{limit}:{cursor or ''}"
    cached = cache.get(cache_key)
    if cached is not None:
        metrics.increment("documents_cache_hits")
        return make_jsonable(cached)

    query = db.query(Document).filter(Document.status == "APPROVED")
    if q:
        like_q = f"%{q}%"
        query = query.filter(or_(Document.title.ilike(like_q), Document.description.ilike(like_q), Document.category.ilike(like_q)))
    if category:
        query = query.filter(Document.category.ilike(f"%{category}%"))
    if isPremium is not None:
        query = query.filter(Document.isPremium == isPremium)
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(400, detail="cursor invalide") from exc
        query = query.filter(Document.createdAt < cursor_dt)

    documents = query.order_by(desc(Document.createdAt)).limit(limit + 1).all()
    items = documents[:limit]
    scored = []
    for doc in items:
        scored.append((score_document_match(current_user, doc), doc))
    scored.sort(key=lambda item: item[0], reverse=True)
    result = make_jsonable([doc for _, doc in scored])
    cache.set(cache_key, result, ttl=120)
    metrics.increment("documents_cache_misses")
    metrics.observe("documents_latency_ms", (perf_counter() - started) * 1000)
    logger.info("documents_served", extra={"request_id": str(current_user.id), "limit": limit})
    return result


@router.get("/{id}")
def get_document(id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")

    author = db.query(User).filter(User.id == doc.authorId).first()

    doc_dict = {
        **doc.__dict__,
        "authorDetails": {
            "firstName": author.firstName,
            "lastName": author.lastName,
            "avatarUrl": author.avatarUrl,
            "roleType": author.roleType,
            "jobTitle": author.jobTitle,
            "institutionType": author.institutionType,
        } if author else None,
    }
    doc_dict.pop("_sa_instance_state", None)
    return make_jsonable(doc_dict)
