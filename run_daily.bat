@echo off
cd /d D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops
call venv\Scripts\activate
python scripts/daily_scheduled_pipeline.py >> logs\daily_pipeline.log 2>&1
