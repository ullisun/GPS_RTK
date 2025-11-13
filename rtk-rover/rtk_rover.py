#!/usr/bin/env python3
import serial, socket, threading, base64, time, json, os, sys
from datetime import datetime, timedelta


# === Konfiguration ===
SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 115200
NTRIP_SERVER = "80.158.61.104"
NTRIP_PORT = 2101
NTRIP_MOUNTPOINT = "VRS_3_3G_NW"
NTRIP_USER = "nyUSER"
NTRIP_PASS = "myPWD"
#SOURCE = "local"  # "sapos" oder "local"
SOURCE = "sapos"  # "sapos" oder "local"
DEBUG = sys.stdout.isatty()  # Debug ist True wenn per console gestartet

#JSON_FILE = "rtk_points.json"
#LOG_FILE = "rtk_session.log"


# === Globale Variablen ===
shared_gga = None
last_ntrip_rx = time.time()
last_ntrip_tx = time.time()
watchdog_timeout = 30  # Sekunden
start_time = datetime.now()


def dprint(msg):
    if DEBUG:
        print(msg)
    else:
        pass

def make_logfolder():
    folder=False
    logfolder= os.path.abspath("./")+"/logs/"+ str(time.strftime('%Y%m%d'))+"/"
    if not os.path.isdir(logfolder):
        os.makedirs(logfolder)
        dprint(f"[LOG_FOLDER] {logfolder}  wurde erstellt")
        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        logfile=logfolder+str(time.strftime('%H_%M_'))+"rtk_session.log"
        jsonfile=logfolder+str(time.strftime('%H_%M_'))+"rtk_points.json"
        with open(logfile, "a") as f:
            f.write(f"{now} [LOG_FOLDER] {logfolder}  wurde erstellt\n")
    else:
        logfile=logfolder+str(time.strftime('%H_%M_'))+"rtk_session.log"
        jsonfile=logfolder+str(time.strftime('%H_%M_'))+"rtk_points.json"
    return logfile, jsonfile

def make_jsonfile(path):
    with open(path,"w") as f:
        f.write("[\n")

def log(msg):
    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    with open(LOG_FILE, "a") as f:
       f.write(f"{now} {msg}\n")
    dprint(f"[{now}] {msg}")

# === Hilfsfunktionen ===
def send_cmd(ser, cmd):
    """Sendet ASCII-Befehl an GNSS Modul"""
    ser.write((cmd + "\r\n").encode())
    log(f"[TX] {cmd}")
    time.sleep(0.2)

def parse_nmea(line):
    """Zerlegt NMEA Zeile in Dictionary"""
    #print(line)
    try:
        parts = line.split(",")
        if line.startswith("$GNGGA") and len(parts) > 6:
            #fix_map = {"0": "NOFIX", "1": "3D", "2": "RTK-Float", "4": "RTK-Fixed"}
            fix_map = {"0": "No Fix", "1": "3D", "2": "DGPS", "4": "RTK-Fixed", "5": "RTK-Float"}
            #print(parts[2][:2],  parts[2][2:])
            lat = float(parts[2][:2]) + float(parts[2][2:]) / 60
            if parts[3] == "S": lat = -lat
            lon = float(parts[4][:3]) + float(parts[4][3:]) / 60
            if parts[5] == "W": lon = -lon
            fix = fix_map.get(parts[6], parts[6])
            return {"type": "GGA", "lat": lat, "lon": lon, "fix": fix}

        elif line.startswith("$GNRMC") and len(parts) > 8:
            speed_knots = float(parts[7]) if parts[7] else 0.0
            heading = float(parts[8]) if parts[8] else 0.0
            return {"type": "RMC", "speed": speed_knots * 0.514444, "heading": heading}
    except:
        pass
    return None

def write_json_point(data):
    with open("/dev/shm/rtk_point.json", "w") as f:
        f.write(json.dumps(data, ensure_ascii=False))

def add_json_point(data):
    global JSON_FILE, start_time
    if datetime.now() - start_time > timedelta(minutes=90):
        ret=make_logfolder()
        JSON_FILE = ret[1]
        start_time = datetime.now()
        dprint(f"[INFO] Neues Logfile gestartet: {JSON_FILE}")

    with open(JSON_FILE, "a") as f:
        f.write(json.dumps(data, ensure_ascii=False) + ",\n")



# === Watchdog ===
def watchdog_thread():
    global last_ntrip_rx, last_ntrip_tx
    while True:
        now = time.time()
        if SOURCE=="sapos":
            if (now - last_ntrip_rx > watchdog_timeout) or (now - last_ntrip_tx > watchdog_timeout):
                log("[WATCHDOG] Keine NTRIP TX/RX Aktivität → Neustart")
                os._exit(1)
        time.sleep(5)


