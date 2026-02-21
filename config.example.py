# config.example.py - 이 파일을 config.py로 복사한 뒤 키를 입력하세요.
# config.py는 .gitignore에 등록되어 GitHub에 업로드되지 않습니다.

# 1. 네이버 검색광고 API
CUSTOMER_ID = "여기에_입력"
SECRET_KEY = "여기에_입력"
ACCESS_LICENSE = "여기에_입력"

# 2. 네이버 데이터랩 API
NAVER_CLIENT_ID = "여기에_입력"
NAVER_CLIENT_SECRET = "여기에_입력"

# 3. 쿠팡 파트너스 API
COUPANG_ACCESS_KEY = "여기에_입력"
COUPANG_SECRET_KEY = "여기에_입력"

# 4. 도매 사이트 자동 로그인 (wholesale_searcher.py용, 비워두면 비로그인 검색)
DOEMEGGOOK_ID = ""
DOEMEGGOOK_PW = ""
OWNERCLAN_ID = ""
OWNERCLAN_PW = ""

# (선택) 쿠팡 시각 스크래퍼용 User-Agent - 본인 브라우저와 동일하게 하려면 설정
# Chrome: 주소창에 chrome://version 입력 후 User Agent 복사
# COUPANG_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..."
