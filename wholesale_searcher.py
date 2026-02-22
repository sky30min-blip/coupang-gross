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

from playwright.sync_api import sync_playwright  # type: ignore[reportMissingImports]

# 네이버 검색광고 API (우승 상품 한 달 검색량 심화 분석용)
def _get_naver_search_volume(keyword: str) -> int | None:
    """순마진 15% 이상 우승 상품에 대해 네이버 한 달 검색량 조회. 실패 시 None."""
    try:
        import config
        from naver_api import get_monthly_search_volume
        vid = getattr(config, "CUSTOMER_ID", None)
        lic = getattr(config, "ACCESS_LICENSE", None)
        sec = getattr(config, "SECRET_KEY", None)
        if not (vid and lic and sec):
            return None
        val = get_monthly_search_volume(keyword, vid, lic, sec)
        return int(val) if val is not None else None
    except Exception:
        return None


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
BASE_DIR = Path(__file__).resolve().parent
DEBUG_SCREENSHOT_DIR = BASE_DIR / "debug_screenshots"

# 대형/부피 화물 제외 (Bulky & Heavy Item Exclusion)
BULKY_KEYWORDS_BLACKLIST = {
    "금고", "안마의자", "침대", "소파", "식탁", "냉장고", "세탁기", "에어컨", "책상", "옷장",
    "매트리스", "쇼파", "탁자", "수납장", "신발장", "붙박이장", "책장", "화장대", "텔레비전", "tv",
    "의자", "식탁의자", "침대프레임", "이불", "컴퓨터책상", "게이밍책상",
}
BULKY_PRODUCT_NAME_WORDS = {
    "설치형", "화물배송", "대형", "무거운", "조립식가구", "직접설치", "화물", "가구배송",
    "대형가구", "퀵배송", "설치", "조립", "침대매트리스", "킹침대", "퀸침대",
}
LIGHTWEIGHT_KEYWORDS = {
    "네임스티커", "필통", "양말", "스티커", "볼펜", "노트", "스티커북", "포스트잇",
    "클립", "풀", "테이프", "가위", "지우개", "리필", "심", "스티커팩",
}
SHIPPING_EXCLUDE_WORDS = {"착불", "화물"}  # 상품명에 있으면 일반 배송비(3천)로 불가 → 제외

# 본체가 아닌 부속품/소모품 제외 (상품명에 하나라도 있으면 제외)
ACCESSORY_EXCLUDE_WORDS = {
    "테이프", "박스", "봉투", "케이스", "부품", "소모품", "거치대",
    "리필", "심", "포장", "스티커부착", "매트", "커버", "가방", "파우치",
    "보관함", "정리함", "받침", "받침대", "홀더", "클리너", "세척",
}

# 복합 키워드에서 상품 일치용 토큰 추출 시 제외할 조사/접속
KEYWORD_STOP_PARTS = {"의", "에", "와", "과", "이", "가", "을", "를", "은", "는"}

# 도매가 허용 비율: 쿠팡 평균가 대비 (저가 상품 2만 이하는 5% 하한, 그 외 20% 하한), 상한 80%
PRICE_FLOOR_RATIO = 0.20       # 2만 원 초과 상품
PRICE_FLOOR_RATIO_LOW = 0.05   # 2만 원 이하 소형 상품 (네임스티커 등 박리다매)
PRICE_CEIL_RATIO = 0.80
COUPANG_LOW_PRICE_THRESHOLD = 20000  # 이 금액 이하면 저가 예외 적용

