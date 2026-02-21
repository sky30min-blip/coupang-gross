"""
쿠팡 파트너스 API 수집 모듈 (로켓 상품 수, 평균가)
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class CoupangApiScraper(BaseScraper):
    """쿠팡 파트너스 API (공급 검증)"""

    def __init__(self, access_key: str, secret_key: str, **kwargs):
        super().__init__(**kwargs)
        self.access_key = access_key
        self.secret_key = secret_key

    def get_source_name(self) -> str:
        return "coupang"

    def scrape_keyword(self, keyword: str, limit: int = 10) -> dict:
        try:
            import coupang_api
            js = coupang_api.search_products(keyword, limit, self.access_key, self.secret_key)
            if not js:
                return {}
            data = js.get("data", js)
            products = []
            if isinstance(data, dict):
                products = (
                    data.get("productData")
                    or data.get("products")
                    or data.get("productList")
                    or []
                )
            elif isinstance(data, list):
                products = data
            if not products:
                return {"rocket_count": 0, "avg_price": 0, "total_products": 0}

            prices = []
            rocket_count = 0
            for p in products:
                if not isinstance(p, dict):
                    continue
                if p.get("isRocket") or p.get("rocket") or p.get("isRocketDelivery"):
                    rocket_count += 1
                price = p.get("productPrice") or p.get("price") or p.get("salePrice")
                if price is not None:
                    try:
                        prices.append(int(price))
                    except (ValueError, TypeError):
                        pass
            avg_price = round(sum(prices) / len(prices), 0) if prices else 0
            self._random_delay()
            return {
                "rocket_count": rocket_count,
                "avg_price": int(avg_price),
                "total_products": len(products),
            }
        except Exception as e:
            logger.exception("CoupangApi scrape_keyword error: %s", e)
            return {}
