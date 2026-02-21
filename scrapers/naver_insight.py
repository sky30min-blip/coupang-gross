"""
네이버 쇼핑 인사이트 수집 모듈 (실제 구매 의도)
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

API_URL = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
HEADERS = {
    "Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}
CATEGORIES = [("생활/주방", "50000008"), ("디지털/가전", "50000003")]


class NaverInsightScraper(BaseScraper):
    """네이버 쇼핑 인사이트 인기 검색어"""

    def get_source_name(self) -> str:
        return "naver_insight"

    def scrape_keyword(self, keyword: str) -> dict:
        """단일 키워드는 카테고리 내 순위 검색 미지원 → 전체 TOP 수집 후 키워드 필터"""
        try:
            from datetime import datetime, timedelta
            end = datetime.now()
            start = end - timedelta(days=7)
            start_str = start.strftime("%Y-%m-%d")
            end_str = end.strftime("%Y-%m-%d")
            for cat_name, cid in CATEGORIES:
                data = {
                    "cid": cid, "timeUnit": "date",
                    "startDate": start_str, "endDate": end_str,
                    "page": "1", "count": "100",
                }
                r = requests.post(API_URL, headers={**HEADERS, "User-Agent": self._random_user_agent()}, data=data, timeout=15)
                self._random_delay()
                if r.status_code != 200:
                    continue
                js = r.json()
                for i, item in enumerate(js.get("ranks", [])):
                    if (item.get("keyword") or "").strip() == keyword:
                        return {
                            "rank": item.get("rank", i + 1),
                            "change_trend": str(item.get("rankChange", item.get("change", "")) or "-"),
                        }
            return {}
        except Exception as e:
            logger.exception("NaverInsight scrape_keyword error: %s", e)
            return {}

    def scrape_category_top(self, category: str, cid: str, limit: int = 100) -> list[dict]:
        """카테고리 TOP 키워드 일괄 수집"""
        result = []
        try:
            from datetime import datetime, timedelta
            end = datetime.now()
            start = end - timedelta(days=7)
            page = 1
            while len(result) < limit:
                data = {
                    "cid": cid, "timeUnit": "date",
                    "startDate": start.strftime("%Y-%m-%d"),
                    "endDate": end.strftime("%Y-%m-%d"),
                    "page": str(page), "count": "20",
                }
                r = requests.post(API_URL, headers={**HEADERS, "User-Agent": self._random_user_agent()}, data=data, timeout=15)
                self._random_delay()
                if r.status_code != 200:
                    break
                js = r.json()
                ranks = js.get("ranks", [])
                if not ranks:
                    break
                for i, item in enumerate(ranks):
                    kw = (item.get("keyword") or "").strip()
                    if kw:
                        result.append({
                            "keyword": kw,
                            "category": category,
                            "rank": item.get("rank", (page - 1) * 20 + i + 1),
                            "change_trend": str(item.get("rankChange", item.get("change", "")) or "-"),
                        })
                if len(ranks) < 20:
                    break
                page += 1
                if page > 10:
                    break
        except Exception as e:
            logger.exception("NaverInsight scrape_category_top error: %s", e)
        return result[:limit]