# 도매 사이트 로그인 URL (www / 비www 둘 다 시도)
DOEMEGGOOK_MAIN = "https://www.domeggook.com"
DOEMEGGOOK_LOGIN_URL = "https://www.domeggook.com/ssl/member/mem_loginForm.php"
DOEMEGGOOK_LOGIN_ALT = "https://domeggook.com/ssl/member/mem_loginForm.php"
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
    """niche_test.csv에서 S, A등급만 로드. 대형 화물 키워드(블랙리스트)는 제외."""
    path = Path(INPUT_CSV)
    if not path.exists():
        print(f"오류: {INPUT_CSV} 없음. 먼저 니치 테스트를 실행하세요.")
        return []
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            g = (row.get("grade") or "").strip().upper()
            if g not in ("S", "A"):
                continue
            kw = (row.get("keyword") or "").strip()
            if kw in BULKY_KEYWORDS_BLACKLIST:
                continue
            rows.append(row)
    return rows


def parse_price(text: str) -> int | None:
    """문자열에서 가격 숫자 추출 (쉼표 제거)"""
    if not text:
        return None
    nums = re.sub(r"[^\d]", "", str(text))
    return int(nums) if nums else None


def _safe_filename(keyword: str, max_len: int = 40) -> str:
    """스크린샷 파일명용: 키워드에서 파일명 불가 문자 제거"""
    s = re.sub(r'[\\/:*?"<>|\n\r]+', "_", str(keyword).strip())
    s = s[:max_len].strip() or "keyword"
    return s


def _keyword_tokens(keyword: str) -> list[str]:
    """복합 키워드에서 의미 있는 한글 토큰만 추출 (2자 이상, 조사 제외). 예: 귀멸의칼날피규어 → [귀멸, 칼날, 피규어]"""
    parts = re.findall(r"[가-힣]+", keyword)
    return [p for p in parts if len(p) >= 2 and p not in KEYWORD_STOP_PARTS]


def _filter_products_by_keyword(products: list[dict], keyword: str) -> list[dict]:
    """수집된 상품 중 상품명에 검색 키워드 토큰이 하나라도 포함된 것만 유지 (스크래퍼 단계 필터)."""
    kw = (keyword or "").strip()
    if not kw:
        return products
    tokens = _keyword_tokens(kw)
    if not tokens:
        return products
    name_norm = re.sub(r"\s+", "", kw)
    filtered = []
    for p in products:
        name = (p.get("name") or "").strip()
        if not name:
            continue
        if name_norm in re.sub(r"\s+", "", name):
            filtered.append(p)
            continue
        if any(t in name for t in tokens):
            filtered.append(p)
    return filtered


def _product_matches_keyword(name: str, keyword: str) -> bool:
    """
    키워드 매칭 완화: 핵심 단어가 포함되면 통과.
    - 전체 키워드가 상품명에 있으면 통과.
    - 복합 키워드(예: 졸업식꽃다발)면 핵심 토큰(졸업, 꽃다발) 중 하나라도 상품명에 있으면 인정.
    """
    name = (name or "").strip()
    kw = (keyword or "").strip()
    if not name or not kw:
        return False
    name_norm = re.sub(r"\s+", "", name)
    kw_norm = re.sub(r"\s+", "", kw)
    # 1) 전체 키워드가 상품명에 포함되면 통과
    if kw in name or kw_norm in name_norm:
        return True
    # 2) 복합 키워드: 핵심 토큰이 하나라도 상품명에 있으면 통과 (완화)
    tokens = _keyword_tokens(kw)
    if len(tokens) >= 2:
        in_name = sum(1 for t in tokens if t in name or t in name_norm)
        return in_name >= 1
    if len(tokens) == 1:
        return tokens[0] in name or tokens[0] in name_norm
    return False


