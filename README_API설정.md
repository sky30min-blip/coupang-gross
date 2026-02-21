# 쿠팡 파트너스 API 설정

니치 분석·시장성 분석이 **쿠팡 파트너스 API**를 사용합니다.

## 1. API 키 발급

1. [쿠팡 파트너스](https://partners.coupang.com) 로그인
2. **도구** → **파트너스 API** 메뉴
3. **Access Key**, **Secret Key** 복사

## 2. 설정 파일 생성

1. `coupang_config.example.py`를 복사
2. `coupang_config.py`로 이름 변경
3. 키 입력:

```python
COUPANG_ACCESS_KEY = "발급받은-Access-Key"
COUPANG_SECRET_KEY = "발급받은-Secret-Key"
```

## 3. 실행

- **니치 분석**: `python niche_analysis.py`
- **시장성 분석**: `python coupang_analyzer.py`

## 4. 주의사항

- API 호출 제한이 있음 (시간당 약 10회 등)
- `coupang_config.py`는 절대 git에 올리지 마세요 (API 키 노출)
