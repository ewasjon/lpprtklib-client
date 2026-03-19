import socket
import time
import threading
import subprocess
import shlex
import os

from logger_config import logger

from csclient import CSClient
cs = CSClient("lpp-client", logger=logger)

MAX_TCP_CONNECTIONS = 5

class RunProgram:
    def __init__(self, cmd):
        self.cmd = cmd
        self.process = None
        self.output_thread = None
    
    def quit(self):
        if self.process:
            self.process.kill()
            self.process = None

    def interrupt(self):
        if self.process:
            self.process.send_signal(subprocess.signal.SIGINT)

    def write(self, data):
        if self.process:
            self.process.stdin.write(data)
            self.process.stdin.flush()

    def start(self):
        try:
            # Start the external program and capture its output
            self.process = subprocess.Popen(shlex.split(self.cmd), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=0)

            # Create a thread to read and print the program's output
            def output_thread():
                while True:
                    if not self.process:
                        break
                    try:
                        for line in iter(self.process.stdout.readline, ''):
                            logger.info(line.rstrip())
                            if not self.process:
                                break
                    except UnicodeDecodeError as e:
                        logger.error(f"bad output: {e}")
                        continue

            output_thread = threading.Thread(target=output_thread)
            output_thread.daemon = True
            output_thread.start()

            # Wait for the program to complete and collect the return code
            return_code = self.process.wait()

            # Ensure all remaining output is read
            remaining_output = self.process.stdout.read()
            if remaining_output:
                for line in remaining_output.splitlines():
                    logger.info(line.rstrip())

            logger.info(f"Program exited with return code {return_code}")

            # Return the return code of the program
            return return_code
        except Exception as e:
            logger.exception(f"{e}")
            return -1
        finally:
            self.process = None

def parse_nmea_gga(nmea):
    """Parse GPGGA sentence and return fix data in Cradlepoint format"""
    try:
        parts = nmea.split(',')
        if not parts[0].endswith('GGA') or len(parts) < 15:
            return None
        
        # Extract time (HHMMSS.sss)
        time_str = parts[1]
        if time_str:
            time_val = float(time_str[:2]) * 3600 + float(time_str[2:4]) * 60 + float(time_str[4:])
        else:
            time_val = 0
        
        # Extract latitude (DDMM.MMMM)
        lat_str = parts[2]
        lat_dir = parts[3]
        if lat_str and lat_dir:
            lat_deg = int(lat_str[:2])
            lat_min_full = float(lat_str[2:])
            lat_min = int(lat_min_full)
            lat_sec = (lat_min_full - lat_min) * 60
            if lat_dir == 'S':
                lat_deg = -lat_deg
        else:
            return None
        
        # Extract longitude (DDDMM.MMMM)
        lon_str = parts[4]
        lon_dir = parts[5]
        if lon_str and lon_dir:
            lon_deg = int(lon_str[:3])
            lon_min_full = float(lon_str[3:])
            lon_min = int(lon_min_full)
            lon_sec = (lon_min_full - lon_min) * 60
            if lon_dir == 'W':
                lon_deg = -lon_deg
        else:
            return None
        
        # Quality and satellites
        quality = int(parts[6]) if parts[6] else 0
        satellites = int(parts[7]) if parts[7] else 0
        
        # HDOP (horizontal dilution of precision)
        hdop = float(parts[8]) if parts[8] else 0
        
        # Altitude
        altitude = float(parts[9]) if parts[9] else 0
        
        return {
            "accuracy": hdop,
            "age": 0.0,
            "altitude_meters": altitude,
            "from_sentence": "GPGGA",
            "ground_speed_knots": 0.0,
            "heading": None,
            "latitude": {
                "degree": lat_deg,
                "minute": lat_min,
                "second": lat_sec
            },
            "lock": quality > 0,
            "longitude": {
                "degree": lon_deg,
                "minute": lon_min,
                "second": lon_sec
            },
            "satellites": satellites,
            "time": time_val
        }
    except Exception as e:
        logger.error(f"Failed to parse NMEA GGA: {e}")
        return None

def handle_nmea(nmea, data=None, cs_path="/status/rtk/nmea", override_gps=False, location_output=False):
    if data is None:
        data = {}
    t = time.time()
    # prune data to last 30 seconds
    data = {k: v for k, v in data.items() if (t - k) < 30}
    data[t] = nmea
    cs_data = list(data.values())
    cs_put(cs_path, cs_data)
    
    # Only parse GGA for fix data if location_output is disabled
    if not location_output and 'GGA' in nmea:
        fix_data = parse_nmea_gga(nmea)
        if fix_data:
            # Always write to /status/gps/rtk
            cs_put("/status/gps/rtk", fix_data)
            
            # Optionally override /status/gps/fix
            if override_gps:
                try:
                    cs_put("/status/gps/fix", fix_data)
                except Exception as e:
                    logger.warning(f"Failed to override /status/gps/fix: {e}")
    
    return data

