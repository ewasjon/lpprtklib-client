#!/usr/bin/env python3
"""Test rtkrcv TCP ports - checks which ports are accepting connections and receiving data."""
import socket, time

PORTS = {
    10000: "rtkrcv rover input (RTCM from client)",
    30000: "rtkrcv NMEA output",
    40000: "rtkrcv corrections input",
}

for port, desc in PORTS.items():
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=2)
        s.settimeout(3)
        try:
            data = s.recv(256)
            print(f"[OK ] :{port} ({desc}) - connected, got {len(data)} bytes: {data[:32].hex(' ')}")
        except socket.timeout:
            print(f"[OK ] :{port} ({desc}) - connected, no data in 3s (may need input first)")
        s.close()
    except ConnectionRefusedError:
        print(f"[ERR] :{port} ({desc}) - connection refused (port not open)")
    except socket.timeout:
        print(f"[ERR] :{port} ({desc}) - timeout (port not responding)")
