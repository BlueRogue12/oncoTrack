@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo  OncoTrack Windows Build
echo ============================================================

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: python not found. Please activate your venv first:
    echo   venv\Scripts\activate
    exit /b 1
)

echo Installing/upgrading PyInstaller...
python -m pip install --upgrade pyinstaller

echo Cleaning previous build...
if exist build\OncoTrack rmdir /s /q build\OncoTrack
if exist dist\OncoTrack  rmdir /s /q dist\OncoTrack

echo Running PyInstaller...
pyinstaller oncotrack.spec --noconfirm

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller failed. See output above.
    exit /b 1
)

echo.
echo ============================================================
echo  Build succeeded: dist\OncoTrack\
echo ============================================================
echo.
echo Next steps:
echo   1. Copy your Fiji folder into dist\OncoTrack\Fiji\
echo      Expected: dist\OncoTrack\Fiji\fiji-windows-x64.exe
echo      Command:  xcopy /E /I "C:\path\to\fiji-latest-win64-jdk\Fiji" "dist\OncoTrack\Fiji\"
echo   2. Test locally: dist\OncoTrack\OncoTrack.exe
echo   3. Zip it:
echo      powershell Compress-Archive -Path dist\OncoTrack -DestinationPath OncoTrack.zip
echo   4. Send OncoTrack.zip to the professor
echo ============================================================
