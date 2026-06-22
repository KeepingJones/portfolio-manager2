@echo off
cd /d %~dp0

echo ── Portfolio Manager ──
echo.

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate

echo Installing dependencies...
pip install -r backend\requirements.txt -q

echo.
echo Starting server at http://localhost:8080
echo Press Ctrl+C to stop.
echo.

start "" http://localhost:8080

cd backend
uvicorn main:app --reload --port 8080 --host 0.0.0.0
