"""
쿠팡 시장성 분석기 - 진입 가능성 점수 (쿠팡 파트너스 API 사용)
가격 분할 수집: 다중 API 호출 → 병합·중복제거 → 로켓 비율 재계산
정확도 레이팅: 샘플 수에 따라 '데이터 부족' / '신뢰도 높음'
멀티스레딩: 키워드 단위 병렬 분석 (API I/O 바운드)
"""

import csv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from coupang_api import search_products

# 설정
TRENDING_CSV = "trending_keywords.csv"
OUTPUT_CSV = "niche_score_report.csv"
PRODUCTS_PER_CALL = 10  # 쿠팡 API limit 허용 범위 내
CALLS_PER_KEYWORD = 3  # 키워드당 API 호출 횟수 (가격 구간 대체)
DELAY_BETWEEN_CALLS = 2
TEST_LIMIT = 50
MAX_WORKERS = 3  # 병렬 워커 수 (API rate limit 고려)

# 정확도 레이팅
SAMPLE_LOW = 20   # 미만 → 데이터 부족
SAMPLE_HIGH = 30  # 이상 → 신뢰도 높음


def _extract_products(js: dict) -> list:
    """API 응답에서 상품 리스트 추출"""
    if not js:
        return []
    data = js.get("data", js)
    if not isinstance(data, dict):
        return []
    products = (
        data.get("productData") or data.get("products") or data.get("productList")
        or data.get("items") or data.get("results") or []
    )
    return products if isinstance(products, list) else []


def _is_rocket(p: dict) -> bool:
    """로켓 배송 여부 판별"""
    if not isinstance(p, dict):
        return False
    return bool(
        p.get("isRocket") or p.get("rocket") or p.get("isRocketDelivery")
        or "로켓" in str(p.get("productName", ""))
    )


def _product_id(p: dict) -> str:
    """중복 제거용 상품 식별자"""
    if not isinstance(p, dict):
        return ""
    pid = p.get("productId") or p.get("product_id") or p.get("itemId") or p.get("id")
    url = p.get("productUrl") or p.get("product_url") or p.get("link") or ""
    return str(pid) if pid else (url.split("/")[-1] or url[:80])


def _get_price(p: dict) -> int | None:
    """상품 가격 추출"""
    if not isinstance(p, dict):
        return None
    price = p.get("productPrice") or p.get("price") or p.get("salePrice") or p.get("product_price")
    if price is None:
        return None
    try:
        return int(price)
    except (ValueError, TypeError):
        return None


def analyze_keyword_api(
    keyword: str,
    access_key: str,
    secret_key: str,
) -> dict:
    """
    가격 분할 대체: 3회 이상 API 호출 → 병합 → 중복 제거 → 로켓 비율 재계산.
    (API는 가격 필터 미지원이므로 동일 조건 다중 호출로 샘플 확대)
    """
    result = {
        "rocket_count": 0,
        "avg_price": 0,
        "min_price": 0,
        "max_price": 0,
        "price_range": 0,
        "avg_reviews": 0,
        "total_products": 0,
        "accuracy_rating": "데이터 부족",
    }

    seen: dict[str, dict] = {}
    for call_idx in range(CALLS_PER_KEYWORD):
        js = search_products(keyword, PRODUCTS_PER_CALL, access_key, secret_key)
        products = _extract_products(js)
        for p in products:
            pid = _product_id(p)
            if pid and pid not in seen:
                seen[pid] = p
        time.sleep(DELAY_BETWEEN_CALLS)

    merged = list(seen.values())
    result["total_products"] = len(merged)

    if not merged:
        return result

    rocket_count = sum(1 for p in merged if _is_rocket(p))
    prices = [pr for p in merged if (pr := _get_price(p)) is not None]

    result["rocket_count"] = rocket_count
    result["avg_price"] = round(sum(prices) / len(prices), 0) if prices else 0
    result["min_price"] = min(prices) if prices else 0
    result["max_price"] = max(prices) if prices else 0
    result["price_range"] = result["max_price"] - result["min_price"]

    if result["total_products"] < SAMPLE_LOW:
        result["accuracy_rating"] = "데이터 부족"
    elif result["total_products"] >= SAMPLE_HIGH:
        result["accuracy_rating"] = "신뢰도 높음"
    else:
        result["accuracy_rating"] = "보통"

    return result


