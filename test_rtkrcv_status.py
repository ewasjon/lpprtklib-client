#!/usr/bin/env python3
"""Query rtkrcv status via its telnet console on port 9000."""
import socket, time

HOST, PORT, PASSWD = "127.0.0.1", 29000, "admin"

COMMANDS = ["status", "stream", "satellite", "observ", "navidata", "error"]

def send(s, cmd):
    s.sendall((cmd + "\r\n").encode())
    time.sleep(0.3)
    out = b""
    s.settimeout(1)
    try:
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            out += chunk
    except socket.timeout:
        pass
    return out.decode(errors="replace")

try:
    s = socket.create_connection((HOST, PORT), timeout=3)
    s.settimeout(2)
    # read banner / password prompt
    time.sleep(0.5)
    banner = s.recv(4096).decode(errors="replace")
    print(banner)
    if "password" in banner.lower():
        s.sendall((PASSWD + "\r\n").encode())
        time.sleep(0.3)
        s.recv(4096)

    for cmd in COMMANDS:
        print(f"\n{'='*40}\n>> {cmd}\n{'='*40}")
        print(send(s, cmd))

    s.close()
except ConnectionRefusedError:
    print("ERROR: rtkrcv console not available on port 29000 (is rtkrcv running with -p 29000?)")
except socket.timeout:
    print("ERROR: timeout connecting to rtkrcv console")
