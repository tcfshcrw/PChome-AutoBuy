@echo off
cd /d "%~dp0"

IF NOT EXIST ".installed" (
    echo Installing requirements...
    pip install -r requirements.txt
    if %errorlevel% equ 0 (
        echo. > ".installed"
        echo Install success!
    ) else (
        echo Install failed! Check your python and pip.
        pause
        exit /b
    )
)

echo Starting server...
python web_app.py
pause
