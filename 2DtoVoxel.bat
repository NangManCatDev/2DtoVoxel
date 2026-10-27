@echo off
rem Double-click to start the 2DtoVoxel web UI (opens in the browser).
cd /d "%~dp0"
py -m voxtool ui %*
if errorlevel 1 pause
