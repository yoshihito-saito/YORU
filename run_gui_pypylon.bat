@echo off
REM YORU Real-time GUI with Basler Pypylon Camera
REM This batch script runs the realtime GUI with pypylon backend enabled

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo.
echo ======================================================
echo YORU Real-time GUI (Basler Pypylon Camera)
echo ======================================================
echo.
echo Starting YORU real-time GUI...
echo Activate your Python environment before running this script if needed.
echo Config: config/yoru_pypylon_test.yaml
echo.

python -m yoru.realtime_yoru_GUI --config config/yoru_pypylon_test.yaml

echo.
echo GUI closed.
pause
