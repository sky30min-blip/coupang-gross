"""
market_credibility_report.py
niche_test.csv를 읽어 '데이터 기반 진입 신뢰도 리포트' 생성
- Naver DataLab API로 검색 트렌드 수집 (최근 1년)
- 수요 집중도, 시즌성/안정성/독점가능성 평가
- market_credibility_report.csv 저장
- 상위 5개 검색량 추이 그래프 이미지 저장 (선택)
"""

import csv
import platform
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

INPUT_CSV = "niche_test.csv"
OUTPUT_CSV = "market_credibility_report.csv"
OUTPUT_DIR = "credibility_charts"
API_URL = "https://openapi.naver.com/v1/datalab/search"
KEYWORDS_PER_REQUEST = 5
DELAY_SEC = 1
TREND_YEARS = 1  # 1년 (3년은 startDate 2016-01-01 제한 있음)


def load_naver_config():
    try:
        from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
        if NAVER_CLIENT_ID == "여기에_입력" or NAVER_CLIENT_SECRET == "여기에_입력":
            print("오류: config.py에 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET를 입력하세요.")
            return None, None
        return NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
    except ImportError:
        print("오류: config.py가 없습니다.")
        print("  config.example.py를 복사해 config.py를 만들고")
        print("  NAVER_CLIENT_ID, NAVER_CLIENT_SECRET를 입력하세요.")
        print("  https://developers.naver.com 에서 데이터랩(검색어트렌드) API 등록")
        return None, None


