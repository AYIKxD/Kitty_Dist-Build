@echo off
REM Install required Python packages and run Kitty_Dist.py

REM Check if requirements.txt exists
if not exist requirements.txt (
    echo requirements.txt not found!
    pause
    exit /b
)

REM Install requirements
pip install -r requirements.txt

REM Run the Python script
python Kitty_Dist.py

pause
