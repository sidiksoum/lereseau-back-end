from fastapi import APIRouter, Depends, Form, UploadFile, File
from sqlalchemy.orm import Session
from app.api.dependencies.auth import get_db, require_role
from app.models.user import User
from app.models.feed import FeedPost
from app.models.document import Document
from app.models.opportunity import Opportunity
from typing import Optional, List
from app.services.storage import storage

router = APIRouter()

@router.post("/feed")
async def publish_feed(
    title: str = Form(...),
    content: str = Form(...),
    type: str = Form("TEXT"),
    files: Optional[List[UploadFile]] = File(None),
    imageUrls: Optional[str] = Form(None),
    videoUrl: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("ADMIN"))
):
    attachments = []
    if files:
        for file in files:
            url = await storage.upload_file(file, folder="feed")
            if url:
                attachments.append({"url": url, "type": file.content_type})
    elif imageUrls:
        # Accepte JSON array ou virgule
        import json
        try:
            urls = json.loads(imageUrls)
            if isinstance(urls, list):
                for u in urls: attachments.append({"url": u, "type": "image/jpeg"})
        except Exception:
            for u in imageUrls.split(','):
                if u.strip(): attachments.append({"url": u.strip(), "type": "image/jpeg"})
                
    if videoUrl:
        attachments.append({"url": videoUrl.strip(), "type": "video/external"})
                
    post = FeedPost(
        title=title,
        content=content,
        type=type,
        attachments=attachments if attachments else None,
        authorId=current_admin.id
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post

@router.post("/documents")
async def publish_document(
    title: str = Form(...),
    domain: Optional[str] = Form(None),
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
    current_admin: User = Depends(require_role("ADMIN"))
):
    # Priorité : fichier uploadé > documentUrlString > fileUrl > imageUrl/previewUrl
    resolved_url = documentUrlString or fileUrl or imageUrl or previewUrl
    final_file_url = resolved_url
    final_preview_url = previewUrl or imageUrl
    
    if file:
        uploaded_url = await storage.upload_file(file, folder="library")
        if uploaded_url: final_file_url = uploaded_url
        
    if not final_file_url and not final_preview_url:
        from fastapi import HTTPException
        raise HTTPException(400, "Vous devez fournir soit un fichier soit un URL.")
    
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
        authorId=current_admin.id,
        status="APPROVED"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

@router.post("/opportunities")
async def publish_opportunity(
    title: str = Form(...),
    organization: str = Form(...),
    domain: Optional[str] = Form(None),
    amount: str = Form(...),
    deadline: str = Form(...),
    fundingSource: Optional[str] = Form(None),
    targetAudience: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    eligibilityRequirements: Optional[str] = Form(None),
    applicationProcess: Optional[str] = Form(None),
    selectionCriteria: Optional[str] = Form(None),
    contactEmail: str = Form(...),
    contactPerson: Optional[str] = Form(None),
    applyUrl: Optional[str] = Form(None),
    bannerImg: Optional[UploadFile] = File(None),
    bannerUrlString: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("ADMIN"))
):
    attachments = None
    if bannerImg:
        url = await storage.upload_file(bannerImg, folder="opportunities")
        if url:
            attachments = [{"type": "banner", "url": url}]
    elif bannerUrlString:
        attachments = [{"type": "banner", "url": bannerUrlString}]
            
    from datetime import datetime
    parsed_deadline = None
    if deadline and deadline.lower() != "string":
        try:
            # Handle trailing Z for fromisoformat in Python < 3.11
            d_str = deadline.replace("Z", "+00:00")
            parsed_deadline = datetime.fromisoformat(d_str)
        except Exception:
            pass # Ignore invalid datetime string to avoid crash
            
    # Fix JSON types
    contact_person_json = {"name": contactPerson, "email": contactEmail} if contactPerson or contactEmail else None
    
    opp = Opportunity(
        title=title,
        organization=organization,
        type="SCHOLARSHIP", # fallback default for enum 
        domain=domain,
        amount=amount,
        deadline=parsed_deadline,
        fundingSource=fundingSource,
        targetAudience=targetAudience,
        description=description,
        eligibilityRequirements={"text": eligibilityRequirements} if eligibilityRequirements else None,
        applicationProcess={"text": applicationProcess} if applicationProcess else None,
        selectionCriteria={"text": selectionCriteria} if selectionCriteria else None,
        contactInfo=contactEmail, # Fix: Map to contactInfo
        contactPerson=contact_person_json, # Fix: Ensure JSON
        applyUrl=applyUrl,
        attachments=attachments,
        authorId=current_admin.id,
        isActive=True
    )
    db.add(opp)
    db.commit()
    db.refresh(opp)
    return opp

