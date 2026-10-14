@echo off
setlocal EnableExtensions
title SkadiTerminal - Voraussetzungen installieren
REM ==================================================================
REM  Installiert alles, was SkadiTerminal zum Bauen braucht:
REM    1. Python 3.12 (ueber winget, nur fuer diesen Benutzer, kein Admin noetig)
REM    2. Alle Python-Pakete (pyautogui, opencv, mss, pynput, ...)
REM  Danach kann direkt Aktualisieren.bat laufen.
REM  Einfach doppelklicken. Mehrfach ausfuehren schadet nicht.
REM ==================================================================

echo.
echo  [1/3] Python suchen ...
call :findpy
if not defined PY goto :installieren
echo        gefunden: %PY%
goto :pakete

:installieren

echo        nicht gefunden - installiere Python 3.12 ...
where winget >nul 2>nul
if errorlevel 1 (
  echo.
  echo  FEHLER: winget fehlt ^(App-Installer aus dem Microsoft Store^).
  echo  Python bitte von Hand installieren: https://www.python.org/downloads/
  echo  Wichtig: beim Installieren den Haken bei "Add python.exe to PATH" setzen.
  goto :fehler
)
winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
call :findpy
if not defined PY (
  echo.
  echo  FEHLER: Python wurde installiert, aber nicht gefunden.
  echo  Bitte dieses Fenster schliessen und Einrichten.bat noch einmal starten.
  goto :fehler
)
echo        installiert: %PY%

:pakete
echo.
echo  [2/3] pip aktualisieren ...
"%PY%" -m pip install --quiet --upgrade pip || goto :fehler

echo  [3/3] Pakete installieren ^(dauert 1-2 Minuten^) ...
"%PY%" -m pip install --upgrade pyautogui pillow psutil pynput opencv-python numpy mss pyinstaller || goto :fehler

echo.
echo  FERTIG - alle Voraussetzungen sind installiert.
echo.
if exist "%~dp0Aktualisieren.bat" (
  choice /c JN /m " Jetzt gleich Aktualisieren.bat starten und die EXEs bauen"
  if not errorlevel 2 (
    endlocal
    call "%~dp0Aktualisieren.bat"
    exit /b
  )
)
pause
exit /b 0

:fehler
echo.
echo  Einrichtung abgebrochen - siehe Meldung oben.
echo.
pause
exit /b 1

REM --- Echtes Python suchen (der Microsoft-Store-Platzhalter "python" zaehlt nicht) ---
:findpy
set "PY="
for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
if not defined PY for /f "delims=" %%i in ('python -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
if not defined PY for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%d\python.exe" set "PY=%%d\python.exe"
if not defined PY for /d %%d in ("%ProgramFiles%\Python3*") do if exist "%%d\python.exe" set "PY=%%d\python.exe"
exit /b 0
