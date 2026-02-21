@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [통합 파이프라인] 네이버 -> 쿠팡 -> 교차검증 -> DB 저장
echo.
python main.py --limit 20
echo.
pause
