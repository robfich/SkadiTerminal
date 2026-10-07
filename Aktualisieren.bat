@echo off
setlocal EnableExtensions
title SkadiTerminal aktualisieren
REM ===========================================================================
REM  Holt den neuesten Stand von GitHub, baut SkadiTerminal.exe + SkadiWaechter.exe
REM  und ersetzt die EXEs im Ordner DIESER Datei. Templates/Config bleiben unberuehrt.
REM  Diese Datei neben SkadiTerminal.exe / SkadiWaechter.exe legen und doppelklicken.
REM ===========================================================================
set "REPO=https://github.com/robfich/SkadiTerminal"
set "ZIP_URL=%REPO%/archive/refs/heads/main.zip"
set "TARGET=%~dp0"
set "WORK=%LOCALAPPDATA%\SkadiTerminal\quelle"

echo.
echo  [1/5] Python pruefen ...
where python >nul 2>nul
if errorlevel 1 (
  echo  FEHLER: Python ist nicht installiert oder nicht im PATH.
  echo  Bitte installieren: https://www.python.org/downloads/  ^(Haken bei "Add to PATH"^)
  goto :fehler
)

echo  [2/5] Neuesten Stand von GitHub holen ...
where git >nul 2>nul
if errorlevel 1 goto :zip
if exist "%WORK%\.git" (
  git -C "%WORK%" fetch --quiet origin main || goto :fehler
  git -C "%WORK%" reset --quiet --hard origin/main || goto :fehler
) else (
  if exist "%WORK%" rmdir /s /q "%WORK%"
  git clone --quiet --depth 1 "%REPO%.git" "%WORK%" || goto :fehler
)
goto :bauen

:zip
echo        ^(git nicht gefunden - lade ZIP^)
if exist "%WORK%" rmdir /s /q "%WORK%"
mkdir "%WORK%" 2>nul
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $z=Join-Path $env:TEMP 'skadi_main.zip'; Invoke-WebRequest '%ZIP_URL%' -OutFile $z; $t=Join-Path $env:TEMP 'skadi_unzip'; if(Test-Path $t){Remove-Item $t -Recurse -Force}; Expand-Archive $z $t; Copy-Item (Join-Path $t 'SkadiTerminal-main\*') '%WORK%' -Recurse -Force; Remove-Item $z,$t -Recurse -Force" || goto :fehler

:bauen
cd /d "%WORK%"
echo  [3/5] Pakete installieren ...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt || goto :fehler

echo  [4/5] EXEs bauen (dauert 1-2 Minuten) ...
if exist dist rmdir /s /q dist
python -m PyInstaller --noconfirm --log-level ERROR --onefile --noconsole --name SkadiTerminal --icon skaditerminal.ico --add-data "skaditerminal.ico;." --add-data "templates;templates" skaditerminal.py || goto :fehler
python -m PyInstaller --noconfirm --log-level ERROR --onefile --noconsole --name SkadiWaechter --icon skaditerminal.ico waechter\skadi_waechter.pyw || goto :fehler

echo  [5/5] Alte Version beenden und ersetzen ...
taskkill /IM SkadiWaechter.exe /F >nul 2>nul
taskkill /IM SkadiTerminal.exe /F >nul 2>nul
timeout /t 2 /nobreak >nul
copy /Y "dist\SkadiTerminal.exe" "%TARGET%" >nul || goto :fehler
copy /Y "dist\SkadiWaechter.exe" "%TARGET%" >nul || goto :fehler
copy /Y "waechter\Autostart_einrichten.bat" "%TARGET%" >nul
REM Neue Aktualisieren.bat nur ablegen, nicht ueberschreiben (laufende .bat darf sich nicht selbst ersetzen)
copy /Y "Aktualisieren.bat" "%TARGET%Aktualisieren.neu.bat" >nul

start "" "%TARGET%SkadiWaechter.exe"
echo.
echo  FERTIG - SkadiTerminal und SkadiWaechter sind aktuell.
echo  Ordner: %TARGET%
echo  Der Waechter laeuft wieder; SkadiTerminal startet beim naechsten Dota-Start.
echo.
pause
exit /b 0

:fehler
echo.
echo  Aktualisierung abgebrochen - siehe Meldung oben. Die alte Version bleibt unveraendert.
echo.
pause
exit /b 1
