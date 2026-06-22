@echo off
title ASB Vertragsdaten-Extraktor
echo ===================================================
echo   ASB Vertraege Extraktions-System (Llama 3)
echo ===================================================
echo.
cd /d "%~dp0"
python main.py
if %errorlevel% neq 0 (
    echo.
    echo Ein Fehler ist aufgetreten.
)
echo.
pause
