@echo off
rem OptimaX by X44TO - build the installer Output\OptimaX-Setup-<version>.exe
rem Needs Python 3.10+ and Inno Setup 6.3+ or 7 (winget install JRSoftware.InnoSetup).
rem Optional code signing: set OPTIMAX_PFX=C:\path\cert.pfx and OPTIMAX_PFX_PASS=password first.
rem Optional update channel for winget manifests: set OPTIMAX_UPDATE_REPO=owner/repo
rem Keep this file ASCII-only with CRLF line endings, otherwise cmd.exe misreads it.
set "KITS=%ProgramFiles(x86)%\Windows Kits\10\bin"
set "PF86=%ProgramFiles(x86)%"
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    echo [ERROR] Python not found. Install Python 3.10+ from https://www.python.org
    echo         and tick "Add python.exe to PATH" in the installer.
    goto :fail
)

for %%F in (optimizer.py engine.py hardware.py features.py monitor.py fpstest.py netlab.py guard.py apps.py power.py report.py hotkeys.py lifecycle.py updater.py ui_kit.py pages_optimize.py pages_tools.py pages_extra.py i18n.py lang_ui.py lang_engine.py lang_tweaks.py lang_extra.py lang_setup.py lang_lab.py gpubench.py adblock.py benchtools.py pages_lab.py rescue.py abtest.py smart_ui.py sharecard.py lang_safe.py selftest.py) do (
    if not exist "%%F" (
        echo [ERROR] %%F not found next to this script.
        goto :fail
    )
)

for /f "delims=" %%V in ('%PY% packaging\release.py version') do set "VER=%%V"
if not defined VER (
    echo [ERROR] Could not read the version from engine.py.
    goto :fail
)
echo Version: !VER!
%PY% packaging\release.py version-info >nul
rem buildinfo.py: update repo (OPTIMAX_UPDATE_REPO=owner/repo) and commit, read by the built program
%PY% packaging\release.py buildinfo >nul
if errorlevel 1 goto :fail

echo.
echo [1] Installing PyQt6 and PyInstaller...
%PY% -m pip install --upgrade PyQt6 pyinstaller
if errorlevel 1 (
    echo [ERROR] pip install failed. See the messages above.
    goto :fail
)

set "ARGS=--noconfirm --clean --windowed --uac-admin --noupx --name OptimaX"
if exist icon.ico set "ARGS=!ARGS! --icon icon.ico"
if exist version_info.txt set "ARGS=!ARGS! --version-file version_info.txt"
for %%M in (lang_ui lang_engine lang_tweaks lang_extra lang_setup lang_lab lang_safe gpubench adblock benchtools rescue abtest smart_ui sharecard selftest buildinfo PyQt6.QtNetwork PyQt6.QtOpenGL) do set "ARGS=!ARGS! --hidden-import %%M"
for %%F in (icon.png bench.png msi.png deepsek.png restore.png) do (
    if exist "%%F" set "ARGS=!ARGS! --add-data "%%F;.""
)

set "ISCC="
for %%P in ("!PF86!\Inno Setup 7\ISCC.exe" "%ProgramFiles%\Inno Setup 7\ISCC.exe" "!PF86!\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do (
    if not defined ISCC if exist "%%~P" set "ISCC=%%~P"
)
if not defined ISCC for /f "delims=" %%I in ('where iscc 2^>nul') do if not defined ISCC set "ISCC=%%I"
if not defined ISCC (
    echo [ERROR] Inno Setup not found. Install it with:
    echo         winget install JRSoftware.InnoSetup
    echo         or from https://jrsoftware.org/isdl.php and run this script again.
    goto :fail
)

set "SIGNTOOL="
if defined OPTIMAX_PFX (
    for /f "delims=" %%S in ('where signtool 2^>nul') do if not defined SIGNTOOL set "SIGNTOOL=%%S"
    if not defined SIGNTOOL for /f "delims=" %%S in ('dir /b /s "!KITS!\signtool.exe" 2^>nul ^| findstr /i "\\x64\\"') do if not defined SIGNTOOL set "SIGNTOOL=%%S"
    if not defined SIGNTOOL echo [WARN] signtool.exe not found - the build will not be signed.
)

echo.
echo [2] Building the program folder (dist\OptimaX)...
%PY% -m PyInstaller !ARGS! --onedir optimizer.py
if errorlevel 1 (
    echo [ERROR] PyInstaller failed. See the messages above.
    goto :fail
)
if exist MSI xcopy /e /i /y /q MSI dist\OptimaX\MSI >nul

if defined SIGNTOOL (
    echo [3] Signing OptimaX.exe...
    "!SIGNTOOL!" sign /f "%OPTIMAX_PFX%" /p "%OPTIMAX_PFX_PASS%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "dist\OptimaX\OptimaX.exe"
    if errorlevel 1 (
        echo [ERROR] Signing failed.
        goto :fail
    )
)

echo.
echo [4] Building the installer with Inno Setup...
if defined SIGNTOOL (
    "!ISCC!" /DMyAppVersion=!VER! /DUseSign "/Sstd=$q!SIGNTOOL!$q sign /f $q%OPTIMAX_PFX%$q /p $q%OPTIMAX_PFX_PASS%$q /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $f" packaging\OptimaX.iss
) else (
    "!ISCC!" /DMyAppVersion=!VER! packaging\OptimaX.iss
)
if errorlevel 1 (
    echo [ERROR] Inno Setup failed. See the messages above.
    goto :fail
)

echo.
echo [5] winget manifests...
%PY% packaging\release.py winget "Output\OptimaX-Setup-!VER!.exe"

echo.
echo Done: Output\OptimaX-Setup-!VER!.exe
echo.
if not defined CI pause
exit /b 0

:fail
echo.
echo Build failed.
if not defined CI pause
exit /b 1
