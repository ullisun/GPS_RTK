#!/usr/bin/env python3


'''                   Importand Note
        # Please update your NTRIP Server Datas if you will use this
        # Update also your IP Adress to acces your RTK- Base Station if you will use this
        # you can start the rover script by using your NTRIP Server with python rtk-rover.py
        # you can start the rover script by using your RTK-Base Station with python rtk-rover.py -b
        # or you can use it by creating in /dev/shm/ a file named "RTK-local-Base" with no content
        #
'''


import serial, socket, threading, base64, time, json, os, sys, math
from datetime import datetime, timedelta
from collections import deque
from statistics import mean



# === Konfiguration ===
SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 115200
NTRIP_SERVER = "80.158.61.104"
NTRIP_PORT = 2101
NTRIP_MOUNTPOINT = "VRS_3_3G_NW"
NTRIP_USER = "nyUSER"
NTRIP_PASS = "myPWD"
# =============  Wichtig !! ======  Wichtig !! ======  Wichtig !! ======  Wichtig !! =======================
# =============  Zeile 32 die IP Adresse zur Basisstation auf Deine eigene Anpassen ========================
# ==========================================================================================================
IP_BASISSTATION = "192.168.178.40"
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
gsv_cn0_values = []  # globale Liste, wird pro Sekunde gefüllt



# --- parametrisierung ---
# --- für die Güte Berechnung
sat_min = 6
sat_best = 40

hdop_best = 0.5
hdop_worst = 2.5

delta_still_max = 0.02  # m -> sehr klein, Stand
delta_movement_max = 0.5  # m -> falls > das wird als Bewegung betrachtet

# gewichte (sollten 1.0 zusammen ergeben wenn cn0 nicht genutzt wird)
w_sat = 0.35
w_hdop = 0.45
w_delta = 0.20
# Wenn du CN0 nutzt, addiere w_cn0 und setze w_delta entsprechend kleiner
w_cn0 = 0.0

# rolling smoothing
WINDOW = 10  # Sekunden (bei 1 Hz sampling)
scores_window = deque(maxlen=WINDOW)

# thresholds
TH_ON = 85
TH_OFF = 75




def dprint(msg):
    if DEBUG:
        print(msg)
    else:
        pass

def make_logfolder():
    folder=False
    #logfolder= os.path.abspath("./")+"/logs/"+ str(time.strftime('%Y%m%d'))+"/"
    logfolder= "/home/pi/Mower/logs/"+ str(time.strftime('%Y%m%d'))+"/"
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



def calc_heading(lat1, lon1, lat2, lon2):
    # lat/lon in degrees
    dLon = math.radians(lon2 - lon1)
    lat1r = math.radians(lat1)
    lat2r = math.radians(lat2)
    y = math.sin(dLon) * math.cos(lat2r)
    x = math.cos(lat1r) * math.sin(lat2r) - math.sin(lat1r) * math.cos(lat2r) * math.cos(dLon)
    heading = math.degrees(math.atan2(y, x))
    return (heading + 360) % 360

def geo_distance_m(lat1, lon1, lat2, lon2):
    """
    Berechnet die Distanz in Metern zwischen zwei GPS-Punkten.
    """
    R = 6371000.0  # Erdradius in Metern

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return round((R * c),2)


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
        make_jsonfile("/dev/shm/rtk_session.json")
        make_jsonfile(JSON_FILE)

    with open(JSON_FILE, "a") as f:
        f.write(json.dumps(data, ensure_ascii=False) + ",\n")

def add_json_session(data):
    with open("/dev/shm/rtk_session.json", "a") as f:
       f.write(json.dumps(data, ensure_ascii=False) + ",\n")