def _filter_outlier_products(products: list[dict], keyword: str, coupang_avg: int) -> list[dict]:
    """
    조건부 필터 (우량 상품 보존).
    - 키워드 매칭 완화: 핵심 단어가 하나라도 포함되면 통과.
    - 저가 상품(쿠팡가 2만 이하): 도매가가 쿠팡가의 5%만 넘어도 통과 (네임스티커 등 박리다매).
    - 2만 원 초과: 기존 20% 하한·80% 상한 유지. 10% 미만은 여전히 부속품으로 제외.
    - 제외 단어 정교화: 박스/테이프 등이 있어도, 제목 15자 이상이고 키워드 포함이면 후보 유지 (세트 상품 등).
    """
    kw = keyword.strip()
    if not kw or coupang_avg <= 0:
        return products

    # 저가 상품(2만 이하): 5% 하한 / 2만 초과: 20% 하한
    if coupang_avg <= COUPANG_LOW_PRICE_THRESHOLD:
        floor = int(coupang_avg * PRICE_FLOOR_RATIO_LOW)
        min_ratio = 0.05  # 5% 미만만 부속품으로 제외
    else:
        floor = int(coupang_avg * PRICE_FLOOR_RATIO)
        min_ratio = 0.10
    ceil = int(coupang_avg * PRICE_CEIL_RATIO)

    filtered = []
    for p in products:
        price = p.get("price") or 0
        name = (p.get("name") or "").strip()

        # 1) 키워드 매칭 완화: 핵심 단어 포함 여부
        if not _product_matches_keyword(name, kw):
            continue

        # 2) 비정상적 저가: 쿠팡가 대비 min_ratio 미만은 제외 (저가는 5%, 그 외 10%)
        if price < coupang_avg * min_ratio:
            continue

        # 3) 허용 가격대: floor ~ ceil
        if price < floor or price > ceil:
            continue

        # 4) 제외 단어 정교화: 박스/테이프 등이 있어도 제목 15자 이상 + 키워드 포함이면 통과 (세트·본체 가능성)
        if any(w in name for w in ACCESSORY_EXCLUDE_WORDS):
            if not (len(name) >= 15 and _product_matches_keyword(name, kw)):
                continue

        filtered.append(p)
    return filtered


