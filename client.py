import os
import socket
import threading
import sys
import bcrypt
import ssl

HOST = "localhost"
PORT = int(os.environ.get("SERVER_PORT", 8000))
print(f"Connecting to server on {HOST}:{PORT}...")

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
    # Create SSL context for certificate verification
    ssl_context = ssl.create_default_context()
    
    # For self-signed certificates in testing, we can either:
    # 1. Load the CA certificate
    # 2. Disable certificate verification (not recommended for production)
    
    cert_file = os.environ.get("CERT_FILE", "cert.pem")
    if os.path.exists(cert_file):
        # Load the server certificate for verification
        ssl_context.load_verify_locations(cert_file)
    else:
        # If cert file doesn't exist, still try to connect
        # but be aware this is less secure
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock = ssl_context.wrap_socket(sock, server_hostname=HOST)
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