def parse_gsv(line):
    global gsv_cn0_values

    parts = line.split(',')
    if len(parts) < 4:
        return

    # Anzahl der Sätze und Satzindex
    total_msgs = int(parts[1])
    msg_index = int(parts[2])

    # wie viele Satelliten sichtbar
    sat_count = int(parts[3])

    # ab hier kommen Viererblöcke: PRN, Elev, Azim, CN0
    # startindex = 4
    idx = 4
    while idx + 3 < len(parts):
        try:
            prn = parts[idx]
            elev = parts[idx+1]
            azim = parts[idx+2]
            cn0  = parts[idx+3]

            if cn0 != "":
                gsv_cn0_values.append(int(cn0))
        except:
            pass
        idx += 4

    # Wenn letzter GSV Satz empfangen → Mittelwert bilden
    if msg_index == total_msgs and len(gsv_cn0_values) > 0:
        mean_cn0 = sum(gsv_cn0_values) / len(gsv_cn0_values)
        last_mean_cn0 = mean_cn0
        # Nach außen zurückgeben oder global speichern
        gsv_cn0_values = []  # neue Sekunde vorbereiten
        return mean_cn0

    return None

# --- Hilfsfunktionen ---
def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x

def norm_sat(sat):
    # linear normalization sat_min..sat_best -> 0..1
    return clamp((sat - sat_min) / (sat_best - sat_min), 0.0, 1.0)

def norm_hdop(hdop):
    # hdop_best -> 1, hdop_worst -> 0, linear in between
    if hdop <= hdop_best:
        return 1.0
    if hdop >= hdop_worst:
        return 0.0
    return 1.0 - (hdop - hdop_best) / (hdop_worst - hdop_best)

def norm_delta(delta):
    # small delta -> good (still), moderate delta -> OK, large delta -> movement (OK)
    # we prefer small delta in "stand" detection, but if moving we treat as OK
    # map 0..delta_still_max -> 1..0.5 ; delta_still_max..delta_movement_max -> 0.5..0
    d = abs(delta)
    if d <= delta_still_max:
        return 1.0
    if d <= delta_movement_max:
        # linear from 1 -> 0.2 (or 0.5) as delta grows
        # we want not to penalize moderate movement too much
        return 0.5 * (1.0 - (d - delta_still_max) / (delta_movement_max - delta_still_max))
    # very large delta -> moving fast -> treat as lower trust to instantaneous pos but don't zero out
    return 0.2

def norm_cn0(mean_cn0):
    # optional: 30 dBHz -> 0.2, 45 dBHz -> 1.0
    if mean_cn0 is None:
        return 0.5
    lo = 28.0
    hi = 45.0
    return clamp((mean_cn0 - lo) / (hi - lo), 0.0, 1.0)


# main update: call per sample
#quality = update_quality(fix=fix,sats=int(sats_used),hdop=hdop,cn0=latest_cn0_mean, delta=delta)

