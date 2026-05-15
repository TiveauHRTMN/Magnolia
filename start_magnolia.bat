@echo off
cd /d "%~dp0"
title Magnolia Syndicaat
:loop
python magnolia_scan.py
echo Magnolia gestopt. Herstart over 60 seconden...
timeout /t 60 /nobreak
goto loop
