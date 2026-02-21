@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [도매 검색] niche_test.csv S/A등급 -> 도매꾹, 오너클랜 검색
echo 결과: final_sourcing_list.csv (마진 30%% 이상)
echo.
python wholesale_searcher.py
echo.
pause
