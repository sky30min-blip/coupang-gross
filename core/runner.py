"""
실행 매니저 - 전체 프로세스 총괄
trending_keywords.csv → 네이버 검색량 조회 → DB 적재 → 분석 모듈 순차 실행 → 결과 업데이트
"""

import csv
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import init_db, insert_product, insert_market_data
from core.validator import calc_reliability_score

logger = logging.getLogger(__name__)

TRENDING_CSV = Path(__file__).resolve().parent.parent / "trending_keywords.csv"
MAX_RETRIES = 3
RETRY_DELAY = 2


def _retry(fn, max_retries: int = MAX_RETRIES, delay: float = RETRY_DELAY):
    """재시도 래퍼. 예외 발생 시 delay 후 재시도."""
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as e:
            logger.warning("시도 %d/%d 실패: %s", attempt, max_retries, e)
            if attempt < max_retries:
                time.sleep(delay)
            else:
                raise


def load_trending_keywords() -> list[dict]:
    if not TRENDING_CSV.exists():
        logger.error("trending_keywords.csv 없음. 먼저 네이버 트렌드 스크래핑을 실행하세요.")
        return []
    rows = []
    with open(TRENDING_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kw = (row.get("keyword") or "").strip()
            if kw:
                rows.append({
                    "keyword": kw,
                    "category": row.get("category", ""),
                    "rank": row.get("rank"),
                    "change_trend": row.get("change_trend", ""),
                })
    return rows


def run_coupang_analyzer(keyword: str) -> dict:
    """쿠팡 API 분석 (로켓수, 평균가). limit 20, 로켓 판별 강화."""
    def _do():
        from coupang_config import COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY
        import coupang_api
        js = coupang_api.search_products(keyword, 20, COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY)
        if not js:
            return {}
        data = js.get("data", js)
        products = []
        if isinstance(data, dict):
            products = data.get("productData") or data.get("products") or data.get("productList") or data.get("items") or data.get("results") or []
        if not isinstance(products, list):
            products = []
        if not products:
            return {"rocket_count": 0, "avg_price": 0}
        prices = []
        rocket = 0
        for p in products:
            if not isinstance(p, dict):
                continue
            if p.get("isRocket") or p.get("rocket") or p.get("isRocketDelivery") or "로켓" in str(p.get("productName", "")):
                rocket += 1
            pr = p.get("productPrice") or p.get("price") or p.get("salePrice") or p.get("product_price")
            if pr is not None:
                try:
                    prices.append(int(pr))
                except (ValueError, TypeError):
                    pass
        avg = round(sum(prices) / len(prices), 0) if prices else 0
        return {"rocket_count": rocket, "avg_price": int(avg), "total_products": len(products)}

    try:
        return _retry(_do) or {}
    except Exception as e:
        logger.exception("쿠팡 분석 오류 %s: %s", keyword, e)
        return {}


def calc_opportunity_score(rocket_count: int, price_range: float = 0) -> float:
    score = 100 - rocket_count * 5
    if price_range >= 50000:
        score += 10
    return max(0, min(100, score))


def _get_naver_searchad_config() -> dict | None:
    """네이버 검색광고 API 설정 로드. 없으면 None."""
    try:
        from naver_searchad_config import (
            NAVER_SEARCHAD_CUSTOMER_ID,
            NAVER_SEARCHAD_LICENSE_KEY,
            NAVER_SEARCHAD_SECRET_KEY,
        )
        if not all([NAVER_SEARCHAD_CUSTOMER_ID, NAVER_SEARCHAD_LICENSE_KEY, NAVER_SEARCHAD_SECRET_KEY]):
            return None
        return {
            "customer_id": NAVER_SEARCHAD_CUSTOMER_ID,
            "license_key": NAVER_SEARCHAD_LICENSE_KEY,
            "secret_key": NAVER_SEARCHAD_SECRET_KEY,
        }
    except ImportError:
        logger.info("naver_searchad_config.py 없음. 네이버 검색량은 스킵. (예시: naver_searchad_config.example.py 참고)")
        return None


def run_workflow(limit: int = 50):
    """trending_keywords.csv → 네이버 검색량 조회 → DB → 분석 → market_data 저장"""
    init_db()
    rows = load_trending_keywords()
    if not rows:
        return

    naver_cfg = _get_naver_searchad_config()
    rows = rows[:limit]
    logger.info("trending_keywords.csv %d건 DB 적재 및 분석 시작 (네이버 검색광고 API: %s)", len(rows), "사용" if naver_cfg else "미사용")

    for i, row in enumerate(rows):
        kw = row["keyword"]
        try:
            # 1) 네이버 검색광고 API로 월간 검색량 조회
            naver_search_vol = None
            if naver_cfg:
                import naver_api
                naver_search_vol = naver_api.get_monthly_search_volume(
                    kw,
                    naver_cfg["customer_id"],
                    naver_cfg["license_key"],
                    naver_cfg["secret_key"],
                )
                if naver_search_vol is not None:
                    time.sleep(0.5)  # 검색광고 API 호출 간격

            insert_product(
                keyword=kw,
                category=row.get("category", ""),
                naver_rank=int(row["rank"]) if row.get("rank") else None,
                naver_search_vol=naver_search_vol,
            )

            # 2) 쿠팡 분석
            coupang = run_coupang_analyzer(kw)
            if not coupang:
                continue

            trend_up = (row.get("change_trend") or "").strip() not in ("", "-", "0")
            reliability = calc_reliability_score(
                naver_rank=int(row["rank"]) if row.get("rank") else None,
                naver_search_vol=naver_search_vol,
                coupang_rocket_count=coupang.get("rocket_count"),
                naver_trend_up=bool(trend_up),
            )
            opp_score = calc_opportunity_score(coupang.get("rocket_count", 0))

            insert_product(
                keyword=kw,
                category=row.get("category", ""),
                naver_rank=int(row["rank"]) if row.get("rank") else None,
                naver_search_vol=naver_search_vol,
                coupang_avg_price=coupang.get("avg_price"),
                rocket_count=coupang.get("rocket_count"),
                opportunity_score=opp_score,
            )

            # 3) market_data 테이블에 시계열 적재 (키워드, 검색량, 로켓수, 마진율, 신뢰도점수, 수집일)
            insert_market_data(
                keyword=kw,
                search_vol=naver_search_vol,
                rocket_count=coupang.get("rocket_count"),
                margin_rate=None,  # 도매가 확보 시 추후 계산
                credibility_score=reliability,
            )

            logger.info(
                "[%d/%d] %s | 검색량=%s, 로켓=%s, 가격=%s, 신뢰도=%.1f",
                i + 1, len(rows), kw,
                naver_search_vol if naver_search_vol is not None else "-",
                coupang.get("rocket_count"), coupang.get("avg_price"), reliability,
            )
            time.sleep(2)  # API 제한 회피
        except Exception as e:
            logger.exception("키워드 %s 처리 오류: %s", kw, e)

    logger.info("워크플로우 완료. DB: coupang_gross.db (Products + market_data)")
