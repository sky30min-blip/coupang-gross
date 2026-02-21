# 쿠팡그로스 (Coupang Gross)

네이버 트렌드 키워드 + 쿠팡 시장성 분석 + 도매 최저가 탐지 대시보드입니다.

## 주요 기능

- **트렌드 키워드** 수집 및 니치 테스트
- **쿠팡 시장성 분석** (파트너스 API)
- **도매 최저가 탐지** (도매꾹·오너클랜, 자동 로그인)
- **수익 계산** (수수료·광고비·배송비·부가세 반영)
- **Streamlit 대시보드**로 결과 확인 및 작업 실행

## 설치

```bash
pip install -r requirements.txt
playwright install
```

`config.example.py`를 복사해 `config.py`로 만들고 API 키·도매 계정을 입력하세요.  
자세한 설정은 `README_API설정.md`를 참고하세요.

## 실행

- **대시보드**: `streamlit run app.py`
- **도매 검색**: `python wholesale_searcher.py`

## 주의

- `config.py`에는 API 키와 비밀번호가 들어가므로 **Git에 올리지 마세요.** (`.gitignore`에 포함됨)
