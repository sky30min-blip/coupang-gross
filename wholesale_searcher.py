"""
wholesale_searcher.py - [자동 로그인 최저가 탐지기]
config.py 계정·수익 상수 연동 | 회원 전용가 기준 최저가 탐지
→ calculate_net_profit()로 실제 정산액·최종 순이익·순마진율 산출
→ TARGET_NET_MARGIN 미만 제외, 최종 소싱처 표기
"""

import csv
import json
import re
import sys
import time
import random
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

# config.py 수익 상수 (없으면 기본값)
def _get_config():
    base = Path(__file__).resolve().parent
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    try:
        import config
        return (
            getattr(config, "COUPANG_FEE_RATE", 0.11),
            getattr(config, "SHIPPING_COST", 3000),
            getattr(config, "VAT_RATE", 0.10),
            getattr(config, "AD_RATE", 0.15),
            getattr(config, "TARGET_NET_MARGIN", 0.15),
        )
    except ImportError:
        return (0.11, 3000, 0.10, 0.15, 0.15)

COUPANG_FEE_RATE, SHIPPING_COST, VAT_RATE, AD_RATE, TARGET_NET_MARGIN = _get_config()

INPUT_CSV = "niche_test.csv"
OUTPUT_CSV = "final_sourcing_list.csv"
DELAY_MIN = 2.0
DELAY_MAX = 4.0

# 도매 사이트 로그인 URL
DOEMEGGOOK_LOGIN_URL = "https://www.domeggook.com/ssl/member/mem_loginForm.php"
OWNERCLAN_LOGIN_URL = "https://www.ownerclan.com/"

# 도매꾹 검색 URL (sw=검색어, sf=ttl 상품명)
DOEMEGGOOK_BASE = "https://www.domeggook.com/main/item/itemList.php"
# 오너클랜 검색 (키워드 검색)
OWNERCLAN_BASE = "https://www.ownerclan.com/V2/product/search.php"


def calculate_net_profit(coupang_price: float, wholesale_price: float) -> tuple[float, float, float, float, float]:
    """
    config 상수 기반 수익 계산 (수수료·광고비·배송비·부가세 반영).
    반환: (실제 정산액, 최종 순이익, 순마진율 0~1, 광고비, 부가세)
    """
    # 실제 정산액 = 쿠팡 판매가 * (1 - COUPANG_FEE_RATE)
    actual_settlement = coupang_price * (1 - COUPANG_FEE_RATE)
    # 광고비 = 판매가의 AD_RATE (로켓그로스 노출 필수)
    ad_cost = coupang_price * AD_RATE
    # 매입 부가세 = 도매가 * VAT_RATE
    vat_cost = wholesale_price * VAT_RATE
    # 최종 순이익 = 실제 정산액 - 도매가 - 배송비 - 광고비 - 부가세
    net_profit = actual_settlement - wholesale_price - SHIPPING_COST - ad_cost - vat_cost
    # 순마진율 = 최종 순이익 / 쿠팡 판매가 (쿠팡가 0이면 0)
    net_margin_ratio = (net_profit / coupang_price) if coupang_price else 0.0
    return actual_settlement, net_profit, net_margin_ratio, ad_cost, vat_cost


def load_keywords() -> list[dict]:
    """niche_test.csv에서 S, A등급만 로드"""
    path = Path(INPUT_CSV)
    if not path.exists():
        print(f"오류: {INPUT_CSV} 없음. 먼저 니치 테스트를 실행하세요.")
        return []
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            g = (row.get("grade") or "").strip().upper()
            if g in ("S", "A"):
                rows.append(row)
    return rows


def parse_price(text: str) -> int | None:
    """문자열에서 가격 숫자 추출 (쉼표 제거)"""
    if not text:
        return None
    nums = re.sub(r"[^\d]", "", str(text))
    return int(nums) if nums else None


def _close_popups(page) -> None:
    """팝업/공지사항 창 자동 닫기 (닫기 버튼 클릭 시도)"""
    selectors = [
        ".popup-close, .close, .btn-close, #popup-close, .modal-close",
        "[onclick*='close'], [onclick*='닫기']",
        ".layer-close, .popup_close",
    ]
    for sel in selectors:
        try:
            btns = page.query_selector_all(sel)
            for btn in btns[:3]:
                if btn.is_visible():
                    btn.click(timeout=1000)
                    time.sleep(0.3)
        except Exception:
            pass


