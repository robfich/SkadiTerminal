@echo off
REM Legt eine Verknüpfung zum SkadiWaechter in den Windows-Autostart.
REM Diese .bat in den Ordner legen, in dem SkadiWaechter.exe liegt, und doppelklicken.
set "TARGET=%~dp0SkadiWaechter.exe"
if not exist "%TARGET%" (
  echo SkadiWaechter.exe nicht gefunden in %~dp0
  echo Bitte zuerst build.bat ausfuehren und die EXE hierher kopieren.
  pause
  exit /b 1
)
set "LINK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\SkadiWaechter.lnk"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%LINK%'); $s.TargetPath='%TARGET%'; $s.WorkingDirectory='%~dp0'; $s.Save()"
echo Fertig: SkadiWaechter startet ab jetzt mit Windows.
echo Alten Prozesswatcher bitte aus dem Autostart entfernen (Win+R, shell:startup).
start "" "%TARGET%"
pause
