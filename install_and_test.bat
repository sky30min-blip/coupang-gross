@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ========================================
echo   패키지 설치
echo ========================================
pip install requests streamlit pandas playwright
playwright install chromium

echo.
echo [설치 완료] 계속하려면 아무 키나 누르세요...
pause >nul

echo.
echo ========================================
echo   쿠팡 API 연결 테스트 (키워드 1개)
echo ========================================
python -c "
try:
    from coupang_config import COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY
    from coupang_api import search_products
    r = search_products('텀블러', 5, COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY)
    if r and r.get('data', {}).get('productData'):
        print('OK: 쿠팡 API 연결 성공!')
    else:
        print('응답:', r)
except ImportError as e:
    print('설정 오류:', e)
except Exception as e:
    print('API 오류:', e)
    import traceback
    traceback.print_exc()
"
if errorlevel 1 (
    echo.
    echo [오류 발생] 위 메시지를 확인하세요.
)

echo.
echo ========================================
echo   완료. 아무 키나 누르면 창이 닫힙니다.
echo ========================================
pause
