"""
쿠팡 파트너스 API 클라이언트 (HMAC 인증)
"""

import hashlib
import hmac
import time
from urllib.parse import quote

import requests

BASE_URL = "https://api-gateway.coupang.com"
# 파트너스 상품 검색 API 경로 (v1 포함)
SEARCH_PATH = "/v2/providers/affiliate_open_api/apis/openapi/v1/products/search"


def generate_hmac(method: str, path: str, query_string: str, secret_key: str, access_key: str) -> str:
    """
    HMAC-SHA256 서명 생성
    메시지: timestamp + method + path + query_string (query는 ? 제외, 예: keyword=xxx&limit=20)
    """
    datetime_str = time.strftime("%y%m%d", time.gmtime()) + "T" + time.strftime("%H%M%S", time.gmtime()) + "Z"
    message = datetime_str + method + path + query_string
    signature = hmac.new(
        secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={datetime_str}, signature={signature}"


def search_products(
    keyword: str,
    limit: int,
    access_key: str,
    secret_key: str,
    sub_id: str = "coupang_gross",
    min_price: int | None = None,
    max_price: int | None = None,
) -> dict | None:
    """
    쿠팡 파트너스 API - 상품 검색
    subId: 채널 ID (미입력 시 일부 계정에서 data 미반환될 수 있음)
    """
    time.sleep(1.5)  # API 차단 방지: 요청 간격 유지
    encoded_kw = quote(keyword, safe="", encoding="utf-8")
    query_string = f"keyword={encoded_kw}&limit={limit}&subId={sub_id}"
    # 참고: 쿠팡 파트너스 API는 minPrice/maxPrice 미지원. 향후 지원 시 사용.
    if min_price is not None:
        query_string += f"&minPrice={min_price}"
    if max_price is not None:
        query_string += f"&maxPrice={max_price}"

    path = SEARCH_PATH
    method = "GET"
    authorization = generate_hmac(method, path, query_string, secret_key, access_key)

    url = BASE_URL + path + "?" + query_string

    try:
        resp = requests.get(
            url,
            headers={
                "Authorization": authorization,
                "Content-Type": "application/json; charset=utf-8",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"  [API 오류] HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        rcode = data.get("rCode") or data.get("code")
        if rcode == "ERROR" or rcode == "400" or (isinstance(rcode, int) and rcode >= 400):
            msg = data.get("rMessage") or data.get("message", "Unknown")
            print(f"  [API 오류] rCode: {rcode} | rMessage: {msg}")
            return None
        return data
    except Exception as e:
        print(f"  [API 오류] {e}")
    return None
