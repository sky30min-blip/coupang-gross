"""
네이버 데이터랩 쇼핑 인사이트 인기 검색어 스크래퍼 (API 방식)
- 네이버 내부 API 직접 호출 (Playwright 불필요)
- 핵심 카테고리 5개, 카테고리당 상위 50개 키워드 (총 250개 목표)
- 중복·노이즈 제거 후, 검색량 순으로 전체 인기순 정렬하여 trending_keywords.csv 저장
"""

import csv
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

# 기본 설정
API_URL = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
OUTPUT_FILE = "trending_keywords.csv"
KEYWORDS_PER_CATEGORY = 50   # 카테고리당 상위 50개 (총 250개 확보 목표)
PAGE_SIZE = 20
DELAY_BETWEEN_REQUESTS = 0.3  # 페이지 요청 간 대기 (속도 개선)
DELAY_BETWEEN_CATEGORIES = 2  # 카테고리 이동 시 대기

# 사람처럼 보이게 하는 헤더
HEADERS = {
    "Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}

# 핵심 카테고리 5개 (가성비 최적화)
DEFAULT_CATEGORIES = [
    ("출산/육아", "50000005"),
    ("생활/주방", "50000008"),
    ("패션잡화", "50000001"),
    ("스포츠/레저", "50000007"),
    ("가구/인테리어", "50000004"),
]


def get_date_range_1week():
    """최근 1주일 날짜 범위"""
    end = datetime.now()
    start = end - timedelta(days=7)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def fetch_keyword_rank_page(cid: str, start_date: str, end_date: str, page: int) -> dict | None:
    """한 페이지(20개) 키워드 순위 조회"""
    data = {
        "cid": cid,
        "timeUnit": "date",
        "startDate": start_date,
        "endDate": end_date,
        "age": "",
        "gender": "",
        "device": "",
        "page": str(page),
        "count": str(PAGE_SIZE),
    }
    try:
        r = requests.post(API_URL, headers=HEADERS, data=data, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  [API 오류] {e}")
    return None


def extract_keywords_from_response(js: dict, category: str, page_offset: int = 0) -> list[dict]:
    """API 응답에서 키워드·순위·변화 추이 추출"""
    results = []
    ranks = js.get("ranks") or []
    for i, item in enumerate(ranks):
        keyword = item.get("keyword", "")
        rank_val = item.get("rank") or (page_offset * PAGE_SIZE + i + 1)
        change = item.get("rankChange") or item.get("change") or "-"
        if not keyword:
            continue
        results.append({
            "category": category,
            "rank": rank_val,
            "keyword": keyword,
            "change_trend": str(change) if change else "-",
        })
    return results


def scrape_category(category_name: str, cid: str, start_date: str, end_date: str, max_keywords: int = KEYWORDS_PER_CATEGORY) -> list[dict]:
    """한 카테고리에 대해 상위 max_keywords개 키워드 수집"""
    collected = []
    page = 1
    while len(collected) < max_keywords:
        js = fetch_keyword_rank_page(cid, start_date, end_date, page)
        time.sleep(DELAY_BETWEEN_REQUESTS)
        if not js:
            break
        batch = extract_keywords_from_response(js, category_name, page - 1)
        if not batch:
            break
        collected.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        page += 1
        if page > 10:
            break
    return collected[:max_keywords]


VOLUME_API_INTERVAL = 0.25


def _fetch_search_volume(keyword: str) -> int:
    """네이버 검색광고 API로 월간 검색량 조회. 실패 시 0."""
    try:
        from naver_api_keys import CUSTOMER_ID, ACCESS_LICENSE, SECRET_KEY
        from naver_api import get_monthly_search_volume
        vol = get_monthly_search_volume(
            keyword=keyword,
            customer_id=CUSTOMER_ID,
            license_key=ACCESS_LICENSE,
            secret_key=SECRET_KEY,
        )
        return int(vol) if vol is not None else 0
    except Exception:
        return 0


def save_to_csv(keywords: list[dict], filepath: str):
    """CSV 파일로 저장 (데이터 없어도 헤더만 생성)"""
    fieldnames = ["category", "rank", "keyword", "change_trend", "search_volume"]
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        if keywords:
            writer.writerows(keywords)
    print(f"저장 완료: {path.absolute()} ({len(keywords)}건)")


def _is_meaningful_keyword(keyword: str) -> bool:
    """한 글자짜리·무의미한 키워드 제거"""
    kw = (keyword or "").strip()
    if not kw:
        return False
    if len(kw) <= 1:
        return False
    return True


def main():
    print("네이버 데이터랩 쇼핑 인사이트 스크래퍼 (API 방식)")
    print("-" * 50)

    start_date, end_date = get_date_range_1week()
    print(f"기간: {start_date} ~ {end_date} (최근 1주일)")
    print(f"카테고리: {len(DEFAULT_CATEGORIES)}개, 카테고리당 상위 {KEYWORDS_PER_CATEGORY}개")
    print()

    all_keywords = []
    for idx, (category_name, cid) in enumerate(DEFAULT_CATEGORIES):
        if idx > 0:
            time.sleep(DELAY_BETWEEN_CATEGORIES)
        print(f"카테고리: {category_name} (cid={cid}) 수집 중...")
        keywords = scrape_category(category_name, cid, start_date, end_date)
        all_keywords.extend(keywords)
        print(f"  -> {len(keywords)}개 키워드 수집")

    # 중복 제거: 동일 키워드는 첫 등장(첫 카테고리)만 유지
    seen_kw = set()
    unique = []
    for k in all_keywords:
        kw = (k.get("keyword") or "").strip()
        if kw in seen_kw:
            continue
        if not _is_meaningful_keyword(kw):
            continue
        seen_kw.add(kw)
        unique.append(k)

    print(f"\n중복·노이즈 제거 후 총 {len(unique)}개. 검색량 조회 중... (카테고리 무관 전체 인기순 정렬)")
    total = len(unique)
    for i, row in enumerate(unique):
        kw = row.get("keyword", "")
        vol = _fetch_search_volume(kw)
        row["search_volume"] = vol
        if (i + 1) % 20 == 0 or i == 0:
            print(f"  [{i + 1}/{total}] {kw} → {vol:,}")
        if i < total - 1:
            time.sleep(VOLUME_API_INTERVAL)

    unique.sort(key=lambda r: r.get("search_volume", 0) or 0, reverse=True)
    for i, row in enumerate(unique):
        row["rank"] = i + 1

    has_volume = any(r.get("search_volume", 0) for r in unique)
    if not has_volume:
        print("  ※ 검색량 API(naver_api_keys.py) 미설정 → 카테고리별 순서로 저장. 설정 후 재실행 시 전체 인기순 정렬됩니다.")

    save_to_csv(unique, OUTPUT_FILE)
    print(f"\n{OUTPUT_FILE}에 저장 완료. 전체 인기순(검색량↑) 1위~{len(unique)}위.")


if __name__ == "__main__":
    main()
