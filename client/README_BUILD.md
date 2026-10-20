# Building Win-Merror Client EXE

This guide explains how to create a standalone Windows executable for the Win-Merror client.

## Method 1: Using build_exe.bat (Recommended)

### Requirements
- Windows machine (Windows 10/11)
- Python 3.10 or higher installed
- Internet connection

### Steps

1. **Open Command Prompt** as Administrator

2. **Navigate to client directory**:
   ```cmd
   cd path\to\win-merror\client
   ```

3. **Run the build script**:
   ```cmd
   build_exe.bat
   ```

4. **Wait for completion** (may take 2-5 minutes)

5. **Find your executable**:
   - The EXE will be created in: `client\dist\win-merror-client.exe`

---

## Method 2: Manual PyInstaller Build

### 1. Install PyInstaller
```cmd
pip install pyinstaller
```

### 2. Install dependencies
```cmd
pip install -r requirements-client.txt
```

### 3. Build the EXE
```cmd
pyinstaller --onefile --windowed --name win-merror-client client.py
```

### 4. Find the executable
- Location: `dist\win-merror-client.exe`

---

## Method 3: Using build_exe.py (Python Script)

```cmd
python build_exe.py
```

This script will:
- Check Python installation
- Install PyInstaller if needed
- Install dependencies
- Create an icon
- Build the executable

---

## Running the EXE

### Option A: Double-click
- The EXE will automatically use settings from `config.json`
- Make sure `config.json` is in the same directory as the EXE

### Option B: Command Line
```cmd
win-merror-client.exe --host 208.72.218.144 --username admin --password yourpassword
```

### Available Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--host` | Server IP/hostname | From config.json |
| `--port` | Server port | 8081 |
| `--username` | Login username | From config.json |
| `--password` | Login password | From config.json |
| `--token` | Auth token | From config.json |
| `--fps` | Frames per second | 20 |
| `--quality` | JPEG quality (0-100) | 85 |
| `--scale` | Screen capture scale | 1.0 |
| `--no-auto-reconnect` | Disable auto-reconnect | Enabled |

---

## Troubleshooting

### Error: "Python not found"
- Install Python 3.10+ from [python.org](https://www.python.org/downloads/)
- Make sure to check "Add Python to PATH" during installation

### Error: "PyInstaller not found"
```cmd
pip install pyinstaller
```

### Error: "pywin32 not found"
```cmd
pip install pywin32
```

### Build succeeds but EXE doesn't run
- Try building with console: `pyinstaller --onefile --console --name win-merror-client client.py`
- This will show error messages in a console window

### EXE is too large
- The EXE will be ~10-20MB because it bundles Python and all dependencies
- This is normal for PyInstaller onefile builds

### Antivirus blocks the EXE
- Add an exception for the `dist` folder in your antivirus
- PyInstaller EXEs sometimes trigger false positives

---

## Customizing the EXE

### Change the Icon
1. Create a `.ico` file (e.g., `my-icon.ico`)
2. Place it in the `client` directory
3. Update `build_exe.bat` to use your icon:
   ```bat
   pyinstaller --onefile --windowed --name win-merror-client --icon=my-icon.ico client.py
   ```

### Add Version Info
Create a `version.txt` file:
```
# UTF-8
#
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [('CompanyName', 'Your Company'),
           ('FileDescription', 'Win-Merror Client'),
           ('FileVersion', '1.0.0.0'),
           ('InternalName', 'win-merror-client'),
           ('LegalCopyright', 'Copyright 2024'),
           ('OriginalFilename', 'win-merror-client.exe'),
           ('ProductName', 'Win-Merror'),
           ('ProductVersion', '1.0.0.0')]
        )
      ]
    ),
    VarFileInfo([Var('Translation', [0, 1200])])
  )
)
```

Then build with:
```cmd
pyinstaller --onefile --windowed --name win-merror-client --version-file=version.txt client.py
```

---

## Distributing the EXE

To share the EXE with others:

1. **Create a ZIP file** containing:
   - `win-merror-client.exe`
   - `config.json` (with their settings)
   - `README.md` (instructions)

2. **Or create an installer** using Inno Setup or NSIS

3. **Note**: The EXE is already portable - no additional files needed!

---

## Notes

- The EXE is **Windows-only** (won't run on Linux/Mac)
- The EXE bundles Python 3.10+ and all dependencies
- First run may be slower as it extracts files to temp directory
- For best performance, run from a local drive (not network share)
