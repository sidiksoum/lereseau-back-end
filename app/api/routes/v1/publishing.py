"""
Endpoints de publication pour les utilisateurs Premium (Professionnels certifiés & Institutions).
Fonctionnalités :
  - Publier une annonce Feed (POST /publishing/feed)
  - Publier un document (POST /publishing/documents)
  - Récupérer ses propres annonces feed (GET /publishing/feed)
  - Récupérer ses propres documents (GET /publishing/documents)
"""

import json
from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional, List

from app.api.dependencies.auth import get_db, get_current_active_user
from app.models.user import User, RoleTypeEnum
from app.models.feed import FeedPost, FeedPostStatusEnum, FeedLike
from app.models.document import Document
from app.services.storage import storage

router = APIRouter()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _require_premium_publisher(current_user: User) -> User:
    """
    Vérifie que l'utilisateur est autorisé à publier des annonces :
    - Professionnel Premium
    - Institution Premium
    Lève une 403 sinon.
    """
    is_premium = current_user.isPremium is True
    is_eligible_type = current_user.roleType in [RoleTypeEnum.professional, RoleTypeEnum.institution]

    if not (is_eligible_type and is_premium):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "La publication d'annonces est réservée aux Professionnels "
                "et Institutions Premium."
            ),
        )
    return current_user


def _parse_image_urls(image_urls_str: str) -> list:
    """Parse imageUrls en JSON array ou CSV."""
    result = []
    try:
        parsed = json.loads(image_urls_str)
        if isinstance(parsed, list):
            for u in parsed:
                result.append({"url": u, "type": "image/jpeg"})
    except Exception:
        for u in image_urls_str.split(','):
            if u.strip():
                result.append({"url": u.strip(), "type": "image/jpeg"})
    return result


# ─── Feed ─────────────────────────────────────────────────────────────────────

