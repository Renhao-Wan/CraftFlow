@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   CraftFlow Desktop Build Script
echo ========================================
echo.

:: Set mirrors for China
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
set ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/
set npm_config_registry=https://registry.npmmirror.com

:: Check Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Please install Node.js first.
    echo Download: https://nodejs.org/
    pause
    exit /b 1
)

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python first.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Get script directory
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
cd /d "%PROJECT_DIR%"

echo [1/6] Syncing source files from original projects...
node "%SCRIPT_DIR%..\..\scripts\prepare.js"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to sync source files
    pause
    exit /b 1
)
echo.

echo [2/6] Installing Electron dependencies...
call npm install
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Electron dependencies
    pause
    exit /b 1
)

:: Install 7za wrapper (strips -snld flag to avoid symlink admin requirement)
echo [*] Installing 7za wrapper...
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%compile-7za-wrapper.ps1"
if %errorlevel% neq 0 (
    echo [WARNING] 7za wrapper compilation failed, build may require admin rights
)
echo.

echo [3/6] Building frontend...
cd frontend
call npm install
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install frontend dependencies
    pause
    exit /b 1
)

:: Set frontend environment variables
set "VITE_API_BASE_URL=http://127.0.0.1:8000/api"
set "VITE_WS_URL=ws://127.0.0.1:8000/ws"

call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] Failed to build frontend
    pause
    exit /b 1
)
cd ..
echo.

echo [4/6] Building backend...
cd backend
uv sync --extra build
uv run python -m PyInstaller craftflow.spec --distpath dist --workpath build --clean
if %errorlevel% neq 0 (
    echo [ERROR] Failed to build backend
    pause
    exit /b 1
)
cd ..
echo.

echo [5/6] Packaging Electron app...
call npx electron-builder --win --x64
if %errorlevel% neq 0 (
    echo [ERROR] Failed to package Electron app
    pause
    exit /b 1
)
echo.

echo [6/6] Done!
echo.
echo ========================================
echo   Build successful!
echo   Installer location: release\
echo ========================================
echo.

:: Ensure .gitkeep exists in release directory
if not exist release mkdir release
echo # Keep this directory for git > release\.gitkeep

:: Open output directory
explorer release

pause
