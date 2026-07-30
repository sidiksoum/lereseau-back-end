from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

from app.core.config import settings
from app.api.routes import auth
from app.services.background_jobs import background_jobs
from app.services.cache import cache
from app.services.logging import logger
from app.services.metrics import metrics
from app.api.routes.v1 import users, opportunities, checkout, network, documents, forum, feed, chat, notifications, chatbot, publishing as user_publishing
from app.api.routes.admin import users as admin_users, forum as admin_forum, publishing as admin_publishing, certifications as admin_certifications, dashboard as admin_dashboard
from app.sockets.handlers import register_socket_events

from contextlib import asynccontextmanager
from app.db.session import SessionLocal
from app.db.init_db import init_super_admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    init_super_admin(db)
    db.close()
    await background_jobs.start()
    logger.info("application_started", extra={"request_id": "startup"})
    yield
    await background_jobs.stop()
    logger.info("application_stopped", extra={"request_id": "shutdown"})

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.sockets.handlers import register_socket_events
from app.sockets.server import sio

# Register WebSockets Events
register_socket_events(sio)

sio_app = socketio.ASGIApp(sio, other_asgi_app=app)

@app.get("/")
def root():
    return {"message": "Welcome to LeRéseau API"}


@app.get("/health")
def health():
    return {"status": "ok", "cache": "memory" if not cache._redis_client else "redis"}


@app.get("/metrics")
def metrics_endpoint():
    return metrics.snapshot()

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(opportunities.router, prefix="/api/opportunities", tags=["opportunities"])
app.include_router(checkout.router, prefix="/api/checkout", tags=["checkout"])
app.include_router(network.router, prefix="/api/network", tags=["network"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(forum.router, prefix="/api/forum", tags=["forum"])
app.include_router(feed.router, prefix="/api/feed", tags=["feed"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(chatbot.router, prefix="/api/chatbot", tags=["chatbot"])
app.include_router(user_publishing.router, prefix="/api/publishing", tags=["user-publishing"])

# Admin Routes
app.include_router(admin_users.router, prefix="/api/admin/users", tags=["admin-users"])
app.include_router(admin_forum.router, prefix="/api/admin/forum", tags=["admin-forum"])
app.include_router(admin_publishing.router, prefix="/api/admin/publishing", tags=["admin-publishing"])
app.include_router(admin_certifications.router, prefix="/api/admin/certifications", tags=["admin-certifications"])
app.include_router(admin_dashboard.router, prefix="/api/admin/dashboard", tags=["admin-dashboard"])

# Expose sio_app as the main ASGI application
# Run with: uvicorn app.main:sio_app --reload
# Reloaded