def update_quality(sat_used, hdop, delta_m, mean_cn0=None):
    #return 0
    s_sat = norm_sat(sat_used)
    s_hdop = norm_hdop(hdop)
    s_delta = norm_delta(delta_m)
    s_cn0 = norm_cn0(mean_cn0) if w_cn0 > 0 else 0.0

    combined = w_sat * s_sat + w_hdop * s_hdop + w_delta * s_delta + w_cn0 * s_cn0
    combined = clamp(combined, 0.0, 1.0)
    score = int(round(combined * 100))

    # smoothing window
    scores_window.append(score)
    smooth = int(round(mean(scores_window)))

    # state with hysteresis
    if smooth >= TH_ON:
        state = "RTK-VERY-GOOD"
    elif smooth >= TH_OFF:
        state = "RTK-GOOD"
    else:
        state = "RTK-QUESTIONABLE"

    # return per-sample info
    return {
        "score_instant": score,
        "score_smooth": smooth,
        "state": state,
        "components": {
            "sat": s_sat, "hdop": s_hdop, "delta": s_delta, "cn0": s_cn0
        }
    }


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
        HOST = IP_BASISSTATION  # IP deiner Basisstation
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
    hdop=1.0
    last_alt=None
    last_hdop=None
    last_lat = last_lon = None
    mem=True
    sats_used=0
    latest_cn0_mean=0
    cn0_val = 0

    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if not line.startswith("$"):
            continue

        if "$GPGSV" in line or "$GLGSV" in line or "$GAGSV" in line or "$BDGSV" in line:
            cn0_val = parse_gsv(line)
            if cn0_val is not None:
                latest_cn0_mean = cn0_val

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

                #print(f"Heading= {heading_deg} \t Speed= {speed_m_s}")
        if parsed["type"] == "GGA":
            shared_gga = line
            dprint("")
            lat, lon, fix = parsed["lat"], parsed["lon"], parsed["fix"]
            delta = 0

            if last_lat and last_lon:
                #delta = ((lat - last_lat)**2 + (lon - last_lon)**2)**0.5 * 111000
                delta= geo_distance_m(last_lat,last_lon,lat,lon)
                heading_deg=round(calc_heading(last_lat,last_lon,lat,lon),2)

            # --- Speed ist hier noch nicht sauber aber bei 1Hz annähernd richtig
            speed_m_s = delta


            last_lat, last_lon = lat, lon

            # --- Satellitenzahl ---
            try:
                sats_used = int(parts[7]) if parts[7] != "" else 0
            except:
                sats_used = 0

            # --- HDOP ---
            try:
                hdop = float(parts[8]) if parts[8] != "" else last_hdop or 0.0
                last_hdop = hdop
            except:
                hdop = last_hdop or 0.0

            # --- Höhe ---
            try:
                alt = float(parts[9]) if parts[9] != "" else last_alt or 0.0
                last_alt = alt
            except:
                alt = last_alt or 0.0

            #quality = update_quality(fix=fix,sats=int(sats_used),hdop=hdop,cn0=latest_cn0_mean, delta=delta,
            #                         speed=speed_m_s)
            #         update_quality(sat_used, hdop, delta_m, mean_cn0=None):

            info = update_quality(int(sats_used),hdop,delta,latest_cn0_mean)

            #sats_used = int(parts[7]) if parts[7].isdigit() else 0
            log(f"Lat:{lat:.7f} Lon:{lon:.7f} [{fix}] [Δ={delta:.2f} m] [speed:{speed_m_s:.2f}] [heading: {heading_deg}] [Sat: {sats_used}] [HDOP: {hdop}] [cn0: {round(latest_cn0_mean,2)}] [quality_score: {info['score_smooth']}] [quality_state: {info['state']}] [q_components: {info['components']}] [Alt: {round(alt,2)}]")

            #log(f"Lat:{lat:.7f} Lon:{lon:.7f} [{fix}] [Δ={delta:.2f} m] [speed:{speed_m_s:.2f}] [heading: {heading_deg}] [Sat: {sats_used}] [HDOP: {hdop}] [quality_score: {info['score_smooth']}] [cn0: {latest_cn0_mean}] [Alt: {round(alt,2)}]")



            data = {
                "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "lat": lat,
                "lon": lon,
                "fix": fix,
                "hdop":hdop,
                "quality_score": info["score_smooth"],
                "quality_state": info["state"],
                "q_components": info["components"],
                "alt":alt,
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
                "hdop":hdop,
                "alt":alt,
                "sats":sats_used,
                "cn0": latest_cn0_mean,
                "quality_score": info["score_smooth"],
                "quality_state": info["state"],
                "q_components": info["components"],
                "speed": f"{speed_m_s:.2f}",
                "heading":  heading_deg
            }

            add_json_point(data)         # Datei steht im Logverzeichnis und enthält alle Punkte der Session
            write_json_point(point)      # Datei steht in RAM Disk und enthält nur den letzten Punkt
            add_json_session(point)      # Datei steht in RAM Disk und wird für das initiale laden der Wbseite benötigt


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
    BASE=False
    if os.path.exists("/dev/shm/RTK-local-Base"):
        dprint("***************** Base Station is locally *********************")
        BASE=True
    if len(sys.argv)<2:
        SOURCE="sapos"
    if (len(sys.argv)==2 and sys.argv[1]=="-b") or BASE == True:
        SOURCE="local"
    dprint(f"\n########## Hole Korrecturdaten von {SOURCE} #########################")
    dprint("")
    ret=make_logfolder()
    JSON_FILE = ret[1]
    LOG_FILE = ret[0]
    make_jsonfile(JSON_FILE)
    make_jsonfile("/dev/shm/rtk_session.json")
    log("=== RTK Rover Full Startup ===")

    try:
        main()
    except KeyboardInterrupt:
        log("Exiting by user")
        sys.exit(0)