def start_localbase_thread(ser):
    """Empfängt RTCM von lokaler RTK-Basisstation"""
    def base_loop():
        global last_ntrip_rx
        HOST = "192.168.178.29"  # IP deiner Basisstation
        PORT = 2102             # Port, den die Basis sendet
        while True:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                log(f"[LOCALBASE] Verbinde zu Basisstation {HOST}:{PORT}")
                sock.connect((HOST, PORT))
                log("[LOCALBASE] Verbindung steht ✓")

                sock.settimeout(2)
                while True:
                    data = sock.recv(1024)
                    if not data:
                        log("[LOCALBASE] Verbindung getrennt, reconnect …")
                        break
                    ser.write(data)
                    last_ntrip_rx = time.time()
                    log(f"[LOCALBASE RX] {len(data)} bytes -> LC29H")
            except Exception as e:
                log(f"[LOCALBASE ERROR] {e}")
                time.sleep(5)
    threading.Thread(target=base_loop, daemon=True).start()



# === NTRIP Client ===
def start_ntrip_thread(ser):
    def ntrip_loop():
        global shared_gga, last_ntrip_rx, last_ntrip_tx
        while True:
            try:
                credentials = base64.b64encode(f"{NTRIP_USER}:{NTRIP_PASS}".encode()).decode()
                headers = (
                    f"GET /{NTRIP_MOUNTPOINT} HTTP/1.0\r\n"
                    f"User-Agent: NTRIP PythonClient\r\n"
                    f"Authorization: Basic {credentials}\r\n\r\n"
                )

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10)
                log(f"[NTRIP] Connecting to {NTRIP_SERVER}:{NTRIP_PORT}")
                sock.connect((NTRIP_SERVER, NTRIP_PORT))
                sock.send(headers.encode())
                response = sock.recv(1024)
                if b"200" not in response:
                    raise Exception(f"Bad NTRIP response: {response.decode(errors='ignore')}")
                log("[NTRIP] Now Connected to SAPOS ✓")

                sock.settimeout(1.0)  # nicht blockierend warten

                # Warten auf ersten GGA vom GNSS oder Dummy senden
                time.sleep(1)
                if shared_gga:
                    gga_to_send = shared_gga.strip()
                else:
                    # Dummy GGA zentriert in Deutschland
                    log(f"[NTRIP INIT] **************   Dummy wird gesendet ****************")
                    gga_to_send = "$GPGGA,120000.00,5216.000,N,00840.000,E,1,05,1.5,100.0,M,46.9,M,,*5A"
                sock.send((gga_to_send + "\r\n").encode())
                last_ntrip_tx = time.time()
                #log(f"[NTRIP INIT] GGA sent: {gga_to_send}")

                # Hauptloop
                while True:
                    try:
                        data = sock.recv(1024)
                        if data:
                            ser.write(data)
                            last_ntrip_rx = time.time()
                            log(f"[NTRIP RX] {len(data)} bytes -> LC29H")
                    except socket.timeout:
                        pass  # kein Problem, weiter pollen

                    # Alle 5s GGA senden
                    if shared_gga and time.time() - last_ntrip_tx > 1:
                        sock.send((shared_gga.strip() + "\r\n").encode())
                        last_ntrip_tx = time.time()
                        log(f"[NTRIP TX] GGA -> caster: {shared_gga.strip()}")

            except Exception as e:
                log(f"[NTRIP ERROR] {e}")
                time.sleep(5)
                log("[NTRIP] reconnecting …")
                continue
    threading.Thread(target=ntrip_loop, daemon=True).start()


