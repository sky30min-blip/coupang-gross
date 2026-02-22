"""
naver_api.py - 네이버 검색광고 API 연동
keywordstool로 키워드별 월간 검색량(PC+모바일) 조회
retry + logging 포함
"""

import hashlib
import hmac
import base64
import logging
import time
from typing import Callable, TypeVar

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.searchad.naver.com"
KEYWORDSTOOL_URI = "/keywordstool"
MAX_RETRIES = 3
RETRY_DELAY_SEC = 2


def _get_secret_bytes(secret_key: str) -> bytes:
    """네이버 검색광고 API: Secret Key는 hex 문자열이면 디코딩, 아니면 UTF-8 바이트 사용."""
    s = (secret_key or "").strip()
    if len(s) == 64 and all(c in "0123456789abcdefABCDEF" for c in s):
        try:
            return bytes.fromhex(s)
        except ValueError:
            pass
    return s.encode("utf-8")


def _generate_signature(timestamp: str, method: str, uri: str, secret_key: str) -> str:
    """HMAC-SHA256 서명 생성 (네이버 검색광고 API). request_uri는 경로만(쿼리 제외)."""
    message = f"{timestamp}.{method}.{uri}"
    key_bytes = _get_secret_bytes(secret_key)
    dig = hmac.new(
        key_bytes,
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(dig).decode("utf-8")


def _get_headers(
    method: str,
    uri: str,
    customer_id: str,
    license_key: str,
    secret_key: str,
) -> dict:
    timestamp = str(int(time.time() * 1000))
    signature = _generate_signature(timestamp, method, uri, secret_key)
    return {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Timestamp": timestamp,
        "X-API-KEY": license_key,
        "X-Customer": str(customer_id),
        "X-Signature": signature,
    }


def _parse_monthly_count(val: str | int | None) -> int:
    """월간 검색량 파싱. '<10'이면 5로 반환 (대략치)."""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip()
    if not s or s == "<10":
        return 5  # 최소 추정
    try:
        return int(s.replace(",", ""))
    except ValueError:
        return 0


def get_monthly_search_volume(
    keyword: str,
    customer_id: str,
    license_key: str,
    secret_key: str,
) -> float | None:
    """
    네이버 검색광고 keywordstool API로 해당 키워드의 월간 검색량 조회.
    PC + 모바일 합산 반환. 실패 시 None.
    """
    uri = KEYWORDSTOOL_URI
    params = {"hintKeywords": keyword, "showDetail": 1}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            headers = _get_headers(
                "GET", uri, customer_id, license_key, secret_key
            )
            resp = requests.get(
                BASE_URL + uri,
                params=params,
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            keyword_list = data.get("keywordList") or []
            # 정확히 일치하는 키워드 또는 첫 번째 결과 사용
            for item in keyword_list:
                rel = (item.get("relKeyword") or "").strip()
                if rel == keyword:
                    pc = _parse_monthly_count(item.get("monthlyPcQcCnt"))
                    mo = _parse_monthly_count(item.get("monthlyMobileQcCnt"))
                    total = pc + mo
                    logger.debug("키워드 '%s' 월간 검색량: PC=%s, 모바일=%s → %s", keyword, pc, mo, total)
                    return float(total)
            # 일치 없으면 첫 번째 관련 키워드 합산값 사용 (대안)
            if keyword_list:
                item = keyword_list[0]
                pc = _parse_monthly_count(item.get("monthlyPcQcCnt"))
                mo = _parse_monthly_count(item.get("monthlyMobileQcCnt"))
                total = pc + mo
                logger.debug("키워드 '%s' 관련어 검색량 사용: %s", keyword, total)
                return float(total)
            return 0.0
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                logger.warning("API 확인 필요 (403 Forbidden): config.py API 키·승인 확인")
            else:
                logger.warning(
                    "네이버 검색광고 API 요청 실패 (시도 %d/%d): %s - %s",
                    attempt, MAX_RETRIES, keyword, e,
                )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SEC)
            else:
                return None  # 프로그램 중단 없이 None 반환
        except requests.exceptions.RequestException as e:
            logger.warning("API 확인 필요 (요청 실패): %s", e)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SEC)
            else:
                return None
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("API 확인 필요 (파싱 오류): %s", e)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SEC)
            else:
                return None

    return None


T = TypeVar("T")


def with_retry(
    fn: Callable[[], T],
    max_retries: int = MAX_RETRIES,
    delay: float = RETRY_DELAY_SEC,
    name: str = "함수",
) -> T | None:
    """제네릭 retry 래퍼. 예외 시 재시도."""
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as e:
            logger.warning("%s 실패 (시도 %d/%d): %s", name, attempt, max_retries, e)
            if attempt < max_retries:
                time.sleep(delay)
            else:
                logger.exception("%s 최종 실패", name)
                return None
    return None
