@echo off
rem Starts the AI Gym Coach: the API in its own window, then the screens, then opens the browser.
rem Double-click this file. Close both windows to stop the app.
cd /d "%~dp0"
start "Gym Coach API" python -m uvicorn app.main:app --reload
start "" cmd /c "timeout /t 8 /nobreak >nul & start http://127.0.0.1:8501"
python -m streamlit run app/streamlit_app.py
