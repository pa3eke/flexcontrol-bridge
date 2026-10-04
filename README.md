# PA3EKE FlexControl → Thetis

Desktop-app voor Windows en macOS. De FlexControl zit via USB aan de computer met deze app; Thetis wordt via TCI over het netwerk bediend. Geen virtuele CAT-poort nodig. Bediening van RX1 / VFO A.

## Gebruik

1. Zet de **TCI-server** aan in Thetis. Controleer het ingestelde adres en de poort.
2. Pak het zipbestand uit. Open **FlexControl-Thetis.app** (Mac) of **FlexControl-Thetis.exe** in de map FlexControl-Thetis (Windows). Bewaar de Mac-app bij voorkeur in Programma’s, buiten een gesynchroniseerde cloudmap.
3. Op dezelfde computer: `ws://127.0.0.1:40001`, als Thetis op poort 40001 luistert. Op een Mac met Thetis op een Windows-pc: `ws://IP-VAN-WINDOWS-PC:40001`. Laat de TCI-server luisteren op het LAN-adres of `0.0.0.0` en sta die poort toe in de Windows-firewall voor je lokale netwerk.
4. De USB-poort wordt automatisch gevonden. Kies zo nodig de poort handmatig. Klik **Verbinden**. Instellingen worden onthouden; de volgende keer verbindt de app bij openen automatisch.

| Bediening | Functie |
| --- | --- |
| Draaien | Frequentie omhoog/omlaag met de gekozen stap; snelle draaipulsen behouden de FlexControl-vermenigvuldiger |
| Eerste korte druk op draaiknop | 100 Hz |
| Tweede korte druk | 250 Hz |
| Derde korte druk | 1.000 Hz, frequentie afgerond naar dichtstbijzijnde kHz |
| Volgende druk | Terug naar 100 Hz; reeks herhaalt |
| AUX1 kort indrukken | PTT aan/uit per druk |
| AUX3 kort indrukken | Afstemmen via FlexControl vergrendelen/vrijgeven |
| PTT uit in venster | Zenden uitschakelen |

Bijvoorbeeld: 14.200.650 Hz wordt bij de 1 kHz-stap 14.201.000 Hz. Halve kHz wordt omhoog afgerond. Tijdens vergrendeling worden draaipulsen en de afronding genegeerd; de stap mag wel veranderen. Dit is een vergrendeling van deze controller: bediening in Thetis zelf blijft mogelijk. AUX2 is niet toegewezen. Gebruik afzonderlijke korte drukken; de firmware stuurt andere berichten voor snelle dubbelklikken en lang indrukken, die de app negeert.

De app volgt frequentiewijzigingen en PTT-status uit Thetis. Afstemmen en PTT zijn pas actief na ontvangst van de werkelijke frequentie. Na USB- of TCI-uitval probeert de app opnieuw te verbinden; opgeslagen draaipulsen worden niet later opnieuw uitgevoerd. Bij USB-uitval en normaal afsluiten wordt door deze app gestarte PTT vrijgegeven. Bij netwerkuitval kan dat commando pas na herverbinding worden verstuurd; ontvangen blijft de standaard bij herstel van eigen PTT, zenden wordt niet automatisch hervat.

## Vanuit broncode

Python 3.10+ met Qt/PySide6-ondersteuning (met de huidige PySide6 op Mac: macOS 13+):

```sh
python -m pip install .
python launcher.py
```

Of start de geïnstalleerde app met `flexcontrol-thetis`. Zonder venster: `python -m pa3eke_flexcontrol_bridge.terminal --tci ws://127.0.0.1:40001`.

## Desktop-app bouwen

Op Windows kun je na installatie van Python 3.12 (64-bit, met Python Launcher) dubbelklikken op **build-windows.cmd**. Dit installeert de bouwpakketten in een eigen omgeving, voert de tests uit en maakt **dist/FlexControl-Thetis-Windows.zip**. Zie [WINDOWS.md](WINDOWS.md) voor de stappen.

```sh
python -m pip install '.[build]'
python scripts/build_app.py
```

Bouw op het doelplatform: een Windows-exe op Windows, een Mac-app op macOS. De Python- en Qt-runtime zitten in de app; gebruikers hoeven Python niet te installeren. Bewaar op Windows de volledige uitvoermap bij elkaar. De GitHub Actions-workflow bouwt beide platforms bij handmatig starten of een `v*`-tag. Dit project is momenteel een lokale map; de workflow draait pas wanneer je het in een GitHub-repository zet. Mac-builds zijn niet met een Apple Developer-certificaat ondertekend of genotariseerd; openbare distributie vraagt een aparte ondertekenstap. De macos-14 workflow bouwt voor Apple Silicon; bouw op een Intel-Mac voor Intel.

Tests: `python -m unittest discover -s tests -v`.

## Protocolbronnen

De gebruikte TCI-commando's zijn `vfo:0,0,<Hz>;`, de query `vfo:0,0;` en `trx:0,true/false;`, overeenkomstig [Thetis TCIServer.cs](https://github.com/ramdor/Thetis/blob/master/Project%20Files/Source/Console/TCIServer.cs). FlexControl-berichten: `U;`, `D;`, `U02;`, `S;`, `X1S;` en `X3S;`. Alleen apparaten met de FlexControl USB-identiteit/naam worden automatisch geselecteerd; andere USB-seriële apparaten worden niet geopend om te zoeken.

## Validatie van deze versie

21 geautomatiseerde tests geslaagd: knopbediening, 100/250/1.000 Hz, afronding, PTT-vrijgave, USB-berichten in delen, statusvolging, instellingen, venster en een echte lokale WebSocket-handshake. De Mac-build is voor Apple Silicon en de uitgepakte bundel heeft een gecontroleerde ad-hoc-handtekening. De venstertest op deze Mac gebruikte de verpakte Qt-bibliotheken omdat Qt de plugins in de gesynchroniseerde bronmap niet kon lezen. Windows-build en fysieke FlexControl/Thetis-bediening zijn nog niet op hardware getest.
