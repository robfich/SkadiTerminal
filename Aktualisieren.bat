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
call :findpy
if not defined PY (
  echo  FEHLER: Python 3.12 ist nicht installiert.
  echo  Bitte zuerst Einrichten.bat ausfuehren ^(installiert Python und alle Pakete^).
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
"%PY%" -m pip install --quiet --disable-pip-version-check --prefer-binary -r requirements.txt || goto :fehler

echo  [4/5] EXEs bauen (dauert 1-2 Minuten) ...
if exist dist rmdir /s /q dist
"%PY%" -m PyInstaller --noconfirm --log-level ERROR --onefile --noconsole --name SkadiTerminal --icon skaditerminal.ico --add-data "skaditerminal.ico;." --add-data "templates;templates" skaditerminal.py || goto :fehler
"%PY%" -m PyInstaller --noconfirm --log-level ERROR --onefile --noconsole --name SkadiWaechter --icon skaditerminal.ico waechter\skadi_waechter.pyw || goto :fehler

echo  [5/5] Alte Version beenden und ersetzen ...
taskkill /IM SkadiWaechter.exe /F >nul 2>nul
taskkill /IM SkadiTerminal.exe /F >nul 2>nul
timeout /t 2 /nobreak >nul
copy /Y "dist\SkadiTerminal.exe" "%TARGET%" >nul || goto :fehler
copy /Y "dist\SkadiWaechter.exe" "%TARGET%" >nul || goto :fehler
copy /Y "waechter\Autostart_einrichten.bat" "%TARGET%" >nul
copy /Y "Einrichten.bat" "%TARGET%" >nul
REM Neue Aktualisieren.bat nur ablegen, wenn sie sich unterscheidet (laufende .bat darf sich nicht selbst ersetzen)
fc /b "Aktualisieren.bat" "%~f0" >nul 2>nul && (del "%TARGET%Aktualisieren.neu.bat" >nul 2>nul) || (copy /Y "Aktualisieren.bat" "%TARGET%Aktualisieren.neu.bat" >nul & echo  Hinweis: Neue Aktualisieren.bat liegt als Aktualisieren.neu.bat bereit - alte loeschen, neue umbenennen.)

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

REM --- Python 3.12 suchen (dafuer gibt es fertige Pakete fuer alles; andere Versionen werden ignoriert) ---
:findpy
set "PY="
for /f "delims=" %%i in ('py -3.12 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%ProgramFiles%\Python312\python.exe" set "PY=%ProgramFiles%\Python312\python.exe"
exit /b 0
