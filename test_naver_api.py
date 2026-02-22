"""네이버 검색광고 API 테스트 - 403 시 서버 응답 내용 확인"""
import logging
logging.basicConfig(level=logging.WARNING)  # DEBUG 끄고

import requests
from config import CUSTOMER_ID, SECRET_KEY, ACCESS_LICENSE
from naver_api import _get_headers

uri = "/keywordstool"
params = {"hintKeywords": "물티슈", "showDetail": 1}
headers = _get_headers("GET", uri, CUSTOMER_ID, ACCESS_LICENSE, SECRET_KEY)

resp = requests.get(
    "https://api.searchad.naver.com" + uri,
    params=params,
    headers=headers,
    timeout=15,
)

print("상태코드:", resp.status_code)
print("응답 본문:", resp.text[:500] if resp.text else "(비어있음)")
if resp.status_code == 200:
    import json
    data = resp.json()
    print("검색량(키워드리스트 샘플):", data.get("keywordList", [])[:2])
