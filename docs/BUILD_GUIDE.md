# Building the VARA Term Windows Installer

## The 3-Step Version

1. **Install Python 3.10+** from https://www.python.org/downloads/
   - **Check "Add Python to PATH"** during installation — this is critical

2. **Install Inno Setup 6** from https://jrsoftware.org/isdl.php
   - Use the default install location — the build script auto-detects it
   - This creates the `VARA Term_Setup_1.0.0.exe` installer
   - Skip this if you only want a portable .zip

3. **Double-click `build.bat`**
   - It installs all pip dependencies for you
   - It runs PyInstaller to create the .exe
   - It runs Inno Setup to create the installer
   - It creates a portable .zip as a fallback

When it finishes you'll find these in the `dist\` folder:

| File | What it is |
|------|------------|
| `dist\VARA Term_Setup_1.0.0.exe` | Installer (Start Menu, uninstaller, the works) |
| `dist\VARA Term_Portable_1.0.0.zip` | Portable zip (extract anywhere, run VARA Term.exe) |
| `dist\VARA Term\VARA Term.exe` | Raw build output (used by the above two) |

---

## Why can't this be built in the cloud?

PyInstaller doesn't cross-compile — a Windows .exe must be built on Windows.
The build script makes this as painless as possible: Python is the only thing
you need to install manually, everything else is automated.

---

## Troubleshooting

**"Python is not installed or not on PATH"**
→ Reinstall Python and check "Add Python to PATH". Or open a new terminal.

**PyInstaller build fails with antivirus warnings**
→ Temporarily disable real-time AV scanning, or add the project folder to exclusions. PyInstaller executables are commonly flagged as false positives.

**Inno Setup not found (but installed)**
→ The script checks standard install paths. If you installed elsewhere, add its folder to your system PATH so `iscc.exe` is reachable.

**Missing module at runtime**
→ Add the module name to `hiddenimports` in `vara_term.spec` and rebuild.

**App icon**
→ Drop a `resources\vara_term.ico` file (256×256 multi-size .ico), uncomment the `icon=` line in `vara_term.spec` and `SetupIconFile` in `installer.iss`, rebuild.
