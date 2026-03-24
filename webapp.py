import os
import json
import tornado.web
import tornado.template
from tornado.ioloop import IOLoop

from csclient import CSClient
from logger_config import logger, LOG_PATH

LPP_VERSION = os.environ.get('LPP_VERSION', 'v0.0.0')
LPP_CLIENT_CONTAINER_VERSION = os.environ.get('LPP_CLIENT_CONTAINER_VERSION', 'v0.0.0')

cs = CSClient("lpp-client", logger=logger)

def get_appdata(key):
    env_key = key.upper().replace('.', '_').replace('-', '_')
    env_value = os.environ.get(env_key)
    if env_value:
        return env_value
    if cs.ON_DEVICE:
        return cs.get_appdata(key)
    else:
        if os.path.exists("config.json"):
            with open("config.json") as f:
                config = json.load(f)
                value = config.get(key)
                logger.info(f"Getting {key}={value}")
                return value

def set_appdata(key, value):
    logger.info(f"Setting {key}={value}")
    if cs.ON_DEVICE:
        cs.set_appdata(key, value)
    else:
        if os.path.exists("config.json"):
            with open("config.json") as f:
                config = json.load(f)
        else:
            config = {}
        config[key] = value
        with open("config.json", "w") as f:
            json.dump(config, f)

class MainHandler(tornado.web.RequestHandler):
    async def get(self):
        config = {
            'host': get_appdata("lpp-client.host") or "129.192.82.125",
            'port': get_appdata("lpp-client.port") or 5431,
            'serial': get_appdata("lpp-client.serial") or "/dev/ttyS1",
            'baud': get_appdata("lpp-client.baud") or 115200,
            'output': get_appdata("lpp-client.output") or "un",
            'format': get_appdata("lpp-client.format") or "osr",
            'forwarding': get_appdata("lpp-client.forwarding") or "",
            'flags': get_appdata("lpp-client.flags") or "",
            'path': get_appdata("lpp-client.path") or "/status/rtk/nmea",
            'starting_mcc': get_appdata("lpp-client.starting_mcc") or "",
            'starting_mnc': get_appdata("lpp-client.starting_mnc") or "",
            'starting_tac': get_appdata("lpp-client.starting_tac") or "",
            'starting_cell_id': get_appdata("lpp-client.starting_cell_id") or "",
            'mcc': get_appdata("lpp-client.mcc") or "",
            'mnc': get_appdata("lpp-client.mnc") or "",
            'tac': get_appdata("lpp-client.tac") or "",
            'cell_id': get_appdata("lpp-client.cell_id") or "",
            'imsi': get_appdata("lpp-client.imsi") or ""
        }
        return self.render('config_form.tpl', config=config, lpp_version=LPP_VERSION, lpp_client_container_version=LPP_CLIENT_CONTAINER_VERSION)

class LogsHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
    
    async def get(self):
        # Send an initial heartbeat
        self.write("event: heartbeat\ndata: ping\n\n")
        await self.flush()
        
        last_pos = 0
        heartbeat_counter = 0
        
        try:
            with open(LOG_PATH, "r") as log_file:
                while True:
                    log_file.seek(last_pos)
                    new_content = log_file.read()
                    if new_content:
                        for line in new_content.splitlines():
                            if line.strip():
                                self.write(f"data: {line}\n\n")
                        last_pos = log_file.tell()
                    
                    heartbeat_counter += 1
                    if heartbeat_counter >= 30:
                        self.write("event: heartbeat\ndata: ping\n\n")
                        heartbeat_counter = 0
                    
                    await self.flush()
                    await tornado.gen.sleep(0.5)
        except Exception as e:
            self.write(f"data: Error: {str(e)}\n\n")
            await self.flush()

class SendLogHandler(tornado.web.RequestHandler):
    async def post(self):
        msg = self.get_body_argument("msg", default=None)
        if msg is not None:
            logger.info(msg)
            self.write("OK")
        else:
            self.set_status(400)
            self.write("Missing msg parameter.")

class UpdateConfigHandler(tornado.web.RequestHandler):
    async def post(self):
        # For each POST field, update application data
        for key, values in self.request.body_arguments.items():
            # self.request.body_arguments returns list of byte strings; decode each.
            value = values[0].decode('utf-8')
            # Update configuration using set_appdata – ensure set_appdata is defined/imported.
            set_appdata(f"lpp-client.{key}", value)
        self.set_status(303)
        self.set_header('Location', '/')
        self.write("Redirecting...")

def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/logs", LogsHandler),
        (r"/send_log", SendLogHandler),
        (r"/update", UpdateConfigHandler)
    ], template_path=os.path.join(os.path.dirname(__file__), "views"))

if __name__ == '__main__':
    if os.environ.get('WEBAPP', 'false').lower() in ['true', 'yes', '1', 1, True]:
        logger.info("Starting webapp on port 8080...")
        app = make_app()
        app.listen(8080)
        IOLoop.current().start()
        exit(1)
    exit(0)