"""
seasonal_analyzer.py - 시즌 헌터(Seasonal Hunter) 엔진
매년 특정 월에만 검색량이 급증하는 '반복 시즌 키워드'를 찾아내고,
앞으로 2개월 내 폭등 예정 상품을 선제적으로 알림.
"""

import csv
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

# 스크립트 위치를 sys.path에 추가 (config.py 로드용)
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_CSV = "niche_test.csv"
OUTPUT_CSV = "seasonal_hunter_report.csv"
OUTPUT_CHARTS = "seasonal_charts"
API_URL = "https://openapi.naver.com/v1/datalab/search"
KEYWORDS_PER_REQUEST = 5
DELAY_SEC = 1
TREND_YEARS = 3  # 2023~2025
SPIKE_THRESHOLD = 2.0  # 평균 대비 200% 이상 = 폭등
REPEAT_MIN_YEARS = 2   # 최소 2년 연속 같은 월에 폭등해야 재현성 인정


def load_config():
    """config.py에서 네이버 데이터랩 API 키 로드"""
    try:
        from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
        cid = (NAVER_CLIENT_ID or "").strip()
        sec = (NAVER_CLIENT_SECRET or "").strip()
        if not cid or not sec or cid == "여기에_입력" or sec == "여기에_입력":
            return None, None
        return cid, sec
    except ImportError as e:
        print(f"  (ImportError: {e})")
        return None, None


def load_keywords() -> list[str]:
    """niche_test.csv 또는 trending_keywords.csv에서 키워드 로드"""
    for fname in [INPUT_CSV, "trending_keywords.csv"]:
        path = Path(fname)
        if path.exists():
            rows = []
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    kw = (row.get("keyword") or "").strip()
                    if kw:
                        rows.append(kw)
            if rows:
                return rows[:100]  # 최대 100개 (API 호출 제한 고려)
    return []


def fetch_3year_trend(client_id: str, client_secret: str, keywords: list[str]) -> dict | None:
    """Naver DataLab API로 최근 3년(2023~2025) 월별 검색 트렌드 조회"""
    start_str = "2023-01-01"
    end = datetime.now()
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


def detect_seasonal_spike(periods: list[str], ratios: list[float]) -> dict | None:
    """
    월별 ratio에서 폭등 패턴 감지.
    특정 월이 평균 대비 200% 이상이고, 여러 해에 걸쳐 같은 월에 반복되는지 검사.
    반환: {"peak_month": 5, "avg_spike_ratio": 4.5} 또는 None
    """
    if not periods or not ratios or len(periods) != len(ratios):
        return None
    # period 형식: "2023-01-01" → 월만 추출
    month_ratios: dict[int, list[float]] = {}  # month(1~12) -> [ratio, ratio, ...] (년도별)
    for p, v in zip(periods, ratios):
        try:
            parts = p.split("-")
            if len(parts) >= 2:
                month = int(parts[1])
                month_ratios.setdefault(month, []).append(float(v or 0))
        except (ValueError, IndexError):
            continue

    avg_all = sum(ratios) / len(ratios) if ratios else 0
    if avg_all <= 0:
        return None

    best_month = None
    best_avg_spike = 0
    best_repeat_count = 0

    for month, vals in month_ratios.items():
        if not vals:
            continue
        month_avg = sum(vals) / len(vals)
        spike_ratio = month_avg / avg_all if avg_all > 0 else 0
        # 해당 월이 평균 대비 200% 이상이고, 2년 이상 데이터 있으면 재현성 있음
        if spike_ratio >= SPIKE_THRESHOLD and len(vals) >= REPEAT_MIN_YEARS:
            if spike_ratio > best_avg_spike:
                best_avg_spike = spike_ratio
                best_month = month
                best_repeat_count = len(vals)

    if best_month is None:
        return None
    return {
        "peak_month": best_month,
        "avg_spike_ratio": round(best_avg_spike * 100),
        "repeat_years": best_repeat_count,
        "periods": periods,
        "ratios": ratios,
    }


