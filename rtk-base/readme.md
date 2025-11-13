# RTK-Basis Station #
Derzeit läuft bei mir auf einem separatem Pi3 meine
RTK-Basistation.  <img width="644" height="387" alt="grafik" src="https://github.com/user-attachments/assets/7ae4045c-73e9-4843-bda6-79f63c3a1528" />

Diese habe ich mit einem LC29H(BS) von Quectel und einer  
YB0017AA Antenne installiert und an einem festen Standort mit freier Sicht zum Himmel
montiert. Mein Pi erkennt die Basistation an der Schnittstelle /dev/ttyUSB0
Zur Inbetriebnahme der Baisistation benötigst Du zwei python scripts. Als erstes muss die Basisstation wissen an welchem Punkt sie steht, damit sie diese
als Referenzdaten zu dem Rover schicken kann. Wenn Antenne und Platine über das USB Kabel mit dem Pi verbunden ist, dann rufst Du mit *python LC29HBS.py* auf.
<img align="right" width="500" alt="grafik" src="https://github.com/user-attachments/assets/cdfd1264-23b8-4494-8cd8-2ac26fcbc744" />

Klappt alles, so gibt Dir das Modul
folgendes aus, was auf dem Screenshot zu
sehen ist.



Der erste TX Befehl setzt das Modul auf Werksauslieferung zurück. Der zweite TX Befehl fragt den
Firmwarestand ab und der dritte TX Befehl fragt ab, ob es sich das Modul im Survey-IN prozess
befindet oder im normalen Betriebs Modus arbeitet. Hier ist es der normale Modus wie er für die
Basisstation notwendig ist. Das erkennst Du an der 2 hinter dem OK in der letzten Zeile. Ich
empfehle auch die Lektüre des [**Datenblattes.**](https://files.waveshare.com/wiki/LC29H(XX)-GPS-RTK-HAT/Quectel_LC29H(BS)_GNSS_Protocol_Specification_V1.0.pdf)
Den Link habe ich aus dem [**Waveshare Wiki**](https://www.waveshare.com/wiki/LC29H(XX)_GPS/RTK_HAT) zu den
LC29H Pi Erweiterungen. Auch sehr interessant, wenn man näheres Wissen möchte.

Nun hast Du 2 Möglichkeiten der Basisstation mitzuteilen wo sie sich befindet, damit sie die Korrekturdaten passend zu ihrer Position an den Rover senden kann.
## Positionierung der Baisstation über Lat und Lon ##

Wenn Du die exakte Lat & Lon Werte und die Höhe Deiner Antenne kennst, so kannst Du
Lat & Lon mit *convert.py* in ECEF Werte umwandeln.

<img align="right" width="300" alt="grafik" src="https://github.com/user-attachments/assets/97d6d8fd-7967-452a-bf95-41058c6089d2" />

Editiere in der  *convert.py*  die Zeilen 22, 23 und 24 mit den Dir
bekannten Werten. Du kannst diese u.U. mit Google-Maps oder anderen Karten-Tools bestimmen.

Hast Du LAT LON und auch **wichtig** die Höhe der Antenne eingetragen, dann rufts Du python  *convert.py LAT*  auf und erhältst folgende Ausgabe. 

<p align="left">
<img width="400" alt="grafik" src="https://github.com/user-attachments/assets/7a09b75c-8262-4548-ac5d-71466cfce9bc" />
</p>
Diese Werte trägst Du dann in der  *rtk_basis.py*  in den Zeilen 67, 68 und 69 ein.

Danach kannst Du mit python  *rtk_basis.py*  Deine Basisstation in Betrieb nehmen. In der Konsole werden Dir nun fortlaufend die RTCM Sätze angezeigt, welche
die Basisstation zur Verfügung stellt. 
<p align="center">
<img width="420" alt="grafik" src="https://github.com/user-attachments/assets/ac25e625-49e5-44b3-ae70-b171e906b835" />
</p>
Rufts Du nun in Deinem Mäher die *rtk_rover.py* auf, und beide Rechner liegen im selben Netzwerk, so wirst Du eine Info in der Konsole der Basisstation sehen, dass sich ein Client verbunden hat. Nach kurzer Zeit, wird sich in der Konsole vom rtk_rover ein RTK-Float einstellen, und je nach Netzwerkverbindung und Sichtverhältnissen nach kurzer Zeit ein RTK-Fix. Sollte es einmal mehr als 5 Minuten dauern, nicht die Geduld verlieren. Er wird sich schon einstellen.

## Positionierung der Baisstation über Survey-In Prozess ##

Eine andere Möglichkeit die Basisstation auf den exakten GeoPosition einzustellen kannst Du mit
dem Survey-In Prozess realisieren. Wichtig ist, dass Du die Antenne für die Basisstation schon
fixiert hast und sie vielleicht auch schon an dem finalen Standort montiert hast. Mit dem python
script  *LC29HBS.py 300 s*  rufts Du einen Survey-In Prozess von 300 Minuten Dauer auf, also von 5 Std.
Je länger der Prozess läuft, umso exakter hat das Modul selbst am Schluss des Prozesses seine
Position errechnet. Ist je nach eingegebener Zeitspanne der Prozess beendet, denn hat das Scipt im Logfile die
ECEF_X, ECEF_Y und ECEF_Z Werte ermittel, die Du dann mit Copy& Paste wieder in die
*rtk_basis.py* in die Zeilen 67 – 69 einfügen kannst.

<img width="856" height="312" alt="grafik" src="https://github.com/user-attachments/assets/b84dea57-09cf-4e3b-9d4d-2c7c3db1f52d" />

Wichtig ist das s in dem script Aufruf, Es bewirkt, dass am Ende die Daten im Flash des LC29HBS
gespeichert werden. 

**Ich empfehle dieses Script direkt auf dem Pi aufzurufen, denn solltest Du es über ssh aufrufen und die Verbindung bricht nach einigen Stunden ab, weil sich Dein Rechner schlafen legt, dann bricht auch der Survey-In Prozess auf dem Pi ab.**

Beide Methoden habe ich bei meiner Basistation ausgetestet und kann sagen, dass der Survey-In Prozess genauere Daten ermittelt.

**Viel Erfolg bei der Inbetriebnahme Deiner GPS-RTK Lösung**
