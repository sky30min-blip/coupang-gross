"""
네이버 데이터랩 쇼핑 인사이트 인기 검색어 스크래퍼 (API 방식)
- 네이버 내부 API 직접 호출 (Playwright 불필요)
- 생활/주방 → 생활/건강(cid:50000008), 디지털/가전(cid:50000003)
- 최근 1주일 TOP 100 인기 검색어 수집
- trending_keywords.csv 저장
"""

import csv
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

# 기본 설정
API_URL = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
OUTPUT_FILE = "trending_keywords.csv"
TOP_KEYWORDS_COUNT = 100
PAGE_SIZE = 20
DELAY_BETWEEN_REQUESTS = 0.5  # 차단 방지를 위한 요청 간 대기(초)

# 사람처럼 보이게 하는 헤더
HEADERS = {
    "Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}

# 카테고리 ID (네이버 쇼핑 1단계 분야)
# 생활/주방 → 네이버에는 '생활/건강'만 있음. 생활/주방은 서브카테고리일 수 있음.
CATEGORIES = {
    "생활/건강": "50000008",   # 생활 관련 (생활/주방에 가까움)
    "디지털/가전": "50000003",
}
# 사용자가 요청한 '생활/주방' → 생활/건강으로 매핑
DEFAULT_CATEGORIES = [
    ("생활/주방", "50000008"),  # 생활/건강 cid 사용
    ("디지털/가전", "50000003"),
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


def scrape_category(category_name: str, cid: str, start_date: str, end_date: str) -> list[dict]:
    """한 카테고리에 대해 TOP 100 키워드 수집"""
    collected = []
    page = 1
    while len(collected) < TOP_KEYWORDS_COUNT:
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
        if page > 10:  # 10페이지 = 200개, 여유 있게
            break
    return collected[:TOP_KEYWORDS_COUNT]


def save_to_csv(keywords: list[dict], filepath: str):
    """CSV 파일로 저장 (데이터 없어도 헤더만 생성)"""
    fieldnames = ["category", "rank", "keyword", "change_trend"]
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        if keywords:
            writer.writerows(keywords)
    print(f"저장 완료: {path.absolute()} ({len(keywords)}건)")


def main():
    print("네이버 데이터랩 쇼핑 인사이트 스크래퍼 (API 방식)")
    print("-" * 50)

    start_date, end_date = get_date_range_1week()
    print(f"기간: {start_date} ~ {end_date} (최근 1주일)")
    print()

    all_keywords = []
    for category_name, cid in DEFAULT_CATEGORIES:
        print(f"카테고리: {category_name} (cid={cid}) 수집 중...")
        keywords = scrape_category(category_name, cid, start_date, end_date)
        all_keywords.extend(keywords)
        print(f"  -> {len(keywords)}개 키워드 수집")

    # 중복 제거 (카테고리+키워드 기준)
    seen = set()
    unique = []
    for k in all_keywords:
        key = (k["category"], k["keyword"])
        if key not in seen:
            seen.add(key)
            unique.append(k)

    save_to_csv(unique, OUTPUT_FILE)
    print(f"\n총 {len(unique)}개 키워드를 {OUTPUT_FILE}에 저장했습니다.")


if __name__ == "__main__":
    main()
