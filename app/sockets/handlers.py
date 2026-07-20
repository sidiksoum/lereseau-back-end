def register_socket_events(sio):
    @sio.event
    async def connect(sid, environ, auth):
        print(f"WS Client connected: {sid}")
        # Automatically join global room for feed updates
        await sio.enter_room(sid, "global")

    @sio.event
    async def disconnect(sid):
        print(f"WS Client disconnected: {sid}")

    @sio.event
    async def join_user_room(sid, data):
        # The frontend emits this after successful login
        user_id = data.get("userId")
        if user_id:
            await sio.enter_room(sid, f"user_{user_id}")
            print(f"Client {sid} joined room user_{user_id}")

    @sio.event
    async def user_typing(sid, data):
        conversation_id = data.get("conversationId")
        if conversation_id:
            await sio.emit("typing", data, room=f"conv_{conversation_id}", skip_sid=sid)
