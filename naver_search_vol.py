"""
naver_search_vol.py - 네이버 검색광고 API로 키워드별 지난 30일 PC/모바일 합산 검색량 조회
"""

import csv
import time
from pathlib import Path

from naver_api_keys import CUSTOMER_ID, SECRET_KEY, ACCESS_LICENSE
from naver_api import get_monthly_search_volume

# API 제한: 초당 5회 내외 → 호출 간 0.25초 대기
API_CALL_INTERVAL = 0.25

TRENDING_CSV = Path(__file__).resolve().parent / "trending_keywords.csv"
OUTPUT_CSV = Path(__file__).resolve().parent / "trending_with_volume.csv"


def get_search_volume(keyword: str) -> int | None:
    """
    특정 키워드의 지난 30일간 PC/모바일 합산 검색량 반환.
    네이버 검색광고 keywordstool API 사용.
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


def run_all():
    """trending_keywords.csv의 모든 키워드에 검색량을 추가하여 trending_with_volume.csv 저장"""
    if not TRENDING_CSV.exists():
        print(f"오류: {TRENDING_CSV} 파일이 없습니다.")
        return

    rows = []
    with open(TRENDING_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or []) + ["search_volume"]
        for row in reader:
            rows.append(row)

    total = len(rows)
    print(f"총 {total}개 키워드 검색량 조회 시작 (API 호출 간격 {API_CALL_INTERVAL}초)")

    for i, row in enumerate(rows):
        kw = (row.get("keyword") or "").strip()
        if not kw:
            row["search_volume"] = ""
            continue

        vol = get_search_volume(kw)
        row["search_volume"] = vol if vol is not None else ""
        print(f"[{i + 1}/{total}] {kw} → {vol if vol is not None else '실패'}")

        if i < total - 1:
            time.sleep(API_CALL_INTERVAL)

    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"저장 완료: {OUTPUT_CSV}")


if __name__ == "__main__":
    run_all()
