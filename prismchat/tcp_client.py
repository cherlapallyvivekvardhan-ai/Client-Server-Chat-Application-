"""Terminal client: python tcp_client.py [host] [port]"""
import os
import socket
import sys
import threading

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5050


def listen(sock):
    while True:
        data = sock.recv(4096)
        if not data:
            print("\n[disconnected]")
            os._exit(0)
        sys.stdout.write(data.decode("utf-8", "replace"))
        sys.stdout.flush()


s = socket.create_connection((HOST, PORT))
threading.Thread(target=listen, args=(s,), daemon=True).start()
try:
    for line in sys.stdin:
        s.sendall(line.encode("utf-8"))
except KeyboardInterrupt:
    pass
s.close()