def load_niche_data() -> list[dict]:
    path = Path(INPUT_CSV)
    if not path.exists():
        print(f"오류: {INPUT_CSV} 없음. 먼저 니치 테스트를 실행하세요.")
        return []
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def fetch_trend(client_id: str, client_secret: str, keywords: list[str]) -> dict | None:
    """Naver DataLab API로 키워드별 검색 트렌드 조회 (월간, 1년)"""
    end = datetime.now()
    start = end - timedelta(days=365 * TREND_YEARS)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    groups = [{"groupName": kw, "keywords": [kw]} for kw in keywords[:KEYWORDS_PER_REQUEST]]
    body = {
        "startDate": start_str,
        "endDate": end_str,
        "timeUnit": "month",
        "keywordGroups": groups,
    }
    try:
        r = requests.post(
            API_URL,
            headers={
                "X-Naver-Client-Id": client_id,
                "X-Naver-Client-Secret": client_secret,
                "Content-Type": "application/json",
            },
            json=body,
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  [API 오류] {e}")
    return None


def analyze_trend(data_list: list[dict]) -> dict:
    """period, ratio 리스트에서 수요집중도, 피크월, 시즌성, 안정성 계산"""
    if not data_list:
        return {
            "demand_concentration": 0,
            "peak_month": "-",
            "seasonality_score": 0,
            "stability_score": 0,
            "trend_direction": "flat",
            "ratios": [],
        }
    ratios = [float(d.get("ratio", 0) or 0) for d in data_list]
    periods = [d.get("period", "") for d in data_list]
    if not ratios:
        return {
            "demand_concentration": 0,
            "peak_month": "-",
            "seasonality_score": 0,
            "stability_score": 0,
            "trend_direction": "flat",
            "ratios": [],
        }

    avg = sum(ratios) / len(ratios) if ratios else 0
    current = ratios[-1] if ratios else 0
    demand_concentration = round((current / avg * 100), 1) if avg > 0 else 0

    peak_idx = ratios.index(max(ratios))
    peak_period = periods[peak_idx] if peak_idx < len(periods) else "-"
    peak_month = peak_period[:7] if peak_period else "-"  # yyyy-mm

    # 시즌성: 현재가 평균 대비 높으면 가산
    seasonality = min(100, (current / avg * 50) if avg > 0 else 0)

    # 안정성: 표준편차가 낮을수록 높음 (변동 적을수록)
    n = len(ratios)
    var = sum((x - avg) ** 2 for x in ratios) / n if n else 0
    std = var ** 0.5
    stability = max(0, 100 - std) if std else 100

    # 트렌드 방향: 최근 3개월 추이
    recent = ratios[-3:] if len(ratios) >= 3 else ratios
    if len(recent) >= 2 and recent[-1] > recent[0]:
        trend_direction = "up"
    elif len(recent) >= 2 and recent[-1] < recent[0]:
        trend_direction = "down"
    else:
        trend_direction = "flat"

    return {
        "demand_concentration": demand_concentration,
        "peak_month": peak_month,
        "seasonality_score": round(seasonality, 1),
        "stability_score": round(stability, 1),
        "trend_direction": trend_direction,
        "ratios": ratios,
        "periods": periods,
    }


def get_monopoly_level(rocket_count: int, trend_up: bool, stability_high: bool) -> str:
    """독점 가능성: 로켓 적고 트렌드 상승 → Best"""
    if rocket_count < 5 and trend_up:
        return "최상(Best)"
    if rocket_count < 5 and stability_high:
        return "우수"
    if rocket_count < 5:
        return "양호"
    if trend_up:
        return "보통"
    return "저조"


def get_recommendation(
    rocket_count: int,
    demand_concentration: float,
    trend_direction: str,
    margin_30_plus: bool = False,
) -> str:
    """
    진입권장여부
    강력 추천: (마진 30%+ & 로켓 5미만 & 수요집중도 상승) - margin은 final_sourcing_list 병합 시 사용
    """
    rocket_ok = rocket_count < 5
    demand_up = demand_concentration > 100
    trend_up = trend_direction == "up"

    if rocket_ok and (demand_up or trend_up) and (margin_30_plus or (demand_up and trend_up)):
        return "강력 추천"
    if rocket_ok and demand_up:
        return "추천 (시즌 아이템)"
    if rocket_ok and trend_direction == "flat":
        return "추천 (스테디셀러)"
    if trend_direction == "down":
        return "주의 (하락세)"
    if not rocket_ok and trend_up:
        return "검토"
    return "보통"


def save_chart(keyword: str, periods: list, ratios: list, out_dir: Path):
    """상위 5개 상품 검색량 추이 그래프 저장"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm
    except ImportError:
        return

    # 한글 폰트 설정 (Glyph missing 방지)
    if platform.system() == "Windows":
        plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False  # 마이너스 기호 깨짐 방지

    if not periods or not ratios:
        return

    plt.figure(figsize=(8, 4))
    x = range(len(periods))
    plt.plot(x, ratios, marker="o", linewidth=2, markersize=4)
    plt.xticks(x, [p[5:7] + "월" if len(p) >= 7 else p for p in periods], rotation=45)
    plt.ylabel("검색량 (상대값)")
    plt.title(f"'{keyword}' 검색 트렌드")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in keyword)
    out_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_dir / f"{safe_name}.png", dpi=100)
    plt.close()


def main():
    print("데이터 기반 진입 신뢰도 리포트")
    print("-" * 50)

    client_id, client_secret = load_naver_config()
    if not client_id or not client_secret:
        return

    rows = load_niche_data()
    if not rows:
        return

    keywords_all = [(r.get("keyword") or "").strip() for r in rows if (r.get("keyword") or "").strip()]
    print(f"대상 키워드 {len(keywords_all)}개, Naver DataLab API 호출 중...")

    trend_by_keyword = {}
    for i in range(0, len(keywords_all), KEYWORDS_PER_REQUEST):
        batch = keywords_all[i : i + KEYWORDS_PER_REQUEST]
        js = fetch_trend(client_id, client_secret, batch)
        time.sleep(DELAY_SEC)
        if not js:
            for kw in batch:
                trend_by_keyword[kw] = analyze_trend([])
            continue
        for res in js.get("results", []):
            kw = res.get("title", "")
            data = res.get("data", [])
            trend_by_keyword[kw] = analyze_trend(data)
        print(f"  {i + len(batch)}/{len(keywords_all)} 수집")

    # margin 30%+ 키워드 (final_sourcing_list 있으면)
    margin_30_keywords = set()
    sourcing_path = Path("final_sourcing_list.csv")
    if sourcing_path.exists():
        with open(sourcing_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                m = re.search(r"([\d.]+)", str(r.get("예상마진율", "")))
                if m and float(m.group(1)) >= 30:
                    margin_30_keywords.add((r.get("키워드") or "").strip())

    report = []
    for row in rows:
        kw = (row.get("keyword") or "").strip()
        if not kw:
            continue
        rank = row.get("rank", "")
        rocket = int(row.get("rocket_count") or 0)
        trend = trend_by_keyword.get(kw, analyze_trend([]))

        demand = trend["demand_concentration"]
        peak = trend["peak_month"]
        rec = get_recommendation(
            rocket,
            demand,
            trend["trend_direction"],
            margin_30_plus=kw in margin_30_keywords,
        )

        report.append({
            "상품명": kw,
            "현재랭킹": rank,
            "로켓수": rocket,
            "현재수요도(평균대비)": f"{demand}%",
            "피크월": peak,
            "진입권장여부": rec,
            "_seasonality": trend["seasonality_score"],
            "_stability": trend["stability_score"],
            "_monopoly": get_monopoly_level(
                rocket, trend["trend_direction"] == "up", trend["stability_score"] > 70
            ),
            "_ratios": trend.get("ratios", []),
            "_periods": trend.get("periods", []),
        })

    report.sort(key=lambda x: (0 if x["진입권장여부"] == "강력 추천" else 1, -x["_seasonality"] - x["_stability"]))

    out_path = Path(OUTPUT_CSV)
    fieldnames = ["상품명", "현재랭킹", "로켓수", "현재수요도(평균대비)", "피크월", "진입권장여부"]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in report:
            row = {k: r.get(k, "") for k in fieldnames}
            writer.writerow(row)

    print(f"\n저장 완료: {out_path.absolute()}")

    # 상위 5개 시각화
    out_dir = Path(OUTPUT_DIR)
    top5 = report[:5]
    for r in top5:
        save_chart(
            r["상품명"],
            r.get("_periods", []),
            r.get("_ratios", []),
            out_dir,
        )
    if top5:
        print(f"차트 저장: {out_dir.absolute()} ({len(top5)}개)")

    # 3대 지표 요약
    seasonal = [r for r in report if "시즌" in r["진입권장여부"]]
    steady = [r for r in report if "스테디" in r["진입권장여부"]]
    decline = [r for r in report if "하락" in r["진입권장여부"]]
    print("\n[3대 지표 요약]")
    print(f"  이건 지금 사야 해 (시즌): {len(seasonal)}개")
    print(f"  이건 1년 내내 팔려 (스테디): {len(steady)}개")
    print(f"  이건 함정 (하락세): {len(decline)}개")


if __name__ == "__main__":
    main()
