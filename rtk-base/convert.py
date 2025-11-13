import math
import sys


#      Dieses sind Daten von Berlin Alexanderplatz
#      Deine Daten zur Umrechnung musst Du selber
#      hier eingeben, je nachdem in welche Richtung
#      Du umwandeln willst
#      Die Richtung bestimmst Du mit den Parameterm
#      python convert.py LAT
#      Damit werden LAT LON und ALT in ECEF Werte gewandelt
#      python convert.py ECEF
#      Damit werden ECEF Werte in LAT LON Werte gewandelt
#
#      Die hier angegebenen Daten sind vom Place Berlin Alexanderplatz


ECEF_X = 3784034.4618
ECEF_Y = 899874.5653
ECEF_Z = 5037987.4823

LAT =  52.516181
LON =  13.376935
ALT =  34

def ecef_to_geodetic(x, y, z):
    """ECEF → WGS84 (Latitude, Longitude, Altitude)"""
    print("Convert ECEF 2 LAT LON Values")
    a = 6378137.0
    e2 = 6.69437999014e-3

    lon = math.atan2(y, x)
    p = math.sqrt(x**2 + y**2)
    lat = math.atan2(z, p * (1 - e2))
    for _ in range(5):
        N = a / math.sqrt(1 - e2 * math.sin(lat)**2)
        lat = math.atan2(z + e2 * N * math.sin(lat), p)
    alt = p / math.cos(lat) - N

    print(f"LAT: {round(math.degrees(lat),6)}")
    print(f"LON: {round(math.degrees(lon),6)}")
    print(f"ALT: {round(alt,0)}")



def calc_x_y_z(lat_deg, lon_deg, alt_m):
    print("Convert LAT LON 2 ECEF Values")


    # WGS-84 Konstanten
    a = 6378137.0          # Äquatorradius
    e2 = 6.69437999014e-3  # Exzentrizität²

    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    N = a / math.sqrt(1 - e2 * math.sin(lat)**2)

    x = (N + alt_m) * math.cos(lat) * math.cos(lon)
    y = (N + alt_m) * math.cos(lat) * math.sin(lon)
    z = ((1 - e2) * N + alt_m) * math.sin(lat)
    print(f"ECEF_X: {round(x,4)}")
    print(f"ECEF_Y: {round(y,4)}")
    print(f"ECEF_Z: {round(z,4)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Keinen passenden Paramter übergeben")
        print("Aufruf erfolgt mit convert.py LAT oder mit convert.py ECEF")
    elif "LAT" in sys.argv:
       calc_x_y_z(LAT, LON, ALT)
    elif "ECEF" in sys.argv:
        ecef_to_geodetic(ECEF_X, ECEF_Y, ECEF_Z)
    else:
        print("Keinen passenden Paramter übergeben")
        print("Aufruf erfolgt mit convert.py LAT oder mit convert.py ECEF")
