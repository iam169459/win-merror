@echo off
:: Win-Merror Client EXE Builder
:: This script creates a standalone Windows executable for the client
::
:: Requirements:
::   - Python 3.10+
::   - PyInstaller (pip install pyinstaller)
::   - Run on Windows machine

setlocal

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

:: Install client dependencies
pip install -r requirements-client.txt

:: Build the executable
echo Building Win-Merror Client EXE...
echo This may take a few minutes...

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
    echo The executable is in: dist\win-merror-client.exe
    echo.
    echo Usage:
    echo   win-merror-client.exe --host 208.72.218.144 --username admin --password yourpass
    echo.
    echo Or double-click to use config.json settings
    echo.
    pause
) else (
    echo.
    echo ERROR: Build failed!
    echo Check the error messages above
    pause
    exit /b 1
)
