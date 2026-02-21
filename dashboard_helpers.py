"""대시보드용 API 헬퍼 - 트렌드/검색량 조회"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

API_URL = "https://openapi.naver.com/v1/datalab/search"


def load_naver_datalab_config():
    """config에서 네이버 데이터랩 키 로드"""
    try:
        from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
        cid = (NAVER_CLIENT_ID or "").strip()
        sec = (NAVER_CLIENT_SECRET or "").strip()
        if cid and sec and cid != "여기에_입력":
            return cid, sec
    except Exception:
        pass
    return None, None


def fetch_trend_3year(keyword: str) -> tuple[list[str], list[float]]:
    """3년치 월별 트렌드 조회 (periods, ratios)"""
    cid, sec = load_naver_datalab_config()
    if not cid or not sec:
        return [], []
    body = {
        "startDate": "2023-01-01",
        "endDate": datetime.now().strftime("%Y-%m-%d"),
        "timeUnit": "month",
        "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}],
    }
    try:
        r = requests.post(
            API_URL,
            headers={
                "X-Naver-Client-Id": cid,
                "X-Naver-Client-Secret": sec,
                "Content-Type": "application/json",
            },
            json=body,
            timeout=30,
        )
        if r.status_code != 200:
            return [], []
        data = r.json()
        for res in data.get("results", []):
            if res.get("title") == keyword:
                pts = res.get("data", [])
                periods = [p.get("period", "") for p in pts]
                ratios = [float(p.get("ratio", 0) or 0) for p in pts]
                return periods, ratios
    except Exception:
        pass
    return [], []


def fetch_search_volume(keyword: str) -> float | None:
    """네이버 검색광고 API로 월간 검색량 조회"""
    try:
        from config import CUSTOMER_ID, ACCESS_LICENSE, SECRET_KEY
        from naver_api import get_monthly_search_volume
        return get_monthly_search_volume(keyword, CUSTOMER_ID, ACCESS_LICENSE, SECRET_KEY)
    except Exception:
        return None
