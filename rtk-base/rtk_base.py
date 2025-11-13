#!/usr/bin/env python3

#      tested on 12th Nov. 2025
#      Es müssen von Dir die ECEF_X, ECEF_Y und ECEF_Z Daten in die Zeilen 67 - 69 aktualisiert
#      werden. Diese Werte liefert das LC29HBS.py script wenn es mit python LC29HBS.py 300 s
#      aufgerufen wird. 300 bedeutet, es scannt 300 Minuten die aktuelle Position und bildet
#      aus den Werten dann einen Mittelwert und nimmt diesen als aktuellen Standort an. Je Länger
#      dieser Prozess läuft, umso genauer ist dann die Position des Standortes für die Basisstaion



import serial, socket, threading, time, math, sys, os
from datetime import datetime

# === Konfiguration ===
SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 115200
TCP_PORT = 2102           # Port, über den Rover und Basis sich verbinden


DEBUG = sys.stdout.isatty() # ist True wenn Datei über Terminal aufgerufen wird

# === Globale Variablen ===
clients = []
stop_flag = False
_last_seen_pqtm = {}


def dprint(msg):
    if DEBUG:
        print(msg)
    else:
        pass

def log(msg):
    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    dprint(f"[{now}] {msg}")


def nmea_checksum(sentence):
    """Berechnet NMEA-Checksumme"""
    csum = 0
    for c in sentence:
        csum ^= ord(c)
    return f"*{csum:02X}"

def send_cmd(ser, cmd):
    """Sendet ASCII-Befehl mit automatischer Prüfsumme"""
    if "*" not in cmd:
        base = cmd.split("$")[1]
        cmd = f"${base}{nmea_checksum(base)}"
    ser.write((cmd + "\r\n").encode())
    log(f"[TX] {cmd}")
    time.sleep(0.2)

# === Initialisierung LC29H ===
def init_lc29_base(ser):

    log("=== LC29HDA Basis Init Start ===")

    '''
    #  ECEF Daten von Berlin Alexanderplatz
    #  Diese müssen durch die ECEF Daten ersetzt werden
    #  die vom LC29HBS.py script am Ende in die Log Datei geschrieben werden
    '''

    ECEF_X = 3782949.3699
    ECEF_Y =  902134.8435
    ECEF_Z = 5038395.3797




    log(f"[BASE POS] X={ECEF_X:.4f}, Y={ECEF_Y:.4f}, Z={ECEF_Z:.4f}")

    # Standort (ECEF) in das LC29HBS schreiben
    send_cmd(ser, f"$PQTMCFGSVIN,W,2,0,0.0,{ECEF_X:.4f},{ECEF_Y:.4f},{ECEF_Z:.4f}")

    # Antenne aktivieren, Ausgabe einschalten
    send_cmd(ser, "$PQTMCFGRTCM,W,1,1,1,1,1,1,1,1,1,1")  # alle RTCM aktivieren
    send_cmd(ser, "$PQTMCFGMSG,0,1,0,0,0,0,0")           # nur RTCM-Ausgabe
    send_cmd(ser, "$PQTMVERNO")
    log("[DONE] LC29HDA ready and transmitting RTCM ")

# === RTCM Listener + Antwortanzeige ===
def rx_thread(ser):
    """Liest RTCM + ASCII ($P...) gleichzeitig aus dem LC29H"""
    global stop_flag, _last_seen_pqtm
    buffer = b""
    while not stop_flag:
        try:
            data = ser.read(1024)
            if not data:
                continue
            buffer += data

            i = 0
            while i < len(buffer):
                # --- RTCM Frame ---
                if buffer[i] == 0xD3:
                    if i + 3 > len(buffer):
                        break
                    length = ((buffer[i+1] & 0x03) << 8) | buffer[i+2]
                    frame_len = 3 + length + 3
                    if i + frame_len > len(buffer):
                        break  # unvollständig
                    frame = buffer[i:i+frame_len]
                    msg_type = ((frame[3] & 0xFC) << 4) | (frame[4] >> 4)
                    log(f"[RTCM3] Type {msg_type:<4} | Size {len(frame)} bytes")
                    for c in clients.copy():
                        try:
                            c.sendall(frame)
                        except Exception:
                            clients.remove(c)
                    i += frame_len
                    continue

                # --- ASCII Zeile ($P...) ---
                elif buffer[i] == 0x24:  # '$'
                    end_idx = buffer.find(b"\n", i)
                    if end_idx == -1:
                        break  # unvollständig
                    line = buffer[i:end_idx].decode(errors="ignore").strip()
                    if line.startswith("$P"):
                        now = time.time()
                        if line not in _last_seen_pqtm or (now - _last_seen_pqtm[line]) >= 5:
                            _last_seen_pqtm[line] = now
                            log(f"[LC29H RESP] {line}")
                    i = end_idx + 1
                    continue

                # --- sonst: verwerfen ---
                i += 1

            # Verbleibende Daten im Buffer halten (z. B. halbe Zeile)
            buffer = buffer[i:]

        except Exception as e:
            log(f"[RX ERROR] {e}")
            time.sleep(0.1)


# === Thread zum Überwachen von pos.conf ===
def watch_conf_thread(ser):
    """Überwacht pos.conf und aktualisiert Basisposition"""
    while not stop_flag:
        try:
            if os.path.exists("pos.conf"):
                with open("pos.conf") as f:
                    parts = f.read().strip().split(",")
                if len(parts) >= 3:
                    lat = float(parts[0])
                    lon = float(parts[1])
                    alt = float(parts[2])
                    X, Y, Z = calc_x_y_z(lat, lon, alt)
                    cmd = f"$PQTMCFGSVIN,W,2,0,0.0,{X:.4f},{Y:.4f},{Z:.4f}"
                    send_cmd(ser, cmd)
                    log(f"[UPDATE] Neue Basispos: {lat:.7f},{lon:.7f},{alt:.2f}")
                    os.remove("pos.conf")
                    log("[UPDATE] pos.conf verarbeitet und gelöscht ✓")
        except Exception as e:
            log(f"[UPDATE ERROR] {e}")
        time.sleep(5)

# === TCP-Server für Rover ===
def tcp_server():
    """TCP Server, der RTCM an Rover streamt"""
    global clients
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", TCP_PORT))
    s.listen(1)
    log(f"[SERVER] RTCM TCP Server läuft auf Port {TCP_PORT}")
    while not stop_flag:
        conn, addr = s.accept()
        log(f"[SERVER] Neuer Rover verbunden: {addr}")
        clients.append(conn)

# === Main ===
def main():
    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
    init_lc29_base(ser)
    threading.Thread(target=tcp_server, daemon=True).start()
    threading.Thread(target=watch_conf_thread, args=(ser,), daemon=True).start()
    rx_thread(ser)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Beendet durch Benutzer.")
        stop_flag = True
        sys.exit(0)
