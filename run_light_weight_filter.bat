@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [사입 적합성 필터] 가격/키워드/묶음 필터 적용
echo 결과: light_weight_niche.xlsx
echo.
python light_weight_filter.py
echo.
pause
