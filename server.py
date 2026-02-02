import socket
import threading
import time

HOST = "0.0.0.0"
PORT = 8000

clients = {}            # socket -> username
clients_lock = threading.Lock()


def broadcast(message, exclude_sock=None):
    with clients_lock:
        for sock in list(clients):
            if sock != exclude_sock:
                try:
                    sock.sendall(message.encode())
                except:
                    remove_client(sock)


def remove_client(sock):
    with clients_lock:
        username = clients.pop(sock, None)
    try:
        sock.close()
    except:
        pass
    if username:
        broadcast(f"🔴 {username} left the chat\n")


def handle_client(client_sock, addr):
    try:
        client_sock.sendall(b"Enter username: ")
        username = client_sock.recv(1024).decode().strip()

        with clients_lock:
            clients[client_sock] = username

        broadcast(f"🟢 {username} joined the chat\n")
        print(f"{username} connected from {addr}")

        while True:
            data = client_sock.recv(1024)
            if not data:
                break

            ts = time.strftime("%H:%M:%S")
            msg = data.decode().strip()
            broadcast(f"[{ts}] {username}: {msg}\n", exclude_sock=client_sock)

    except Exception as e:
        print(f"Error with {addr}: {e}")

    finally:
        remove_client(client_sock)


def main():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen()

    print(f"Thread-based chat server running on port {PORT}")

    try:
        while True:
            client_sock, addr = server_sock.accept()
            t = threading.Thread(
                target=handle_client,
                args=(client_sock, addr),
                daemon=True
            )
            t.start()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server_sock.close()


if __name__ == "__main__":
    main()
