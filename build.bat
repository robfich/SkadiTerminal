@echo off
REM Baut SkadiTerminal.exe (Ordner dist\)
pip install -r requirements.txt
pyinstaller --onefile --noconsole --name SkadiTerminal --icon skaditerminal.ico --add-data "skaditerminal.ico;." --add-data "templates;templates" skaditerminal.py
pause