def handle_location(location_json, override_gps=False):
    """Handle location format output from S3LC client"""
    try:
        location_data = json.loads(location_json)
        if location_data.get("type") == "location":
            loc = location_data.get("location", {})
            
            # Convert to Cradlepoint GPS fix format
            lat = loc.get("latitude", 0)
            lon = loc.get("longitude", 0)
            alt = loc.get("altitude", 0)
            
            lat_deg = int(abs(lat))
            lat_min_full = (abs(lat) - lat_deg) * 60
            lat_min = int(lat_min_full)
            lat_sec = (lat_min_full - lat_min) * 60
            if lat < 0:
                lat_deg = -lat_deg
            
            lon_deg = int(abs(lon))
            lon_min_full = (abs(lon) - lon_deg) * 60
            lon_min = int(lon_min_full)
            lon_sec = (lon_min_full - lon_min) * 60
            if lon < 0:
                lon_deg = -lon_deg
            
            h_acc = loc.get("horizontal-accuracy", {})
            accuracy = h_acc.get("uncertainty-semi-major", 0) if isinstance(h_acc, dict) else 0
            
            fix_data = {
                "accuracy": accuracy,
                "age": 0.0,
                "altitude_meters": alt,
                "from_sentence": "LOCATION",
                "ground_speed_knots": 0.0,
                "heading": None,
                "latitude": {
                    "degree": lat_deg,
                    "minute": lat_min,
                    "second": lat_sec
                },
                "lock": True,
                "longitude": {
                    "degree": lon_deg,
                    "minute": lon_min,
                    "second": lon_sec
                },
                "satellites": 0,
                "time": 0
            }
            
            # Write to /status/gps/rtk
            cs_put("/status/gps/rtk", fix_data)
            
            # Optionally override /status/gps/fix
            if override_gps:
                try:
                    cs_put("/status/gps/fix", fix_data)
                except Exception as e:
                    logger.warning(f"Failed to override /status/gps/fix: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse location JSON: {e}")
    except Exception as e:
        logger.error(f"Failed to handle location: {e}")

def handle_nmea_tcp(nmea, tcp_clients):
    for client in tcp_clients:
        try:
            client.sendall((nmea+ '\r\n').encode())
        except:
            tcp_clients.remove(client)

def un_thread_server(cs_path="/status/rtk/nmea", tcp_clients=[], log_messages=True, override_gps=False, location_output=False):
    """ Thread for reading from unix socket and logging the output"""
    socket_path = "/tmp/nmea.sock"
    data = {}
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as unix_socket:
        unix_socket.bind(socket_path)
        unix_socket.listen(1)
        while True:
            client_socket, addr = unix_socket.accept()
            with client_socket:
                buffer = ""
                while True:
                    chunk = client_socket.recv(8192)
                    try:
                        chunk = chunk.decode()
                    except UnicodeDecodeError:
                        logger.error(f"failed decoding chunk as utf-8 {chunk}")
                        chunk = None
                    if not chunk:
                        break
                    buffer += chunk
                    while '\r\n' in buffer:
                        line, buffer = buffer.split('\r\n', 1)
                        if line:
                            # Check if it's JSON location format
                            if line.startswith('{') and '"type"' in line and '"location"' in line:
                                handle_location(line, override_gps)
                            else:
                                # NMEA format
                                if line[0] !='$':
                                    line = f'${line}'
                                if log_messages:
                                    logger.info(line)
                                if cs_path:
                                    data = handle_nmea(line, data=data, cs_path=cs_path, override_gps=override_gps, location_output=location_output)
                            handle_nmea_tcp(line, tcp_clients)

def location_thread_server(override_gps=False):
    """Thread for reading location JSON from separate unix socket"""
    socket_path = "/tmp/location.sock"
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as unix_socket:
        unix_socket.bind(socket_path)
        unix_socket.listen(1)
        while True:
            client_socket, addr = unix_socket.accept()
            with client_socket:
                buffer = ""
                while True:
                    chunk = client_socket.recv(8192)
                    try:
                        chunk = chunk.decode()
                    except UnicodeDecodeError:
                        logger.error(f"failed decoding location chunk as utf-8 {chunk}")
                        chunk = None
                    if not chunk:
                        break
                    buffer += chunk
                    while '\r\n' in buffer:
                        line, buffer = buffer.split('\r\n', 1)
                        if line and line.startswith('{'):
                            handle_location(line, override_gps)

