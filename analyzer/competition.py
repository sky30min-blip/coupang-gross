"""
경쟁 강도 분석 (로켓 수 기반 등급)
"""


def get_grade(rocket_count: int) -> str:
    if rocket_count < 5:
        return "S"
    if rocket_count <= 10:
        return "A"
    return "B"


def calc_opportunity_score(rocket_count: int, avg_reviews: float, price_range: float) -> int:
    """진입 가능성 점수 0~100"""
    score = 100
    score -= rocket_count * 5
    score -= int(avg_reviews / 100) * 10
    if price_range >= 50000:
        score += 10
    return max(0, min(100, score))


def calc_margin_rate(coupang_price: int, wholesale_price: int) -> float:
    """마진율: (쿠팡가 - 도매가) / 쿠팡가"""
    if coupang_price <= 0:
        return 0.0
    return (coupang_price - wholesale_price) / coupang_price
