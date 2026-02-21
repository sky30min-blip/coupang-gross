"""
사입 적합성 필터
niche_test.csv(또는 niche_analysis.csv)에 가격/키워드 제외/묶음 가산점 적용 → light_weight_niche.xlsx
"""

import csv
from pathlib import Path

INPUT_CSV = "niche_test.csv"
FALLBACK_CSV = "niche_analysis.csv"
OUTPUT_XLSX = "light_weight_niche.xlsx"

# 가격 필터: 15,000원 ~ 60,000원
PRICE_MIN = 15_000
PRICE_MAX = 60_000

# 제외 키워드 (부피 큰 품목)
EXCLUDE_KEYWORDS = ["가구", "가전", "침대", "소파", "의자", "건조대", "금고", "세탁기", "냉장고", "TV"]

# 묶음 판매 가산 키워드
BUNDLE_KEYWORDS = ["세트", "키트", "팩"]


def load_niche_data(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def contains_any(text: str, keywords: list[str]) -> bool:
    if not text:
        return False
    t = str(text).strip()
    return any(kw in t for kw in keywords)


def get_bundle_bonus(keyword: str) -> int:
    """묶음 판매 가능 상품 가산점 (1=가산)"""
    return 1 if contains_any(keyword, BUNDLE_KEYWORDS) else 0


def main():
    print("사입 적합성 필터")
    print("-" * 50)

    path = Path(INPUT_CSV)
    if not path.exists():
        path = Path(FALLBACK_CSV)
    if not path.exists():
        print(f"오류: {INPUT_CSV} 또는 {FALLBACK_CSV} 없음. 니치 분석을 먼저 실행하세요.")
        return

    rows = load_niche_data(path)
    if not rows:
        print("분석 데이터가 없습니다.")
        return

    print(f"입력: {path.name} ({len(rows)}건)")
    print()

    filtered = []
    for row in rows:
        kw = (row.get("keyword") or "").strip()
        avg_price = int(row.get("avg_price") or 0)

        # 1. 가격 필터
        if not (PRICE_MIN <= avg_price <= PRICE_MAX):
            continue

        # 2. 제외 키워드 (부피 큰 품목)
        if contains_any(kw, EXCLUDE_KEYWORDS):
            continue

        # 3. 묶음 가산점
        bundle_bonus = get_bundle_bonus(kw)

        filtered.append({
            **row,
            "묶음가산": bundle_bonus,
        })

    # 정렬: 묶음가산 내림차순, 등급(S>A>B), 순위
    grade_order = {"S": 0, "A": 1, "B": 2}
    filtered.sort(
        key=lambda r: (
            -r.get("묶음가산", 0),
            grade_order.get((r.get("grade") or "").upper(), 9),
            int(r.get("rank") or 999),
        )
    )

    # pandas로 Excel 저장
    try:
        import pandas as pd
    except ImportError:
        print("오류: pandas 필요. pip install pandas openpyxl")
        return

    df = pd.DataFrame(filtered)

    # 칼럼 순서 정리 (묶음가산 포함)
    base_cols = ["category", "rank", "keyword", "change_trend", "rocket_count", "total_products", "avg_price", "max_reviews", "grade"]
    if "묶음가산" not in df.columns:
        df["묶음가산"] = 0
    cols = [c for c in base_cols + ["묶음가산"] if c in df.columns]
    df = df[cols]

    # 한글 칼럼명
    col_map = {
        "category": "카테고리",
        "rank": "순위",
        "keyword": "상품명",
        "change_trend": "변화추이",
        "rocket_count": "로켓수",
        "total_products": "상품수",
        "avg_price": "평균가",
        "max_reviews": "최대리뷰",
        "grade": "등급",
        "묶음가산": "묶음가산",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    out_path = Path(OUTPUT_XLSX)
    df.to_excel(out_path, index=False, engine="openpyxl")

    print(f"저장 완료: {out_path.absolute()} ({len(filtered)}건)")
    print()
    print("[필터 조건]")
    print(f"  가격: {PRICE_MIN:,}원 ~ {PRICE_MAX:,}원")
    print(f"  제외: {', '.join(EXCLUDE_KEYWORDS)}")
    print(f"  묶음가산: {', '.join(BUNDLE_KEYWORDS)} 포함 시 +1")


if __name__ == "__main__":
    main()