def calc_opportunity_score(rocket_count: int, avg_reviews: float, price_range: float) -> int:
    """진입 가능성 점수: 100 - 로켓*5 - 리뷰보너스 + 가격편차보너스"""
    score = 100
    score -= rocket_count * 5
    score -= int(avg_reviews / 100) * 10
    if price_range >= 50000:
        score += 10
    return max(0, min(100, score))


def _process_single(args: tuple) -> tuple[dict, dict]:
    """멀티프로세싱용: (row, data) 반환"""
    row, access_key, secret_key = args
    kw = (row.get("keyword") or "").strip()
    if not kw:
        return row, {}
    data = analyze_keyword_api(kw, access_key, secret_key)
    return row, data


def main():
    print("쿠팡 시장성 분석기 (파트너스 API) - 다중 호출 병합 + 병렬 분석")
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
        for row in csv.DictReader(f):
            kw = (row.get("keyword") or "").strip()
            if kw:
                rows.append(row)

    rows = rows[:TEST_LIMIT]
    print(f"분석 대상: {len(rows)}개 키워드 | 호출/키워드: {CALLS_PER_KEYWORD}회 | 워커: {MAX_WORKERS}")
    print()

    results = []
    use_mp = len(rows) >= 3 and MAX_WORKERS > 1

    if use_mp:
        args_list = [(row, COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY) for row in rows]
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(_process_single, a): a[0] for a in args_list}
            for i, future in enumerate(as_completed(futures)):
                row = futures[future]
                kw = (row.get("keyword") or "").strip()
                try:
                    _, data = future.result()
                    score = calc_opportunity_score(
                        data["rocket_count"], data["avg_reviews"], data["price_range"]
                    )
                    results.append({
                        "category": row.get("category", ""),
                        "rank": row.get("rank", ""),
                        "keyword": kw,
                        "change_trend": row.get("change_trend", ""),
                        "rocket_count": data["rocket_count"],
                        "avg_price": int(data["avg_price"]),
                        "min_price": int(data["min_price"]),
                        "max_price": int(data["max_price"]),
                        "price_range": int(data["price_range"]),
                        "avg_reviews": data["avg_reviews"],
                        "opportunity_score": score,
                        "total_products": data["total_products"],
                        "accuracy_rating": data["accuracy_rating"],
                    })
                    print(f"[{i+1}/{len(rows)}] {kw} | 로켓 {data['rocket_count']}개, 샘플 {data['total_products']}개, {data['accuracy_rating']}")
                except Exception as e:
                    print(f"[{i+1}/{len(rows)}] {kw} 오류: {e}")
                    results.append({
                        "category": row.get("category", ""),
                        "rank": row.get("rank", ""),
                        "keyword": kw,
                        "change_trend": row.get("change_trend", ""),
                        "rocket_count": 0,
                        "avg_price": 0,
                        "min_price": 0,
                        "max_price": 0,
                        "price_range": 0,
                        "avg_reviews": 0,
                        "opportunity_score": 0,
                        "total_products": 0,
                        "accuracy_rating": "데이터 부족",
                    })
    else:
        for i, row in enumerate(rows):
            kw = (row.get("keyword") or "").strip()
            if not kw:
                continue
            print(f"[{i + 1}/{len(rows)}] {kw}")
            data = analyze_keyword_api(kw, COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY)
            score = calc_opportunity_score(
                data["rocket_count"], data["avg_reviews"], data["price_range"]
            )
            results.append({
                "category": row.get("category", ""),
                "rank": row.get("rank", ""),
                "keyword": kw,
                "change_trend": row.get("change_trend", ""),
                "rocket_count": data["rocket_count"],
                "avg_price": int(data["avg_price"]),
                "min_price": int(data["min_price"]),
                "max_price": int(data["max_price"]),
                "price_range": int(data["price_range"]),
                "avg_reviews": data["avg_reviews"],
                "opportunity_score": score,
                "total_products": data["total_products"],
                "accuracy_rating": data["accuracy_rating"],
            })
            print(f"  로켓 {data['rocket_count']}개, 샘플 {data['total_products']}개, {data['accuracy_rating']}")

    out_path = Path(OUTPUT_CSV)
    fieldnames = [
        "category", "rank", "keyword", "change_trend",
        "rocket_count", "avg_price", "min_price", "max_price", "price_range",
        "avg_reviews", "opportunity_score", "total_products", "accuracy_rating",
    ]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print()
    print(f"저장 완료: {out_path.absolute()}")


if __name__ == "__main__":
    main()
