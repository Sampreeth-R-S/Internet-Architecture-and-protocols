import socket
import threading
import sys

SERVER = "localhost"
PORT = 8000


def receive(sock):
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                break
            print(data.decode(), end="")
        except:
            break
    print("\nDisconnected from server")
    sys.exit(0)


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER, PORT))

    prompt = sock.recv(1024).decode()
    username = input(prompt)
    sock.sendall((username + "\n").encode())
    threading.Thread(target=receive, args=(sock,), daemon=True).start()

    try:
        while True:
            msg = input()
            sock.sendall((msg + "\n").encode())
    except KeyboardInterrupt:
        sock.close()


if __name__ == "__main__":
    main()
