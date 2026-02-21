@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [신뢰도 리포트] niche_test.csv -> Naver DataLab 트렌드 분석
echo 결과: market_credibility_report.csv, credibility_charts\*.png
echo (config.py에 네이버 데이터랩 API 키 필요)
echo.
python market_credibility_report.py
echo.
pause