def tcp_server_thread(port, tcp_clients):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_socket:
        tcp_socket.bind(('0.0.0.0', port))
        tcp_socket.listen(MAX_TCP_CONNECTIONS)
        logger.info(f"TCP server listening on port {port}")
        while True:
            client_socket, addr = tcp_socket.accept()
            logger.info(f"TCP client connected from {addr}")
            tcp_clients.append(client_socket)

def cs_get(path):
    try:
        if cs.ON_DEVICE:
            return cs.get(path)
        else:
            raise Exception("Not on device")
    except Exception as e:
        logger.error(f"failed getting {path} from CS: {e}")

def cs_put(path, value):
    try:
        if cs.ON_DEVICE:
            return cs.put(path, value)
        else:
            raise Exception("Not on device")
    except Exception as e:
        logger.error(f"failed putting to {path} in CS: {e}")

def get_appdata(key):
    try:
        if cs.ON_DEVICE:
            return cs.get_appdata(key)
    except Exception as e:
        logger.error(f"failed getting appdata {key}: {e}")

def get_cellular_info(device=None):
    if device is None:
        device = get_appdata("lpp-client.device") or cs_get("/status/wan/primary_device")
    if not (device and device.startswith("mdm")):
        logger.warning(f"primary_device is not a modem: {device}")
    
    diag = cs_get(f"/status/wan/devices/{device}/diagnostics") or {}
    plmn = diag.get('CUR_PLMN') or "000000"
    mcc = plmn[:3]
    mnc = plmn[3:]
    tac = diag.get('TAC') or '0'
    imsi = diag.get('IMSI') or '0'
    cell_id = diag.get('CELL_ID','').split(" ")[0] or '0'
    mdn = diag.get('MDN') or '0'
    nr = False

    if not cell_id:
        cell_id =  diag.get('NR_CELL_ID') or '0'
        if cell_id != '0':
            nr = True
        tac = plmn

    current_cellular = {"mcc": mcc, "mnc": mnc, "tac": tac, "cell_id": cell_id, "imsi": imsi, "nr": nr}

    # cellular overrides
    current_cellular["mcc"] = get_appdata("lpp-client.mcc") or current_cellular["mcc"]
    current_cellular["mnc"] = get_appdata("lpp-client.mnc") or current_cellular["mnc"]
    current_cellular["tac"] = get_appdata("lpp-client.tac") or current_cellular["tac"]
    current_cellular["cell_id"] = get_appdata("lpp-client.cell_id") or current_cellular["cell_id"]
    current_cellular["imsi"] = get_appdata("lpp-client.imsi") or current_cellular["imsi"]
    current_cellular["nr"] = get_appdata("lpp-client.nr") or current_cellular["nr"]

    # mdn can only be used if explicitly requested
    for use_mdn in (get_appdata("lpp-client.mdn"), get_appdata("lpp-client.msisdn")):
        if use_mdn is not None:
            current_cellular["mdn"] = mdn if use_mdn.lower() in ["", "true", "yes", "y"] else use_mdn

    return current_cellular

