@echo off
rem gopro-srt.bat - run gopro_gps_srt.py on every MP4 in this script's folder.
rem Speed-up exports (*32x.MP4, *64x.MP4, etc.) are skipped by the Python script.

setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" || exit /b 1

rem ---------------------------------------------------------------------------
rem Set CLEANUP=1 to delete gopro_gps_srt.py, gopro-srt.sh and this script
rem after a successful run.  Handy if you copy these three files into each
rem folder of footage from a template.  Never runs if anything failed.
rem ---------------------------------------------------------------------------
set "CLEANUP=0"

rem ---------------------------------------------------------------------------
rem exiftool is usually not on PATH on Windows.  It is looked for in order:
rem   1. %EXIFTOOL_DIR%       - uncomment the line below, or set it as a real
rem                             environment variable: setx EXIFTOOL_DIR "..."
rem   2. this script's folder - just drop exiftool.exe next to this file
rem   3. PATH
rem
rem Get exiftool from https://exiftool.org/.  If you take the standalone
rem Windows build, rename exiftool(-k).exe to exiftool.exe first.
rem ---------------------------------------------------------------------------
rem set "EXIFTOOL_DIR=C:\Tools\exiftool"

set "EXIFTOOL="
if defined EXIFTOOL_DIR if exist "%EXIFTOOL_DIR%\exiftool.exe" set "EXIFTOOL=%EXIFTOOL_DIR%\exiftool.exe"
if not defined EXIFTOOL if exist "%SCRIPT_DIR%exiftool.exe" set "EXIFTOOL=%SCRIPT_DIR%exiftool.exe"
if not defined EXIFTOOL for /f "delims=" %%P in ('where exiftool 2^>nul') do (
  if not defined EXIFTOOL set "EXIFTOOL=%%P"
)
if not defined EXIFTOOL goto :noexiftool

rem gopro_gps_srt.py shells out to a bare "exiftool", so put its folder on PATH.
for %%F in ("!EXIFTOOL!") do set "PATH=%%~dpF;!PATH!"
echo Using exiftool: !EXIFTOOL!

rem ---------------------------------------------------------------------------
rem Prefer the py launcher; fall back to python.exe.
rem ---------------------------------------------------------------------------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY goto :nopython

echo Using Python:   !PY!
echo.

!PY! "%SCRIPT_DIR%gopro_gps_srt.py" *.MP4
if errorlevel 1 goto :failed

echo.
echo Finished %TIME%.
if not "%CLEANUP%"=="1" goto :done

rem Only reached on success with CLEANUP=1.
del /q "%SCRIPT_DIR%gopro_gps_srt.py" >nul 2>&1
del /q "%SCRIPT_DIR%gopro-srt.sh"     >nul 2>&1
popd
endlocal
timeout /t 5 /nobreak >nul 2>&1
(goto) 2>nul & del "%~f0"
exit /B 0

:done
popd
endlocal
pause
exit /B 0

:noexiftool
echo.
echo ERROR: could not find exiftool.exe.
echo        Looked in %%EXIFTOOL_DIR%%, this script's folder, and PATH.
echo        Install it from https://exiftool.org/ and either add it to PATH
echo        or set EXIFTOOL_DIR near the top of this script.
goto :halt

:nopython
echo.
echo ERROR: neither "py" nor "python" is on PATH, so the script cannot run.
echo        Install Python 3 from https://www.python.org/downloads/ and tick
echo        "Add python.exe to PATH" in the installer.
goto :halt

:failed
echo.
echo ERROR: gopro_gps_srt.py reported a failure - see the messages above.
goto :halt

:halt
popd
endlocal
echo.
echo Nothing was deleted.  Fix the problem above and run this again.
pause
exit /B 1
