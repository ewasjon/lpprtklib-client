import serial
import logging
from time import sleep

logger = logging.getLogger(__name__)

DEVICE = "/dev/ttyMSM3"
BAUD_RATE = 115200

PAR1227 = (
    0x20000 |  # Reserved
    0x200   |  # Use BeiDou positioning
    0x100   |  # Enable BeiDou constellation
    0x80    |  # Use Galileo positioning
    0x40    |  # Enable Galileo constellation
    0x1        # Enable GNSS
)
PAR1200 = (
    0x10000000 |  # Reserved
    0x400000   |  # Use GPS positioning
    0x10000    |  # Enable GPS constellation
    0x800         # Enable RTCM input
)

COMMANDS = [
    "$PSTMGETSWVER",
    "$PSTMSETPAR,1200,0x1000000,2",
    "$PSTMSETPAR,1227,0x08,2",
    f"$PSTMSETPAR,1200,0x{PAR1200:08x},1",
    f"$PSTMSETPAR,1227,0x{PAR1227:08x},1",
    "$PSTMSETPAR,1201,0x0",
    "$PSTMSETPAR,1228,0x0",
    f"$PSTMSETCONSTMASK,{0b10001001:d}",
    "$PSTMCFGCONST,2,0,2,0,0",
    "$PSTMSETPAR,1200,0x1000000,2",
    "$PSTMSETPAR,1227,0x8,2",
    "$PSTMSAVEPAR",
    "$PSTMSSR",
]


def _with_checksum(message: str) -> bytes:
    data = message.encode("ascii")
    checksum = 0
    for c in data[1:]:
        checksum ^= c
    return data + f"*{checksum:02X}\r\n".encode("ascii")


def configure():
    logger.info(f"[GNSS] Opening {DEVICE} at {BAUD_RATE} baud")
    try:
        with serial.Serial(DEVICE, BAUD_RATE, timeout=1) as ser:
            for cmd in COMMANDS:
                frame = _with_checksum(cmd)
                logger.info(f"[GNSS] Sending: {frame}")
                try:
                    ser.write(frame)
                except serial.SerialException as e:
                    logger.error(f"[GNSS] Failed to send '{cmd}': {e}")
                sleep(1)
        logger.info("[GNSS] Configuration complete")
    except serial.SerialException as e:
        logger.error(f"[GNSS] Could not open {DEVICE}: {e}")
