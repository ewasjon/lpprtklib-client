import logging
import logging.handlers
import os

logger = logging.getLogger('lpp-client')
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# File handler
LOG_PATH = './log/main.txt'
os.makedirs('./log', exist_ok=True)
file_handler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=1024 * 1024 * 8, backupCount=1)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Stream handler for stderr
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# Stream handler for syslog
if os.path.exists('/dev/log'):
    syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
    syslog_handler.setLevel(logging.DEBUG)
    syslog_handler.setFormatter(formatter)
    logger.addHandler(syslog_handler)