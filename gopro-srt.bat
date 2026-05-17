@echo off
rem gopro-srt.bat - run gopro_gps_srt.py on every MP4 in this script's folder.
rem Speed-up exports (*32x.MP4, *64x.MP4, etc.) are skipped by the Python script.

setlocal
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" || exit /b 1

rem exiftool lives in F:\File Tools on this machine and is not on PATH by default.
set "PATH=F:\File Tools;%PATH%"

rem Prefer the py launcher (standard on Windows Python installs); fall back to python.
where py >nul 2>&1
if %errorlevel% equ 0 (
    py -3 "%SCRIPT_DIR%gopro_gps_srt.py" *.MP4
) else (
    python "%SCRIPT_DIR%gopro_gps_srt.py" *.MP4
)

popd
endlocal
pause
