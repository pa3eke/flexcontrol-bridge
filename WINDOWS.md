# Windows-app bouwen en starten

Dit pakket bevat broncode en een bouwscript. De Windows-exe moet op een Windows-pc worden gebouwd.

1. Installeer Python 3.12 voor Windows, **64-bit**, inclusief de **Python Launcher**: https://www.python.org/downloads/windows/
2. Klik met rechts op het zipbestand en kies **Alles uitpakken**. Open daarna de uitgepakte map **pa3eke_flexcontrol_bridge**. Start het script niet vanuit het geopende zipbestand: Windows pakt dan alleen het script tijdelijk uit en de bouw mislukt.
3. Dubbelklik op **build-windows.cmd**. Internet is nodig om de bouwpakketten te downloaden. Het script installeert de benodigde pakketten in een eigen omgeving, voert de tests uit en bouwt de app.
4. Na een geslaagde bouw opent de uitvoermap. Dubbelklik op **FlexControl-Thetis.exe**.

De deelbare app staat in **dist/FlexControl-Thetis-Windows.zip**. Pak die volledig uit op de Windows-pc waar je de app wilt gebruiken. Bewaar de exe en de map **_internal** bij elkaar. Voor de gebouwde app is geen Python-installatie nodig.

## Verbinden met Thetis

1. Sluit de FlexControl via USB aan.
2. Zet de TCI-server aan in Thetis.
3. Gebruik **ws://127.0.0.1:40001** als Thetis op dezelfde pc draait en poort 40001 gebruikt. Vul anders het IP-adres en de ingestelde TCI-poort van de Thetis-pc in.
4. Kies indien nodig de COM-poort en klik op **Verbinden**.

De daadwerkelijke Windows-bouw en hardwarebediening zijn nog niet op Windows gecontroleerd.
