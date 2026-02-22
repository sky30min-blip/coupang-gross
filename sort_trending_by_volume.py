"""
trending_keywords.csv 전체 키워드에 대해 네이버 검색량을 조회한 뒤,
검색량 내림차순으로 정렬하여 trending_keywords.csv를 덮어씁니다.

→ 이후 니치분석/니치테스트의 '상위 50개' = 5개 카테고리 통틀어 검색량 상위 50개.
(트렌드 수집 후 이 스크립트를 실행한 다음 니치분석을 돌리면 됩니다.)
"""

import csv
import time
from pathlib import Path

TRENDING_CSV = Path(__file__).resolve().parent / "trending_keywords.csv"
API_CALL_INTERVAL = 0.25


def main():
    if not TRENDING_CSV.exists():
        print(f"오류: {TRENDING_CSV} 없음. 먼저 '📥 트렌드' 수집을 실행하세요.")
        return

    try:
        from naver_api_keys import CUSTOMER_ID, ACCESS_LICENSE, SECRET_KEY
        from naver_api import get_monthly_search_volume
    except ImportError:
        print("오류: naver_api_keys.py 또는 naver_api.py 없음. 네이버 검색광고 API 설정 후 실행하세요.")
        return

    rows = []
    with open(TRENDING_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        base_fieldnames = [c for c in (reader.fieldnames or []) if c != "search_volume"]
        for row in reader:
            kw = (row.get("keyword") or "").strip()
            if kw:
                rows.append({k: row.get(k, "") for k in base_fieldnames})

    if not rows:
        print("trending_keywords.csv에 키워드가 없습니다.")
        return

    total = len(rows)
    print(f"트렌드 검색량 정렬: {total}개 키워드 검색량 조회 후 검색량 순 정렬")
    print(f"(호출 간격 {API_CALL_INTERVAL}초, 약 {total * API_CALL_INTERVAL / 60:.1f}분 소요)")
    print()

    for i, row in enumerate(rows):
        kw = row["keyword"]
        try:
            vol = get_monthly_search_volume(
                keyword=kw,
                customer_id=CUSTOMER_ID,
                license_key=ACCESS_LICENSE,
                secret_key=SECRET_KEY,
            )
            row["search_volume"] = int(vol) if vol is not None else 0
        except Exception:
            row["search_volume"] = 0
        print(f"[{i + 1}/{total}] {kw} → {row['search_volume']:,}")
        if i < total - 1:
            time.sleep(API_CALL_INTERVAL)

    rows.sort(key=lambda r: (r.get("search_volume") or 0) if isinstance(r.get("search_volume"), (int, float)) else 0, reverse=True)

    fieldnames = base_fieldnames + ["search_volume"]
    with open(TRENDING_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"저장 완료: {TRENDING_CSV} (검색량 높은 순으로 정렬됨)")
    print("이제 '니치분석' 또는 '니치테스트'를 실행하면 상위 50개 = 전체 카테고리에서 검색량 상위 50개입니다.")


if __name__ == "__main__":
    main()
