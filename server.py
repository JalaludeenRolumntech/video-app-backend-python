from flask import Flask, request
from flask_socketio import SocketIO, join_room, leave_room

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

rooms = {}


@app.route("/")
def index():
    return "Video Conferencing Signaling Server is running!"

@app.route("/home")
def index():
    return "Video Home"

@socketio.on("create-room")
def create_room(data):
    room = data["room"]
    user_id = data["user_id"]
    name = data.get("name", "Host")

    if room not in rooms:
        rooms[room] = {"users": [], "pending": [], "host": {"user_id": user_id, "name": name, "sid": request.sid}}

    rooms[room]["users"].append({"user_id": user_id, "name": name, "sid": request.sid})
    join_room(room)
    socketio.emit("user-joined", {"user_id": user_id, "name": name}, to=room, skip_sid=request.sid)

@socketio.on("join-room")
def join_room_event(data):
    room = data["room"]
    user_id = data["user_id"]
    name = data.get("name", "Guest")

    if room not in rooms:
        socketio.emit("room-error", {"error": "Room does not exist."}, to=request.sid)
        return

    if "host" not in rooms[room]:
        socketio.emit("room-error", {"error": "No host in the room."}, to=request.sid)
        return

    host_sid = rooms[room]["host"]["sid"]
    rooms[room].setdefault("pending", []).append({"user_id": user_id, "name": name, "sid": request.sid})
    socketio.emit("join-request", {"user_id": user_id, "name": name}, to=host_sid)

@socketio.on("approve-request")
def approve_request(data):
    room = data["room"]
    user_id = data["user_id"]

    if room not in rooms or "pending" not in rooms[room]:
        return

    pending_users = rooms[room]["pending"]
    for user in pending_users:
        if user["user_id"] == user_id:
            rooms[room]["users"].append(user)
            pending_users.remove(user)
            join_room(room)
            socketio.emit("user-joined", {"user_id": user_id, "name": user["name"]}, to=room)
            break

@socketio.on("reject-request")
def reject_request(data):
    room = data["room"]
    user_id = data["user_id"]

    if room not in rooms or "pending" not in rooms[room]:
        return

    pending_users = rooms[room]["pending"]
    for user in pending_users:
        if user["user_id"] == user_id:
            pending_users.remove(user)
            socketio.emit("join-rejected", {"user_id": user_id}, to=user["sid"])
            break

@socketio.on("chat-message")
def handle_chat_message(data):
    room = data["room"]
    message = {"user_id": data["user_id"], "message": data["message"]}
    socketio.emit("chat-message", message, to=room)

@socketio.on("leave-room")
def leave(data):
    room = data["room"]
    user_id = data["user_id"]
    if room in rooms:
        rooms[room]["users"] = [
            user for user in rooms[room]["users"] if user["user_id"] != user_id
        ]
        if not rooms[room]["users"]:  # If the room is empty, delete it
            del rooms[room]
    leave_room(room)
    socketio.emit("user-left", {"user_id": user_id}, to=room)

@socketio.on("offer")
def handle_offer(data):
    socketio.emit("offer", data, to=data["target"])

@socketio.on("answer")
def handle_answer(data):
    socketio.emit("answer", data, to=data["target"])

@socketio.on("ice-candidate")
def handle_ice_candidate(data):
    socketio.emit("ice-candidate", data, to=data["target"])

@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    for room, data in rooms.items():
        for user in data["users"]:
            if user["sid"] == sid:
                data["users"].remove(user)
                if not data["users"]:
                    del rooms[room]
                socketio.emit("user-left", {"user_id": user["user_id"]}, to=room)
                return

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5001)
