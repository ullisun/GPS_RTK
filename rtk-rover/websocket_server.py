#!/usr/bin/env python3
import asyncio
import json
import websockets
import datetime


# Liste aller verbundenen Clients
connected_clients = set()

# Beispiel: Funktion die die aktuellen Daten aus deiner Datei liest
# -> später kannst du das durch direkten Zugriff auf Variablen ersetzen
def read_robot_status():
    try:
        with open("/dev/shm/rtk_point.json", "r") as f:
            data = json.load(f)
        return data
    except:
        return {
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "lat": 0,
            "lon": 0,
            "fix": "none",
            "sats": 0,
            "speed": 0,
            "heading": 0
        }

# Handler wenn sich ein neuer Client verbindet
async def client_handler(websocket, path):
    print("Client connected:", websocket.remote_address)
    # erstes empfangenes Paket bestimmt den Client-Typ
    hello = await websocket.recv()
    info = json.loads(hello)
    try:
        print(info.get("client"))
        if info.get("client") == "analyzer":
            print("Analyzer connected → sending session data")

            # rtk_session.json schicken
            await send_rtk_session(websocket)

        # danach normal weiter → Live-Daten streamen

        # Endlosschleife: jede Sekunde Daten senden
        while True:
            #print("Hallo")
            data = read_robot_status()
            #msg = json.dumps(data)
            msg = data

            # Nachricht an *diesen Client* senden
            await websocket.send(json.dumps({
            "type": "gps",
            "data": msg
            }))


            #await websocket.send(msg)

            # Optional: falls später Kommunikation vom Client nötig ist
            # (z.B. Start/Stop, Kommandos etc.)
            await asyncio.sleep(1)

    except websockets.exceptions.ConnectionClosed:
        print(f"[{datetime.datetime.now()}] Client getrennt: {websocket.remote_address}")

    finally:
        connected_clients.discard(websocket)
        print(f"[{datetime.datetime.now}] Client getrennt: {websocket.remote_address}")



    #await stream_live_data(websocket)

async def send_rtk_session(websocket):
    try:
        with open("/dev/shm/rtk_session.json", "r") as f:
            raw = f.read().strip()


        # "," entfernen und "]" anhängen
        if raw.endswith(","):
            raw=raw[:-1]
            raw = raw + "]"
        # ggf fehlendes "]" ergänzen
        if not raw.endswith("]"):
            raw = raw + "]"

        # JSON validieren
        arr = json.loads(raw)

        await websocket.send(json.dumps({
            "type": "session",
            "data": arr
        }))

    except Exception as e:
        print("Could not send session:", e)



async def __client_handler(websocket, path):
    # Client eintragen
    connected_clients.add(websocket)
    print(f"[{datetime.datetime.now()}] Client verbunden: {websocket.remote_address}")

    try:
        # Endlosschleife: jede Sekunde Daten senden
        while True:
            data = read_robot_status()
            msg = json.dumps(data)

            # Nachricht an *diesen Client* senden
            await websocket.send(msg)

            # Optional: falls später Kommunikation vom Client nötig ist
            # (z.B. Start/Stop, Kommandos etc.)
            await asyncio.sleep(1)

    except websockets.exceptions.ConnectionClosed:
        print(f"[{datetime.datetime.now()}] Client getrennt: {websocket.remote_address}")

    finally:
        connected_clients.remove(websocket)

# Server starten
async def main():
    # 0.0.0.0 = lauscht auf allen Interfaces (LAN, WLAN)
    async with websockets.serve(client_handler, "0.0.0.0", 8765):
        print("WebSocket-Server läuft auf Port 8765...")
        await asyncio.Future()  # läuft unbegrenzt

if __name__ == "__main__":
    asyncio.run(main())
