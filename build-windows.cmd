@echo off
setlocal
cd /d "%~dp0"
echo FlexControl-Thetis voor Windows bouwen
echo.
if not exist "pyproject.toml" goto not_extracted
if not exist "launcher.py" goto not_extracted
if not exist "scripts\build_app.py" goto not_extracted
py -3.12 -c "import sys; assert sys.platform == 'win32'; assert sys.maxsize > 2**32" >nul 2>&1
if errorlevel 1 goto missing_python
if not exist ".venv-windows\Scripts\python.exe" (
    py -3.12 -m venv .venv-windows
    if errorlevel 1 goto failed
)
".venv-windows\Scripts\python.exe" -m pip install ".[build]"
if errorlevel 1 goto failed
".venv-windows\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto failed
".venv-windows\Scripts\python.exe" scripts\build_app.py
if errorlevel 1 goto failed
echo.
echo Klaar! Open dist\FlexControl-Thetis\FlexControl-Thetis.exe
echo Om te delen: dist\FlexControl-Thetis-Windows.zip
explorer "%~dp0dist\FlexControl-Thetis"
pause
exit /b 0

:not_extracted
echo De projectbestanden ontbreken. Start dit script niet vanuit het zipbestand.
echo Klik met rechts op het zipbestand en kies Alles uitpakken.
echo Open daarna de uitgepakte map pa3eke_flexcontrol_bridge.
echo Dubbelklik daar op build-windows.cmd.
pause
exit /b 1

:missing_python
echo Installeer eerst Python 3.12 voor Windows, 64-bit, met de Python Launcher.
echo Download: https://www.python.org/downloads/windows/
echo Start daarna dit bestand opnieuw. Internet is nodig voor de bouwpakketten.
pause
exit /b 1

:failed
echo.
echo Bouwen mislukt. Bekijk de foutmelding hierboven.
pause
exit /b 1
