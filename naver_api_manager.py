"""
naver_api_manager.py - 실시간 검색량 수집기
naver_api_keys.py에서 키를 불러와 네이버 검색광고 API로 최근 30일 PC+모바일 통합 검색량 조회
"""

import csv
import time
from pathlib import Path

from naver_api_keys import CUSTOMER_ID, ACCESS_LICENSE, SECRET_KEY
from naver_api import get_monthly_search_volume

# 초당 호출 제한 준수 (초당 약 5회 → 0.25초 간격)
API_CALL_INTERVAL = 0.25

INPUT_CSV = Path(__file__).resolve().parent / "niche_test.csv"
OUTPUT_CSV = Path(__file__).resolve().parent / "niche_with_volume.csv"


def fetch_search_volume(keyword: str) -> int | None:
    """
    키워드의 최근 30일간 PC+모바일 통합 검색량 반환.
    실패 시 None.
    """
    result = get_monthly_search_volume(
        keyword=keyword,
        customer_id=CUSTOMER_ID,
        license_key=ACCESS_LICENSE,
        secret_key=SECRET_KEY,
    )
    if result is not None:
        return int(result)
    return None


def run():
    """niche_test.csv의 모든 키워드에 검색량을 추가 → niche_with_volume.csv 저장 (검색량↑ 로켓↓ 순 정렬)"""
    if not INPUT_CSV.exists():
        print(f"오류: {INPUT_CSV} 파일이 없습니다.")
        return

    rows = []
    with open(INPUT_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or []) + ["search_volume"]
        for row in reader:
            rows.append(row)

    total = len(rows)
    print(f"총 {total}개 키워드 검색량 조회 시작 (호출 간격 {API_CALL_INTERVAL}초)")

    for i, row in enumerate(rows):
        kw = (row.get("keyword") or "").strip()
        if not kw:
            row["search_volume"] = 0
            continue

        vol = fetch_search_volume(kw)
        row["search_volume"] = vol if vol is not None else 0
        print(f"[{i + 1}/{total}] {kw} → {vol if vol is not None else '실패'}")

        if i < total - 1:
            time.sleep(API_CALL_INTERVAL)

    # 검색량은 많은데 로켓배송은 적은 순 정렬
    def sort_key(r):
        sv = r.get("search_volume")
        rc = r.get("rocket_count", "")
        vol = int(sv) if sv not in (None, "", "-") else 0
        try:
            rockets = int(rc) if rc != "" else 999
        except (ValueError, TypeError):
            rockets = 999
        return (-vol, rockets)  # 검색량 내림차순, 로켓수 오름차순

    rows.sort(key=sort_key)

    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"저장 완료: {OUTPUT_CSV} (검색량↑ 로켓↓ 순 정렬)")


if __name__ == "__main__":
    run()
