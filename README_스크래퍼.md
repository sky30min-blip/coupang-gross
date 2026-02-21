# 네이버 데이터랩 쇼핑 인사이트 인기 검색어 스크래퍼

Python과 Playwright를 사용하여 네이버 데이터랩의 '쇼핑 인사이트' 페이지에서 인기 검색어 TOP 100을 수집합니다.

## 기능

- **카테고리**: 생활/주방, 디지털/가전 (기본 설정)
- **기간**: 최근 1주일
- **수집 데이터**: 순위, 키워드, 변화 추이(상승/하락 등)
- **저장 파일**: `trending_keywords.csv`
- **차단 방지**: 사람처럼 보이는 브라우저 헤더 및 설정 적용

## 설치

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. Playwright 브라우저 설치 (Chromium)
playwright install chromium
```

## 실행

```bash
python naver_shopping_insight_scraper.py
```

실행이 완료되면 `trending_keywords.csv` 파일이 생성됩니다.

## 출력 CSV 형식

| category | rank | keyword | change_trend |
|----------|------|---------|--------------|
| 생활/주방 | 1 | 키워드1 | ▲3 |
| 생활/주방 | 2 | 키워드2 | - |
| 디지털/가전 | 1 | 키워드1 | ▼2 |
| ... | ... | ... | ... |

## 설정 변경

`naver_shopping_insight_scraper.py` 상단에서 다음 값을 수정할 수 있습니다.

- `DEFAULT_CATEGORIES`: 수집할 카테고리 목록
- `TOP_KEYWORDS_COUNT`: 카테고리당 수집할 키워드 수 (기본 100)
- `DELAY_MIN`, `DELAY_MAX`: 액션 간 랜덤 대기 시간(초)
- `headless=True`: `False`로 변경 시 브라우저 실행 과정을 눈으로 확인 가능

## 참고

- 네이버 데이터랩 페이지 구조가 변경되면 선택자 수정이 필요할 수 있습니다.
- 과도한 요청 시 차단될 수 있으니 대기 시간을 늘려 사용하세요.
- 네이버 서비스 이용약관을 준수하여 사용하세요.
