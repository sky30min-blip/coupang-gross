@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [니치 테스트] trending_keywords.csv 상위 20개 쿠팡 분석
echo 결과: niche_test.csv
echo.
python niche_test.py
echo.
pause
