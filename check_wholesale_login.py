"""
check_wholesale_login.py
config.py 계정으로 도매꾹·오너클랜 로그인만 시도하고 결과를 wholesale_login_status.json에 저장.
대시보드에서 '로그인 상태 확인' 버튼으로 호출됨.
"""

import json
import random
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from playwright.sync_api import sync_playwright

from wholesale_searcher import login_domeggook, login_ownerclan

STATUS_FILE = BASE / "wholesale_login_status.json"


def main():
    try:
        import config
        domeggook_id = (getattr(config, "DOEMEGGOOK_ID", "") or "").strip()
        domeggook_pw = (getattr(config, "DOEMEGGOOK_PW", "") or "").strip()
        ownerclan_id = (getattr(config, "OWNERCLAN_ID", "") or "").strip()
        ownerclan_pw = (getattr(config, "OWNERCLAN_PW", "") or "").strip()
    except ImportError:
        domeggook_id = domeggook_pw = ownerclan_id = ownerclan_pw = ""

    domeggook_ok = False
    ownerclan_ok = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            locale="ko-KR",
        )
        page = context.new_page()

        def _handle_dialog(dialog):
            try:
                dialog.accept()
            except Exception:
                pass
        page.on("dialog", _handle_dialog)

        if domeggook_id and domeggook_pw:
            domeggook_ok = login_domeggook(page, domeggook_id, domeggook_pw)
            time.sleep(random.uniform(2.0, 4.0))
        if ownerclan_id and ownerclan_pw:
            ownerclan_ok = login_ownerclan(page, ownerclan_id, ownerclan_pw)

        browser.close()

    status = {
        "domeggook": domeggook_ok,
        "ownerclan": ownerclan_ok,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False)
    print("로그인 상태 저장:", status)


if __name__ == "__main__":
    main()
