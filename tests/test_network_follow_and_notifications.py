import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.api.dependencies.auth import get_current_active_user, get_db
from app.api.routes.v1.network import router as network_router
from app.api.routes.v1.publishing import router as publishing_router
from app.db.base import Base
from app.models.feed import FeedPost
from app.models.network import Connection, ConnectionStatusEnum, ConnectionTypeEnum
from app.models.notification import Notification, NotificationTypeEnum
from app.models.user import RoleEnum, RoleTypeEnum, StatusEnum, User


@pytest.fixture()
def client_and_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(network_router, prefix="/api/network")
    app.include_router(publishing_router, prefix="/api/publishing")
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        db = TestingSessionLocal()
        try:
            yield client, db
        finally:
            db.close()


def _create_user(db, *, email, role_type, is_premium=False, status=StatusEnum.VERIFIED):
    user = User(
        email=email,
        passwordHash="hashed",
        firstName="Test",
        lastName="User",
        roleType=role_type,
        role=RoleEnum.USER,
        status=status,
        isPremium=is_premium,
        isEmailVerified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_follow_endpoint_creates_follower_relation_and_not_accepted_connection(client_and_db):
    client, db = client_and_db

    institution = _create_user(db, email="institution@example.com", role_type=RoleTypeEnum.institution, is_premium=True)
    follower = _create_user(db, email="follower@example.com", role_type=RoleTypeEnum.student)

    def override_current_user():
        return follower

    client.app.dependency_overrides[get_current_active_user] = override_current_user

    response = client.post(f"/api/network/follow/{institution.id}")
    assert response.status_code == 200

    relation = db.query(Connection).filter(
        Connection.requesterId == follower.id,
        Connection.addresseeId == institution.id,
    ).one()

    assert relation.type == ConnectionTypeEnum.FOLLOWER
    assert relation.status == ConnectionStatusEnum.ACCEPTED

    accepted_response = client.get("/api/network/accepted")
    assert accepted_response.status_code == 200
    payload = accepted_response.json()
    assert all(
        item.get("addresseeId") != institution.id and item.get("requesterId") != institution.id
        for item in payload
    )


def test_suggestions_exclude_admin_accounts(client_and_db):
    client, db = client_and_db

    current_user = _create_user(db, email="current@example.com", role_type=RoleTypeEnum.student)
    admin_user = _create_user(
        db,
        email="admin@example.com",
        role_type=RoleTypeEnum.professional,
    )
    admin_user.role = RoleEnum.ADMIN
    db.commit()

    def override_current_user():
        return current_user

    client.app.dependency_overrides[get_current_active_user] = override_current_user

    response = client.get("/api/network/suggestions")

    assert response.status_code == 200
    payload = response.json()
    assert all(item["id"] != admin_user.id for item in payload)


def test_publishing_feed_notifies_followers(client_and_db):
    client, db = client_and_db

    institution = _create_user(db, email="institution2@example.com", role_type=RoleTypeEnum.institution, is_premium=True)
    follower = _create_user(db, email="follower2@example.com", role_type=RoleTypeEnum.student)

    relation = Connection(
        requesterId=follower.id,
        addresseeId=institution.id,
        type=ConnectionTypeEnum.FOLLOWER,
        status=ConnectionStatusEnum.ACCEPTED,
    )
    db.add(relation)
    db.commit()

    def override_current_user():
        return institution

    client.app.dependency_overrides[get_current_active_user] = override_current_user

    response = client.post(
        "/api/publishing/feed",
        data={"title": "Annonce", "content": "Contenu"},
    )

    assert response.status_code == 201
    assert db.query(FeedPost).count() == 1

    notifications = db.query(Notification).filter(Notification.userId == follower.id).all()
    assert len(notifications) >= 1
    assert any(n.type == NotificationTypeEnum.FOLLOWER_POST for n in notifications)
