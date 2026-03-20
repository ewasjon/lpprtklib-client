#!/usr/bin/env python3
"""Read from serial and decode RTCM3 message types - confirms receiver is outputting RTCM."""
import serial, time

PORT = "/dev/ttyMSM3"
BAUD = 115200
RTCM_PREAMBLE = 0xD3

print(f"Listening for RTCM3 on {PORT} at {BAUD} baud, press Ctrl+C to stop...\n")
counts = {}
with serial.Serial(PORT, BAUD, timeout=1) as s:
    buf = b""
    start = time.time()
    while True:
        buf += s.read(512)
        while len(buf) >= 6:
            idx = buf.find(bytes([RTCM_PREAMBLE]))
            if idx == -1:
                buf = b""
                break
            buf = buf[idx:]
            if len(buf) < 6:
                break
            length = ((buf[1] & 0x03) << 8) | buf[2]
            frame_len = length + 6
            if len(buf) < frame_len:
                break
            msg_type = ((buf[3] & 0xFF) << 4) | ((buf[4] & 0xF0) >> 4)
            counts[msg_type] = counts.get(msg_type, 0) + 1
            print(f"[+{time.time()-start:.1f}s] RTCM {msg_type:4d} ({length} bytes)  seen: {dict(sorted(counts.items()))}")
            buf = buf[frame_len:]
