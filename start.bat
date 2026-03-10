@echo off
set PORT=%1
if "%PORT%"=="" set PORT=5000
py app.py --port %PORT%
