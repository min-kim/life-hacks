import os
import sqlite3
import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st
from dotenv import load_dotenv
import streamlit.components.v1 as components

# 기존 로직 모듈 임포트 (기존 파이썬 코드의 주요 함수들)
from NEST_pipeline import (
    DB_FILE,
    SEOUL_COURTS,
    evaluate_auction_properties_fast,
    fetch_all_seoul_auctions,
    fetch_filtered_auction_properties,
    init_db,
    send_telegram_message,
)

# 환경 변수 로드 (.env)
load_dotenv()

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="NEST - 부동산 경매 매물 분석 파이프라인",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# DB 초기화
init_db()

# ==========================================
# TARGETED GREEN ACCENT INJECTION (Preserve All Other Styles)
# ==========================================
components.html(
    """
    <script>
    const parentDoc = window.parent.document;
    
    function applyGreenAccent() {
        // 기존 테마 및 배경 CSS는 건드리지 않고, Primary 변수 및 선택 요소만 초록색으로 지정
        let customStyle = parentDoc.getElementById('custom-green-accent');
        if (!customStyle) {
            customStyle = parentDoc.createElement('style');
            customStyle.id = 'custom-green-accent';
            parentDoc.head.appendChild(customStyle);
        }
        
        customStyle.innerHTML = `
            :root {
                --primary-color: #2E7D32 !important;
            }
            /* Radio 버튼 선택 지점 */
            div[data-testid="stRadio"] div[role="radiogroup"] div[aria-checked="true"] {
                background-color: #2E7D32 !important;
                border-color: #2E7D32 !important;
            }
            /* Checkbox 선택 지점 */
            div[data-testid="stCheckbox"] label div[aria-checked="true"] {
                background-color: #2E7D32 !important;
                border-color: #2E7D32 !important;
            }
            /* Select / Multi-select 태그 칩 */
            div[data-baseweb="select"] div[aria-selected="true"],
            span[data-baseweb="tag"] {
                background-color: #2E7D32 !important;
            }
        `;
    }

    // DOM 렌더링 시점에 맞춰 주기적 실행 (Streamlit Cloud의 덮어쓰기 방지)
    applyGreenAccent();
    setInterval(applyGreenAccent, 500);
    </script>
    """,
    height=0,
)


# ==========================================
# HELPER FUNCTIONS & CACHING
# ==========================================
@st.cache_data(ttl=3600)
def load_db_processed_auctions():
    """SQLite DB에 저장된 검증 완료 매물 데이터 로드"""
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query(
            "SELECT * FROM processed_auctions ORDER BY score DESC", conn
        )
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df


# ==========================================
# SIDEBAR CONTROL PANEL
# ==========================================
st.sidebar.title("🏠 NEST Control Panel")
st.sidebar.markdown("---")

st.sidebar.subheader("1. 데이터 수집 설정")
selected_courts = st.sidebar.multiselect(
    "검색 대상 법원 선택",
    options=list(SEOUL_COURTS.keys()),
    default=list(SEOUL_COURTS.keys()),
)

building_type = st.sidebar.selectbox("매물 유형", ["빌라", "아파트"], index=0)
max_items_per_court = st.sidebar.number_input(
    "법원당 최대 수집 건수 (0: 전체)",
    min_value=0,
    max_value=200,
    value=20,
    step=10,
)
max_workers = st.sidebar.slider(
    "Multi-threading Worker 수", min_value=1, max_value=20, value=10
)

st.sidebar.markdown("---")
st.sidebar.subheader("2. 필터링 & 가중치 조건")
min_score = st.sidebar.slider(
    "최소 최종점수 (Score)", min_value=0.0, max_value=100.0, value=50.0, step=5.0
)
elevator_only = st.sidebar.checkbox("엘리베이터 필수 포함", value=True)

# 실행 버튼
run_pipeline_btn = st.sidebar.button("🚀 파이프라인 실행", use_container_width=True)


# ==========================================
# MAIN DASHBOARD AREA
# ==========================================
st.title("🎯 NEST: 부동산 경매 정밀 분석 & 필터링 시스템")
st.caption(
    "서울 전역 법원 실시간 API 수집 | Kakao Local API & 건축물대장 융합 검증 파이프라인"
)

# tab 구성을 통한 인터랙티브 UI 제공
tab1, tab2, tab3 = st.tabs(
    ["📊 분석 대시보드", "🗺️ 매물 위치 지도", "📜 전체 DB 데이터"]
)

