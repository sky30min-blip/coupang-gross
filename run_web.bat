@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Streamlit 웹 대시보드 실행 중...
echo 브라우저가 자동으로 열립니다. (http://localhost:8501)
echo 종료하려면 이 창을 닫으세요.
echo.
streamlit run app.py
