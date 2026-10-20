@echo off
:: Win-Merror Client EXE Builder
:: This script creates a standalone Windows executable for the client
::
:: IMPORTANT: This script MUST be run on a WINDOWS machine
:: It will NOT work on Linux, Mac, or WSL (without additional setup)
::
:: Requirements:
::   - Windows 10/11
::   - Python 3.10+
::   - Run in Command Prompt (cmd.exe)

setlocal

:: Check if we're on Windows
if not defined OS (
    echo Error: This script must be run on Windows
    echo Current system: %OS%
    pause
    exit /b 1
)

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

:: Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo Error: Failed to install PyInstaller
        pause
        exit /b 1
    )
)

:: Install client dependencies
if exist requirements-client.txt (
    echo Installing client dependencies...
    pip install -r requirements-client.txt
    if errorlevel 1 (
        echo Warning: Failed to install some dependencies
        echo Continuing anyway...
    )
) else (
    echo Warning: requirements-client.txt not found
    echo Installing basic dependencies...
    pip install websockets opencv-python numpy Pillow pywin32
)

:: Build the executable
echo.
echo ============================================
    echo Building Win-Merror Client EXE...
    echo This may take 2-5 minutes...
    echo ============================================
echo.

:: Create icon if it doesn't exist
if not exist icon.ico (
    echo Creating default icon...
    python -c "
import sys
try:
    from PIL import Image, ImageDraw
    img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 200, 200], fill=(0, 120, 215, 255))
    draw.ellipse([70, 70, 180, 180], fill=(255, 255, 255, 255))
    draw.ellipse([80, 80, 100, 100], fill=(0, 0, 0, 255))
    draw.ellipse([150, 80, 170, 100], fill=(0, 0, 0, 255))
    draw.ellipse([90, 150, 110, 170], fill=(0, 0, 0, 255))
    draw.ellipse([140, 150, 160, 170], fill=(0, 0, 0, 255))
    img.save('icon.ico', format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
    print('Icon created')
except Exception as e:
    print(f'Warning: Could not create icon: {e}')
    sys.exit(0)
"
)

pyinstaller ^
    --onefile ^
    --windowed ^
    --name win-merror-client ^
    --icon=icon.ico ^
    --clean ^
    --noconfirm ^
    client.py

:: Check if build succeeded
if exist dist\win-merror-client.exe (
    echo.
    echo ============================================
    echo SUCCESS: win-merror-client.exe created!
    echo ============================================
    echo.
    echo Location: dist\win-merror-client.exe
    echo.
    echo Usage:
    echo   1. Double-click to run with config.json settings
    echo   2. Or from command line:
    echo      win-merror-client.exe --host 208.72.218.144 --username admin --password yourpass
    echo.
    echo Common options:
    echo   --host        Server IP (default: from config.json)
    echo   --port        Server port (default: 8081)
    echo   --username    Login username
    echo   --password    Login password
    echo   --token      Auth token
    echo   --no-auto-reconnect  Disable auto-reconnect
    echo.
    pause
) else (
    echo.
    echo ERROR: Build failed!
    echo Check the error messages above
    echo.
    echo Troubleshooting:
    echo   - Make sure you're on Windows
    echo   - Make sure Python 3.10+ is installed
    echo   - Try: pip install --upgrade pyinstaller
    echo   - Try: pyinstaller --onefile --console client.py (to see errors)
    pause
    exit /b 1
)
