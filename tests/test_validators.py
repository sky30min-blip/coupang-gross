"""
유닛 테스트: 교차 검증 로직
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validators.cross_check import validate_keyword, compute_consistency


def test_validate_keyword_valid():
    naver = {"rank": 5, "change_trend": "+3"}
    coupang = {"rocket_count": 0, "avg_price": 30000}
    score, status = validate_keyword(naver, coupang, naver_search_ratio=180, consistency_threshold=70)
    assert status in ("Valid", "Invalid")
    assert 0 <= score <= 100


def test_validate_keyword_pending():
    naver = {}
    coupang = {"rocket_count": 5}
    _, status = validate_keyword(naver, coupang)
    assert status == "pending"


def test_compute_consistency():
    s = compute_consistency(naver_rank=10, coupang_rocket_count=0, naver_search_ratio=200, naver_trend_up=True)
    assert 50 <= s <= 100


if __name__ == "__main__":
    test_validate_keyword_valid()
    test_validate_keyword_pending()
    test_compute_consistency()
    print("All validator tests passed.")
