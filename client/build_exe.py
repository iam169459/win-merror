#!/usr/bin/env python3
"""
Win-Merror Client EXE Builder
Creates a standalone Windows executable using PyInstaller

Usage:
    python build_exe.py

Requirements:
    - Python 3.10+
    - PyInstaller (pip install pyinstaller)
    - Run on Windows machine
"""

import os
import sys
import subprocess
from pathlib import Path


def check_python():
    """Check if Python is installed"""
    print("Checking Python installation...")
    result = subprocess.run([sys.executable, "--version"], capture_output=True, text=True)
    if result.returncode != 0:
        print("Error: Python is not installed or not in PATH")
        print("Please install Python 3.10+ from https://www.python.org/downloads/")
        sys.exit(1)
    print(f"Found: {result.stdout.strip()}")


def install_pyinstaller():
    """Install PyInstaller if not already installed"""
    print("Checking PyInstaller...")
    result = subprocess.run([sys.executable, "-m", "pip", "show", "pyinstaller"], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        print("Installing PyInstaller...")
        result = subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("Error: Failed to install PyInstaller")
            print(result.stderr)
            sys.exit(1)
        print("PyInstaller installed successfully")
    else:
        print("PyInstaller is already installed")


def install_dependencies():
    """Install client dependencies"""
    print("Installing client dependencies...")
    req_file = Path(__file__).parent / "requirements-client.txt"
    if req_file.exists():
        result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req_file)], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("Warning: Failed to install some dependencies")
            print(result.stderr)
    else:
        print("requirements-client.txt not found, installing basic dependencies...")
        result = subprocess.run([sys.executable, "-m", "pip", "install", "websockets", "Pillow", "pywin32"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("Warning: Failed to install dependencies")
            print(result.stderr)


def create_icon():
    """Create a simple icon file if it doesn't exist"""
    icon_path = Path(__file__).parent / "icon.ico"
    if not icon_path.exists():
        print("Creating default icon...")
        try:
            from PIL import Image, ImageDraw
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Draw a simple camera icon
            draw.rectangle([50, 50, 200, 200], fill=(0, 120, 215, 255))
            draw.ellipse([70, 70, 180, 180], fill=(255, 255, 255, 255))
            draw.ellipse([80, 80, 100, 100], fill=(0, 0, 0, 255))
            draw.ellipse([150, 80, 170, 100], fill=(0, 0, 0, 255))
            
            img.save(icon_path, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            print(f"Icon created at {icon_path}")
        except ImportError:
            print("PIL/Pillow not available, skipping icon creation")
        except Exception as e:
            print(f"Warning: Failed to create icon: {e}")
            print("Will build without custom icon")
    else:
        print(f"Icon found at {icon_path}")


def build_exe():
    """Build the executable using PyInstaller"""
    print("\n" + "=" * 60)
    print("Building Win-Merror Client EXE")
    print("=" * 60)
    
    client_py = Path(__file__).parent / "client.py"
    if not client_py.exists():
        print(f"Error: {client_py} not found")
        sys.exit(1)
    
    # Build command
    cmd = [
        sys.executable, "-m", "pyinstaller",
        "--onefile",           # Single executable file
        "--windowed",          # No console window
        "--name", "win-merror-client",
        "--clean",             # Clean PyInstaller cache
        "--noconfirm",        # Don't ask for confirmation
        str(client_py)
    ]
    
    # Add icon if available
    icon_path = Path(__file__).parent / "icon.ico"
    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])
    
    print(f"Running: {' '.join(cmd)}")
    print("This may take 2-5 minutes...")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("\nError: Build failed!")
        print(result.stderr)
        sys.exit(1)
    
    print("\nBuild completed successfully!")


def main():
    """Main build script"""
    print("Win-Merror Client EXE Builder")
    print("-" * 30)
    
    # Check Python
    check_python()
    
    # Install PyInstaller
    install_pyinstaller()
    
    # Install dependencies
    install_dependencies()
    
    # Create icon
    create_icon()
    
    # Build EXE
    build_exe()
    
    # Show results
    dist_dir = Path(__file__).parent / "dist"
    exe_path = dist_dir / "win-merror-client.exe"
    
    if exe_path.exists():
        print("\n" + "=" * 60)
        print("SUCCESS: win-merror-client.exe created!")
        print("=" * 60)
        print(f"\nExecutable location: {exe_path.resolve()}")
        print("\nUsage:")
        print("  Double-click to run with config.json settings")
        print("  Or from command line:")
        print(f"    {exe_path.name} --host 208.72.218.144 --username admin --password yourpass")
        print("\nCommand line options:")
        print("  --host       Server host (default: from config.json)")
        print("  --port       Server port (default: 8081)")
        print("  --username   Username for authentication")
        print("  --password   Password for authentication")
        print("  --token      Authentication token")
        print("  --no-auto-reconnect  Disable auto-reconnect")
    else:
        print("\nError: Executable not found in dist/ directory")
        sys.exit(1)


if __name__ == "__main__":
    main()
