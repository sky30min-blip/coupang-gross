@echo off
chcp 65001 >nul
echo ========================================
echo  쿠팡그로스 패키지 설치
echo ========================================
cd /d "%~dp0"

echo.
echo [1/2] pip install -r requirements.txt
pip install -r requirements.txt
if errorlevel 1 (
    echo 오류: pip 설치 실패. Python/pip 설치 여부를 확인하세요.
    pause
    exit /b 1
)

echo.
echo [2/2] playwright install (브라우저 다운로드)
playwright install
if errorlevel 1 (
    echo 경고: playwright install 실패. 도매 검색 기능만 영향받을 수 있습니다.
) else (
    echo Playwright 브라우저 설치 완료.
)

echo.
echo ========================================
echo  설치 완료.
echo ========================================
pause
