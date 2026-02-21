"""
스크래퍼 추상 베이스 클래스
새 도매/쇼핑몰 추가 시 이 클래스를 상속
"""

import logging
import random
import time
from abc import ABC, abstractmethod

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]
logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """수집 모듈 추상 베이스 클래스"""

    def __init__(self, delay_min: float = 1.0, delay_max: float = 3.0):
        self.delay_min = delay_min
        self.delay_max = delay_max

    def _random_delay(self):
        """사람처럼 랜덤 대기 (IP 차단 방지)"""
        time.sleep(random.uniform(self.delay_min, self.delay_max))

    def _random_user_agent(self) -> str:
        return random.choice(USER_AGENTS)

    @abstractmethod
    def scrape_keyword(self, keyword: str) -> dict:
        """키워드 1개 수집 → dict 반환 (실패 시 빈 dict 또는 에러 로그)"""
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """수집 소스 이름 (naver_insight, coupang, domeggook 등)"""
        pass