def get_cmd_params():
    host = get_appdata("lpp-client.host") or "129.192.82.125"
    port = get_appdata("lpp-client.port") or 5431
    serial = get_appdata("lpp-client.serial") or "/dev/ttyS1"
    baud = get_appdata("lpp-client.baud") or 115200
    output = get_appdata("lpp-client.output") or "un"
    format = get_appdata("lpp-client.format") or "osr"

    # mcc, mnc, tac, and cell_id can be statically configured as parsed by get_cellular_info(), 
    # or it could be dynamically updated from the momdem (default).  Additionality the initial params
    # can be specified explicitly, which THEN get updated dynamically by the modem. This allows the 
    # lpp client to start with known initial values
    starting_mcc = get_appdata("lpp-client.starting_mcc") or None
    starting_mnc = get_appdata("lpp-client.starting_mnc") or None
    starting_tac = get_appdata("lpp-client.starting_tac") or None
    starting_cell_id = get_appdata("lpp-client.starting_cell_id") or None

    forwarding = get_appdata("lpp-client.forwarding") or ""
    flags = get_appdata("lpp-client.flags") or ""
    #flags are comma separated. For example:
    # "confidence-95to39,ura-override=2,ublox-clock-correction,force-continuity,sf055-default=3,sf042-default=1,increasing-siou"
    cs_path = get_appdata("lpp-client.path")
    cs_path = "/status/rtk/nmea" if  cs_path is None else cs_path

    tokoro_flags = get_appdata("lpp-client.tokoro_flags") or ""
    spartn_flags = get_appdata("lpp-client.spartn_flags") or ""

    log_nmea = True
    log_nmea_value = get_appdata("lpp-client.log_nmea")
    if log_nmea_value is not None:
        if log_nmea_value.lower() in ["", "true", "yes", "y"]:
            log_nmea = True
        elif log_nmea_value.lower() in ["false", "no", "n"]:
            log_nmea = False

    enable_rtklib = False
    enable_rtklib_value = get_appdata("lpp-client.enable_rtklib")
    if enable_rtklib_value is not None:
        if enable_rtklib_value.lower() in ["true", "yes", "y"]:
            enable_rtklib = True

    override_gps = False
    override_gps_value = get_appdata("lpp-client.override_gps")
    if override_gps_value is not None:
        if override_gps_value.lower() in ["true", "yes", "y"]:
            override_gps = True

    location_output = False
    location_output_value = get_appdata("lpp-client.location_output")
    if location_output_value is not None:
        if location_output_value.lower() in ["true", "yes", "y"]:
            location_output = True

    return {
        "host": host,
        "port": port,
        "serial": serial,
        "baud": baud,
        "output": output,
        "cs_path": cs_path,
        "format": format,
        "starting_mcc": starting_mcc,
        "starting_mnc": starting_mnc,
        "starting_tac": starting_tac,
        "starting_cell_id": starting_cell_id,
        "forwarding": forwarding,
        "flags": flags,
        "tokoro_flags": tokoro_flags,
        "spartn_flags": spartn_flags,
        "log_nmea": log_nmea,
        "enable_rtklib": enable_rtklib,
        "override_gps": override_gps,
        "location_output": location_output,
    }

def build_v4_command(params, cellular):
    """Build command for v4 example-client"""
    app_path = "./example-client"

    # Handle additional flags
    additional_flags = params["flags"].replace(',', ' ').split()
    additional_flags = ' '.join(f"--{flag.lstrip('-')}" for flag in additional_flags)

    tokoro_flags = params["tokoro_flags"].replace(', ', ' ').split()
    tokoro_flags = ' '.join(f"--{flag.lstrip('-')}" for flag in tokoro_flags)

    # Use tokoro format
    ad_type = "--ad-type=ssr"
    processors = ["--tokoro"]
    additional_flags += " " + tokoro_flags
    
    # Identity specification
    identity_param = ""
    if cellular.get('mdn'):
        identity_param = f"--msisdn {cellular['mdn']}"
    else:
        identity_param = f"--imsi {cellular['imsi']}"
    
    # RTKLIB outputs (only if enabled)
    rtklib_outputs = []
    if params["enable_rtklib"]:
        input_param = f"--input serial:device={params['serial']},baudrate={params['baud']},format=rtcm"
        rtklib_outputs = [
            "--output tcp-server:host=localhost,port=5432,format=rtcm",
            "--output tcp-server:host=localhost,port=20000,format=rtcm",
            "--input tcp-client:host=localhost,port=5433,format=nmea"
        ]
    else:
        input_param = f"--input serial:device={params['serial']},baudrate={params['baud']},format=nmea+ubx"
    
    serial_rtcm_output = f"--output serial:device={params['serial']},baudrate={params['baud']},format=rtcm"
    
    # Output configuration for CS path
    outputs = []
    if params["output"].startswith("un"):
        outputs.append("--output tcp-client:path=/tmp/nmea.sock,format=nmea")
        if params["location_output"]:
            outputs.append("--output tcp-client:path=/tmp/location.sock,format=location")
    elif params["output"].startswith("tcp-server:"):
        _, ip, port = params["output"]
        outputs.append(f"--output tcp-server:host={ip},port={port},format=nmea")
        if params["location_output"]:
            outputs.append(f"--output tcp-server:host={ip},port={port},format=location")
    elif params["output"].startswith("tcp-client:"):
        _, ip, port = params["output"]
        outputs.append(f"--output tcp-client:host={ip},port={port},format=nmea")
        if params["location_output"]:
            outputs.append(f"--output tcp-client:host={ip},port={port},format=location")
    else:
        ip, port = params['output'].split(':')
        outputs.append(f"--output tcp-client:host={ip},port={port},format=nmea")
        if params["location_output"]:
            outputs.append(f"--output tcp-client:host={ip},port={port},format=location")
    
    export_param = " ".join(outputs)
    
    control_param = "--input stdin:format=ctrl"

    cmd = (
        f"{app_path} "
        f"{' '.join(processors)} "
        f"{additional_flags} "
        f"--ls-host {params['host']} "
        f"--ls-port {params['port']} "
        f"--mcc {params['starting_mcc'] or cellular['mcc']} "
        f"--mnc {params['starting_mnc'] or cellular['mnc']} "
        f"--tac {params['starting_tac'] or cellular['tac']} "
        f"--ci {params['starting_cell_id'] or cellular['cell_id']} "
        f"{'--nr-cell ' if cellular['nr'] else ''}"
        f"{identity_param} "
        f"{input_param} "
        f"{serial_rtcm_output} "
        f"{' '.join(rtklib_outputs)} "
        f"{export_param} "
        f"{control_param} "
        f"{ad_type} "
    )
    
    return cmd

