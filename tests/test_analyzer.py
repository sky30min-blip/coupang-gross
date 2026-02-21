"""
유닛 테스트: 쿠팡 로켓 개수/등급/마진 계산 정확성 검증
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer.competition import get_grade, calc_opportunity_score, calc_margin_rate


def test_get_grade():
    assert get_grade(0) == "S"
    assert get_grade(3) == "S"
    assert get_grade(4) == "S"
    assert get_grade(5) == "A"
    assert get_grade(10) == "A"
    assert get_grade(11) == "B"
    assert get_grade(20) == "B"


def test_calc_opportunity_score():
    assert 0 <= calc_opportunity_score(0, 0, 0) <= 100
    assert calc_opportunity_score(0, 0, 60000) > calc_opportunity_score(0, 0, 10000)
    assert calc_opportunity_score(5, 0, 0) > calc_opportunity_score(15, 0, 0)


def test_calc_margin_rate():
    assert calc_margin_rate(10000, 7000) == 0.3
    assert calc_margin_rate(100000, 70000) == 0.3
    assert calc_margin_rate(10000, 0) == 1.0
    assert calc_margin_rate(0, 1000) == 0.0


if __name__ == "__main__":
    test_get_grade()
    test_calc_opportunity_score()
    test_calc_margin_rate()
    print("All tests passed.")
