@echo off
chcp 65001 >nul
title CToS2 Launcher
setlocal enabledelayedexpansion

echo ============================================
echo   CToS2 Startup Script
echo ============================================

set ROOT_DIR=%~dp0
set BACKEND_DIR=%ROOT_DIR%CToS2Back
set VENV_DIR=%ROOT_DIR%venv

:: ==============================================
:: Step 0: Check and install Python 3.11 if needed
:: ==============================================

py -3.11 --version >nul 2>nul
if errorlevel 1 (
    echo [0/4] Python 3.11 not found. Attempting auto-install...
    echo.
    
    :: Method 1: winget (built-in on Win 10 1809+ / Win 11)
    winget install Python.Python.3.11 --disable-interactivity --accept-source-agreements --accept-package-agreements >nul 2>nul
    if errorlevel 1 (
        :: Method 2: Chinese mirrors for faster download
        set DOWNLOAD_OK=0
        for %%m in (
            "https://mirrors.tuna.tsinghua.edu.cn/python-release/windows/3.11.9/python-3.11.9-amd64.exe"
            "https://repo.huaweicloud.com/python/3.11.9/python-3.11.9-amd64.exe"
            "https://mirrors.aliyun.com/python-release/windows/3.11.9/python-3.11.9-amd64.exe"
            "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
        ) do (
            if !DOWNLOAD_OK! EQU 0 (
                echo [INFO] Downloading Python 3.11.9 from mirror...
                powershell -Command "Invoke-WebRequest -Uri '%%~m' -OutFile '%TEMP%\python-3.11.9-amd64.exe'"
                if errorlevel 1 (
                    echo [WARN] Download failed. Trying next mirror...
                ) else (
                    set DOWNLOAD_OK=1
                )
            )
        )
        if !DOWNLOAD_OK! EQU 0 (
            echo [ERR] Download failed from all mirrors. Check your internet connection.
            echo       Manual download: https://www.python.org/downloads/release/python-3119/
            pause
            exit /b 1
        )
        echo [INFO] Installing Python 3.11...
        start /wait "" "%TEMP%\python-3.11.9-amd64.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
        del "%TEMP%\python-3.11.9-amd64.exe" >nul 2>nul
    )
    
    :: Find installed Python 3.11 by checking standard locations
    echo [INFO] Searching for Python 3.11 installation...
    
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
    ) else (
        if exist "%SYSTEMROOT%\py.exe" (
            set "PATH=%SYSTEMROOT%;%PATH%"
        ) else (
            if exist "%ProgramFiles%\Python311\python.exe" (
                set "PATH=%ProgramFiles%\Python311;%ProgramFiles%\Python311\Scripts;%PATH%"
            ) else (
                if exist "%ProgramFiles(x86)%\Python311-32\python.exe" (
                    set "PATH=%ProgramFiles(x86)%\Python311-32;%ProgramFiles(x86)%\Python311-32\Scripts;%PATH%"
                ) else (
                    echo [ERR] Python 3.11 installed but cannot be found.
                    echo       Please run the script again after restarting terminal.
                    pause
                    exit /b 1
                )
            )
        )
    )
    
    py -3.11 --version >nul 2>nul
    if errorlevel 1 (
        echo [ERR] Python 3.11 still not accessible. Starting venv creation directly...
    ) else (
        echo [0/4] OK Python 3.11 found
        py -3.11 --version
    )
) else (
    echo [0/4] OK Python 3.11 found
    py -3.11 --version
)

:: ==============================================
:: Step 1: Check or create virtual environment
:: ==============================================

if exist "%VENV_DIR%\Scripts\python.exe" (
    "%VENV_DIR%\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3,11) else 1)"
    if errorlevel 1 (
        echo [WARN] Existing venv version is not 3.11. Rebuilding...
        rmdir /s /q "%VENV_DIR%"
        echo [1/4] Creating Python 3.11 virtual environment...
        py -3.11 -m venv "%VENV_DIR%"
        if errorlevel 1 (
            echo [ERR] Failed to create venv.
            pause
            exit /b 1
        )
        echo [1/4] OK Virtual environment created
    ) else (
        echo [1/4] OK Virtual environment found
    )
) else (
    echo [1/4] Creating Python 3.11 virtual environment...
    py -3.11 -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERR] Failed to create venv.
        pause
        exit /b 1
    )
    "%VENV_DIR%\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3,11) else 1)"
    if errorlevel 1 (
        echo [ERR] Created venv but version is not 3.11
        pause
        exit /b 1
    )
    echo [1/4] OK Virtual environment created
)

:: ==============================================
:: Step 2: Activate virtual environment
:: ==============================================
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERR] Failed to activate virtual environment
    pause
    exit /b 1
)
echo [2/4] OK Virtual environment activated
python --version
echo   Path:
python -c "import sys; print(sys.executable)"

:: ==============================================
:: Step 3: Install dependencies via Tsinghua mirror
:: ==============================================
if exist "%BACKEND_DIR%\requirements.txt" (
    echo [3/4] Installing dependencies via Tsinghua mirror...
    pip install -r "%BACKEND_DIR%\requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [WARN] Tsinghua mirror failed. Retrying with default PyPI...
        pip install -r "%BACKEND_DIR%\requirements.txt"
    )
    echo [3/4] OK Dependencies installed
) else (
    echo [3/4] SKIP requirements.txt not found
)

:: ==============================================
:: Step 4: Check .env and start server
:: ==============================================
if not exist "%BACKEND_DIR%\.env" (
    if exist "%BACKEND_DIR%\.env.example" (
        copy "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env" >nul
    )
)
echo [4/4] OK Starting development server...
echo.
echo ============================================
echo   URL: http://localhost:8000
echo   Frontend: CToS2Front/frontend/
echo   Backend: CToS2Back/
echo   Press Ctrl+C to stop
echo ============================================
echo.

cd /d "%ROOT_DIR%"
python run.py

if errorlevel 1 (
    echo [ERR] Server exited with error code %errorlevel%
    pause
) else (
    echo.
    echo CToS2 server stopped.
    timeout /t 3 >nul
)