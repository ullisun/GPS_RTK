# RTK-Rover

Mein Testaufbau ist derzeit folgender:
Pi3 mit dem script rtk_rover.py steht im Gartenhaus.
Wichtig ist, dass er im WLAN erreichbar ist. Das ist
später auch für den Mäher Voraussetzung, da er sonst
keine Korrekturdaten erhalten kann.

<img align="right" width="250" alt="grafik" src="https://github.com/user-attachments/assets/c5724c91-5fae-40af-a0f2-fff6e25039ea" />


Die GPS Antenne YB0017AA liegt im Moment auf dem
Dach des Gartenhauses und ist stationär. Über einen
Serial => USB Adapter habe ich das Quectel- GPS
Modul LC29H(DA) an den Pi 3 angeschlossen. Das
Modul wird bei mir auf /dev/ttyUSB0 erkannt.

Im ersten Schritt betreibe ich das Modul über meinen SAPOS Account und dazu reicht auf dem Pi
dann der Aufruf des scriptes ohne weiteren Parameter, also **python rtk_rover.py**  . Sollte später die RTK-Basisstation die
Korrekturdaten liefern, so wird das Script mit **python rtk_rover.py -b** aufgerufen (b für Basis).
Damit der SAPOS Dienst genutzt werden kann sind im python script die entsprechenden Parameter
zu setzen. Diese habe ich aus dem Informationsmaterial herausgezogen, das mir die SAPOS NRW
zur Verfügung gestellt hat. Das kann bei Dir natürlich anders sein, und muss ggf. angepasst werden.

 #=== Konfiguration ===<br>
 SERIAL_PORT = "/dev/ttyUSB0"<br>
 BAUDRATE = 115200<br>
 NTRIP_SERVER = "80.158.61.104"<br>
 NTRIP_PORT = 2101<br>
 NTRIP_MOUNTPOINT = "VRS_3_3G_NW" # Quelle SAPOS NRW<br>
 NTRIP_USER = "myuser"            #Quelle SAPOS NRW<br>
 NTRIP_PASS = "mypwd"             #Quelle SAPOS NRW<br>
 <br>
 
("VRS_3_3G_NW" ist der Mountpoint der GPS Glonass und Galileo Korrekturdaten mit einer
Genauigleit von 1 – 2 cm bereitstellt.
Also Script Konfiguration ggf. anpassen und dann mit python rtk_rover.py starten.
Die Ausgabe sieht derzeit so aus.
<p align="center">
<img width="800" alt="grafik" src="https://github.com/user-attachments/assets/26064764-6db6-40b9-bac6-ee6aa14b579d" />
</p>

Die für die SW erforderlichen Daten werden in zwei logFiles gespeichert.
Für die *mower.py* werden jetzt schon sekündlich die Geo Daten nach */dev/shm/rtk_point.json*
geschrieben. Diese sollen später sekündlich ausgewertet und wirken sich auf die Automatisierung
aus.
Der Inhalt der */dev/shm/rtk_point.json* ist:
{"time": "16:37:22.259", "lat": 52.1267968, "lon": 8.663306716666666, "fix": "RTK-Fixed", "sats":
"36", "speed": 0.0, "heading": 0.0}
Durch lat und lon sollen später die aktuelle Position während der Fahrt zum programmierten Ziel
verglichen werden und ggf. Korrekturen eingeleitet werden heading und speed sind Kontrollwerte
während der Fahrt zu den bestehenden Sensoren. Diese Funktion ist noch nicht implementiert /
getestet.

Das zweite logFile steht im täglichen log Verzeichnis. 
<img align="right" width="234" height="262" alt="grafik" src="https://github.com/user-attachments/assets/5d02e319-5117-4594-8035-0559ed96f8fa" />

Der Pfad muss
später dann noch angepasst werden. In dem täglichem log
Verzeichnis findet man dann für den rtk_rover 2 logFiles. Für uns ist im
Moment das <uhrzeit>_rtk_points.json wichtig. In diesem logFile
stehen die aktuellen GPS Daten seit dem Start von rtk_rover.py
Und genau dieses logFile kann man mit dem Durchsuchen Button der
Analyse.html Seite selektieren und laden.
Mit dem Slider unterhalb der Map kann nun durch die Datei navigiert
werden. Mit dem Play Button rechts neben dem Slider kann läuft eine
Art Wiedergabe des logFiles.
Wie schon weiter oben beschrieben, wird dieses Logfile später durch weitere Informationen ergänzt
und auf der Map in der Html Seite dann angezeigt. Dieses ist für eine nachträgliche Analyse des
Mähvorganges nützlich.

**Alle Informationen zu der Basisstation findest Du in dem [rtk-base](https://github.com/ullisun/GPS_RTK/tree/main/rtk-base) Ordner**

