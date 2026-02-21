@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [네이버 검색량 수집] niche_test.csv -> niche_with_volume.csv
python naver_api_manager.py
pause