@router.post("/feed", status_code=status.HTTP_201_CREATED)
async def publish_feed_as_user(
    title: str = Form(...),
    content: str = Form(...),
    type: str = Form("TEXT"),
    files: Optional[List[UploadFile]] = File(None),
    imageUrls: Optional[str] = Form(None),
    videoUrl: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Publie une annonce de type feed.
    Réservé aux Professionnels certifiés + Premium et Institutions certifiées + Premium.
    """
    _require_premium_publisher(current_user)

    attachments = []
    if files:
        for file in files:
            url = await storage.upload_file(file, folder="feed")
            if url:
                attachments.append({"url": url, "type": file.content_type})
    elif imageUrls:
        attachments = _parse_image_urls(imageUrls)

    if videoUrl:
        attachments.append({"url": videoUrl.strip(), "type": "video/external"})

    post = FeedPost(
        title=title,
        content=content,
        type=type,
        attachments=attachments if attachments else None,
        authorId=current_user.id,
        status=FeedPostStatusEnum.APPROVED,  # Approuvé directement pour les premium
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.get("/feed")
def get_my_feed_posts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Récupère toutes les annonces feed de l'utilisateur connecté."""
    _require_premium_publisher(current_user)
    posts = (
        db.query(FeedPost)
        .filter(FeedPost.authorId == current_user.id)
        .order_by(desc(FeedPost.createdAt))
        .all()
    )
    
    # Pre-fetch liked post IDs for current user in one query
    post_ids = [p.id for p in posts]
    liked_post_ids = set()
    if post_ids and current_user:
        likes = db.query(FeedLike.postId).filter(FeedLike.postId.in_(post_ids), FeedLike.userId == current_user.id).all()
        liked_post_ids = {l.postId for l in likes}

    res = []
    for p in posts:
        d = p.__dict__.copy()
        d['liked'] = p.id in liked_post_ids
        d.pop('_sa_instance_state', None)
        res.append(d)
        
    return res


@router.delete("/feed/{post_id}")
def delete_my_feed_post(
    post_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Supprime une de ses propres annonces feed."""
    _require_premium_publisher(current_user)
    post = db.query(FeedPost).filter(
        FeedPost.id == post_id,
        FeedPost.authorId == current_user.id
    ).first()
    if not post:
        raise HTTPException(404, "Annonce introuvable ou vous n'êtes pas l'auteur.")
    db.delete(post)
    db.commit()
    return {"ok": True}


# ─── Documents ────────────────────────────────────────────────────────────────

@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def publish_document_as_user(
    title: str = Form(...),
    category: Optional[str] = Form(None),
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
    # Accepte plusieurs noms de champ pour l'URL (compatibilité frontend)
    documentUrlString: Optional[str] = Form(None),
    fileUrl: Optional[str] = Form(None),
    imageUrl: Optional[str] = Form(None),
    previewUrl: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Publie un document dans la bibliothèque.
    Réservé aux Professionnels Premium et Institutions Premium.
    Accepte: un fichier uploadé OU une URL de fichier OU une URL d'image de couverture.
    """
    _require_premium_publisher(current_user)

    # Résoudre l'URL de document : priorité au fichier uploadé, sinon l'URL fournie sous n'importe quel nom
    resolved_file_url = documentUrlString or fileUrl or imageUrl or previewUrl
    
    final_file_url = resolved_file_url  # peut être None si image fournie séparément
    final_preview_url = previewUrl or imageUrl  # URL de couverture/prévisualisation
    
    if file:
        uploaded_url = await storage.upload_file(file, folder="library")
        if uploaded_url:
            final_file_url = uploaded_url

    author_metadata = {"name": author} if author else None

    doc = Document(
        title=title,
        category=category or domain or "Général",
        price=price,
        description=description,
        pagesCount=pagesCount,
        format=format,
        authorDetails=author_metadata,
        publicationYear=publicationYear,
        publisher=publisher,
        associatedCourse=associatedCourse,
        edition=edition,
        referenceKey=referenceKey,
        tags=tags.split(',') if tags else None,
        fileUrl=final_file_url,
        previewUrl=final_preview_url,
        authorId=current_user.id,
        status="APPROVED",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/documents")
def get_my_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Récupère tous les documents publiés par l'utilisateur connecté."""
    _require_premium_publisher(current_user)
    docs = (
        db.query(Document)
        .filter(Document.authorId == current_user.id)
        .order_by(desc(Document.createdAt))
        .all()
    )
    return docs


@router.put("/documents/{doc_id}")
async def update_my_document(
    doc_id: str,
    title: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
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
    documentUrlString: Optional[str] = Form(None),
    fileUrl: Optional[str] = Form(None),
    imageUrl: Optional[str] = Form(None),
    previewUrl: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Met à jour un document dont l'utilisateur est l'auteur."""
    _require_premium_publisher(current_user)
    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.authorId == current_user.id
    ).first()
    if not doc:
        raise HTTPException(404, "Document introuvable ou vous n'êtes pas l'auteur.")

    if title is not None: doc.title = title
    if category is not None: doc.category = category
    if price is not None: doc.price = price
    if description is not None: doc.description = description
    if pagesCount is not None: doc.pagesCount = pagesCount
    if format is not None: doc.format = format
    if author is not None: doc.authorDetails = {"name": author}
    if publicationYear is not None: doc.publicationYear = publicationYear
    if publisher is not None: doc.publisher = publisher
    if associatedCourse is not None: doc.associatedCourse = associatedCourse
    if edition is not None: doc.edition = edition
    if referenceKey is not None: doc.referenceKey = referenceKey
    if tags is not None: doc.tags = tags.split(',')

    # Résoudre l'URL : fichier uploadé en priorité, sinon n'importe lequel des alias
    resolved_url = documentUrlString or fileUrl or imageUrl or previewUrl
    if file:
        url = await storage.upload_file(file, folder="library")
        if url: doc.fileUrl = url
    elif resolved_url:
        doc.fileUrl = resolved_url
    
    if previewUrl or imageUrl:
        doc.previewUrl = previewUrl or imageUrl

    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/documents/{doc_id}")
def delete_my_document(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Supprime un de ses propres documents."""
    _require_premium_publisher(current_user)
    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.authorId == current_user.id
    ).first()
    if not doc:
        raise HTTPException(404, "Document introuvable ou vous n'êtes pas l'auteur.")
    db.delete(doc)
    db.commit()
    return {"ok": True}