# --- Feed Updates/Deletions ---
@router.put("/feed/{id}")
async def update_feed(
    id: str,
    title: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    type: Optional[str] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
    imageUrls: Optional[str] = Form(None),
    videoUrl: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("ADMIN"))
):
    from fastapi import HTTPException
    post = db.query(FeedPost).filter(FeedPost.id == id).first()
    if not post: raise HTTPException(404, "Post introuvable")
    
    if title is not None: post.title = title
    if content is not None: post.content = content
    if type is not None: post.type = type
    
    attachments = []
    if files:
        for file in files:
            url = await storage.upload_file(file, folder="feed")
            if url: attachments.append({"url": url, "type": file.content_type})
    elif imageUrls:
        import json
        try:
            urls = json.loads(imageUrls)
            if isinstance(urls, list):
                for u in urls: attachments.append({"url": u, "type": "image/jpeg"})
        except Exception:
            for u in imageUrls.split(','):
                if u.strip(): attachments.append({"url": u.strip(), "type": "image/jpeg"})
                
    if videoUrl:
        attachments.append({"url": videoUrl.strip(), "type": "video/external"})
                
    if attachments:
        # Add to existing or replace? Replace to keep it simple as standard PUT/PATCH behavior for arrays
        post.attachments = attachments
            
    db.commit()
    db.refresh(post)
    return post

@router.delete("/feed/{id}")
def delete_feed(id: str, db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    from fastapi import HTTPException
    post = db.query(FeedPost).filter(FeedPost.id == id).first()
    if not post: raise HTTPException(404, "Post introuvable")
    db.delete(post)
    db.commit()
    return {"ok": True}

# --- Documents Updates/Deletions ---
@router.put("/documents/{id}")
async def update_document(
    id: str,
    title: Optional[str] = Form(None),
    domain: Optional[str] = Form(None),
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
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("ADMIN"))
):
    from fastapi import HTTPException
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc: raise HTTPException(404, "Document introuvable")
    
    if title is not None: doc.title = title
    
    cat_val = category or domain
    if cat_val is not None: doc.category = cat_val
        
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
    
    if file:
        file_url = await storage.upload_file(file, folder="library")
        if file_url: doc.fileUrl = file_url
    elif documentUrlString:
        doc.fileUrl = documentUrlString
        
    db.commit()
    db.refresh(doc)
    return doc

@router.delete("/documents/{id}")
def delete_document(id: str, db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    from fastapi import HTTPException
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc: raise HTTPException(404, "Document introuvable")
    db.delete(doc)
    db.commit()
    return {"ok": True}

# --- Opportunities Updates/Deletions ---
@router.put("/opportunities/{id}")
async def update_opportunity(
    id: str,
    title: Optional[str] = Form(None),
    organization: Optional[str] = Form(None),
    domain: Optional[str] = Form(None),
    amount: Optional[str] = Form(None),
    deadline: Optional[str] = Form(None),
    fundingSource: Optional[str] = Form(None),
    targetAudience: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    eligibilityRequirements: Optional[str] = Form(None),
    applicationProcess: Optional[str] = Form(None),
    selectionCriteria: Optional[str] = Form(None),
    contactEmail: Optional[str] = Form(None),
    contactPerson: Optional[str] = Form(None),
    applyUrl: Optional[str] = Form(None),
    bannerImg: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("ADMIN"))
):
    from fastapi import HTTPException
    opp = db.query(Opportunity).filter(Opportunity.id == id).first()
    if not opp: raise HTTPException(404, "Opportunité introuvable")
    
    if title is not None: opp.title = title
    if organization is not None: opp.organization = organization
    if domain is not None: opp.domain = domain
    if amount is not None: opp.amount = amount
    
    if deadline is not None and deadline.lower() != "string":
        from datetime import datetime
        try:
            d_str = deadline.replace("Z", "+00:00")
            opp.deadline = datetime.fromisoformat(d_str)
        except Exception:
            pass
            
    if fundingSource is not None: opp.fundingSource = fundingSource
    if targetAudience is not None: opp.targetAudience = targetAudience
    if description is not None: opp.description = description
    
    if eligibilityRequirements is not None: opp.eligibilityRequirements = {"text": eligibilityRequirements}
    if applicationProcess is not None: opp.applicationProcess = {"text": applicationProcess}
    if selectionCriteria is not None: opp.selectionCriteria = {"text": selectionCriteria}
    
    if contactEmail is not None: opp.contactInfo = contactEmail
    if contactPerson is not None or contactEmail is not None:
        c_person = opp.contactPerson or {}
        if isinstance(c_person, dict):
            if contactPerson: c_person["name"] = contactPerson
            if contactEmail: c_person["email"] = contactEmail
            opp.contactPerson = c_person
            
    if applyUrl is not None: opp.applyUrl = applyUrl
    
    if bannerImg:
        url = await storage.upload_file(bannerImg, folder="opportunities")
        if url: opp.attachments = [{"type": "banner", "url": url}]
    elif bannerUrlString:
        opp.attachments = [{"type": "banner", "url": bannerUrlString}]
        
    db.commit()
    db.refresh(opp)
    return opp

@router.delete("/opportunities/{id}")
def delete_opportunity(id: str, db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    from fastapi import HTTPException
    opp = db.query(Opportunity).filter(Opportunity.id == id).first()
    if not opp: raise HTTPException(404, "Opportunité introuvable")
    db.delete(opp)
    db.commit()
    return {"ok": True}
