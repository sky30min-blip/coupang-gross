"""
데이터 신뢰도 교차 검증 엔진
네이버 + 쿠팡 데이터 일관성 80% 이상일 때만 'Valid' 판정
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

ValidationStatus = Literal["Valid", "Invalid", "pending"]


def compute_consistency(
    naver_rank: int | None,
    coupang_rocket_count: int | None,
    naver_search_ratio: float | None,
    naver_trend_up: bool = False,
) -> float:
    """
    네이버와 쿠팡 데이터의 일관성 점수 (0~100)
    - 네이버 검색량 폭증 + 쿠팡 로켓 0 + 트렌드 우상향 → 신뢰도 극상
    - 반대로 공급 과다 + 수요 하락 → 불일치
    """
    score = 50.0  # 기본
    if naver_rank is not None and naver_rank <= 20:
        score += 15  # 상위 순위 = 수요 있음
    if coupang_rocket_count is not None:
        if coupang_rocket_count == 0:
            score += 20  # 공급 부족 = 블루오션
        elif coupang_rocket_count < 5:
            score += 10
        else:
            score -= 10  # 공급 과다
    if naver_search_ratio is not None and naver_search_ratio > 150:
        score += 15  # 현재 수요 급증
    if naver_trend_up:
        score += 10
    return max(0.0, min(100.0, score))


def validate_keyword(
    naver_data: dict,
    coupang_data: dict,
    naver_search_ratio: float | None = None,
    consistency_threshold: float = 80.0,
) -> tuple[float, ValidationStatus]:
    """
    동일 키워드에 대해 네이버·쿠팡 데이터 대조
    일관성 80% 이상이면 'Valid'
    """
    has_naver = bool(naver_data and (naver_data.get("rank") is not None or naver_data.get("keyword")))
    has_coupang = bool(coupang_data and coupang_data.get("rocket_count") is not None)

    if not has_naver or not has_coupang:
        return 0.0, "pending"

    naver_rank = naver_data.get("rank")
    rocket = coupang_data.get("rocket_count")
    trend = (naver_data.get("change_trend") or "").strip()
    trend_up = bool(trend and trend not in ("-", "", "0") and ("상승" in str(trend) or str(trend).startswith("+")))

    consistency = compute_consistency(naver_rank, rocket, naver_search_ratio, trend_up)
    status: ValidationStatus = "Valid" if consistency >= consistency_threshold else "Invalid"
    return consistency, status
