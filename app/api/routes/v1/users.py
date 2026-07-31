from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Any, Optional
import json
from app.api.dependencies.auth import get_db, get_current_user, get_current_active_user
from app.models.user import User, Experience, Education, StatusEnum, RoleEnum
from app.models.network import Connection, ConnectionStatusEnum, ConnectionTypeEnum
from app.schemas.user import UserResponse, ExperienceCreate, ExperienceUpdate, ExperienceResource, EducationCreate, EducationUpdate, EducationResource
from app.services.storage import storage
from app.services.recommendations import score_profile_match

router = APIRouter()


def _serialize_user_for_response(db: Session, current_user: User, user: User) -> UserResponse:
    payload = UserResponse.model_validate(user).model_dump()

    try:
        follow_relation = (
            db.query(Connection)
            .filter(
                Connection.requesterId == current_user.id,
                Connection.addresseeId == user.id,
                Connection.status == ConnectionStatusEnum.ACCEPTED,
            )
            .all()
        )
        reverse_relation = (
            db.query(Connection)
            .filter(
                Connection.requesterId == user.id,
                Connection.addresseeId == current_user.id,
                Connection.status == ConnectionStatusEnum.ACCEPTED,
            )
            .all()
        )
        follow_relation = next((item for item in follow_relation if getattr(item, "type", None) in {ConnectionTypeEnum.FOLLOWER, ConnectionTypeEnum.FOLLOWING}), None)
        reverse_relation = next((item for item in reverse_relation if getattr(item, "type", None) in {ConnectionTypeEnum.FOLLOWER, ConnectionTypeEnum.FOLLOWING}), None)
    except Exception:
        follow_relation = None
        reverse_relation = None

    payload.update(
        {
            "isFollowing": follow_relation is not None,
            "isFollowed": reverse_relation is not None,
            "followedByMe": follow_relation is not None,
            "iFollow": follow_relation is not None,
        }
    )
    return UserResponse(**payload)


