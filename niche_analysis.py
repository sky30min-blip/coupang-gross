"""
쿠팡 니치 파인더 - 경쟁 강도 분석 (쿠팡 파트너스 API 사용)
trending_keywords.csv를 읽어 API로 검색 → 로켓 개수, 평균가격, 등급
"""

import csv
import time
from pathlib import Path

from coupang_api import search_products

# 설정
TRENDING_CSV = "trending_keywords.csv"
OUTPUT_CSV = "niche_analysis.csv"
PRODUCTS_PER_KEYWORD = 20  # API 샘플링 한계 보완 (10~36)
MAX_KEYWORDS = 50
DELAY_BETWEEN_CALLS = 2


def get_grade(rocket_count: int) -> str:
    if rocket_count < 5:
        return "S"
    if rocket_count <= 10:
        return "A"
    return "B"


def analyze_keyword_api(keyword: str, access_key: str, secret_key: str) -> dict:
    """쿠팡 파트너스 API로 상품 검색 후 분석"""
    result = {
        "rocket_count": 0,
        "total_products": 0,
        "avg_price": 0,
        "max_reviews": 0,
        "grade": "B",
    }

    js = search_products(keyword, PRODUCTS_PER_KEYWORD, access_key, secret_key)
    if not js:
        return result

    products = []
    data = js.get("data", js)
    if isinstance(data, dict):
        products = (
            data.get("productData")
            or data.get("products")
            or data.get("productList")
            or data.get("items")
            or data.get("results")
            or []
        )
    elif isinstance(data, list):
        products = data

    if not products and js:
        if not getattr(analyze_keyword_api, "_debug_done", False):
            analyze_keyword_api._debug_done = True
            print("  [디버그] rCode:", js.get("rCode"), "| rMessage:", js.get("rMessage", "")[:80])
            print("  [참고] data 없음. 쿠팡 파트너스 최종승인+검색API 권한 확인. subId 추가됨.")
        return result

    result["total_products"] = len(products)
    prices = []
    rocket_count = 0

    for p in products:
        if not isinstance(p, dict):
            continue
        if p.get("isRocket") or p.get("rocket") or p.get("isRocketDelivery") or "로켓" in str(p.get("productName", "")):
            rocket_count += 1
        price = p.get("productPrice") or p.get("price") or p.get("salePrice") or p.get("product_price")
        if price is not None:
            try:
                prices.append(int(price))
            except (ValueError, TypeError):
                pass

    result["rocket_count"] = rocket_count
    result["avg_price"] = round(sum(prices) / len(prices), 0) if prices else 0
    result["grade"] = get_grade(rocket_count)
    return result


def main():
    print("쿠팡 니치 파인더 (파트너스 API)")
    print("-" * 50)

    try:
        from coupang_config import COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY
    except ImportError:
        print("오류: coupang_config.py가 없습니다.")
        print("  coupang_config.example.py를 복사하여 coupang_config.py를 만들고")
        print("  COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY를 입력하세요.")
        return

    path = Path(TRENDING_CSV)
    if not path.exists():
        print(f"오류: {TRENDING_CSV} 없음")
        return

    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kw = (row.get("keyword") or "").strip()
            if kw:
                rows.append(row)

    rows = rows[:MAX_KEYWORDS]
    print(f"분석 대상: {len(rows)}개 키워드 (API 호출 간 {DELAY_BETWEEN_CALLS}초 대기)")
    print("(API 제한: 시간당 10회 권장. 너무 많은 호출 시 차단될 수 있음)")
    print()

    results = []
    for i, row in enumerate(rows):
        kw = row["keyword"]
        print(f"[{i + 1}/{len(rows)}] {kw}")
        data = analyze_keyword_api(kw, COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY)
        results.append({
            "category": row.get("category", ""),
            "rank": row.get("rank", ""),
            "keyword": kw,
            "change_trend": row.get("change_trend", ""),
            "rocket_count": data["rocket_count"],
            "total_products": data["total_products"],
            "avg_price": int(data["avg_price"]),
            "max_reviews": data["max_reviews"],
            "grade": data["grade"],
        })
        print(f"  -> 로켓 {data['rocket_count']}개, 평균가 {data['avg_price']:,.0f}원, 등급 {data['grade']}")
        time.sleep(DELAY_BETWEEN_CALLS)

    out_path = Path(OUTPUT_CSV)
    fieldnames = ["category", "rank", "keyword", "change_trend", "rocket_count", "total_products", "avg_price", "max_reviews", "grade"]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print()
    print(f"저장 완료: {out_path.absolute()}")
    s_count = sum(1 for r in results if r["grade"] == "S")
    a_count = sum(1 for r in results if r["grade"] == "A")
    print(f"S등급 {s_count}개, A등급 {a_count}개, B등급 {len(results) - s_count - a_count}개")


if __name__ == "__main__":
    main()