def login_domeggook(page, user_id: str, password: str) -> bool:
    """도매꾹 로그인. 성공 True, 실패/계정없음 False."""
    if not user_id or not password:
        return False
    try:
        page.goto(DOEMEGGOOK_LOGIN_URL, wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)
        _close_popups(page)

        # 폼 필드 (mb_id, mb_password 등)
        id_sel = page.query_selector("input[name='mb_id'], input[name='user_id'], input#mb_id, input[name='id']")
        pw_sel = page.query_selector("input[name='mb_password'], input[name='password'], input[type='password']")
        if not id_sel or not pw_sel:
            print("  [도매꾹] 로그인 폼을 찾을 수 없습니다.")
            return False

        id_sel.fill(user_id)
        pw_sel.fill(password)
        time.sleep(0.5)

        submit = page.query_selector(
            "input[type='submit'], button[type='submit'], .btn_login, button.btn-primary, [onclick*='login']"
        )
        if submit:
            submit.click()
        else:
            page.keyboard.press("Enter")
        time.sleep(3)
        _close_popups(page)

        # 로그인 실패: "비밀번호가", "일치하지", "오류" 등
        body = (page.inner_text("body") or "").lower()
        if "비밀번호" in body and ("일치" in body or "오류" in body or "틀렸" in body):
            print("  [도매꾹] 로그인 실패 (아이디/비밀번호 확인)")
            return False
        if "mem_login" in page.url.lower() or "login" in page.url.lower():
            print("  [도매꾹] 로그인 실패 (페이지 이동 없음)")
            return False
        return True
    except Exception as e:
        print(f"  [도매꾹] 로그인 예외: {e}")
        return False


def _random_delay() -> None:
    """봇 차단 방지: 2~4초 랜덤 대기"""
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def login_all_sites(
    page,
    domeggook_id: str,
    domeggook_pw: str,
    ownerclan_id: str,
    ownerclan_pw: str,
) -> tuple[bool, bool]:
    """
    config.py 정보로 도매꾹·오너클랜 자동 로그인.
    세션(쿠키) 유지로 이후 모든 검색이 '회원 전용가'로 진행됨.
    반환: (도매꾹_성공, 오너클랜_성공)
    """
    domeggook_ok = False
    ownerclan_ok = False

    if domeggook_id and domeggook_pw:
        print("[login_all_sites] 도매꾹 로그인 중...")
        domeggook_ok = login_domeggook(page, domeggook_id, domeggook_pw)
        print(f"  도매꾹: {'✓ 회원 전용가 적용' if domeggook_ok else '✗ 실패'}")
        _random_delay()

    if ownerclan_id and ownerclan_pw:
        print("[login_all_sites] 오너클랜 로그인 중...")
        ownerclan_ok = login_ownerclan(page, ownerclan_id, ownerclan_pw)
        print(f"  오너클랜: {'✓ 회원 전용가 적용' if ownerclan_ok else '✗ 실패'}")
        _random_delay()

    return domeggook_ok, ownerclan_ok


def login_ownerclan(page, user_id: str, password: str) -> bool:
    """오너클랜 로그인. 성공 True, 실패/계정없음 False."""
    if not user_id or not password:
        return False
    try:
        page.goto(OWNERCLAN_LOGIN_URL, wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)
        _close_popups(page)

        # 로그인 링크/버튼 클릭 후 폼 표시되는 경우
        login_btn = page.query_selector("a[href*='login'], .login-btn, #loginBtn, .btn-login, [class*='login']")
        if login_btn and login_btn.is_visible():
            login_btn.click()
            time.sleep(2)

        id_sel = page.query_selector(
            "input[name='mb_id'], input[name='user_id'], input[name='id'], input#userId, input[name='username']"
        )
        pw_sel = page.query_selector("input[name='mb_password'], input[name='password'], input[type='password']")
        if not id_sel or not pw_sel:
            print("  [오너클랜] 로그인 폼을 찾을 수 없습니다.")
            return False

        id_sel.fill(user_id)
        pw_sel.fill(password)
        time.sleep(0.5)

        submit = page.query_selector(
            "input[type='submit'], button[type='submit'], .btn_login, button.btn-primary, [onclick*='login']"
        )
        if submit:
            submit.click()
        else:
            page.keyboard.press("Enter")
        time.sleep(3)
        _close_popups(page)

        body = (page.inner_text("body") or "").lower()
        if "비밀번호" in body and ("일치" in body or "오류" in body or "틀렸" in body):
            print("  [오너클랜] 로그인 실패 (아이디/비밀번호 확인)")
            return False
        # 로그인 성공: 로그인 페이지에서 벗어남
        return True
    except Exception as e:
        print(f"  [오너클랜] 로그인 예외: {e}")
        return False