def main():
    logger.info("Starting lpp client and RTKLIB")

    params = get_cmd_params()
    cellular = get_cellular_info()
    logger.info(params)
    
    start_time = time.time()

    # Store configuration and start time in config store
    config_status = {
        "config": params,
        "cellular": cellular,
        "start_time": start_time,
        "start_time_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_time))
    }
    cs_put("/status/rtk/config", config_status)

    if params["cs_path"] == "/status/rtk/nmea": # the default
        if cs_get("/status/rtk") is None:
            cs_put("/status/rtk", {"nmea": []})
    
    tcp_clients=[]

    if params["output"].startswith("un"):
        un_thread = threading.Thread(target=un_thread_server, args=(params["cs_path"], tcp_clients, params["log_nmea"], params["override_gps"], params["location_output"]))
        un_thread.daemon = True
        un_thread.start()
        
        # Start location socket thread if location_output is enabled
        if params["location_output"]:
            location_thread = threading.Thread(target=location_thread_server, args=(params["override_gps"],))
            location_thread.daemon = True
            location_thread.start()
        
        if params["output"].startswith("un-tcp"):
            _, port = params["output"].split(":")
            tcp_thread = threading.Thread(target=tcp_server_thread, args=(int(port), tcp_clients))
            tcp_thread.daemon = True
            tcp_thread.start()

    logger.info("Using v4 client (example-client)")
    cmd = build_v4_command(params, cellular)
    
    logger.info(cmd)
    lpp_program = RunProgram(cmd)

    # Start RTKLIB rtkrcv with config file if enabled
    rtklib_program = None
    if params["enable_rtklib"]:
        rtklib_cmd = "rtkrcv -s -nc -o /lpp-client/rtklib.conf"
        logger.info(f"RTKLIB command: {rtklib_cmd}")
        rtklib_program = RunProgram(rtklib_cmd)
    else:
        logger.info("RTKLIB disabled via config")

    # Create a control thread to handle user input (e.g., stopping the program)
    def control_thread(lpp_program, rtklib_program, current_params, current_cellular):
        logger.info("Periodically checking for changes")
        while True:
            time.sleep(10)
            if lpp_program.process is None or (rtklib_program and rtklib_program.process is None):
                logger.info("Program terminated")
                break
            new_params = get_cmd_params()
            if new_params != current_params:
                current_params = new_params
                logger.info("params changed", current_params)
                lpp_program.interrupt()
                if rtklib_program:
                    rtklib_program.quit()
                break
            new_cellular = get_cellular_info()
            logger.info(f"cell check: {new_cellular['mnc']},{new_cellular['mcc']},{new_cellular['tac']},{new_cellular['cell_id']},{new_cellular["nr"]} == {current_cellular['mnc']},{current_cellular['mcc']},{current_cellular['tac']},{current_cellular['cell_id']},{current_cellular["nr"]}")
            if new_cellular != current_cellular:
                current_cellular = new_cellular
                logger.info("cellular info changed")
                if current_cellular["nr"]:
                    cmd = f"/CID,N,{current_cellular['mcc']},{current_cellular['mnc']},{current_cellular['tac']},{current_cellular['cell_id']}\r\n"
                else:
                    cmd = f"/CID,L,{current_cellular['mcc']},{current_cellular['mnc']},{current_cellular['tac']},{current_cellular['cell_id']}\r\n"
                lpp_program.write(cmd)

    ct = threading.Thread(target=control_thread, args=(lpp_program,rtklib_program,params,cellular))
    ct.daemon = True
    ct.start()

    # Start both programs
    lpp_thread = threading.Thread(target=lpp_program.start)
    lpp_thread.start()
    
    if rtklib_program:
        rtklib_thread = threading.Thread(target=rtklib_program.start)
        rtklib_thread.start()

    ct.join()

    logger.info("Exiting program, hopefully restarting...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception(f"{e}")
        raise e