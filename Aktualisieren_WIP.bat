@echo off
REM Holt die TESTVERSION (Branch "workinprogress") statt der stabilen Version.
REM Zurueck zur stabilen Version: einfach wieder Aktualisieren.bat starten.
call "%~dp0Aktualisieren.bat" workinprogress
