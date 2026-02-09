import socket
import threading
import bcrypt

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000
MAIN_ROOM = "lobby"


connection_to_user = {}
user_credentials = {}
user_location = {}

room_members = {MAIN_ROOM: set()}
room_connections = {MAIN_ROOM: set()}
subscribers = {}
subscriptions = {}

state_lock = threading.Lock()

SHARED_SALT = b"$2b$12$abcdefghijklmnopqrstuu"


def hash_password(pwd):
    return bcrypt.hashpw(pwd.encode(), SHARED_SALT).decode()



def register_user(user, pwd):
    user_credentials[user] = hash_password(pwd)


def send_to_room(room, text, skip_conn=None):
    with state_lock:
        sockets = room_connections.get(room, set()).copy()
        for s in sockets:
            if s != skip_conn:
                try:
                    s.sendall(text.encode())
                except:
                    pass


def move_user(user, target_room, conn):
    with state_lock:
        current_room = user_location[user]

        room_members[current_room].discard(user)
        room_connections[current_room].discard(conn)

        if current_room != MAIN_ROOM and not room_members[current_room]:
            room_members.pop(current_room, None)
            room_connections.pop(current_room, None)

        room_members.setdefault(target_room, set()).add(user)
        room_connections.setdefault(target_room, set()).add(conn)
        user_location[user] = target_room




def process_input(conn, user, command):
    try:
        if command.startswith("/join "):
            with state_lock:
                new_room = command.split(maxsplit=1)[1]
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
            with state_lock:
                listing = ", ".join(
                    f"{r}({len(u)})" for r, u in room_members.items()
                )
                conn.sendall(f"Available rooms: {listing}\n".encode())
        
        elif command == "/users":
            with state_lock:
                room = user_location[user]
                users = user_credentials.keys()
                listing = ", ".join(users)
                conn.sendall(f"Users in server: {listing}\n".encode())

        elif command.startswith("/subscribe"):
            user_to_subscribe = command.split(maxsplit=1)[1]
            with state_lock:
                if user_to_subscribe not in user_credentials:
                    conn.sendall("User does not exist\n".encode())
                    return
                subscribers.setdefault(user_to_subscribe, set()).add(conn)
                subscriptions.setdefault(user, set()).add(user_to_subscribe)
                conn.sendall(f"Subscribed to {user_to_subscribe}\n".encode())

        elif command.startswith("/unsubscribe"):
            user_to_unsubscribe = command.split(maxsplit=1)[1]
            with state_lock:
                if user_to_unsubscribe not in user_credentials:
                    conn.sendall("User does not exist\n".encode())
                    return
                if user_to_unsubscribe in subscribers:
                    subscribers[user_to_unsubscribe].discard(conn)
                if user in subscriptions:
                    subscriptions[user].discard(user_to_unsubscribe)
                conn.sendall(f"Unsubscribed from {user_to_unsubscribe}\n".encode())
        
        elif command.startswith("/publish"):
            message = command.split(maxsplit=1)[1]
            with state_lock:
                if user in subscribers:
                    for s in subscribers[user]:
                        try:
                            s.sendall(f"Notification from {user}: {message}\n".encode())
                        except:
                            pass
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

        with state_lock:
            if user in connection_to_user.values():
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
            room_members[MAIN_ROOM].add(username)
            room_connections[MAIN_ROOM].add(conn)
            for subscribed_user in subscriptions.get(username, set()):
                subscribers.setdefault(subscribed_user, set()).add(conn)

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
                    room_members[room].discard(username)
                    room_connections[room].discard(conn)

                    if room != MAIN_ROOM and not room_members[room]:
                        room_members.pop(room, None)
                        room_connections.pop(room, None)
                for subscribed_user in subscriptions.get(username, set()):
                    if subscribed_user in subscribers:
                        subscribers[subscribed_user].discard(conn)
                        if not subscribers[subscribed_user]:
                            subscribers.pop(subscribed_user, None)

                connection_to_user.pop(conn, None)

            send_to_room(room, f"{username} disconnected\n")

        conn.close()




def start_server():
    for u in "abcdefgh":
        register_user(u, "1")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((SERVER_HOST, SERVER_PORT))
    server.listen()

    print(f"Chat server running on {SERVER_HOST}:{SERVER_PORT}")

    while True:
        conn, addr = server.accept()
        threading.Thread(
            target=client_session,
            args=(conn, addr),
            daemon=True
        ).start()


if __name__ == "__main__":
    start_server()
