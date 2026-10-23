@echo off
cd /d "%~dp0"
where pyw >nul 2>nul
if errorlevel 1 (
  start "" py -3 -m lanist
) else (
  start "" pyw -3 -m lanist
)
