@echo off
REM Baut SkadiTerminal.exe und SkadiWaechter.exe (Ordner dist\)
pip install -r requirements.txt
set "ADD_ITEMS="
if exist "items\items.json" set ADD_ITEMS=--add-data "items;items"
pyinstaller --onefile --noconsole --name SkadiTerminal --icon skaditerminal.ico --add-data "skaditerminal.ico;." --add-data "templates;templates" %ADD_ITEMS% skaditerminal.py
pyinstaller --onefile --noconsole --name SkadiWaechter --icon skaditerminal.ico waechter\skadi_waechter.pyw
copy /Y waechter\Autostart_einrichten.bat dist\ >nul
copy /Y Aktualisieren.bat dist\ >nul
echo.
echo Fertig. In dist\ liegen SkadiTerminal.exe, SkadiWaechter.exe, Autostart_einrichten.bat und Aktualisieren.bat
pause
