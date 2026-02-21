# 쿠팡그로스 아키텍처

## 폴더 구조

```
/쿠팡그로스
  ├── /config          # 로깅 설정
  ├── /database        # SQLite 저장 (coupang_gross.db)
  ├── /scrapers        # 사이트별 수집 (Naver, Coupang, Wholesale)
  ├── /analyzer        # 경쟁 강도 및 마진 계산
  ├── /validators      # 데이터 신뢰도 교차 검증
  ├── /tests           # 유닛 테스트
  └── main.py          # 통합 컨트롤러
```

## 데이터 신뢰도 검증 (3단계)

1. **수요 검증**: 네이버 쇼핑 인사이트(구매 의도) + 네이버 키워드 도구(검색량)
2. **공급 검증**: 쿠팡 검색 결과(로켓 상품 수) + 평균가
3. **신뢰도 점수**: 네이버·쿠팡 데이터 일관성 80% 이상 시 `Valid` 판정

## 로깅

- `system.log`: 전체 로그
- `error.log`: 에러만 기록
- 에러 발생 시 해당 키워드 건너뛰고 다음 키워드 계속 처리

## 스크래퍼 확장

새 도매 사이트 추가 시 `scrapers/base.py`의 `BaseScraper`를 상속:

```python
from scrapers.base import BaseScraper

class NewSiteScraper(BaseScraper):
    def get_source_name(self) -> str:
        return "new_site"
    def scrape_keyword(self, keyword: str) -> dict:
        # 수집 로직
        return {"price": ..., "url": ...}
```

## 유닛 테스트

```
python -m pytest tests/
# 또는
python tests/test_analyzer.py
python tests/test_validators.py
```
