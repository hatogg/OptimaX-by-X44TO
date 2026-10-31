@echo off
rem OptimaX by X44TO - portable build: one OptimaX.exe that runs without installation.
rem For a full installer (Start menu, uninstall, updates) use build_installer.bat.
rem Self-test of the result: Output\OptimaX-<ver>-portable.exe --selftest=report.json --selftest-ui
rem Keep this file ASCII-only with CRLF line endings, otherwise cmd.exe misreads it.
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

for %%F in (optimizer.py engine.py hardware.py hwnative.py features.py monitor.py fpstest.py netlab.py guard.py apps.py power.py report.py hotkeys.py lifecycle.py updater.py ui_kit.py pages_optimize.py pages_tools.py pages_extra.py i18n.py lang_ui.py lang_engine.py lang_tweaks.py lang_extra.py lang_setup.py lang_lab.py gpubench.py adblock.py benchtools.py pages_lab.py rescue.py abtest.py smart_ui.py sharecard.py lang_safe.py lang_v64.py lang_mining.py lang_gpu.py mining.py gpuinfo.py gpudiag.py gamedb.py pages_mining.py crashlog.py library.py qr.py phonemon.py bugreport.py whatsnew.py transfer.py pages_library.py pages_life.py lang_life.py baseline.py verify.py modes.py selftest.py) do (
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
rem PyQt6 is pinned in requirements.txt: Qt 6.13+ no longer runs on Windows 10
%PY% -m pip install --upgrade -r requirements.txt pyinstaller
if errorlevel 1 (
    echo [ERROR] pip install failed. See the messages above.
    goto :fail
)

set "ARGS=--noconfirm --clean --windowed --uac-admin --noupx --name OptimaX"
if exist icon.ico set "ARGS=!ARGS! --icon icon.ico"
if exist version_info.txt set "ARGS=!ARGS! --version-file version_info.txt"
for %%M in (lang_ui lang_engine lang_tweaks lang_extra lang_setup lang_lab lang_safe lang_v64 lang_mining lang_gpu mining gpuinfo gpudiag gamedb pages_mining crashlog library qr phonemon bugreport whatsnew transfer pages_library pages_life lang_life baseline verify modes gpubench adblock benchtools rescue abtest smart_ui sharecard selftest buildinfo PyQt6.QtNetwork PyQt6.QtOpenGL) do set "ARGS=!ARGS! --hidden-import %%M"
for %%F in (icon.png bench.png msi.png deepsek.png restore.png) do (
    if exist "%%F" set "ARGS=!ARGS! --add-data "%%F;.""
)

echo.
echo [2] Building the portable EXE...
%PY% -m PyInstaller !ARGS! --onefile optimizer.py
if errorlevel 1 (
    echo [ERROR] PyInstaller failed. See the messages above.
    goto :fail
)
if not exist Output mkdir Output
copy /y dist\OptimaX.exe "Output\OptimaX-!VER!-portable.exe" >nul
copy /y packaging\OptimaX-Rescue.cmd Output\OptimaX-Rescue.cmd >nul

rem Copy the MSI Afterburner folder next to the EXE, if present
if exist MSI xcopy /e /i /y /q MSI dist\MSI >nul

echo.
echo Done: dist\OptimaX.exe  and  Output\OptimaX-!VER!-portable.exe
echo.
if not defined CI pause
exit /b 0

:fail
echo.
echo Build failed.
if not defined CI pause
exit /b 1