def _filter_bulky_and_shipping(products: list[dict], keyword: str) -> list[dict]:
    """
    대형/부피 화물·착불·화물배송 제외 (Bulky & Heavy Item Exclusion).
    - 상품명에 '착불', '화물' 포함 → 일반 배송비(3천 원)로 불가이므로 제외.
    - 상품명에 '설치형', '대형', '조립식가구' 등 포함 → 대형 화물로 제외.
    - 경량 상품 키워드(네임스티커, 필통, 양말 등)는 대형 상품명 필터만 느슨 적용(착불/화물은 그대로 제외).
    """
    kw = keyword.strip()
    is_lightweight = kw in LIGHTWEIGHT_KEYWORDS

    filtered = []
    for p in products:
        name = (p.get("name") or "").strip()

        # 배송비 현실화: 착불·화물이면 3천 원으로 감당 불가 → 제외 (경량도 동일 적용)
        if any(w in name for w in SHIPPING_EXCLUDE_WORDS):
            continue

        # 경량 상품은 대형 상품명 필터 미적용 (기회 보존)
        if is_lightweight:
            filtered.append(p)
            continue

        # 상품명에 대형/부피 관련 단어 포함 시 제외
        if any(w in name for w in BULKY_PRODUCT_NAME_WORDS):
            continue

        filtered.append(p)
    return filtered


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
        # 1) 메인 페이지 먼저 접속 (쿠키/세션 확보 후 로그인 페이지로)
        try:
            page.goto(DOEMEGGOOK_MAIN, wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)
        except Exception as e:
            print(f"  [도매꾹] 메인 접속 실패: {e}")
        # 2) 로그인 페이지 접속 (타임아웃 30초)
        login_ok = False
        for login_url in [DOEMEGGOOK_LOGIN_URL, DOEMEGGOOK_LOGIN_ALT]:
            try:
                page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
                login_ok = True
                break
            except Exception as e:
                print(f"  [도매꾹] 로그인 페이지 접속 실패: {e}")
        if not login_ok:
            print("  [도매꾹] 접속 불가. 인터넷/방화벽 또는 도매꾹 사이트 상태를 확인하세요.")
            return False
        time.sleep(2)
        _close_popups(page)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        time.sleep(1)
        _close_popups(page)

        # 로그인 폼 (mb_id, mb_password)
        id_sel = page.query_selector(
            "input[name='mb_id'], input[name='user_id'], input#mb_id, input[name='id']"
        )
        pw_sel = page.query_selector(
            "input[name='mb_password'], input[name='password'], input[type='password']"
        )
        if not id_sel or not pw_sel:
            print("  [도매꾹] 로그인 폼을 찾을 수 없습니다. (사이트 구조 변경 가능성)")
            return False

        id_sel.click()
        id_sel.fill("")
        id_sel.fill(user_id)
        time.sleep(0.3)
        pw_sel.click()
        pw_sel.fill("")
        pw_sel.fill(password)
        time.sleep(0.5)

        submit = page.query_selector(
            "input[type='submit'], button[type='submit'], .btn_login, button.btn-primary, "
            "[onclick*='login'], a.btn_login, .login_btn, [value='로그인']"
        )
        if submit and submit.is_visible():
            submit.click()
        else:
            page.keyboard.press("Enter")
        time.sleep(4)
        _close_popups(page)

        # 로그인 실패: "비밀번호가", "일치하지", "오류" 등
        body = (page.inner_text("body") or "").lower()
        if "비밀번호" in body and ("일치" in body or "오류" in body or "틀렸" in body):
            print("  [도매꾹] 로그인 실패 (아이디/비밀번호 확인)")
            return False
        # 아직 로그인 폼 페이지에 있으면 실패 ("login"만 보면 다른 페이지에서도 걸려서 로그인폼 URL만 확인)
        url_lower = page.url.lower()
        if "mem_loginform" in url_lower:
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
        # 도매꾹 검색어 인코딩: EUC-KR (한글 검색 필수)
        try:
            encoded = quote(keyword, encoding="euc-kr", safe="")
        except (TypeError, UnicodeEncodeError, LookupError):
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

        # 디버깅: 가격 파싱 직전 스크린샷 저장
        try:
            DEBUG_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            safe_kw = _safe_filename(keyword)
            page.screenshot(path=str(DEBUG_SCREENSHOT_DIR / f"debug_domeggook_{safe_kw}.png"))
        except Exception:
            pass

        products = []
        # 가격 셀렉터: 넓게 (span, strong, div 등 class에 price 포함 + 기존)
        price_selectors = (
            ".selling_price, .price, [class*='price'], .item_price, "
            "span[class*='price'], strong[class*='price'], div[class*='price'], "
            "em[class*='price'], b[class*='price']"
        )
        items = page.query_selector_all(".item, .product, tr, [class*='list'], [class*='prd'], tbody tr, .goods_item")
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
                # URL: 하위/부모 <a> 태그에서 href 추출 (도매꾹은 상대 경로만 쓸 수 있음 → 절대 URL로 변환)
                url_val = ""
                a = item.query_selector("a[href*='domeggook.com']")
                if a:
                    url_val = a.get_attribute("href") or ""
                if not url_val:
                    a = item.query_selector("a[href]")  # 상대 경로 링크도 수집 (예: /main/..., /board/...)
                    if a:
                        url_val = a.get_attribute("href") or ""
                if not url_val:
                    try:
                        url_val = item.evaluate(
                            "el => { const a = el.closest('a[href]'); return a ? (a.href || a.getAttribute('href') || '') : ''; }"
                        ) or ""
                    except Exception:
                        pass
                url_val = (url_val or "").strip()
                if not url_val or url_val.lower().startswith("javascript:"):
                    continue
                if url_val.startswith("http"):
                    pass
                elif url_val.startswith("/"):
                    url_val = "https://www.domeggook.com" + url_val
                else:
                    url_val = "https://www.domeggook.com/" + url_val
                products.append({"name": name or "상품", "price": price, "url": url_val})
                if len(products) >= 3:
                    break
            except Exception:
                continue
        # 2) 폴백: 링크 텍스트에 "원" 포함 (상대 경로 링크 포함)
        if not products:
            links = page.query_selector_all("a[href*='domeggook.com/'], a[href^='/']")
            for a in links:
                try:
                    text = a.inner_text() or ""
                    href = (a.get_attribute("href") or "").strip()
                    if not href or href.lower().startswith("javascript:"):
                        continue
                    if not href.startswith("/") and "domeggook.com" not in href:
                        continue
                    match = re.search(r"([\d,]+)\s*원", text)
                    if match:
                        price = parse_price(match.group(1))
                        if price and 100 <= price <= 100_000_000:
                            if href.startswith("/"):
                                url_val = "https://www.domeggook.com" + href
                            elif href.startswith("http"):
                                url_val = href
                            else:
                                url_val = "https://www.domeggook.com" + href
                            products.append({"name": text[:80].strip(), "price": price, "url": url_val})
                            if len(products) >= 3:
                                break
                except Exception:
                    continue
        # 3) 폴백: 페이지 전체에서 가격처럼 보이는 숫자(숫자+원) 수집
        if not products:
            try:
                body_text = page.inner_text("body") or ""
                for m in re.finditer(r"([\d,]+)\s*원", body_text):
                    pv = parse_price(m.group(1))
                    if pv and 100 <= pv <= 100_000_000:
                        products.append({"name": "상품", "price": pv, "url": ""})
                        if len(products) >= 3:
                            break
            except Exception:
                pass
        # 키워드 관련성 필터: 상품명에 검색 키워드 토큰이 하나라도 있어야 함
        raw_count = len(products)
        products = _filter_products_by_keyword(products, keyword)
        if raw_count > 0 and len(products) == 0:
            try:
                with open(BASE_DIR / "no_results_log.txt", "a", encoding="utf-8") as f:
                    f.write(f"{keyword}: 검색결과있으나 키워드 불일치로 전체 제외\n")
            except Exception:
                pass
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

        # 디버깅: 가격 파싱 직전 스크린샷 저장
        try:
            DEBUG_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            safe_kw = _safe_filename(keyword)
            page.screenshot(path=str(DEBUG_SCREENSHOT_DIR / f"debug_ownerclan_{safe_kw}.png"))
        except Exception:
            pass

        products = []
        # 우선 셀렉터: .prd-item, .goods-item, [class*='prd']
        items = page.query_selector_all(
            ".prd-item, .goods-item, [class*='prd'], .product-item, .item, [class*='product'], "
            ".search-result-item, tr[class*='list']"
        )
        # 가격 셀렉터 넓게: span, strong, em, div 등
        price_selectors = (
            ".price em, .prd-price, [class*='price'], "
            "span[class*='price'], strong[class*='price'], em[class*='price'], div[class*='price']"
        )
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
                    a = item.query_selector("a[href*='product'], a[href*='detail'], a[href]")
                    url_val = (a.get_attribute("href") or "") if a else ""
                    url_val = (url_val or "").strip()
                    if not url_val or url_val.lower().startswith("javascript:"):
                        continue
                    if url_val.startswith("http"):
                        pass
                    elif url_val.startswith("/"):
                        url_val = "https://www.ownerclan.com" + url_val
                    else:
                        url_val = "https://www.ownerclan.com/" + url_val
                    products.append({
                        "name": (text[:80] + "…") if len(text) > 80 else text.strip(),
                        "price": price,
                        "url": url_val,
                    })
                    if len(products) >= 3:
                        break
            except Exception:
                continue
        # 키워드 관련성 필터: 상품명에 검색 키워드 토큰이 하나라도 있어야 함
        raw_count = len(products)
        products = _filter_products_by_keyword(products, keyword)
        if raw_count > 0 and len(products) == 0:
            try:
                with open(BASE_DIR / "no_results_log.txt", "a", encoding="utf-8") as f:
                    f.write(f"{keyword}: 검색결과있으나 키워드 불일치로 전체 제외\n")
            except Exception:
                pass
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
        # headless=False: 브라우저 창 표시 (디버깅·봇 감지 완화)
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="ko-KR",
            viewport={"width": 1920, "height": 1080},
        )
        # 자동화 감지 완화
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
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

            # 부속품/이상치 제거 (가격 하한·키워드 일치·고가 최소 도매가, 쿠팡 2만 원 이하는 예외)
            all_products = _filter_outlier_products(all_products, kw, coupang_avg)
            if not all_products:
                print(f"  -> 필터 후 후보 없음 (부속품/키워드불일치 제외)")
                try:
                    log_path = base_dir / "no_results_log.txt"
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(f"{kw}\t필터제외\t{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                except Exception:
                    pass
                continue

            # 대형/부피 화물·착불·화물배송 제외 (경량 상품은 대형 상품명 필터만 느슨)
            all_products = _filter_bulky_and_shipping(all_products, kw)
            if not all_products:
                print(f"  -> 필터 후 후보 없음 (대형화물/착불·화물 제외)")
                try:
                    log_path = base_dir / "no_results_log.txt"
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(f"{kw}\t대형/착불제외\t{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
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
            link = (min_prod.get("url") or "").strip()
            # 저장 전 최종 검수: 절대 URL이 아니면 소싱처별 베이스 URL 강제 부착
            if link and not link.startswith("http"):
                base = "https://www.domeggook.com" if "도매꾹" in final_source else "https://www.ownerclan.com"
                link = base + (link if link.startswith("/") else "/" + link)
            if not link:
                link = "검색결과없음"

            # 우승 상품(순마진 15% 이상) → 네이버 검색광고 API로 한 달 검색량 심화 분석 (403/에러 시 중단 없이 'API 확인 필요' 표기)
            try:
                monthly_search_volume = _get_naver_search_volume(kw)
            except Exception:
                monthly_search_volume = None
            if monthly_search_volume is not None:
                print(f"  -> [심화] 한 달 검색량: {monthly_search_volume:,}회")
            else:
                print(f"  -> [심화] 한 달 검색량: API 확인 필요")

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
                "wholesale_link": link,
                "monthly_search_volume": monthly_search_volume,
            })
            print(f"  -> 최종 소싱처: {final_source} | 도매 {wholesale_price:,}원 | 최종 순마진액 {net_profit:,.0f}원 | 순마진율 {net_margin_pct:.1f}% ✓")
            print(f"  -> 최종 소싱처 링크: {link}")

        browser.close()

    # 저장: final_sourcing_list.csv (스크립트와 동일 폴더에 절대 경로로 저장 → 대시보드와 경로 일치)
    out = BASE_DIR / OUTPUT_CSV
    fieldnames = ["키워드", "쿠팡가", "도매가(최저)", "광고비", "부가세", "최종 순마진액", "순마진율", "한 달 검색량", "태그", "최종 소싱처", "도매처링크"]
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            sv = r.get("monthly_search_volume")
            sv_display = sv if sv is not None else "API 확인 필요"
            tag = "[강력 추천]" if (sv or 0) >= 5000 and r["net_margin_ratio"] >= 0.15 else ""
            writer.writerow({
                "키워드": r["keyword"],
                "쿠팡가": r["coupang_price"],
                "도매가(최저)": r["wholesale_price"],
                "광고비": r["ad_cost"],
                "부가세": r["vat_cost"],
                "최종 순마진액": r["net_profit"],
                "순마진율": f"{r['net_margin_pct']}%",
                "한 달 검색량": sv_display,
                "태그": tag,
                "최종 소싱처": r["final_source"],
                "도매처링크": r["wholesale_link"],
            })

    print()
    print(f"저장 완료: {out.absolute()} ({len(results)}건, 순마진 {TARGET_NET_MARGIN*100:.0f}% 이상)")


if __name__ == "__main__":
    main()
