@echo off
title Language Coach — ভাষা শিক্ষক
color 0A
echo.
echo =====================================================
echo   Language Coach  —  ভাষা শিক্ষক
echo   Learn French and Spanish through Bengali
echo =====================================================
echo.

cd /d "%~dp0"

:: Check if Flask is installed; if not, install requirements
python -c "import flask" 2>nul
if errorlevel 1 (
    echo Installing required packages...
    python -m pip install -r requirements.txt
    echo.
)

echo  Starting server at http://localhost:5000
echo  Press Ctrl+C to stop
echo.

:: Open browser after 2 second delay
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

:: Start the Flask app
python app.py

pause
