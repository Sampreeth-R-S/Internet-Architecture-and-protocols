import socket
import threading
import bcrypt
import json
import os
import uuid
import ssl

import redis

SERVER_HOST = "0.0.0.0"
SERVER_PORT = int(os.environ.get("SERVER_PORT", 8000))
MAIN_ROOM = "lobby"

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))
SERVER_ID = os.environ.get("SERVER_ID", str(uuid.uuid4()))

ACTIVE_TTL_SECONDS = int(os.environ.get("ACTIVE_TTL_SECONDS", "15"))
HEARTBEAT_INTERVAL_SECONDS = int(os.environ.get("HEARTBEAT_INTERVAL_SECONDS", "5"))

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True
)


connection_to_user = {}
user_credentials = {}
user_location = {}

room_connections = {MAIN_ROOM: set()}
subscribers = {}
subscriptions = {}
active_users_local = set()

state_lock = threading.Lock()

SHARED_SALT = b"$2b$12$abcdefghijklmnopqrstuu"


def hash_password(pwd):
    return bcrypt.hashpw(pwd.encode(), SHARED_SALT).decode()


def room_key(room):
    return f"room:{room}"


def session_key(user):
    return f"session:{user}"


def active_key(user):
    return f"active:{user}"


def subscriptions_key(user):
    return f"subscriptions:{user}"


def subscribers_key(user):
    return f"subscribers:{user}"


def notify_key(user):
    return f"notify:{user}"


def online_users_key():
    return "online_users"


def add_user_to_room(user, room):
    redis_client.sadd("rooms", room)
    redis_client.sadd(room_key(room), user)
    redis_client.hset(session_key(user), mapping={"room": room, "server": SERVER_ID})


def remove_user_from_room(user, room):
    redis_client.srem(room_key(room), user)
    if room != MAIN_ROOM and redis_client.scard(room_key(room)) == 0:
        redis_client.delete(room_key(room))
        redis_client.srem("rooms", room)


def publish_room_message(room, text, sender=None):
    payload = {
        "type": "room_message",
        "room": room,
        "text": text,
        "sender": sender,
        "origin": SERVER_ID
    }
    redis_client.publish(room_key(room), json.dumps(payload))


def publish_notification(publisher, message):
    payload = {
        "type": "notify_message",
        "publisher": publisher,
        "message": message,
        "origin": SERVER_ID
    }
    redis_client.publish(notify_key(publisher), json.dumps(payload))


def set_active_user(user):
    return redis_client.set(
        active_key(user),
        SERVER_ID,
        nx=True,
        ex=ACTIVE_TTL_SECONDS
    )


def refresh_active_user(user):
    if redis_client.get(active_key(user)) != SERVER_ID:
        return False
    redis_client.set(active_key(user), SERVER_ID, xx=True, ex=ACTIVE_TTL_SECONDS)
    return True


def release_active_user(user):
    if redis_client.get(active_key(user)) == SERVER_ID:
        redis_client.delete(active_key(user))


def deliver_to_local(room, text, sender=None, origin=None):
    with state_lock:
        sockets = room_connections.get(room, set()).copy()
        for s in sockets:
            if sender and origin == SERVER_ID and connection_to_user.get(s) == sender:
                continue
            try:
                s.sendall(text.encode())
            except:
                pass


def deliver_notification_to_local(publisher, message):
    with state_lock:
        sockets = subscribers.get(publisher, set()).copy()
        for s in sockets:
            try:
                s.sendall(f"Notification from {publisher}: {message}\n".encode())
            except:
                pass


def start_pubsub_listener():
    pubsub = redis_client.pubsub()
    pubsub.psubscribe("room:*", "notify:*")
    for message in pubsub.listen():
        if message.get("type") != "pmessage":
            continue
        data = message.get("data")
        if not data:
            continue
        try:
            payload = json.loads(data)
        except Exception:
            continue
        payload_type = payload.get("type")
        if payload_type == "room_message":
            deliver_to_local(
                payload.get("room"),
                payload.get("text"),
                payload.get("sender"),
                payload.get("origin")
            )
        elif payload_type == "notify_message":
            deliver_notification_to_local(
                payload.get("publisher"),
                payload.get("message")
            )


