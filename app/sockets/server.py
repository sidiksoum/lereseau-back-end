import socketio
import os
from app.core.config import settings

# Check if REDIS_URL is provided for scaling WebSockets across multiple server instances
redis_url = getattr(settings, "REDIS_URL", os.getenv("REDIS_URL"))

if redis_url and str(redis_url).strip():
    # Use Redis manager to broadcast socket events across all cluster instances
    client_manager = socketio.AsyncRedisManager(redis_url.strip())
    sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*", client_manager=client_manager)
    print("[SOCKET.IO] Mode distribué activé via Redis Manager.")
else:
    # Standard single-instance socket server
    sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")
    print("[SOCKET.IO] Mode local (single instance) activé.")
