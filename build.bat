@echo off
REM Baut SkadiTerminal.exe (Ordner dist\)
pip install -r requirements.txt
if exist skaditerminal.ico (
  pyinstaller --onefile --noconsole --name SkadiTerminal --icon skaditerminal.ico skaditerminal.py
) else (
  pyinstaller --onefile --noconsole --name SkadiTerminal skaditerminal.py
)
pause
