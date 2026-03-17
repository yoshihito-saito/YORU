@echo off
REM YORU Real-time GUI with Basler Pypylon Camera
REM This batch script runs the realtime GUI with pypylon backend enabled

echo.
echo ======================================================
echo YORU Real-time GUI (Basler Pypylon Camera)
echo ======================================================
echo.
echo Activating YORU environment...
call C:\Users\Cornell\miniconda3\Scripts\activate.bat yoru

echo.
echo Starting YORU real-time GUI...
echo Config: config/yoru_pypylon_test.yaml
echo.

python -m yoru.realtime_yoru_GUI -c config/yoru_pypylon_test.yaml

echo.
echo GUI closed.
pause
