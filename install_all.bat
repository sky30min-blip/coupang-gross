@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   쿠팡그로스 프로젝트 패키지 설치
echo ========================================
echo.

echo [1/2] pip 패키지 설치 (requirements.txt)...
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo pip 설치 실패. python이 설치되어 있는지 확인하세요.
    pause
    exit /b 1
)

echo.
echo [2/2] Playwright Chromium 브라우저 설치...
playwright install chromium
if errorlevel 1 (
    echo.
    echo Chromium 설치 실패
    pause
    exit /b 1
)

echo.
echo ========================================
echo   설치 완료!
echo ========================================
echo.
echo 실행 가능한 스크립트:
echo   - run_web.bat             : 웹 대시보드 (브라우저에서 결과 확인)
echo   - run_niche_test.bat      : 니치 테스트 (niche_test.csv)
echo   - run_wholesale_searcher.bat : 도매 검색 (final_sourcing_list.csv)
echo   - run_credibility_report.bat : 신뢰도 리포트 (market_credibility_report.csv)
echo   - run_light_weight_filter.bat : 사입 적합성 필터 (light_weight_niche.xlsx)
echo.
pause