def start_heartbeat():
    while True:
        with state_lock:
            users = list(active_users_local)
        for user in users:
            if not refresh_active_user(user):
                with state_lock:
                    active_users_local.discard(user)
        threading.Event().wait(HEARTBEAT_INTERVAL_SECONDS)



def register_user(user, pwd):
    user_credentials[user] = hash_password(pwd)


def send_to_room(room, text, skip_conn=None):
    sender = None
    if skip_conn is not None:
        sender = connection_to_user.get(skip_conn)
    publish_room_message(room, text, sender)


def move_user(user, target_room, conn):
    with state_lock:
        current_room = user_location[user]
        room_connections[current_room].discard(conn)

        if current_room != MAIN_ROOM and not room_connections[current_room]:
            room_connections.pop(current_room, None)

        room_connections.setdefault(target_room, set()).add(conn)
        user_location[user] = target_room

    remove_user_from_room(user, current_room)
    add_user_to_room(user, target_room)




def process_input(conn, user, command):
    try:
        if command.startswith("/join "):
            new_room = command.split(maxsplit=1)[1]
            with state_lock:
                old_room = user_location[user]

            move_user(user, new_room, conn)

            conn.sendall(f"Joined room {new_room}\n".encode())
            send_to_room(old_room, f"{user} left {old_room}\n")
            send_to_room(new_room, f"{user} joined {new_room}\n", conn)

        elif command == "/leave":
            with state_lock:
                old_room = user_location[user]

            move_user(user, MAIN_ROOM, conn)

            conn.sendall(f"Returned to {MAIN_ROOM}\n".encode())
            send_to_room(old_room, f"{user} left {old_room}\n")
            send_to_room(MAIN_ROOM, f"{user} joined {MAIN_ROOM}\n", conn)

        elif command == "/rooms":
            rooms = sorted(redis_client.smembers("rooms"))
            listing = ", ".join(
                f"{r}({redis_client.scard(room_key(r))})" for r in rooms
            )
            conn.sendall(f"Available rooms: {listing}\n".encode())
        
        elif command == "/users":
            users = sorted(redis_client.smembers(online_users_key()))
            listing = ", ".join(users)
            conn.sendall(f"Users online: {listing}\n".encode())

        elif command.startswith("/subscribe"):
            user_to_subscribe = command.split(maxsplit=1)[1]
            with state_lock:
                if user_to_subscribe not in user_credentials:
                    conn.sendall("User does not exist\n".encode())
                    return
                subscribers.setdefault(user_to_subscribe, set()).add(conn)
                subscriptions.setdefault(user, set()).add(user_to_subscribe)
                redis_client.sadd(subscriptions_key(user), user_to_subscribe)
                redis_client.sadd(subscribers_key(user_to_subscribe), user)
                conn.sendall(f"Subscribed to {user_to_subscribe}\n".encode())

        elif command.startswith("/unsubscribe"):
            user_to_unsubscribe = command.split(maxsplit=1)[1]
            with state_lock:
                if user_to_unsubscribe not in user_credentials:
                    conn.sendall("User does not exist\n".encode())
                    return
                if user_to_unsubscribe in subscribers:
                    subscribers[user_to_unsubscribe].discard(conn)
                    if not subscribers[user_to_unsubscribe]:
                        subscribers.pop(user_to_unsubscribe, None)
                if user in subscriptions:
                    subscriptions[user].discard(user_to_unsubscribe)
                    if not subscriptions[user]:
                        subscriptions.pop(user, None)
                redis_client.srem(subscriptions_key(user), user_to_unsubscribe)
                redis_client.srem(subscribers_key(user_to_unsubscribe), user)
                conn.sendall(f"Unsubscribed from {user_to_unsubscribe}\n".encode())
        
        elif command.startswith("/publish"):
            message = command.split(maxsplit=1)[1]
            publish_notification(user, message)
        else:
            room = user_location[user]
            send_to_room(room, f"{user}: {command}\n", conn)

    except Exception as e:
        print(f"Error processing command from {user}: {e}")
        conn.sendall("Error processing command\n".encode())