def search_domeggook(page, keyword: str) -> list[dict]:
    """도매꾹에서 키워드 검색 → 상위 3개 상품 {name, price, url}"""
    try:
        try:
            encoded = quote(keyword, encoding="euc-kr", safe="")
        except TypeError:
            encoded = quote(keyword, safe="")
        url = f"{DOEMEGGOOK_BASE}?sw={encoded}&sf=ttl"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)
        _close_popups(page)

        # 동적 콘텐츠 로딩 대기
        try:
            page.wait_for_selector(".item, .product", timeout=5000)
        except Exception:
            pass

        products = []
        # 가격 셀렉터: .selling_price, .price, [class*='price'], .item_price
        price_selectors = ".selling_price, .price, [class*='price'], .item_price"
        items = page.query_selector_all(".item, .product, tr, [class*='list'], [class*='prd']")
        for item in items[:20]:
            try:
                price_el = item.query_selector(price_selectors)
                price = None
                if price_el:
                    txt = price_el.inner_text() or ""
                    m = re.search(r"([\d,]+)", txt)
                    if m:
                        price = parse_price(m.group(1))
                if not price:
                    txt = item.inner_text() or ""
                    for m in re.finditer(r"([\d,]+)\s*원", txt):
                        pv = parse_price(m.group(1))
                        if pv and 100 <= pv <= 100_000_000:
                            price = pv
                            break
                if not price or not (100 <= price <= 100_000_000):
                    continue
                # 상품명: .item_name, .product_name, h3, h4
                name_el = item.query_selector(".item_name, .product_name, h3, h4")
                name = (name_el.inner_text() or "").strip() if name_el else ""
                if not name:
                    name = (item.inner_text() or "")[:80].strip()
                # URL: 하위/부모 <a> 태그에서 href 추출
                a = item.query_selector("a[href*='domeggook.com']")
                url_val = ""
                if a:
                    url_val = a.get_attribute("href") or ""
                if not url_val:
                    try:
                        url_val = item.evaluate(
                            "el => { const a = el.closest('a[href*=\"domeggook\"]'); return a ? (a.href || '') : ''; }"
                        ) or ""
                    except Exception:
                        pass
                if url_val and not url_val.startswith("http"):
                    url_val = "https://www.domeggook.com" + url_val
                products.append({"name": name or "상품", "price": price, "url": url_val})
                if len(products) >= 3:
                    break
            except Exception:
                continue
        # 2) 기존 방식 폴백: 링크 텍스트에 "원" 포함
        if not products:
            links = page.query_selector_all("a[href*='domeggook.com/']")
            for a in links:
                try:
                    text = a.inner_text() or ""
                    href = a.get_attribute("href") or ""
                    if "domeggook.com/" not in href:
                        continue
                    match = re.search(r"([\d,]+)\s*원", text)
                    if match:
                        price = parse_price(match.group(1))
                        if price and 100 <= price <= 100_000_000:
                            url_val = href if href.startswith("http") else "https://www.domeggook.com" + href
                            products.append({"name": text[:80].strip(), "price": price, "url": url_val})
                            if len(products) >= 3:
                                break
                except Exception:
                    continue
        return products[:3]
    except Exception:
        return []