# ------------------------------------------
# 파이프라인 실행 로직
# ------------------------------------------
if run_pipeline_btn:
    with st.spinner("🌐 대법원 API 수집 및 정밀 분석 파이프라인 가동 중..."):
        target_max_items = max_items_per_court if max_items_per_court > 0 else None
        collected_properties = []

        # 선택된 법원별 수집
        for court_name in selected_courts:
            court_code = SEOUL_COURTS[court_name]
            props = fetch_filtered_auction_properties(
                court_name=court_name,
                court_code=court_code,
                building_type=building_type,
                max_items=target_max_items,
            )
            collected_properties.extend(props)

        st.toast(f"수집 완료: 총 {len(collected_properties)}개 매물", icon="✅")

        # 멀티스레딩 고속 검증
        if collected_properties:
            top_df = evaluate_auction_properties_fast(
                collected_properties, top_n=5, max_workers=max_workers
            )
            st.success(f"검증 완료! DB 저장 및 텔레그램 알림 발송 완료.")
            st.cache_data.clear()  # 캐시 갱신
        else:
            st.warning("수집된 매물이 없습니다.")

# 데이터 로드
db_df = load_db_processed_auctions()

# 사용자 필터 적용
if not db_df.empty:
    filtered_df = db_df[db_df["score"] >= min_score]
    if elevator_only and "has_elevator" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["has_elevator"] == 1]
else:
    filtered_df = pd.DataFrame()

# ------------------------------------------
# TAB 1: 분석 대시보드
# ------------------------------------------
with tab1:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("DB 누적 검증 매물", f"{len(db_df)} 건")
    with col2:
        st.metric("현재 필터링 매물", f"{len(filtered_df)} 건")
    with col3:
        avg_score = (
            round(filtered_df["score"].mean(), 1) if not filtered_df.empty else 0
        )
        st.metric("평균 최종 점수", f"{avg_score} 점")
    with col4:
        top_score = filtered_df["score"].max() if not filtered_df.empty else 0
        st.metric("최고 매물 점수", f"{top_score} 점")

    st.markdown("---")

    if not filtered_df.empty:
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.subheader("📈 매물 최종 점수 분포")
            fig_hist = px.histogram(
                filtered_df,
                x="score",
                nbins=15,
                color_discrete_sequence=["#1f77b4"],
                labels={"score": "최종 점수"},
            )
            fig_hist.update_layout(margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_hist, use_container_width=True)

        with col_chart2:
            st.subheader("🌳 공원 거리 vs 스카/도서관 인프라")
            fig_scatter = px.scatter(
                filtered_df,
                x="min_park_dist",
                y="study_infra_count",
                size="score",
                color="court_name",
                hover_data=["address", "score"],
                labels={
                    "min_park_dist": "공원 거리(m)",
                    "study_infra_count": "주변 스카/도서관 개수",
                },
            )
            fig_scatter.update_layout(margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_scatter, use_container_width=True)

        st.subheader("🏆 Top Recommended Properties")
        st.dataframe(
            filtered_df.head(10),
            column_config={
                "naver_link": st.column_config.LinkColumn("네이버 부동산 링크"),
                "score": st.column_config.NumberColumn("최종 점수", format="%.2f 점"),
                "min_park_dist": st.column_config.NumberColumn(
                    "공원 거리(m)", format="%.1f m"
                ),
            },
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "조건에 일치하는 매물이 없거나 DB가 비어 있습니다. 사이드바에서"
            " 파이프라인을 실행해 주세요."
        )

# ------------------------------------------
# TAB 2: 매물 위치 지도 (Pydeck)
# ------------------------------------------
with tab2:
    st.subheader("🗺️ 서울시 검증 매물 입지 지도")
    # 카카오 좌표 추가 조회가 가능하거나 coordinate가 포함된 경우 시각화
    if not filtered_df.empty:
        st.info("💡 각 매물의 정밀 위치 및 입지 밀집도를 나타냅니다.")
        # 기본 위치 (서울시청 기준)
        view_state = pdk.ViewState(
            latitude=37.5665, longitude=126.9780, zoom=10, pitch=45
        )

        st.caption(
            "Pydeck Map 시각화를 지원하기 위해 좌표 데이터가 DB에 함께 업데이트됩니다."
        )
    else:
        st.warning("지도 표시를 위한 매물 데이터가 없습니다.")

# ------------------------------------------
# TAB 3: 전체 DB 데이터
# ------------------------------------------
with tab3:
    st.subheader("📂 SQLite DB 전체 기록")
    if not db_df.empty:
        st.dataframe(db_df, use_container_width=True)
        # CSV 다운로드 버튼
        csv = db_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 CSV 데이터 다운로드",
            data=csv,
            file_name="nest_auction_processed.csv",
            mime="text/csv",
        )
    else:
        st.write("저장된 데이터가 없습니다.")
