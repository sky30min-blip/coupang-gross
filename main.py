"""
쿠팡그로스 통합 컨트롤러
데이터 신뢰성을 최우선으로 하는 이커머스 통합 분석 시스템
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.logging_config import setup_logging
from database.db import init_db, insert_keyword_data, get_latest_by_keywords
from scrapers.naver_insight import NaverInsightScraper
from scrapers.coupang_api import CoupangApiScraper
from validators.cross_check import validate_keyword

logger = logging.getLogger(__name__)


def load_coupang_config():
    try:
        from coupang_config import COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY
        return COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY
    except ImportError:
        logger.error("coupang_config.py 없음. COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY 설정 필요")
        return None, None


def run_pipeline(limit: int = 20):
    """전체 파이프라인: 네이버 수집 → 쿠팡 분석 → 교차 검증 → DB 저장"""
    setup_logging()
    init_db()

    naver = NaverInsightScraper(delay_min=0.5, delay_max=1.5)
    access_key, secret_key = load_coupang_config()
    if not access_key or not secret_key:
        logger.error("쿠팡 API 키가 없습니다. 파이프라인 중단.")
        return

    coupang = CoupangApiScraper(access_key, secret_key, delay_min=2, delay_max=4)

    logger.info("네이버 쇼핑 인사이트 TOP 키워드 수집")
    keywords_data = []
    for cat_name, cid in [("생활/주방", "50000008"), ("디지털/가전", "50000003")]:
        try:
            items = naver.scrape_category_top(cat_name, cid, limit=limit // 2)
            keywords_data.extend(items)
        except Exception as e:
            logger.exception("네이버 수집 오류: %s", e)

    seen = set()
    unique = []
    for k in keywords_data:
        kw = (k.get("keyword") or "").strip()
        if kw and kw not in seen:
            seen.add(kw)
            unique.append(k)
    keywords_data = unique[:limit]

    logger.info("쿠팡 API 분석 및 교차 검증 (%d개)", len(keywords_data))
    for i, row in enumerate(keywords_data):
        kw = row.get("keyword", "")
        if not kw:
            continue
        try:
            coupang_result = coupang.scrape_keyword(kw)
            consistency, status = validate_keyword(row, coupang_result)
            insert_keyword_data(
                keyword=kw,
                category=row.get("category", ""),
                naver_rank=row.get("rank"),
                naver_change_trend=row.get("change_trend", ""),
                coupang_rocket_count=coupang_result.get("rocket_count"),
                coupang_avg_price=coupang_result.get("avg_price"),
                coupang_total_products=coupang_result.get("total_products"),
                consistency_score=consistency,
                validation_status=status,
            )
            logger.info("[%d/%d] %s | 로켓=%s, 가격=%s, 일관성=%.1f, %s",
                i + 1, len(keywords_data), kw,
                coupang_result.get("rocket_count"), coupang_result.get("avg_price"),
                consistency, status)
        except Exception as e:
            logger.exception("키워드 %s 처리 중 오류: %s", kw, e)

    logger.info("파이프라인 완료. DB: coupang_gross.db")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20, help="분석할 키워드 수")
    args = parser.parse_args()
    run_pipeline(limit=args.limit)


if __name__ == "__main__":
    main()
