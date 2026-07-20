from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File
from sqlalchemy.orm import Session
from app.api.dependencies.auth import get_db, get_current_active_user
from app.models.user import User
from app.models.document import Document
from app.services.storage import storage
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
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Only Mentor (Pro + certified) or Institution
    is_mentor = current_user.roleType.value == "professional" and current_user.nineaUploaded
    is_inst = current_user.roleType.value == "institution"
    
    if not (is_mentor or is_inst):
        raise HTTPException(403, "Seuls les institutions et mentors certifiés peuvent publier.")

    file_url = await storage.upload_file(file, folder="library")

    doc = Document(
        title=title,
        category=domain,
        price=price,
        description=description,
        pagesCount=pagesCount,
        format=format,
        author=author,
        publicationYear=publicationYear,
        publisher=publisher,
        associatedCourse=associatedCourse,
        edition=edition,
        referenceKey=referenceKey,
        tags=tags.split(',') if tags else None,
        fileUrl=file_url,
        authorId=current_user.id,
        status="APPROVED" if is_inst else "PENDING"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

@router.get("/")
def list_documents(db: Session = Depends(get_db)):
    return db.query(Document).filter(Document.status == "APPROVED").all()

@router.get("/{id}")
def get_document(id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")
    
    # Renvoyer les infos de l'auteur
    author = db.query(User).filter(User.id == doc.authorId).first()
    
    doc_dict = {
        **doc.__dict__,
        "authorDetails": {
            "firstName": author.firstName,
            "lastName": author.lastName,
            "avatarUrl": author.avatarUrl,
            "roleType": author.roleType,
            "jobTitle": author.jobTitle,
            "institutionType": author.institutionType
        } if author else None
    }
    doc_dict.pop('_sa_instance_state', None)
    return doc_dict
