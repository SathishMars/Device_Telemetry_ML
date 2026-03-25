@echo off
cd /d D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops
call venv\Scripts\activate
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 >> logs\api.log 2>&1
