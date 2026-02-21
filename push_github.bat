@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo 작업 내용 저장 및 GitHub 업로드
echo.

git add .
git status
echo.
git commit -m "TEST_LIMIT 25로 변경, 수익 계산 광고비/부가세 반영, 스크래퍼 개선 등"
if errorlevel 1 (
    echo 커밋할 변경사항이 없거나 이미 커밋되었습니다.
) else (
    git push origin main
    if errorlevel 1 (
        echo push 실패. GitHub 로그인/연결을 확인하세요.
    ) else (
        echo GitHub 최신화 완료!
    )
)
echo.
pause