# === GNSS Reader ===
def gnss_thread(ser):
    global shared_gga
    heading_deg =0
    speed_m_s=0
    last_lat = last_lon = None
    mem=True
    sats_used=0

    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if not line.startswith("$"):
            continue
        parsed = parse_nmea(line)

        if line.startswith(("$GNGGA", "$GPGGA")):
            parts = line.split(',')
            if len(parts) >= 8:
                #print(f"sehe {parts[7]} Sateliten")
                sats_used = parts[7]
            else:
                sats_used = 0

        if not parsed:
            continue
        if line.startswith(("$GNRMC", "$GPRMC")):
            parts = line.split(',')
            if parts[2] == 'A':  # Status A = valid
                speed_knots = float(parts[7]) if parts[7] else 0.0
                heading_deg = float(parts[8]) if parts[8] else 0.0
                speed_m_s = speed_knots * 0.514444  # Knoten → m/s

                #print(f"Heading= {heading_deg} \t Speed= {speed_m_s}")
        if parsed["type"] == "GGA":
            shared_gga = line
            #print(shared_gga)
            #print("==================================================================")
            dprint("")
            lat, lon, fix = parsed["lat"], parsed["lon"], parsed["fix"]
            delta = 0
            if last_lat and last_lon:
                delta = ((lat - last_lat)**2 + (lon - last_lon)**2)**0.5 * 111000
            last_lat, last_lon = lat, lon

            try:
                alt = float(parts[9].strip()) if parts[9].strip() else 0.0
            except (ValueError, IndexError):
                alt = 0.0


            #sats_used = int(parts[7]) if parts[7].isdigit() else 0
            log(f"Lat:{lat:.7f} Lon:{lon:.7f} [{fix}] [Δ={delta:.2f} m]  [speed:{speed_m_s:.2f}][heading: {heading_deg}][Sat: {sats_used}] [Alt: {round(alt,2)}]")




            #log(f"Lat:{lat:.7f} Lon:{lon:.7f} [{fix}] [Δ={delta:.2f} m]  [speed:{speed_m_s:.2f}][heading: {heading_deg}]")
            #if fix=="3D":
            #     print(datetime.now().strftime("%H:%M:%S")+ fix)
            #if fix=="RTK-Float":
            #    print(datetime.now().strftime("%H:%M:%S")+ "       " +fix)
            #if fix=="RTK-Fixed":
            #    print(datetime.now().strftime("%H:%M:%S")+"                          " +fix)
            data = {
                "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "lat": lat,
                "lon": lon,
                "fix": fix,
                "sats":sats_used,
                "speed": f"{speed_m_s:.2f}",
                "heading": heading_deg,
                "delta":f"{delta:.2f}",
                "event": "",
                "image": ""
            }
            point= {
                "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "lat": lat,
                "lon": lon,
                "fix": fix,
                "sats":sats_used,
                "speed": f"{speed_m_s:.2f}",
                "heading":  heading_deg
            }
            #print(f"data= {data}")
            if mem==True:
                add_json_point(data)         # Datei steht im Logverzeichnis und enthält alle Punkte der Session
                write_json_point(point)      # Datei steht in RAM Disk und enthält nur den letzten Punkt
        #elif parsed["type"] == "RMC":
            # Update letzte Speed/Heading im JSON
        #    data = {
        #        "time": datetime.utcnow().isoformat(),
        #        "lat": last_lat,
        #        "lon": last_lon,
        #        "fix": "3D",
        #        "speed": parsed["speed"],
        #        "heading": parsed["heading"],
        #        "event": "",
        #        "image": ""
        #    }

        #    write_json_point(data)

# === Initialisierung ===
def init_lc29(ser):
    """Setzt LC29H-DA in Rover Modus"""
    log("=== LC29HDA Rover Init Start ===")
    send_cmd(ser, "$PQTMVERNO*58")
    send_cmd(ser, "$PQTMCFGRCVRMODE,R*32")
    send_cmd(ser, "$PQTMCFGRCVRMODE,W,2*29")
    send_cmd(ser, "$PQTMCFGRCVRMODE,R*32")
    send_cmd(ser, "$PAIR434,1*24")
    send_cmd(ser, "$PAIR062,0,01*0F")
    log("[DONE] LC29HDA ready for NTRIP startup ✓")

# === Main ===
def main():
    log("=== RTK bridge with watchdog starting ===")
    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
    init_lc29(ser)
    #start_ntrip_thread(ser)
    if SOURCE == "sapos":
        start_ntrip_thread(ser)
    elif SOURCE == "local":
        start_localbase_thread(ser)
    else:
        log("[ERROR] Ungültige SOURCE-Option!")
        return
    threading.Thread(target=watchdog_thread, daemon=True).start()
    gnss_thread(ser)

if __name__ == "__main__":
    if len(sys.argv)<2:
        SOURCE="sapos"
    if len(sys.argv)==2 and sys.argv[1]=="-b":
        SOURCE="local"
    dprint(f"\n########## Hole Korrecturdaten von {SOURCE} #########################")
    dprint("")
    ret=make_logfolder()
    JSON_FILE = ret[1]
    LOG_FILE = ret[0]
    make_jsonfile(JSON_FILE)
    log("=== RTK Rover Full Startup ===")

    try:
        main()
    except KeyboardInterrupt:
        log("Exiting by user")
        sys.exit(0)