def authenticate(conn):
    data = ""
    while "\n" not in data:
        packet = conn.recv(1024).decode()
        if not packet:
            return False, ""
        data += packet
    try:
        line = data.strip()
        parts = line.split(maxsplit=2)

        if len(parts) != 3 or parts[0] != "LOGIN":
            conn.sendall("Invalid login request\n".encode())
            conn.close()
            return False, ""

        _, user, client_hash = parts

        if user not in user_credentials:
            conn.sendall("Authentication failed\n".encode())
            conn.close()
            return False, ""

        if client_hash != user_credentials[user]:
            conn.sendall("Authentication failed\n".encode())
            conn.close()
            return False, ""

        if not set_active_user(user):
            conn.sendall("User already active\n".encode())
            conn.close()
            return False, ""

        conn.sendall(f"Login successful. Room: {MAIN_ROOM}\n".encode())
        return True, user
    
    except Exception as e:
        print(f"Authentication error: {e}")
        conn.sendall("Authentication failed\n".encode())
        conn.close()
        return False, ""




def client_session(conn, addr):
    logged_in = False
    username = None

    try:
        logged_in, username = authenticate(conn)
        if not logged_in:
            return

        with state_lock:
            connection_to_user[conn] = username
            user_location[username] = MAIN_ROOM
            room_connections[MAIN_ROOM].add(conn)
            active_users_local.add(username)

            saved_subscriptions = set(redis_client.smembers(subscriptions_key(username)))
            if saved_subscriptions:
                subscriptions[username] = saved_subscriptions
                for subscribed_user in saved_subscriptions:
                    subscribers.setdefault(subscribed_user, set()).add(conn)

        add_user_to_room(username, MAIN_ROOM)
        redis_client.sadd(online_users_key(), username)

        send_to_room(MAIN_ROOM, f"{username} joined the lobby\n", conn)

        buffer = ""
        while True:
            data = conn.recv(1024).decode()
            if not data:
                break

            buffer += data
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                process_input(conn, username, line.strip())

    except Exception as e:
        print(f"Client error {addr}: {e}")

    finally:
        if logged_in:
            with state_lock:
                room = user_location.pop(username, None)
                if room:
                    room_connections[room].discard(conn)

                    if room != MAIN_ROOM and not room_connections[room]:
                        room_connections.pop(room, None)
                for subscribed_user in subscriptions.get(username, set()):
                    if subscribed_user in subscribers:
                        subscribers[subscribed_user].discard(conn)
                        if not subscribers[subscribed_user]:
                            subscribers.pop(subscribed_user, None)

                subscriptions.pop(username, None)

                connection_to_user.pop(conn, None)

            if room:
                remove_user_from_room(username, room)
            redis_client.delete(session_key(username))
            release_active_user(username)
            redis_client.srem(online_users_key(), username)

            send_to_room(room, f"{username} disconnected\n")

        conn.close()




def start_server():
    for u in "abcdefgh":
        register_user(u, "1")

    redis_client.sadd("rooms", MAIN_ROOM)

    threading.Thread(target=start_pubsub_listener, daemon=True).start()
    threading.Thread(target=start_heartbeat, daemon=True).start()

    # Create SSL context
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(
        certfile=os.environ.get("CERT_FILE", "cert.pem"),
        keyfile=os.environ.get("KEY_FILE", "key.pem")
    )

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((SERVER_HOST, SERVER_PORT))
    
    # Wrap socket with SSL
    server = ssl_context.wrap_socket(server, server_side=True)
    server.listen()

    print(f"Chat server running on {SERVER_HOST}:{SERVER_PORT} (TLS enabled)")

    while True:
        conn, addr = server.accept()
        threading.Thread(
            target=client_session,
            args=(conn, addr),
            daemon=True
        ).start()


if __name__ == "__main__":
    start_server()
