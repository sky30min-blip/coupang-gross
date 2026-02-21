"""
쿠팡그로스 대시보드 - 웹에서 데이터 확인 및 작업 실행
데이터 검증(Validation) 시각화 포함
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

st.set_page_config(
    page_title="쿠팡그로스 대시보드",
    page_icon="🛒",
    layout="wide",
)

# 데이터 파일 경로 (절대경로로 고정해 한글 경로/터미널 인코딩 문제 완화)
BASE = Path(__file__).resolve().parent
TRENDING = BASE / "trending_keywords.csv"
NICHE_SCORE = BASE / "niche_score_report.csv"
NICHE_ANALYSIS = BASE / "niche_analysis.csv"
NICHE_TEST = BASE / "niche_test.csv"
FINAL_SOURCING = BASE / "final_sourcing_list.csv"
MARKET_CREDIBILITY = BASE / "market_credibility_report.csv"
SEASONAL_HUNTER = BASE / "seasonal_hunter_report.csv"
SEASONAL_CHARTS = BASE / "seasonal_charts"
NICHE_WITH_VOLUME = BASE / "niche_with_volume.csv"
TRENDING_WITH_VOLUME = BASE / "trending_with_volume.csv"
LIGHT_WEIGHT = BASE / "light_weight_niche.xlsx"
DB_PATH = BASE / "coupang_gross.db"
DEBUG_SCREENSHOTS = BASE / "debug_screenshots"
WHOLESALE_LOGIN_STATUS = BASE / "wholesale_login_status.json"


def _read_wholesale_login_status():
    if not WHOLESALE_LOGIN_STATUS.exists():
        return None
    try:
        import json
        with open(WHOLESALE_LOGIN_STATUS, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def run_script(script_name: str, desc: str) -> tuple[str, int]:
    """Python 스크립트 실행, (출력텍스트, 리턴코드) 반환. 로그 파일에도 기록."""
    script_path = (BASE / script_name).resolve()
    if not script_path.exists():
        return f"오류: {script_name} 파일을 찾을 수 없습니다.", 1
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        result = subprocess.run(
            [sys.executable, "-u", str(script_path)],
            cwd=str(BASE),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3600,
            env=env,
        )
        out = (result.stdout or "") + (result.stderr or "")
        out_stripped = out.strip() or f"{desc} 완료 (출력 없음)"
        log_dir = BASE / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        try:
            from datetime import datetime
            with open(log_dir / "dashboard_run.log", "a", encoding="utf-8") as f:
                f.write(f"\n=== {datetime.now().isoformat()} | {script_name} ===\n{out_stripped}\n")
        except Exception:
            pass
        return out_stripped, result.returncode
    except subprocess.TimeoutExpired:
        return "오류: 실행 시간 초과 (1시간)", 1
    except Exception as e:
        return f"오류: {e}", 1


# 상단: 제목(좌) + 도매 로그인 신호등(우)
_header_left, _header_right = st.columns([3, 1])
with _header_left:
    st.title("🛒 쿠팡그로스 대시보드")
    st.caption("네이버 트렌드 키워드 & 쿠팡 시장성 분석 결과")
with _header_right:
    _ls = _read_wholesale_login_status()
    _dg = _ls.get("domeggook") if _ls else None
    _oc = _ls.get("ownerclan") if _ls else None
    st.markdown("**도매 로그인**")
    if _dg is True:
        st.markdown("🟢 도매꾹")
    elif _dg is False:
        st.markdown("🔴 도매꾹")
    else:
        st.markdown("⚪ 도매꾹")
    if _oc is True:
        st.markdown("🟢 오너클랜")
    elif _oc is False:
        st.markdown("🔴 오너클랜")
    else:
        st.markdown("⚪ 오너클랜")
    if st.button("상태 확인", key="btn_wholesale_check", help="로그인만 시도 후 신호등 갱신"):
        with st.spinner("확인 중..."):
            run_script("check_wholesale_login.py", "로그인 상태 확인")
        st.rerun()


def _style_rocket_zero(df: pd.DataFrame, rocket_col: str = "rocket_count") -> Any:
    """로켓수 0인 행 주황색 강조"""
    if rocket_col not in df.columns:
        return df.style
    def _row_style(row):
        try:
            rc = row.get(rocket_col)
            if rc is not None and (rc == 0 or rc == "0"):
                return ["background-color: #ffcc80"] * len(row)
        except Exception:
            pass
        return [""] * len(row)
    return df.style.apply(_row_style, axis=1)


def _add_validation_icon(df: pd.DataFrame, rocket_col: str = "rocket_count", vcol: str = "verification_needed") -> pd.DataFrame:
    """로켓수 0 또는 verification_needed=Y인 행에 수동 검증 필요 아이콘 추가"""
    df = df.copy()
    if "_validation" not in df.columns:
        df["_validation"] = ""
    def _need(r):
        if str(r.get(vcol, "")).upper() == "Y":
            return "⚠️ 수동 검증 필요"
        if rocket_col in df.columns and r.get(rocket_col) is not None and r.get(rocket_col) == 0:
            return "⚠️ 수동 검증 필요"
        return ""
    df["_validation"] = df.apply(_need, axis=1)
    return df


# === 작업 실행 패널 (상단) ===
st.subheader("🚀 작업 실행")
st.markdown("아래 버튼을 눌러 각 작업을 실행하세요. 실행 후 해당 탭에서 결과를 확인할 수 있습니다.")

col1, col2, col3, col4, col5, col6, col7, col8, col9, col10 = st.columns(10)

with col1:
    if st.button(
        "📥 네이버 트렌드 스크래핑",
        key="btn_scraper",
        help="네이버 데이터랩 쇼핑 인사이트에서 최근 1주일 인기 검색어를 수집하여 trending_keywords.csv에 저장합니다. 이후 쿠팡 분석 작업의 입력 데이터로 사용됩니다.",
        use_container_width=True,
    ):
        with st.spinner("스크래핑 실행 중... (1~2분 소요)"):
            out, code = run_script("naver_shopping_insight_scraper.py", "네이버 트렌드 스크래핑")
        st.session_state["last_output"] = out
        st.session_state["last_code"] = code

with col2:
    if st.button(
        "📈 쿠팡 시장성 분석",
        key="btn_analyzer",
        help="trending_keywords.csv를 읽어 쿠팡 파트너스 API로 상품을 분석하고, 진입 가능성 점수(Opportunity Score)를 계산하여 niche_score_report.csv에 저장합니다. 상위 10개 키워드만 분석합니다.",
        use_container_width=True,
    ):
        with st.spinner("시장성 분석 실행 중... (약 30초~1분 소요)"):
            out, code = run_script("coupang_analyzer.py", "쿠팡 시장성 분석")
        st.session_state["last_output"] = out
        st.session_state["last_code"] = code

with col3:
    if st.button(
        "🔍 쿠팡 니치 분석",
        key="btn_niche",
        help="trending_keywords.csv를 읽어 쿠팡 파트너스 API로 로켓배송 상품 수, 평균가격, S/A/B 등급을 분석하여 niche_analysis.csv에 저장합니다. 최대 50개 키워드를 분석합니다.",
        use_container_width=True,
    ):
        with st.spinner("니치 분석 실행 중... (2~5분 소요, API 제한 적용)"):
            out, code = run_script("niche_analysis.py", "쿠팡 니치 분석")
        st.session_state["last_output"] = out
        st.session_state["last_code"] = code

with col4:
    if st.button(
        "🧪 니치 테스트 (상위 20개)",
        key="btn_niche_test",
        help="trending_keywords.csv 상위 20개 키워드만 쿠팡에서 분석하여 niche_test.csv에 저장합니다. 빠른 테스트용입니다.",
        use_container_width=True,
    ):
        with st.spinner("니치 테스트 실행 중... (약 1분 소요)"):
            out, code = run_script("niche_test.py", "니치 테스트")
        st.session_state["last_output"] = out
        st.session_state["last_code"] = code

with col5:
    if st.button(
        "🏪 도매 검색 (소싱 리스트)",
        key="btn_wholesale",
        help="niche_test.csv의 S/A등급 키워드를 도매꾹·오너클랜에서 검색하고, 광고비·수수료·배송비·부가세 반영 후 최종 순마진 15% 이상만 final_sourcing_list.csv로 저장합니다.",
        use_container_width=True,
    ):
        with st.spinner("도매 검색 실행 중... (5~15분 소요, 키워드 수에 따라)"):
            out, code = run_script("wholesale_searcher.py", "도매 검색")
        st.session_state["last_output"] = out
        st.session_state["last_code"] = code

with col6:
    if st.button(
        "📋 신뢰도 리포트",
        key="btn_credibility",
        help="niche_test.csv 키워드에 대해 Naver DataLab API로 검색 트렌드(1년)를 수집하고, 수요집중도·시즌성·안정성·독점가능성을 평가하여 market_credibility_report.csv로 저장합니다. 상위 5개 추이 그래프 이미지 저장.",
        use_container_width=True,
    ):
        with st.spinner("신뢰도 리포트 생성 중... (1~2분 소요)"):
            out, code = run_script("market_credibility_report.py", "신뢰도 리포트")
        st.session_state["last_output"] = out
        st.session_state["last_code"] = code

with col7:
    if st.button(
        "📦 사입 적합성 필터",
        key="btn_light",
        help="가격 1.5~6만원, 부피 큰 품목 제외, 묶음(세트/키트/팩) 가산점 적용 후 light_weight_niche.xlsx 저장",
        use_container_width=True,
    ):
        with st.spinner("사입 적합성 필터 적용 중..."):
            out, code = run_script("light_weight_filter.py", "사입 적합성 필터")
        st.session_state["last_output"] = out
        st.session_state["last_code"] = code

with col8:
    if st.button(
        "🔄 마스터 파이프라인",
        key="btn_main",
        help="trending_keywords.csv → Products DB → 쿠팡 분석 → 업데이트. 로그: logs/system.log",
        use_container_width=True,
    ):
        with st.spinner("마스터 파이프라인 실행 중... (2~5분)"):
            out, code = run_script("run_master.py", "마스터 파이프라인")
        st.session_state["last_output"] = out
        st.session_state["last_code"] = code

with col9:
    if st.button(
        "📅 시즌 헌터",
        key="btn_seasonal",
        help="niche_test.csv 키워드 3년치 시즌 패턴 분석. 매년 특정 월에 폭등하는 반복 시즌 키워드 추출.",
        use_container_width=True,
    ):
        with st.spinner("시즌 헌터 실행 중... (1~3분 소요)"):
            out, code = run_script("seasonal_analyzer.py", "시즌 헌터")
        st.session_state["last_output"] = out
        st.session_state["last_code"] = code

with col10:
    if st.button(
        "📊 검색량 수집",
        key="btn_volume",
        help="niche_test.csv 키워드에 네이버 검색광고 API로 검색량 추가 → niche_with_volume.csv (검색량↑ 로켓↓ 순)",
        use_container_width=True,
    ):
        with st.spinner("검색량 수집 중... (약 1~2분)"):
            out, code = run_script("naver_api_manager.py", "검색량 수집")
        st.session_state["last_output"] = out
        st.session_state["last_code"] = code

if "last_output" in st.session_state:
    code = st.session_state.get("last_code", 0)
    st.divider()
    st.caption("실행 결과")
    if code == 0:
        st.success("실행 완료")
    else:
        st.error("실행 중 오류가 발생했습니다.")
    st.code(st.session_state["last_output"], language="text")

st.divider()

# 탭 구성
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs(
    ["📊 트렌드", "📈 시장성", "🔍 니치", "🧪 니치테스트", "📊 검색량", "🏪 소싱", "📋 신뢰도", "📦 사입적합", "🗄️ DB", "📅 시즌헌터", "📋 요약"]
)

# === 탭1: 트렌드 키워드 ===
with tab1:
    if TRENDING.exists():
        df = pd.read_csv(TRENDING, encoding="utf-8-sig")
        st.subheader("네이버 쇼핑 인사이트 인기 검색어")
        st.write(f"총 **{len(df)}**개 키워드")
        col1, col2 = st.columns(2)
        with col1:
            cat_filter = st.multiselect("카테고리 필터", df["category"].unique().tolist(), default=df["category"].unique().tolist())
        with col2:
            search = st.text_input("키워드 검색", placeholder="키워드 입력...")
        df_filtered = df[df["category"].isin(cat_filter)]
        if search:
            df_filtered = df_filtered[df_filtered["keyword"].str.contains(search, case=False, na=False)]
        col_map = {"category": "카테고리", "rank": "순위", "keyword": "키워드", "change_trend": "변화추이"}
        st.dataframe(df_filtered.rename(columns=col_map), use_container_width=True, hide_index=True)
    else:
        st.warning("trending_keywords.csv 파일이 없습니다. 상단 '📥 네이버 트렌드 스크래핑' 버튼을 실행하세요.")

# === 탭2: 시장성 점수 (coupang_analyzer 결과) ===
with tab2:
    if NICHE_SCORE.exists():
        df = pd.read_csv(NICHE_SCORE, encoding="utf-8-sig")
        st.subheader("쿠팡 진입 가능성 점수")
        st.write(f"총 **{len(df)}**개 키워드 분석")

        # 요약 카드
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("평균 점수", f"{df['opportunity_score'].mean():.1f}")
        with c2:
            high = (df["opportunity_score"] >= 70).sum()
            st.metric("70점 이상", f"{high}개")
        with c3:
            st.metric("평균 로켓 수", f"{df['rocket_count'].mean():.1f}")
        with c4:
            st.metric("평균 가격대", f"{df['avg_price'].mean():,.0f}원")

        # 점수순 정렬
        score_min = st.slider("최소 진입점수", 0, 100, 0)
        df_filtered = df[df["opportunity_score"] >= score_min].sort_values("opportunity_score", ascending=False)
        col_map = {
            "category": "카테고리", "rank": "순위", "keyword": "키워드", "change_trend": "변화추이",
            "rocket_count": "로켓수", "avg_price": "평균가", "min_price": "최저가", "max_price": "최고가",
            "price_range": "가격폭", "avg_reviews": "평균리뷰", "opportunity_score": "진입점수",
            "total_products": "샘플수", "accuracy_rating": "신뢰도",
        }
        df_renamed = df_filtered.rename(columns=col_map)
        styled = _style_rocket_zero(df_renamed, "로켓수") if "rocket_count" in df_filtered.columns else df_renamed.style
        price_cols = [c for c in ["avg_price", "min_price", "max_price", "price_range"] if c in df_filtered.columns]
        if price_cols:
            fmt_map = {col_map[c]: "{:,.0f}" for c in price_cols if col_map[c] in df_renamed.columns}
            if fmt_map:
                styled = styled.format(fmt_map)
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.warning("niche_score_report.csv 파일이 없습니다. 상단 '📈 쿠팡 시장성 분석' 버튼을 실행하세요.")

# === 탭3: 니치 분석 (niche_analysis 결과) ===
with tab3:
    if NICHE_ANALYSIS.exists():
        df = pd.read_csv(NICHE_ANALYSIS, encoding="utf-8-sig")
        st.subheader("쿠팡 니치 분석 (로켓/가격/리뷰)")
        st.write(f"총 **{len(df)}**개 키워드")
        grade_filter = st.multiselect("등급 필터", ["S", "A", "B"], default=["S", "A"])
        df_filtered = df[df["grade"].isin(grade_filter)]
        col_map = {
            "category": "카테고리", "rank": "순위", "keyword": "키워드", "change_trend": "변화추이",
            "rocket_count": "로켓수", "total_products": "상품수", "avg_price": "평균가",
            "max_reviews": "최대리뷰", "grade": "등급",
        }
        df_renamed = df_filtered.rename(columns=col_map)
        styled = _style_rocket_zero(df_renamed, "로켓수") if "rocket_count" in df_filtered.columns else df_renamed.style
        if "avg_price" in df_filtered.columns:
            styled = styled.format({"평균가": "{:,.0f}"})
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.warning("niche_analysis.csv 파일이 없습니다. 상단 '🔍 쿠팡 니치 분석' 버튼을 실행하세요.")

# === 탭4: 니치 테스트 (상위 20개) ===
with tab4:
    if NICHE_TEST.exists():
        df = pd.read_csv(NICHE_TEST, encoding="utf-8-sig")
        st.subheader("쿠팡 니치 테스트 (상위 20개)")
        st.write(f"총 **{len(df)}**개 키워드 | 주황색 행 = 로켓 0 → 수동 검증 필요")
        grade_filter = st.multiselect("등급 필터 ", ["S", "A", "B"], default=["S", "A"], key="grade_filter_test")
        df_filtered = df[df["grade"].isin(grade_filter)]
        col_map = {
            "category": "카테고리", "rank": "순위", "keyword": "키워드", "change_trend": "변화추이",
            "rocket_count": "로켓수", "total_products": "상품수", "avg_price": "평균가",
            "max_reviews": "최대리뷰", "grade": "등급",
        }
        df_valid = _add_validation_icon(df_filtered, "rocket_count")
        col_map["_validation"] = "⚠️검증"

        col_tbl, col_val = st.columns([3, 1])
        with col_tbl:
            df_renamed = df_valid.rename(columns=col_map)
            styled = _style_rocket_zero(df_renamed, "로켓수") if "rocket_count" in df_valid.columns else df_renamed.style
            if "평균가" in df_renamed.columns:
                styled = styled.format({"평균가": "{:,.0f}"})
            st.dataframe(styled, use_container_width=True, hide_index=True)

        with col_val:
            keywords_list = df_filtered["keyword"].dropna().astype(str).tolist()
            selected_kw = st.selectbox("키워드 선택 (검증 이미지)", [""] + keywords_list, key="kw_select_niche")
            if selected_kw:
                safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in selected_kw)
                for p in [DEBUG_SCREENSHOTS / f"{safe_name}.png", DEBUG_SCREENSHOTS / f"{selected_kw}.png", BASE / "debug_screenshot.png"]:
                    if p.exists():
                        st.image(str(p), caption=f"검증: {selected_kw}", use_container_width=True)
                        break
                else:
                    st.caption("검증 스크린샷 없음 (debug_screenshots/ 폴더)")

                # 수동 검증 재조사: 시각 스크래퍼로 해당 키워드만 재분석 → niche_test.csv, DB 반영
                if st.button("🔁 수동 검증 재조사", key="btn_verify_rescan"):
                    sys.path.insert(0, str(BASE))
                    try:
                        from coupang_visual_fallback import scrape_and_save
                        from core.database import update_product_rocket_count
                        fallback = scrape_and_save(selected_kw)
                        if fallback.get("error"):
                            st.error(f"시각 검증 실패: {fallback['error']} (쿠팡 차단 시 발생)")
                        else:
                            new_rocket = fallback.get("rocket_count", 0)
                            # niche_test.csv 해당 행 업데이트
                            ntf = pd.read_csv(NICHE_TEST, encoding="utf-8-sig")
                            mask = ntf["keyword"] == selected_kw
                            if mask.any():
                                ntf.loc[mask, "rocket_count"] = new_rocket
                                ntf.loc[mask, "verification_needed"] = ""
                                grade = "S" if new_rocket < 5 else ("A" if new_rocket <= 10 else "B")
                                ntf.loc[mask, "grade"] = grade
                                ntf.to_csv(NICHE_TEST, index=False, encoding="utf-8-sig")
                            # DB 반영
                            opp = 80 - new_rocket * 5 if new_rocket < 15 else 10
                            updated = update_product_rocket_count(selected_kw, new_rocket, opp)
                            st.success(f"재조사 완료: 로켓 {new_rocket}개 | DB 반영: {'됨' if updated else '해당 없음'}")
                            st.rerun()
                    except Exception as e:
                        st.error(f"재조사 오류: {e}")

                with st.expander(f"📊 {selected_kw} 상세 분석"):
                    if st.button("3년 트렌드 + 검색량 조회", key=f"fetch_{selected_kw}"):
                        sys.path.insert(0, str(BASE))
                        from dashboard_helpers import fetch_trend_3year, fetch_search_volume
                        periods, ratios = fetch_trend_3year(selected_kw)
                        vol = fetch_search_volume(selected_kw)
                        st.session_state["keyword_detail"] = {"kw": selected_kw, "periods": periods, "ratios": ratios, "vol": vol}
                    detail = st.session_state.get("keyword_detail", {})
                    if detail.get("kw") == selected_kw and (detail.get("periods") or detail.get("vol")):
                        if detail.get("periods") and detail.get("ratios") and HAS_PLOTLY:
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(x=detail["periods"], y=detail["ratios"], mode="lines+markers", name="검색량(상대)"))
                            fig.update_layout(title=f"'{selected_kw}' 3년 트렌드", xaxis_title="월", height=250)
                            st.plotly_chart(fig, use_container_width=True)
                        if detail.get("vol") is not None:
                            st.metric("실시간 검색량 (월)", f"{int(detail['vol']):,}")
                    elif st.session_state.get("keyword_detail", {}).get("kw") == selected_kw and not detail.get("periods") and detail.get("vol") is None:
                        st.info("API 키 확인 필요 (config.py)")
                    if not HAS_PLOTLY:
                        st.caption("pip install plotly")
    else:
        st.warning("niche_test.csv 파일이 없습니다. 상단 '🧪 니치 테스트 (상위 20개)' 버튼을 실행하세요.")

# === 탭5: 검색량 (niche_with_volume / trending_with_volume) ===
with tab5:
    vol_df = None
    vol_title = ""
    if NICHE_WITH_VOLUME.exists():
        vol_df = pd.read_csv(NICHE_WITH_VOLUME, encoding="utf-8-sig")
        vol_title = "검색량 포함 니치 결과 (niche_with_volume.csv)"
    elif TRENDING_WITH_VOLUME.exists():
        vol_df = pd.read_csv(TRENDING_WITH_VOLUME, encoding="utf-8-sig")
        vol_title = "검색량 포함 트렌드 (trending_with_volume.csv)"
    if vol_df is not None and not vol_df.empty:
        st.subheader(vol_title)
        st.write(f"총 **{len(vol_df)}**개 키워드 (검색량↑ 로켓↓ 순 정렬)")
        st.caption("niche_test.csv에 네이버 검색광고 API로 검색량 추가. 상단 '📊 검색량 수집' 버튼으로 생성.")
        col_map_vol = {c: c for c in vol_df.columns}
        if "keyword" in vol_df.columns:
            col_map_vol["keyword"] = "키워드"
        if "rocket_count" in vol_df.columns:
            col_map_vol["rocket_count"] = "로켓수"
        vol_display = vol_df.rename(columns=col_map_vol)
        st.dataframe(vol_display, use_container_width=True, hide_index=True)
    else:
        st.warning("niche_with_volume.csv가 없습니다. 먼저 '🧪 니치 테스트'를 실행한 뒤 '📊 검색량 수집' 버튼을 실행하세요.")

# === 탭6: 소싱 리스트 (final_sourcing_list) ===
with tab6:
    if FINAL_SOURCING.exists():
        df = pd.read_csv(FINAL_SOURCING, encoding="utf-8-sig")
        st.subheader("최종 소싱 리스트 (최종 순마진 15% 이상)")
        st.caption("광고비(15%)·수수료·배송비·부가세 반영 후 순이익 기준 (광고비 제외 후 순이익)")
        st.write(f"총 **{len(df)}**건")
        col_config = {}
        if "도매처링크" in df.columns:
            col_config["도매처링크"] = st.column_config.LinkColumn("도매처링크", display_text="열기")
        if "쿠팡가" in df.columns:
            col_config["쿠팡가"] = st.column_config.NumberColumn("쿠팡가", format="%d원")
        if "도매가(최저)" in df.columns:
            col_config["도매가(최저)"] = st.column_config.NumberColumn("도매가(최저)", format="%d원")
        if "예상 순이익" in df.columns:
            col_config["예상 순이익"] = st.column_config.NumberColumn("예상 순이익", format="%d원")
        if "최종 순마진액" in df.columns:
            col_config["최종 순마진액"] = st.column_config.NumberColumn(
                "최종 순마진액 (광고비 제외 순이익)", format="%d원",
                help="광고비·수수료·배송비·부가세 차감 후 순이익"
            )
        if "최종 순마진율" in df.columns:
            col_config["최종 순마진율"] = st.column_config.TextColumn("최종 순마진율")
        if "순마진율" in df.columns:
            col_config["순마진율"] = st.column_config.TextColumn("순마진율")
        if "최종 소싱처" in df.columns:
            col_config["최종 소싱처"] = st.column_config.TextColumn("최종 소싱처", help="도매꾹/오너클랜 중 더 저렴한 곳")
        st.dataframe(df, use_container_width=True, hide_index=True, column_config=col_config or None)
    else:
        st.warning("final_sourcing_list.csv 파일이 없습니다. 상단 '🏪 도매 검색 (소싱 리스트)' 버튼을 실행하세요.")

# === 탭7: 신뢰도 리포트 ===
with tab7:
    if MARKET_CREDIBILITY.exists():
        df = pd.read_csv(MARKET_CREDIBILITY, encoding="utf-8-sig")
        st.subheader("데이터 기반 진입 신뢰도 리포트")
        st.write(f"총 **{len(df)}**건")
        st.caption("이건 지금 사야 해(시즌) | 이건 1년 내내 팔려(스테디) | 이건 함정(하락세)")
        rec_filter = st.multiselect("진입권장 필터", df["진입권장여부"].unique().tolist(), default=df["진입권장여부"].unique().tolist(), key="rec_filter")
        df_filtered = df[df["진입권장여부"].isin(rec_filter)]
        st.dataframe(df_filtered, use_container_width=True, hide_index=True)
        charts_dir = BASE / "credibility_charts"
        if charts_dir.exists():
            imgs = list(charts_dir.glob("*.png"))
            if imgs:
                st.subheader("상위 5개 검색량 추이")
                for p in sorted(imgs)[:5]:
                    st.image(str(p), caption=p.stem, use_container_width=True)
    else:
        st.warning("market_credibility_report.csv 파일이 없습니다. 상단 '📋 신뢰도 리포트' 버튼을 실행하세요. (config.py에 네이버 데이터랩 API 키 필요)")

# === 탭8: 사입 적합 ===
with tab8:
    if LIGHT_WEIGHT.exists():
        df = pd.read_excel(LIGHT_WEIGHT, engine="openpyxl")
        st.subheader("사입 적합성 필터 (light_weight_niche.xlsx)")
        st.write(f"총 **{len(df)}**건 (가격 1.5~6만원, 부피 큰 품목 제외, 묶음 가산)")
        price_cols = [c for c in ["평균가", "avg_price"] if c in df.columns]
        if price_cols:
            df_display = df.copy()
            try:
                df_display = df_display.style.format({price_cols[0]: "{:,.0f}"})
            except Exception:
                pass
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.warning("light_weight_niche.xlsx 파일이 없습니다. 상단 '📦 사입 적합성 필터' 버튼을 실행하세요.")

# === 탭9: DB (SQLite) ===
with tab9:
    if DB_PATH.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(str(DB_PATH))
            # Products 테이블 우선 (마스터 시스템)
            try:
                df = pd.read_sql_query("SELECT keyword, category, naver_rank, naver_search_vol, coupang_avg_price, rocket_count, opportunity_score, updated_at FROM Products ORDER BY updated_at DESC LIMIT 200", conn)
                col_map = {"keyword": "키워드", "category": "카테고리", "naver_rank": "네이버순위", "naver_search_vol": "네이버검색량", "coupang_avg_price": "평균가", "rocket_count": "로켓수", "opportunity_score": "진입점수", "updated_at": "수정일시"}
            except Exception:
                df = pd.read_sql_query("SELECT keyword, category, collected_at, naver_rank, coupang_rocket_count, coupang_avg_price, consistency_score, validation_status FROM keyword_data ORDER BY collected_at DESC LIMIT 200", conn)
                col_map = {"keyword": "키워드", "category": "카테고리", "collected_at": "수집일시", "naver_rank": "네이버순위", "coupang_rocket_count": "로켓수", "coupang_avg_price": "평균가", "consistency_score": "일관성점수", "validation_status": "검증상태"}
            conn.close()
            st.subheader("SQLite DB (Products)")
            st.write(f"최근 **{len(df)}**건")
            df_display = df.rename(columns=col_map)
            fmt_cols = {c: "{:,.0f}" for c in ["평균가"] if c in df_display.columns}
            fmt_cols.update({c: "{:.1f}" for c in ["일관성점수", "진입점수", "네이버검색량"] if c in df_display.columns})
            if fmt_cols:
                df_display = df_display.style.format(fmt_cols)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"DB 조회 오류: {e}")
    else:
        st.warning("coupang_gross.db 없음. 상단 '🔄 마스터 파이프라인' 실행 후 생성됩니다.")

# === 탭10: 시즌 헌터 ===
with tab10:
    if SEASONAL_HUNTER.exists():
        df = pd.read_csv(SEASONAL_HUNTER, encoding="utf-8-sig")
        st.subheader("시즌 헌터 - 반복 시즌 키워드")
        st.write(f"총 **{len(df)}**개 키워드 분석")
        st.caption("매년 특정 월에만 검색량이 폭등하는 키워드. 앞으로 2개월 내 폭등 예정을 선제적으로 확인하세요.")
        upcoming_filter = st.radio("2개월 내 폭등 예정만", ["전체", "예정만"], horizontal=True, key="seasonal_filter")
        if upcoming_filter == "예정만":
            df_filtered = df[df["2개월 내 폭등 예정"] == "예"]
        else:
            df_filtered = df
        st.dataframe(df_filtered, use_container_width=True, hide_index=True)
        if SEASONAL_CHARTS.exists():
            imgs = list(SEASONAL_CHARTS.glob("*.png"))
            if imgs:
                st.subheader("3년치 검색량 추이 차트")
                for p in sorted(imgs)[:5]:
                    st.image(str(p), caption=p.stem.replace("_3year", ""), use_container_width=True)
    else:
        st.warning("seasonal_hunter_report.csv 파일이 없습니다. 상단 '📅 시즌 헌터' 버튼을 실행하세요. (config.py에 네이버 데이터랩 API 키 필요)")

# === 탭11: 요약 ===
with tab11:
    st.subheader("📋 실행 가이드")
    st.markdown("""
    | 순서 | 상단 버튼 | 결과 |
    |------|-----------|------|
    | 1 | 📥 네이버 트렌드 스크래핑 | trending_keywords.csv |
    | 2 | 📈 쿠팡 시장성 분석 | niche_score_report.csv |
    | 3 | 🔍 쿠팡 니치 분석 | niche_analysis.csv |
    | 4 | 🧪 니치 테스트 (상위 20개) | niche_test.csv |
    | 5 | 📊 검색량 수집 | niche_with_volume.csv |
    | 6 | 🏪 도매 검색 (소싱 리스트) | final_sourcing_list.csv |
    | 7 | 📋 신뢰도 리포트 | market_credibility_report.csv |
    | 8 | 📦 사입 적합성 필터 | light_weight_niche.xlsx |
    | 9 | 📅 시즌 헌터 | seasonal_hunter_report.csv |
    | 10 | 🔄 마스터 파이프라인 | coupang_gross.db (Products) |
    """)
    st.info("모든 작업은 상단 버튼에서 실행할 수 있습니다. 이 페이지를 새로고침(F5)하면 최신 CSV 데이터가 반영됩니다.")
    st.caption("💡 Cursor 터미널에서 한글 경로 때문에 오류가 나면: 대시보드 버튼으로 실행하거나, 폴더에서 run_web.bat / run_niche_test.bat 등을 더블클릭해서 실행하세요.")

# === 실행 로그 스트리밍 (하단) ===
st.divider()
with st.expander("📜 실행 로그 스트리밍", expanded=False):
    if "last_output" in st.session_state:
        st.caption("마지막 실행 결과")
        st.text_area("stdout", st.session_state["last_output"], height=200, disabled=True, key="log_area")
    log_path = BASE / "logs" / "dashboard_run.log"
    if log_path.exists():
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            tail = "".join(lines[-100:]) if len(lines) > 100 else "".join(lines)
            st.caption("로그 파일 (logs/dashboard_run.log 최근 100줄)")
            st.text_area("dashboard_run.log", tail, height=150, disabled=True, key="log_file_area")
        except Exception as e:
            st.caption(f"로그 파일 읽기 오류: {e}")
