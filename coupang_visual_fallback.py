"""
coupang_visual_fallback.py - 시각 검증용 스크래퍼 (차단 시 예외 처리)
API 로켓수 0일 때 보조 검증용. 쿠팡이 차단하면 실패하고 스크린샷은 저장되지 않음.
"""

import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))

DEBUG_SCREENSHOTS = Path(__file__).resolve().parent / "debug_screenshots"
COUPANG_SEARCH_URL = "https://www.coupang.com/np/search"


def scrape_and_save(keyword: str) -> dict:
    """
    쿠팡 검색 화면 스크래핑 후 debug_screenshots/{keyword}.png 저장.
    차단 시 실패 반환. 성공 시 rocket_count, screenshot_path 반환.
    """
    result = {"rocket_count": None, "screenshot_path": None, "error": None}
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in keyword)
    out_path = DEBUG_SCREENSHOTS / f"{safe_name}.png"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        result["error"] = "playwright 미설치"
        return result

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                    locale="ko-KR",
                )
                page = context.new_page()
                url = f"{COUPANG_SEARCH_URL}?q={quote(keyword)}"
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(3000)

                body = page.inner_text("body") or ""
                if "Access Denied" in body or "접근이 제한" in body:
                    result["error"] = "쿠팡 차단 (Access Denied)"
                    return result

                DEBUG_SCREENSHOTS.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(out_path), full_page=False)
                result["screenshot_path"] = str(out_path)

                items = page.query_selector_all("li.search-product")
                rocket = 0
                for item in items:
                    ad = item.query_selector(".search-product__ad-badge, [class*='ad-badge']")
                    if ad:
                        continue
                    text = item.inner_text() or ""
                    if "로켓" in text:
                        rocket += 1
                result["rocket_count"] = rocket
            finally:
                browser.close()
    except Exception as e:
        result["error"] = str(e)
    return result
