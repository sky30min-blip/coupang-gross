"""
base_scraper.py - 모든 스크래퍼가 상속받을 추상 클래스
공통: User-Agent 랜덤, Proxy 인터페이스, Time-sleep 랜덤
"""

import random
import time
from abc import ABC, abstractmethod
from typing import Any

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class BaseScraper(ABC):
    """수집 모듈 추상 베이스 클래스"""

    def __init__(
        self,
        delay_min: float = 1.0,
        delay_max: float = 3.0,
        proxy: str | None = None,
    ):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self._proxy = proxy

    def get_random_user_agent(self) -> str:
        """User-Agent 랜덤 변경"""
        return random.choice(USER_AGENTS)

    def set_proxy(self, proxy: str | None):
        """Proxy 설정 (예: http://user:pass@host:port)"""
        self._proxy = proxy

    def get_proxy(self) -> dict[str, str] | None:
        """requests 사용 시 proxies 인자로 전달할 dict 반환"""
        if not self._proxy:
            return None
        return {"http": self._proxy, "https": self._proxy}

    def random_sleep(self):
        """Time-sleep 랜덤 제어 (봇 탐지 회피)"""
        time.sleep(random.uniform(self.delay_min, self.delay_max))

    @abstractmethod
    def scrape(self, keyword: str) -> dict[str, Any]:
        """키워드 1개 수집. 반환: {naver_rank?, coupang_avg_price?, rocket_count?, ...}"""
        pass
