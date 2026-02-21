"""
validator.py - 데이터 검증기
- 가격 0원/검색결과 없음 필터링
- 네이버 트렌드 vs 쿠팡 검색량 비교 → 신뢰도 0~100
"""


def filter_invalid(rows: list[dict]) -> list[dict]:
    """
    수집된 데이터 중 유효하지 않은 것 필터링
    - 가격 0원
    - 검색 결과 없음 (rocket_count=None 또는 total_products=0)
    """
    valid = []
    for r in rows:
        price = r.get("coupang_avg_price") or r.get("avg_price") or 0
        rocket = r.get("rocket_count") is not None
        total = r.get("total_products") or r.get("coupang_total_products") or 0
        if price <= 0:
            continue
        if not rocket and total == 0:
            continue
        valid.append(r)
    return valid


def calc_reliability_score(
    naver_search_vol: float | None = None,
    naver_rank: int | None = None,
    coupang_rocket_count: int | None = None,
    naver_trend_up: bool = False,
) -> float:
    """
    네이버 트렌드 수치와 쿠팡 검색량을 비교해 신뢰도 0~100 환산
    - 네이버 수요 있음 + 쿠팡 공급 부족 = 높은 신뢰
    - 데이터 일치도가 높을수록 점수 상승
    """
    score = 50.0  # 기본

    if naver_rank is not None:
        if naver_rank <= 10:
            score += 20
        elif naver_rank <= 30:
            score += 10
        elif naver_rank <= 50:
            score += 5

    if coupang_rocket_count is not None:
        if coupang_rocket_count == 0:
            score += 20  # 공급 부족 = 블루오션
        elif coupang_rocket_count < 5:
            score += 10
        elif coupang_rocket_count > 10:
            score -= 10

    if naver_search_vol is not None and naver_search_vol > 0:
        if naver_search_vol >= 80:  # 상대적 고수요
            score += 10
        elif naver_search_vol >= 50:
            score += 5

    if naver_trend_up:
        score += 10

    return max(0.0, min(100.0, round(score, 1)))
