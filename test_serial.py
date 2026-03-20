#!/usr/bin/env python3
"""Test raw serial data from /dev/ttyMSM3 - shows hex dump of incoming bytes."""
import serial, sys, time

PORT = "/dev/ttyMSM3"
BAUD = 115200

print(f"Opening {PORT} at {BAUD} baud, press Ctrl+C to stop...\n")
with serial.Serial(PORT, BAUD, timeout=1) as s:
    start = time.time()
    total = 0
    while True:
        data = s.read(256)
        if data:
            total += len(data)
            print(f"[+{time.time()-start:.1f}s] {len(data)} bytes (total {total}): {data[:32].hex(' ')}{'...' if len(data)>32 else ''}")
        else:
            print(f"[+{time.time()-start:.1f}s] no data")