def search_ownerclan(page, keyword: str) -> list[dict]:
    """오너클랜에서 키워드 검색 → 상위 3개 상품"""
    try:
        page.goto("https://www.ownerclan.com/V2/product/search.php", wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)
        _close_popups(page)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        # 검색 입력창 찾아서 입력
        search_input = page.query_selector(
            "input[name='searchKeyword'], input[name='keyword'], input[placeholder*='검색'], "
            "input[placeholder*='키워드'], #searchKeyword, .search-input input"
        )
        if search_input:
            search_input.fill(keyword)
            time.sleep(1)
            page.keyboard.press("Enter")
        else:
            # URL 직접 시도
            enc = quote(keyword)
            page.goto(
                f"https://www.ownerclan.com/V2/product/search.php?searchKeyword={enc}",
                wait_until="domcontentloaded",
                timeout=15000,
            )
        time.sleep(2)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        products = []
        # 우선 셀렉터: .prd-item, .goods-item, [class*='prd']
        items = page.query_selector_all(
            ".prd-item, .goods-item, [class*='prd'], .product-item, .item, [class*='product'], "
            ".search-result-item, tr[class*='list']"
        )
        price_selectors = ".price em, .prd-price, [class*='price']"
        for item in items[:15]:
            try:
                # 가격: .price em, .prd-price, [class*='price'] 우선
                price = None
                price_el = item.query_selector(price_selectors)
                if price_el:
                    txt = price_el.inner_text() or ""
                    m = re.search(r"([\d,]+)", txt)
                    if m:
                        v = parse_price(m.group(1))
                        if v and 100 <= v <= 100_000_000:
                            price = v
                if not price:
                    text = item.inner_text()
                    for m in re.finditer(r"[\d,]+(?:\s*원)?", text):
                        v = parse_price(m.group(0))
                        if v and 100 <= v <= 100_000_000:
                            price = v
                            break
                if price:
                    text = item.inner_text()
                    a = item.query_selector("a[href*='product'], a[href*='detail']")
                    url_val = (a.get_attribute("href") or "") if a else ""
                    if url_val and not url_val.startswith("http"):
                        url_val = "https://www.ownerclan.com" + url_val
                    products.append({
                        "name": (text[:80] + "…") if len(text) > 80 else text.strip(),
                        "price": price,
                        "url": url_val,
                    })
                    if len(products) >= 3:
                        break
            except Exception:
                continue
        return products[:3]
    except Exception:
        return []


