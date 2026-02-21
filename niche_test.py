"""
trending_keywords.csv 상위 20개만 쿠팡에서 분석 → niche_test.csv 저장
"""

import csv
import time
from pathlib import Path

from coupang_api import search_products

TRENDING_CSV = "trending_keywords.csv"
OUTPUT_CSV = "niche_test.csv"
PRODUCTS_PER_KEYWORD = 20  # API 샘플링 한계 보완 (10~36)
MAX_KEYWORDS = 20
DELAY_BETWEEN_CALLS = 2


def get_grade(rocket_count: int) -> str:
    if rocket_count < 5:
        return "S"
    if rocket_count <= 10:
        return "A"
    return "B"


def analyze_keyword_api(keyword: str, access_key: str, secret_key: str, try_visual_on_zero: bool = True) -> dict:
    result = {
        "rocket_count": 0,
        "total_products": 0,
        "avg_price": 0,
        "max_reviews": 0,
        "grade": "B",
        "verification_needed": False,
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

    # API가 0개 반환 시 시각 스크래퍼로 재검증 시도 (쿠팡 차단 시 실패)
    if rocket_count == 0 and try_visual_on_zero:
        try:
            from coupang_visual_fallback import scrape_and_save
            fallback = scrape_and_save(keyword)
            if fallback.get("rocket_count") is not None and fallback.get("error") is None:
                result["rocket_count"] = fallback["rocket_count"]
                result["grade"] = get_grade(result["rocket_count"])
                print(f"    [시각검증] 로켓 {result['rocket_count']}개")
            elif fallback.get("error"):
                result["verification_needed"] = True
                print(f"    [시각검증 실패] {fallback['error']} → 수동 검증 필요")
        except Exception as e:
            result["verification_needed"] = True
            print(f"    [시각검증 예외] {e} → 수동 검증 필요")

    if result["rocket_count"] == 0 and not result.get("verification_needed"):
        result["verification_needed"] = True
    return result


def main():
    print("쿠팡 니치 테스트 - 상위 20개 키워드 분석")
    print("-" * 50)

    try:
        from coupang_config import COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY
    except ImportError:
        print("오류: coupang_config.py가 없습니다.")
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
    print(f"분석 대상: 상위 {len(rows)}개 키워드")
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
            "verification_needed": "Y" if data.get("verification_needed") else "",
        })
        print(f"  -> 로켓 {data['rocket_count']}개, 평균가 {data['avg_price']:,.0f}원, 등급 {data['grade']}")
        time.sleep(DELAY_BETWEEN_CALLS)

    out_path = Path(OUTPUT_CSV)
    fieldnames = ["category", "rank", "keyword", "change_trend", "rocket_count", "total_products", "avg_price", "max_reviews", "grade", "verification_needed"]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print()
    print(f"저장 완료: {out_path.absolute()}")


if __name__ == "__main__":
    main()
