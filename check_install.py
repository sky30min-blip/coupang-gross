"""requirements.txt 패키지 설치 여부 확인"""
import sys

PACKAGES = [
    ("requests", ">=2.28.0"),
    ("playwright", ">=1.40.0"),
    ("streamlit", ">=1.28.0"),
    ("pandas", ">=2.0.0"),
    ("matplotlib", ">=3.7.0"),
    ("openpyxl", ">=3.1.0"),
    ("plotly", ">=5.18.0"),
]

def parse_version(s):
    return tuple(int(x) for x in s.split(".")[:3] if x.isdigit())

def check_min(ver_str, min_str):
    v = parse_version(ver_str)
    m = parse_version(min_str.replace(">=", ""))
    return v >= m

print("=" * 50)
print("  패키지 설치 확인")
print("=" * 50)
print(f"Python: {sys.version}")
print()

ok_count = 0
for name, min_ver in PACKAGES:
    try:
        mod = __import__(name)
        ver = getattr(mod, "__version__", "?")
        status = "OK" if check_min(ver, min_ver) else "WARN (버전 낮음)"
        print(f"  {name:15} {ver:12} {status}")
        ok_count += 1
    except ImportError as e:
        print(f"  {name:15} --          FAIL: {e}")

print()
if ok_count == len(PACKAGES):
    print("  결과: 모든 패키지 설치됨")
else:
    print("  결과: 일부 패키지 누락 - pip install -r requirements.txt 실행")

# Playwright 브라우저 확인
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        # chromium 기본 사용
        browser = p.chromium.launch(headless=True)
        browser.close()
    print("  Playwright Chromium: OK")
except Exception as e:
    print("  Playwright Chromium: FAIL (playwright install 실행 필요)")

print("=" * 50)