def main():
    print("=" * 50)
    print(" [자동 로그인 최저가 탐지기] - 도매꾹 & 오너클랜")
    print("=" * 50)
    print("-" * 50)

    keywords_data = load_keywords()
    if not keywords_data:
        return
    print(f"S/A등급 키워드 {len(keywords_data)}개 로드")

    results = []

    # config.py에서 개인 회원 계정 정보 로드
    base_dir = Path(__file__).resolve().parent
    if str(base_dir) not in sys.path:
        sys.path.insert(0, str(base_dir))
    try:
        import config
        domeggook_id = (getattr(config, "DOEMEGGOOK_ID", "") or "").strip()
        domeggook_pw = (getattr(config, "DOEMEGGOOK_PW", "") or "").strip()
        ownerclan_id = (getattr(config, "OWNERCLAN_ID", "") or "").strip()
        ownerclan_pw = (getattr(config, "OWNERCLAN_PW", "") or "").strip()
    except ImportError:
        domeggook_id = domeggook_pw = ownerclan_id = ownerclan_pw = ""

    if not (domeggook_id and domeggook_pw) and not (ownerclan_id and ownerclan_pw):
        print("※ config.py에 DOEMEGGOOK_ID/PW, OWNERCLAN_ID/PW를 입력하면 개인 회원 전용 가격을 수집합니다.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            locale="ko-KR",
        )
        page = context.new_page()

        # 네이티브 다이얼로그(alert/confirm/prompt) 자동 수락/닫기
        def _handle_dialog(dialog):
            try:
                dialog.accept()  # alert/confirm 모두 수락 후 닫기
            except Exception:
                pass
        page.on("dialog", _handle_dialog)

        # 프로그램 시작 시 모든 사이트 자동 로그인 (세션 유지 → 회원 전용가 적용)
        domeggook_ok, ownerclan_ok = login_all_sites(
            page, domeggook_id, domeggook_pw, ownerclan_id, ownerclan_pw
        )
        _random_delay()  # 로그인 후 검색 전 랜덤 대기 (봇 차단 방지)

        # 대시보드 신호등용 로그인 상태 저장
        try:
            status_path = base_dir / "wholesale_login_status.json"
            status = {
                "domeggook": domeggook_ok,
                "ownerclan": ownerclan_ok,
                "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            with open(status_path, "w", encoding="utf-8") as f:
                json.dump(status, f, ensure_ascii=False)
        except Exception:
            pass

        for i, row in enumerate(keywords_data):
            kw = (row.get("keyword") or "").strip()
            coupang_avg = int(row.get("avg_price") or 0)
            if not kw or coupang_avg <= 0:
                continue

            print(f"[{i + 1}/{len(keywords_data)}] {kw} (쿠팡 평균 {coupang_avg:,}원)")

            all_products = []

            # 도매꾹
            try:
                prods = search_domeggook(page, kw)
                for p in prods:
                    p["site"] = "도매꾹"
                    all_products.append(p)
            except Exception:
                pass
            _random_delay()

            # 오너클랜
            try:
                prods = search_ownerclan(page, kw)
                for p in prods:
                    p["site"] = "오너클랜"
                    all_products.append(p)
            except Exception:
                pass
            _random_delay()

            if not all_products:
                print(f"  -> 검색결과없음")
                try:
                    log_path = base_dir / "no_results_log.txt"
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(f"{kw}\t{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                except Exception:
                    pass
                continue

            # 수익 계산 (config 연동)
            min_prod = min(all_products, key=lambda x: x["price"])
            wholesale_price = min_prod["price"]
            _, net_profit, net_margin_ratio, ad_cost, vat_cost = calculate_net_profit(coupang_avg, wholesale_price)
            net_margin_pct = net_margin_ratio * 100

            # TARGET_NET_MARGIN 미만 → 과감히 제외
            if net_margin_ratio < TARGET_NET_MARGIN:
                print(f"  -> 도매 최저 {wholesale_price:,}원, 순이익 {net_profit:,.0f}원, 순마진 {net_margin_pct:.1f}% (목표 {TARGET_NET_MARGIN*100:.0f}% 미만 제외)")
                continue

            # 최종 소싱처: 도매꾹/오너클랜 중 더 저렴한 곳
            final_source = min_prod.get("site", "도매꾹")
            link = min_prod.get("url") or ""
            if link and not link.startswith("http"):
                link = "https://www.domeggook.com" + link if "도매꾹" in final_source else "https://www.ownerclan.com" + link

            results.append({
                "keyword": kw,
                "coupang_price": coupang_avg,
                "wholesale_price": wholesale_price,
                "net_profit": int(round(net_profit, 0)),
                "net_margin_ratio": net_margin_ratio,
                "net_margin_pct": round(net_margin_pct, 1),
                "ad_cost": int(round(ad_cost, 0)),
                "vat_cost": int(round(vat_cost, 0)),
                "final_source": final_source,
                "wholesale_link": link or "검색결과없음",
            })
            print(f"  -> 최종 소싱처: {final_source} | 도매 {wholesale_price:,}원 | 최종 순마진액 {net_profit:,.0f}원 | 순마진율 {net_margin_pct:.1f}% ✓")

        browser.close()

    # 저장: final_sourcing_list.csv (광고비·부가세 컬럼 포함)
    out = Path(OUTPUT_CSV)
    fieldnames = ["키워드", "쿠팡가", "도매가(최저)", "광고비", "부가세", "최종 순마진액", "순마진율", "최종 소싱처", "도매처링크"]
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "키워드": r["keyword"],
                "쿠팡가": r["coupang_price"],
                "도매가(최저)": r["wholesale_price"],
                "광고비": r["ad_cost"],
                "부가세": r["vat_cost"],
                "최종 순마진액": r["net_profit"],
                "순마진율": f"{r['net_margin_pct']}%",
                "최종 소싱처": r["final_source"],
                "도매처링크": r["wholesale_link"],
            })

    print()
    print(f"저장 완료: {out.absolute()} ({len(results)}건, 순마진 {TARGET_NET_MARGIN*100:.0f}% 이상)")


if __name__ == "__main__":
    main()
