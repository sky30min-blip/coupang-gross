@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [시즌 헌터] niche_test.csv 키워드 3년치 시즌 패턴 분석
echo 결과: seasonal_hunter_report.csv, seasonal_charts\*.png
echo (config.py에 네이버 데이터랩 API 키 필요)
echo.
python seasonal_analyzer.py
echo.
pause
