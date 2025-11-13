#!/usr/bin/env python3

#               Datei Aufruf:
#               python LC29HBS.py          liest die aktuelle Config vom LC29HBS Chip aus
#               python LC29HBS.py 180      führt 180 Minuten einen Survey-In Prozess durch
#               python LC29HBS.py 180 s    führt 180 Minuten einen Survey-In Prozess durch und speichert die Daten im Flash
#
#               Ein guter Survey-In Prozess sollte 24h lang also 1440 Minuten laufen


import serial
import threading
import time
import queue
import sys
import math
import datetime
from datetime import datetime
import os




# WGS84 constants
#A = 6378137.0
#F = 1/298.257223563
#E2 = F * (2 - F)


# https://www.waveshare.com/wiki/LC29H(XX)_GPS/RTK_HAT


# --- Globale Queue für RX-Zeilen ---
rx_queue = queue.Queue()
stop_flag = False

def init_logfile():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{timestamp}_Survey.log"
    with open(log_filename, "w", encoding="utf-8") as f:
        f.write("# Quectel LC29 Survey-In Result\n")
        f.write(f"# Datum: {datetime.now()}\n\n")
    return log_filename

def log_event(direction, message):
    """Protokolliert TX/RX-Ereignisse mit Zeitstempel"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"[{ts}] [{direction}] {message}\n"
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(line)




def calc_checksum(sentence: str) -> str:
    """Berechnet NMEA-Checksumme für einen Befehl ohne Stern (*)"""
    csum = 0
    for c in sentence:
        csum ^= ord(c)
    return f"{sentence}*{csum:02X}"

def ecef_to_geodetic(x, y, z):
    """ECEF → WGS84 (Latitude, Longitude, Altitude)"""
    a = 6378137.0
    e2 = 6.69437999014e-3

    lon = math.atan2(y, x)
    p = math.sqrt(x**2 + y**2)
    lat = math.atan2(z, p * (1 - e2))
    for _ in range(5):
        N = a / math.sqrt(1 - e2 * math.sin(lat)**2)
        lat = math.atan2(z + e2 * N * math.sin(lat), p)
    alt = p / math.cos(lat) - N
    return math.degrees(lat), math.degrees(lon), alt


def log_survey_result(x, y, z, duration, acc_limit):
    lat, lon, alt = ecef_to_geodetic(x, y, z)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"# Survey Dauer: {duration} Sekunden\n")
        f.write(f"# 3D_AccuracyLimit: {acc_limit} m\n\n")
        f.write(f"ECEF_X = {x}\n")
        f.write(f"ECEF_Y = {y}\n")
        f.write(f"ECEF_Z = {z}\n\n")
        f.write(f"Latitude  = {lat:.8f}\n")
        f.write(f"Longitude = {lon:.8f}\n")
        f.write(f"Altitude  = {alt:.2f}\n\n")
        f.write(f'"lat": {lat:.8f}, "lon": {lon:.8f}')
        f.write("\n\n")


    print(f"Ergebnis gespeichert in {LOGFILE}")
    print(f"LAT={lat:.8f}, LON={lon:.8f}, ALT={alt:.2f}")


def format_time(seconds):
    """Formatiert Sekunden in Stunden, Minuten, Sekunden"""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return h, m, s

def run_survey(duration):
    """Zeigt einen laufenden Survey-In Prozess mit Einzeilen-Status und Spinner"""
    print(f"=== Starte Survey-In für {duration//3600} Std. {(duration%3600)//60} Min. {duration%60} Sek. ===")
    log_event("INFO", f"=== Starte Survey-In für  {duration//3600} Std. {(duration%3600)//60} Min. {duration%60} Sek. ===")
    spinner = ['/', '-', '\\', '|']
    spin_idx = 0
    end_time = time.time() + duration

    while True:
        remaining = int(end_time - time.time())
        if remaining <= 0:
            break

        h, m, s = format_time(remaining)

        # Stunden und Minuten ausgeben, Sekunden nur wenn <1h Restzeit
        if remaining > 3600:
            time_str = f"{h:02d} Std. {m:02d} Min."
        else:
            time_str = f"{h:02d} Std. {m:02d} Min. {s:02d} Sek."

        # Spinner-Zeichen wechseln
        spin_char = spinner[spin_idx % len(spinner)]
        spin_idx += 1

        # Eine Zeile, die sich selbst überschreibt
        sys.stdout.write(f"\rVerbleibend: {time_str}   {spin_char}                ")
        sys.stdout.flush()

        time.sleep(1)
    log_event("INFO", f"=== Beende Survey-In nach {duration//3600} Std. {(duration%3600)//60} Min. {duration%60} Sek. ===")
    print("")


def rx_thread(ser):
    """Liest dauerhaft vom GNSS-Modul und legt Zeilen in die Queue"""
    buffer = b""
    while not stop_flag:
        try:

            if survey:
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                        continue
                if line.startswith("$PAIR"):
                    log_event("PAIR", line)
                    if not line.startswith("$PAIR010"):
                        print(f"[PAIR] {line}")  # Status alle 30s


                elif line.startswith("$PQTMCFGSVIN"):
                    print(f"[RX] {line}")   # Survey status oder Ergebnis
                    log_event("RX", line)


            else:
                if ser.in_waiting:
                    data = ser.read(ser.in_waiting)
                    buffer += data
                    # Zeilenweise splitten
                    while b"\r\n" in buffer:
                        line, buffer = buffer.split(b"\r\n", 1)
                        line = line.decode(errors="ignore").strip()
                        if line:
                            clean_line = line[line.find('$'):]
                            rx_queue.put(clean_line)  # in Queue speichern
                            #print(f"[DEBUG] Queue size: {rx_queue.qsize()}")
                        '''
                        if line:
                            rx_queue.put(line)  # in Queue speichern
                            #print(f"[DEBUG] Queue size: {rx_queue.qsize()}")
                        '''
                else:
                    time.sleep(0.05)



        except Exception as e:
            print(f"[RX-Thread Fehler] {e}")
            log_event("ERROR",f"[RX-Thread Fehler] {e}")
            time.sleep(0.2)


def send_command(ser, cmd, expected=None, timeout=5):
    """
    Sendet Befehl, wartet auf erwartete Antwort in Queue.
    expected=None -> keine Prüfung
    """
    full_cmd = f"${calc_checksum(cmd)}"
    ser.write((full_cmd + "\r\n").encode())
    print(f"[TX] {full_cmd}")
    log_event("TX",full_cmd)

    start = time.time()
    responses = []
    while time.time() - start < timeout:
        try:
            line = rx_queue.get(timeout=0.5)
            responses.append(line)

            if expected and expected in line:
                # Suche nach erstem '$' – egal ob $P, $p, ...
                if '$P' in line:
                    clean_line = line[line.find('$P'):]
                else:
                    clean_line = line
                print(f"[RX] {clean_line.strip()}")
                log_event("RX",clean_line.strip())
                return clean_line.strip()


            '''
            if expected and expected in line:
                print(f"[RX] {line}")
                log_event("RX",line)
                return line
            elif not expected:
                print(f"[RX] {line}")
                log_event("RX",line)
                return line
            '''
        except queue.Empty:
            pass

    print(f"Timeout: Keine Antwort auf {full_cmd}")
    log_event("ERROR",f" Timeout: Keine Antwort auf {full_cmd}")
    if responses:
        print(f"Letzte RX-Zeilen: {responses[-3:]}")
    return None


def _exit(ser):
    """Schließt seriellen Port und beendet"""
    global stop_flag
    stop_flag = True
    time.sleep(0.2)
    ser.close()
    sys.exit(1)


# --- Beispiel für Hauptablauf ---
if __name__ == "__main__":
    survey=False
    survey_minutes = 0        # 0 bedeutet: nur Status anzeigen
    save_to_flash = False     # optionaler zweiter Parameter 's'

    # --- Argumente prüfen ---
    if len(sys.argv) > 1:
        try:
            survey_minutes = int(sys.argv[1])
        except ValueError:
            print("Ungültiger Parameter: Bitte Zahl in Minuten angeben, z.B. 'python LC29HBC.py 120' oder 'python LC29HBC.py 120 s'")
            sys.exit(1)

    if len(sys.argv) > 2 and sys.argv[2].lower() == 's':
        save_to_flash = True

    # --- Sekunden berechnen ---
    survey_seconds = survey_minutes * 60
    LOGFILE = init_logfile()
    ser = serial.Serial("/dev/ttyUSB0", baudrate=115200, timeout=0.1)
    threading.Thread(target=rx_thread, args=(ser,), daemon=True).start()

    # Action 1: Parameter Restore
    send_command(ser, "PQTMRESTOREPAR", expected="PQTMRESTOREPAR,OK")
    time.sleep(2)

    # Action 2: Firmware-Version
    send_command(ser, "PQTMVERNO", expected="PQTMVERNO")
    time.sleep(1)

    # Action 3: Status-rüfen Fix oder Survey

    send_command(ser, "PQTMCFGSVIN,R", "PQTMCFGSVIN,OK")
    time.sleep(2)

    # Action 4: Survey starten
    if survey_minutes >0:
        if not send_command(ser, f"PQTMCFGSVIN,W,1,{survey_seconds},15.0,0,0,0", "PQTMCFGSVIN,OK"):
            log_event("ERROR","Kritischer Fehler beim Starten des Surveys")
            _exit(ser)
        survey=True
        duration = survey_seconds + 10
        run_survey(duration)

        survey=False
        # Action 5: Nach Ablauf prüfen
        rx= send_command(ser, "PQTMCFGSVIN,R", "PQTMCFGSVIN,OK")
        if "PQTMCFGSVIN,OK,1" in rx:
            # Erst alles vor dem '*' nehmen
            clean = rx.split('*')[0]
            parts = clean.split(',')

            try:
                x, y, z = map(float, parts[5:8])  # ab Index 5 sind die ECEF-Koordinaten
                duration = int(float(parts[3]))
                acc_limit = float(parts[4])
                print("Survey abgeschlossen oder Status abgefragt.")
                log_survey_result(x, y, z, duration, acc_limit)
                if save_to_flash == False:
                    log_event("INFO", "Survey-In Prozess abgeschlossen aber ohne speichern")
                print(f"ECEF: X={x}, Y={y}, Z={z}")
            except Exception as e:
                print(f"Fehler beim Parsen der ECEF-Werte: {e}")
                print(f"Debug parts: {parts}")
            # Action 6: Wenn Paramter s gesetzt in Flash speichern
            if save_to_flash ==True:
                log_event("INFO", "Survey Daten sollen im LC29HBS gespeichert werden!")
                if not send_command(ser, f"PQTMCFGSVIN,W,2,0,0,{x},{y},{z}","PQTMCFGSVIN,OK"):
                    log_event("ERROR", "Survey Daten konnten nicht gespeichert werden")
                    print("Schreiben fehlgeschlagen")
                    _exit(ser)
                else:
                    # Action 7: prüfen ob alles richtige abgeschlossen wurde
                    log_event("INFO", "Survey Daten wurden erfolgreich gespeichert!")
                    print("Survey Daten wurden erfolgreich gespeichert!")
                    time.sleep(2)
                    if not send_command(ser, "PQTMCFGSVIN,R", "PQTMCFGSVIN,OK"):
                        print("Prüfung fehlgeschlagen")
                        log_event("ERROR", "Letze Prüfung fehlgeschlagen!")
                        _exit(ser)
                    else:
                        time.sleep(0.5)
                        log_event("INFO", "Survey-In Prozess abgeschlossen")
                        print("Survey-In Prozess beendet!")



    _exit(ser)


