@echo off
chcp 65001 >nul
title VARA TERM Setup
setlocal EnableDelayedExpansion

echo.
echo  ##  ##  ####  #####    ####     #####  ##### #####   ##   ##
echo  ##  ## ##  ## ##  ##  ##  ##      ##   ##    ##  ## ####  ####
echo  ##  ## ###### #####   ######      ##   ####  #####   ##   ##
echo   ####  ##  ## ## ##   ##  ##      ##   ##    ## ##
echo    ##   ##  ## ##  ##  ##  ##      ##   ##### ##  ##
echo.
echo                    VARA Term  -  Remote Setup
echo  -------------------------------------------------------------------------------------
echo.

:: -- Check git is available ---------------------------------------------------
where git >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Git not found on PATH.
    echo.
    echo  Please install Git from https://git-scm.com/downloads
    echo  Make sure to select "Add to PATH" during installation.
    echo.
    pause
    exit /b 1
)
echo  Git found: OK

:: -- Check Python is available ------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found on PATH.
    echo.
    echo  Please install Python 3.11 or later from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  Python found: %PY_VER%
echo.

:: -- Ask for install folder ---------------------------------------------------
set "DEFAULT_DIR=%USERPROFILE%\vara-term"
echo  Where would you like to install VARA TERM?
echo  Press Enter for default: %DEFAULT_DIR%
echo.
set /p "INSTALL_DIR=  Install folder: "
if "!INSTALL_DIR!"=="" set "INSTALL_DIR=%DEFAULT_DIR%"

:: Expand any environment variables / relative paths
for %%i in ("!INSTALL_DIR!") do set "INSTALL_DIR=%%~fi"

echo.
echo  Installing to: !INSTALL_DIR!
echo.

:: -- Clone the repository -----------------------------------------------------
if exist "!INSTALL_DIR!\.git" (
    echo  Repository already exists at !INSTALL_DIR!
    echo  Pulling latest changes...
    pushd "!INSTALL_DIR!"
    git pull --ff-only
    popd
) else (
    if exist "!INSTALL_DIR!\src\main.py" (
        echo  [ERROR] Folder already contains files but is not a git repo.
        echo  Please choose an empty folder or delete the existing files.
        pause
        exit /b 1
    )
    echo  Cloning VARA Term repository...
    git clone https://github.com/KK4ODA/vara-term.git "!INSTALL_DIR!"
    if errorlevel 1 (
        echo.
        echo  [ERROR] git clone failed. Check your internet connection.
        pause
        exit /b 1
    )
)
echo.
echo  Repository ready.
echo.

:: -- Install Python dependencies ----------------------------------------------
echo  Checking Python dependencies...
echo.

set MISSING=0

python -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo  [MISSING] PyQt6
    set MISSING=1
)

python -c "import cryptography" >nul 2>&1
if errorlevel 1 (
    echo  [MISSING] cryptography
    set MISSING=1
)

python -c "import serial" >nul 2>&1
if errorlevel 1 (
    echo  [MISSING] pyserial
    set MISSING=1
)

if !MISSING!==1 (
    echo.
    echo  Installing required packages...
    python -m pip install PyQt6 cryptography pyserial certifi
    if errorlevel 1 (
        echo.
        echo  [ERROR] pip install failed. Please run manually:
        echo    python -m pip install PyQt6 cryptography pyserial certifi
        pause
        exit /b 1
    )
    echo.
    echo  Dependencies installed.
) else (
    echo  All dependencies satisfied.
)
echo.

:: -- Create start_term.bat inside the install folder --------------------------
> "!INSTALL_DIR!\start_term.bat" (
    echo @echo off
    echo chcp 65001 ^>nul
    echo title VARA TERM
    echo cd /d "%%~dp0"
    echo python src\main.py
    echo pause
)

echo  Created start_term.bat launcher.

:: -- Create desktop shortcut --------------------------------------------------
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP%\VARA TERM.lnk"

echo  Creating desktop shortcut...

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%SHORTCUT%'); $sc.TargetPath = '!INSTALL_DIR!\start_term.bat'; $sc.WorkingDirectory = '!INSTALL_DIR!'; $sc.Description = 'VARA Term - VARA BBS Terminal Client'; $sc.Save()"

if exist "%SHORTCUT%" (
    echo  Desktop shortcut created: VARA TERM
) else (
    echo  [WARNING] Could not create desktop shortcut.
    echo  You can run start_term.bat from: !INSTALL_DIR!
)

echo.
echo  -------------------------------------------------------------------------------------
echo  Setup complete!
echo.
echo  To launch VARA TERM:
echo    - Double-click "VARA TERM" on your desktop
echo    - Or run: !INSTALL_DIR!\start_term.bat
echo.
echo  Updates will be checked automatically on startup.
echo  -------------------------------------------------------------------------------------
echo.
pause
endlocal
