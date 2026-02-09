import socket
import threading
import sys
import bcrypt

HOST = "localhost"
PORT = 8000

SHARED_SALT = b"$2b$12$abcdefghijklmnopqrstuu"


def hash_password(pwd):
    return bcrypt.hashpw(pwd.encode(), SHARED_SALT).decode()


def listen(sock):
    buffer = ""
    while True:
        try:
            chunk = sock.recv(1024).decode()
            if not chunk:
                break

            buffer += chunk
            while "\n" in buffer:
                msg, buffer = buffer.split("\n", 1)
                print(msg)
        except:
            break


def run_client():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))

    user = input("Username: ")
    pwd = input("Password: ")

    pwd_hash = hash_password(pwd)
    sock.sendall(f"LOGIN {user} {pwd_hash}\n".encode())

    response = ""
    while "\n" not in response:
        response += sock.recv(1024).decode()

    print(response, end="")
    if "successful" not in response:
        sock.close()
        return

    threading.Thread(target=listen, args=(sock,), daemon=True).start()

    try:
        while True:
            text = input()
            sock.sendall((text + "\n").encode())
    except KeyboardInterrupt:
        print("\nClient closed")
        sock.close()
        sys.exit()


if __name__ == "__main__":
    run_client()
