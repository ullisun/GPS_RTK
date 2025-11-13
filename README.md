# GPS_RTK
Solution with LC29H(DA) and LC29H(BS) or SAPOS Service as NTRIP Client
## Webseite vorbereiten
Kompletten-. GPS mit Unterordnern in ein Verzeichnis auf dem Rechner kopieren, worauf ein
Webbrowser vom Rechner Zugriff hat. Das kann auf dem Pi sein, muss aber nicht. Zur späteren
Analyse empfehle ich das nicht auf dem Pi zu installieren.
### Anpassen der Html Vorlage
Aus Google-Maps das passende Bild für den Hintergrund der Karte herausschneiden und als
karte.png im Order GPS/pngs ablegen.
Am besten die gleiche Größe wie im html File 600x1024 verwenden, ist aber nicht zwingend
erforderlich. Dann mit Hilfe von Google-Maps die Geodaten von der oberen Bildecke Links
bestimmen in diesem Fall ist das Lat 53.32652 Lon 10.36567 danach die untere Bildecke rechts
bestimmen. Hier ist es Lat 53.32626 Lon 10.36677
Nun im Quellcode der *Analyse.html* diese Daten in Zeile 109 und Zeile 110 eintragen.
Beim Laden der Analyse.html sollte nun ein Bild ähnlich diesem im Browser erscheinen.
<p align="center">
<img width="1700" alt="grafik" src="https://github.com/user-attachments/assets/7647ee6d-d07a-41f6-a9bc-beec82029ea9" />
</p>
An dieser Stelle erkläre ich noch kurz wie man den Rasen in das Bild einfügen kann, die Richtigen
Koordinaten dazu kann aber später der Mähroboter, oder eine Vermessung mit dem GPS-RTK
Empfänger liefern. Die Eckpunkte werden im Uhrzeigersinn aufgenommen und starten oben Links.
Nehmen wir an, die Eckpunkte vom Rasen liegen bei 53.32634, 10.36597 / 53.32637, 10.36615 / 
53.32632, 10.36618 / 53.32628, 10.36600 dann geben wir genau diese Daten in die Datei
*GPS/rasen/rasen.json* ein. Achtung es ist eine json Datei so sollte dann so aussehen.

[
<br>[53.32634, 10.36597],<br>[53.32637, 10.36615],<br>[53.32632, 10.36618],<br>[53.32628, 10.36600]<br>
]

Später kann durch Vermessung mit dem rtk_rover.py die einzelnen Punkte genau bestimmt werden
und das polygon in der Karte aktualisiert werden.
Nun sollte die Karte im html Bild in etwa so aussehen.
<p align="center">
<img width="1000" alt="grafik" src="https://github.com/user-attachments/assets/c7bb7e14-ce5f-4a27-b631-285714d2113a" />
</p>

Die Bedienung der Seite ist intuitiv. 
Später ist gedacht, dass die *mower.py* in meinem [**RopiLawnMow**](https://github.com/ullisun/RopiLawnMow) ein logfile von dem
Mähvorgang erstellt. Dieses logFile kann dann durch den Auswahlbutton selektiert und geladen
werden. Jeder Eintrag in in dem logFile liefert einen Datenpunkt auf der Karte. Neben den
Geodaten habe ich geplant events zu protokollieren. Events wären dann z.B. Stops die ausgelöst
werden und den Mäher zum Ausweichen bringen. So könnten events ausgelöst werden von
„Perimeter“, „Bumper“, „Kamera“, „GPS“ oder vom „ToF“. Für jedes dieser events ist ein Icon im
Ordner GPS/pngs hinterlegt. Zusätzlich gibt es noch für „Start“ und „Ziel“ ein entsprechendes Icon.
Daher ist der Datensatz der jetzt schon eingelesen wird entsprechend komplexer, als im Moment
erforderlich.
{"time": "11:37:13.347", "lat": 52.12679645, "lon": 8.663306383333333, "fix": "RTK-Fixed",
"sats": "39", "speed": "0.01", "heading": 51.54, "delta": "1.15", "event": "", "image": ""},
Im Moment geht es derzeit erst einmal um die Grundfunktion der rtk_rover.py auf dem Mäher
sicherzustellen. Dazu ist die Analyse.html schon ein hilfreiches Tool.

**Die inbetriebnahme des rovers findest Du im Ordner Rover beschrieben** 


