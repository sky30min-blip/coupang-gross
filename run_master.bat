@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [마스터 시스템] trending_keywords.csv -> DB -> 분석
echo 로그: logs\system.log
echo.
python run_master.py --limit 50
echo.
pause
