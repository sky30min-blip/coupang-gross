@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist ".git" (
    echo 이미 Git 저장소가 있습니다.
    goto :done
)

echo Git 저장소 초기화 중...
git init
if errorlevel 1 (
    echo 오류: git init 실패. Git이 설치되어 있는지 확인하세요.
    pause
    exit /b 1
)

echo.
echo 초기 커밋을 만들려면 아래를 순서대로 실행하세요:
echo   git add .
echo   git commit -m "Initial commit"
echo.
echo GitHub에 새 저장소를 만든 뒤 푸시하려면:
echo   git remote add origin https://github.com/내아이디/저장소이름.git
echo   git branch -M main
echo   git push -u origin main
echo.
:done
pause