@router.get("/", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=12, ge=1, le=50),
):
    blocked_ids = set()
    conns = db.query(Connection).filter(((Connection.requesterId == current_user.id) | (Connection.addresseeId == current_user.id))).all()
    for conn in conns:
        if conn.requesterId == current_user.id:
            blocked_ids.add(conn.addresseeId)
        else:
            blocked_ids.add(conn.requesterId)

    query = (
        db.query(User)
        .filter(
            User.id != current_user.id,
            User.status != StatusEnum.BANNED,
            User.role != RoleEnum.ADMIN,
            User.role != RoleEnum.SUPER_ADMIN,
        )
        .filter(~User.id.in_(list(blocked_ids)))
    )
    if q:
        like_q = f"%{q}%"
        query = query.filter(or_(User.firstName.ilike(like_q), User.lastName.ilike(like_q), User.jobTitle.ilike(like_q), User.studyDomain.ilike(like_q)))

    candidates = query.all()
    scored = []
    for candidate in candidates:
        scored.append((score_profile_match(current_user, candidate), candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [_serialize_user_for_response(db, current_user, candidate) for _, candidate in scored[:limit]]


@router.get("/students", response_model=list[UserResponse])
def get_students(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    users = (
        db.query(User)
        .filter(User.roleType == "student", User.role != RoleEnum.ADMIN, User.role != RoleEnum.SUPER_ADMIN)
        .all()
    )
    return [_serialize_user_for_response(db, current_user, user) for user in users]


@router.get("/professionals", response_model=list[UserResponse])
def get_professionals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    users = db.query(User).filter(User.roleType == "professional").all()
    return [_serialize_user_for_response(db, current_user, user) for user in users]


@router.get("/institutions", response_model=list[UserResponse])
def get_institutions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    users = (
        db.query(User)
        .filter(User.roleType == "institution", User.role != RoleEnum.ADMIN, User.role != RoleEnum.SUPER_ADMIN)
        .all()
    )
    return [_serialize_user_for_response(db, current_user, user) for user in users]


@router.get("/mentors", response_model=list[UserResponse])
def get_mentors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    users = (
        db.query(User)
        .filter(User.roleType == "professional", User.role != RoleEnum.ADMIN, User.role != RoleEnum.SUPER_ADMIN)
        .all()
    )
    return [_serialize_user_for_response(db, current_user, user) for user in users]


@router.get("/premium-mentors", response_model=list[UserResponse])
def get_premium_certified_mentors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not current_user.isPremium and current_user.role.value != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="L'accès à cette liste est strictement réservé aux membres Premium.")

    users = (
        db.query(User)
        .filter(
            User.roleType == "professional",
            User.nineaUploaded == True,
            User.isPremium == True,
            User.role != RoleEnum.ADMIN,
            User.role != RoleEnum.SUPER_ADMIN,
        )
        .all()
    )
    return [_serialize_user_for_response(db, current_user, user) for user in users]


@router.get("/me", response_model=UserResponse)
def read_current_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return _serialize_user_for_response(db, current_user, current_user)


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    *,
    db: Session = Depends(get_db),
    firstName: Optional[str] = Form(None),
    lastName: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    about: Optional[str] = Form(None),
    educationLevel: Optional[str] = Form(None),
    studyDomain: Optional[str] = Form(None),
    jobTitle: Optional[str] = Form(None),
    workDomain: Optional[str] = Form(None),
    institutionType: Optional[str] = Form(None),
    institutionDetails: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    linkedin: Optional[str] = Form(None),
    skills: Optional[str] = Form(None),
    settings: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    avatarUrlString: Optional[str] = Form(None),
    cover: Optional[UploadFile] = File(None),
    coverUrlString: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    fields = {
        "firstName": firstName,
        "lastName": lastName,
        "phone": phone,
        "about": about,
        "educationLevel": educationLevel,
        "studyDomain": studyDomain,
        "jobTitle": jobTitle,
        "workDomain": workDomain,
        "institutionType": institutionType,
        "institutionDetails": institutionDetails,
        "location": location,
        "linkedin": linkedin,
    }

    for key, value in fields.items():
        if value is not None:
            setattr(current_user, key, value)

    if skills is not None:
        try:
            current_user.skills = json.loads(skills)
        except json.JSONDecodeError:
            pass

    if settings is not None:
        try:
            current_user.settings = json.loads(settings)
        except json.JSONDecodeError:
            pass

    if avatar:
        url = await storage.upload_file(avatar, folder="avatars")
        if url:
            current_user.avatarUrl = url
    elif avatarUrlString:
        current_user.avatarUrl = avatarUrlString

    if cover:
        url = await storage.upload_file(cover, folder="covers")
        if url:
            current_user.coverUrl = url
    elif coverUrlString:
        current_user.coverUrl = coverUrlString

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/experiences", response_model=ExperienceResource)
def create_experience(*, db: Session = Depends(get_db), exp_in: ExperienceCreate, current_user: User = Depends(get_current_active_user)):
    exp = Experience(**exp_in.model_dump(), user_id=current_user.id)
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


@router.delete("/me/experiences/{id}")
def delete_experience(*, db: Session = Depends(get_db), id: int, current_user: User = Depends(get_current_active_user)):
    exp = db.query(Experience).filter(Experience.id == id, Experience.user_id == current_user.id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    db.delete(exp)
    db.commit()
    return {"ok": True}


@router.post("/me/educations", response_model=EducationResource)
def create_education(*, db: Session = Depends(get_db), edu_in: EducationCreate, current_user: User = Depends(get_current_active_user)):
    edu = Education(**edu_in.model_dump(), user_id=current_user.id)
    db.add(edu)
    db.commit()
    db.refresh(edu)
    return edu


@router.delete("/me/educations/{id}")
def delete_education(*, db: Session = Depends(get_db), id: int, current_user: User = Depends(get_current_active_user)):
    edu = db.query(Education).filter(Education.id == id, Education.user_id == current_user.id).first()
    if not edu:
        raise HTTPException(status_code=404, detail="Education not found")
    db.delete(edu)
    db.commit()
    return {"ok": True}


@router.patch("/me/experiences/{id}", response_model=ExperienceResource)
def update_experience(*, db: Session = Depends(get_db), id: int, exp_in: ExperienceUpdate, current_user: User = Depends(get_current_active_user)):
    exp = db.query(Experience).filter(Experience.id == id, Experience.user_id == current_user.id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")

    for key, value in exp_in.model_dump(exclude_unset=True).items():
        setattr(exp, key, value)

    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


@router.patch("/me/educations/{id}", response_model=EducationResource)
def update_education(*, db: Session = Depends(get_db), id: int, edu_in: EducationUpdate, current_user: User = Depends(get_current_active_user)):
    edu = db.query(Education).filter(Education.id == id, Education.user_id == current_user.id).first()
    if not edu:
        raise HTTPException(status_code=404, detail="Education not found")

    for key, value in edu_in.model_dump(exclude_unset=True).items():
        setattr(edu, key, value)

    db.add(edu)
    db.commit()
    db.refresh(edu)
    return edu


@router.get("/{id}", response_model=UserResponse)
def read_user_by_id(id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _serialize_user_for_response(db, current_user, user)


@router.post("/me/certification-request")
def request_certification(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if current_user.roleType not in ["professional", "institution"]:
        raise HTTPException(status_code=400, detail="Only professionals or institutions can request certification.")

    current_user.kycDocumentUrl = "PENDING_REQUEST"
    current_user.nineaUploaded = False
    db.commit()

    return {"ok": True, "message": "Demande de certification envoyée avec succès."}


@router.post("/me/premium-request")
def request_premium(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if current_user.isPremium:
        raise HTTPException(status_code=400, detail="Vous êtes déjà Premium.")

    current_user.premiumPaymentMethod = "PENDING_REQUEST"
    current_user.isPremium = False
    db.commit()

    return {"ok": True, "message": "Demande Premium envoyée avec succès."}