def get_secretary_advice(keyword: str, peak_month: int, spike_pct: int) -> str:
    """비서의 조언: 현재 월 기준으로 사입·입고 시기 안내"""
    now = datetime.now()
    current_month = now.month
    months_until_peak = (peak_month - current_month) % 12
    if months_until_peak <= 2 and months_until_peak >= 0:
        prep_month = (peak_month - 1) if peak_month > 1 else 12
        return (
            f"지금이 {current_month}월이니, "
            f"{prep_month}월 초에 사입을 완료하고 "
            f"{peak_month}월 초에 로켓그로스 입고를 끝내야 독점할 수 있습니다."
        )
    elif months_until_peak == 0:
        return f"이번 달({peak_month}월)이 피크입니다. 즉시 사입·입고를 서둘러야 합니다."
    elif 3 <= months_until_peak <= 5:
        return (
            f"피크까지 {months_until_peak}개월 남았습니다. "
            f"{peak_month - 1}월 전에 사입 준비를 시작하세요."
        )
    else:
        return (
            f"매년 {peak_month}월에 폭등합니다(평균 {spike_pct}% 상승). "
            f"사입 시점: {peak_month - 1}월 초."
        )


def save_png_chart(keyword: str, periods: list[str], ratios: list[float], out_dir: Path) -> None:
    """3년치 추이 PNG 차트 저장 (matplotlib)"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    if not periods or not ratios:
        return
    plt.figure(figsize=(10, 4))
    x = range(len(periods))
    plt.plot(x, ratios, marker="o", linewidth=2, markersize=4)
    step = max(1, len(periods) // 12)
    tick_idx = list(range(0, len(periods), step))[:15]
    plt.xticks(tick_idx, [periods[i][5:7] + "월" if len(periods[i]) >= 7 else periods[i] for i in tick_idx], rotation=45)
    plt.ylabel("검색량 (상대값)")
    plt.title(f"'{keyword}' 3년치 시즌 트렌드")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in keyword)
    out_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_dir / f"{safe_name}_3year.png", dpi=100)
    plt.close()


def ascii_chart(periods: list[str], ratios: list[float], width: int = 40, height: int = 8) -> str:
    """3년치 추이를 ASCII 텍스트 그래프로 표현"""
    if not periods or not ratios:
        return "(데이터 없음)"
    max_val = max(ratios) if ratios else 1
    min_val = min(ratios) if ratios else 0
    rng = max_val - min_val if max_val > min_val else 1
    lines = []
    # Y축: 최대 → 최소
    for row in range(height, -1, -1):
        threshold = min_val + rng * (row / height)
        line = ""
        for v in ratios:
            if v >= threshold - (rng / height / 2):
                line += "█"
            else:
                line += " "
        lines.append(line)
    # X축: 월 레이블 (간격 두고)
    labels = []
    step = max(1, len(periods) // 12)
    for i in range(0, len(periods), step):
        p = periods[i]
        if len(p) >= 7:
            labels.append(p[5:7] + "월")
        else:
            labels.append("")
    x_axis = " ".join(f"{l:>4}" for l in labels[:12])
    lines.append("-" * min(width, len(ratios)))
    lines.append(x_axis)
    return "\n".join(lines)


def main():
    print("=" * 50)
    print("시즌 헌터(Seasonal Hunter) - 반복 시즌 키워드 분석")
    print("=" * 50)

    client_id, client_secret = load_config()
    if not client_id or not client_secret:
        print("오류: config.py에 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET를 입력하세요.")
        return

    keywords = load_keywords()
    if not keywords:
        print(f"오류: {INPUT_CSV} 또는 trending_keywords.csv에 키워드가 없습니다.")
        return

    print(f"대상 키워드 {len(keywords)}개, 3년치 데이터 수집 중...")
    now = datetime.now()
    # 앞으로 2개월 (예: 2월이면 3월, 4월)
    upcoming_months = [(now.month + i - 1) % 12 + 1 for i in range(1, 3)]

    report = []
    for i in range(0, len(keywords), KEYWORDS_PER_REQUEST):
        batch = keywords[i : i + KEYWORDS_PER_REQUEST]
        js = fetch_3year_trend(client_id, client_secret, batch)
        time.sleep(DELAY_SEC)

        if not js:
            for kw in batch:
                report.append({
                    "키워드": kw,
                    "폭등 시점": "-",
                    "3년 평균 상승률": "-",
                    "2개월 내 폭등 예정": "아니오",
                    "비서의 조언": "(데이터 수집 실패)",
                    "_ascii": "",
                })
            continue

        for res in js.get("results", []):
            kw = res.get("title", "")
            data = res.get("data", [])
            periods = [d.get("period", "") for d in data]
            ratios = [float(d.get("ratio", 0) or 0) for d in data]

            spike = detect_seasonal_spike(periods, ratios)
            if spike:
                peak_month = spike["peak_month"]
                spike_pct = spike["avg_spike_ratio"]
                advice = get_secretary_advice(kw, peak_month, spike_pct)
                is_upcoming = peak_month in upcoming_months
                report.append({
                    "키워드": kw,
                    "폭등 시점": f"매년 {peak_month}월",
                    "3년 평균 상승률": f"평달 대비 {spike_pct}%",
                    "2개월 내 폭등 예정": "예" if is_upcoming else "아니오",
                    "비서의 조언": advice,
                    "_ascii": ascii_chart(periods, ratios),
                    "_periods": periods,
                    "_ratios": ratios,
                    "_peak_month": peak_month,
                })
            else:
                report.append({
                    "키워드": kw,
                    "폭등 시점": "-",
                    "3년 평균 상승률": "-",
                    "2개월 내 폭등 예정": "아니오",
                    "비서의 조언": "반복적 시즌 패턴이 뚜렷하지 않습니다.",
                    "_ascii": ascii_chart(periods, ratios),
                    "_periods": periods,
                    "_ratios": ratios,
                })

        print(f"  {min(i + KEYWORDS_PER_REQUEST, len(keywords))}/{len(keywords)} 수집")

    # 2개월 내 폭등 예정 먼저 정렬
    report.sort(key=lambda x: (0 if x.get("2개월 내 폭등 예정") == "예" else 1, -len(x.get("_ascii", ""))))

    # CSV 저장
    fieldnames = ["키워드", "폭등 시점", "3년 평균 상승률", "2개월 내 폭등 예정", "비서의 조언"]
    out_path = Path(OUTPUT_CSV)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in report:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    print(f"\n저장 완료: {out_path.absolute()}")

    # 시즌 키워드 요약
    seasonal = [r for r in report if r.get("폭등 시점") != "-"]
    upcoming = [r for r in report if r.get("2개월 내 폭등 예정") == "예"]
    print(f"\n[시즌 헌터 요약]")
    print(f"  반복 시즌 키워드: {len(seasonal)}개")
    print(f"  앞으로 2개월 내 폭등 예정: {len(upcoming)}개")
    if upcoming:
        print("  ▶ 선제 사입 추천:")
        for r in upcoming[:5]:
            print(f"    - {r['키워드']}: {r['폭등 시점']} | {r['비서의 조언'][:50]}...")

    # ASCII + PNG 차트 저장 (상위 5개 시즌 키워드)
    chart_dir = Path(OUTPUT_CHARTS)
    chart_dir.mkdir(parents=True, exist_ok=True)
    seasonal_top = [r for r in report if r.get("폭등 시점") != "-"][:5]
    if not seasonal_top:
        seasonal_top = report[:5]
    for r in seasonal_top:
        if r.get("_ascii"):
            safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in r["키워드"])
            with open(chart_dir / f"{safe_name}_trend.txt", "w", encoding="utf-8") as f:
                f.write(f"'{r['키워드']}' 3년치 검색량 추이\n")
                f.write(r["_ascii"])
        if r.get("_periods") and r.get("_ratios"):
            save_png_chart(r["키워드"], r["_periods"], r["_ratios"], chart_dir)
    if seasonal_top:
        print(f"\n차트 저장: {chart_dir.absolute()} (ASCII + PNG, 상위 5개)")


if __name__ == "__main__":
    main()
