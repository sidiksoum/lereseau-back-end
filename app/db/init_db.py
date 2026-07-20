from sqlalchemy.orm import Session
from app.models.user import User, RoleEnum, StatusEnum, RoleTypeEnum
from app.core import security

def init_super_admin(db: Session):
    admin_email = "admin@lereseau.com"
    user = db.query(User).filter(User.email == admin_email).first()
    if not user:
        hashed_password = security.get_password_hash("Admin123!")
        new_admin = User(
            email=admin_email,
            passwordHash=hashed_password,
            firstName="Super",
            lastName="Admin",
            roleType=RoleTypeEnum.professional,
            role=RoleEnum.SUPER_ADMIN,
            status=StatusEnum.VERIFIED,
            isPremium=True,
            nineaUploaded=True,
            isEmailVerified=True
        )
        db.add(new_admin)
        db.commit()
        print("Super Admin created: admin@lereseau.com / Admin123!")
    else:
        print("Super Admin already exists.")
