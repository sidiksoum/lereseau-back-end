import socketio

# Instance globale partagée
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")
