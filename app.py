import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
import calendar
import json

st.set_page_config(
    page_title="스케줄 최적화",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans+KR:wght@300;400;600;700&display=swap');

:root {
    --bg: #0d0f14;
    --surface: #141720;
    --surface2: #1c2030;
    --border: #2a2f40;
    --accent: #4f8ef7;
    --accent2: #e05c5c;
    --accent3: #54c78a;
    --accent4: #f0a040;
    --text: #d8dce8;
    --text-dim: #6b7280;
    --mono: 'IBM Plex Mono', monospace;
    --sans: 'IBM Plex Sans KR', sans-serif;
}

html, body, [class*="css"] {
    font-family: var(--sans);
    background-color: var(--bg);
    color: var(--text);
}

/* Header */
.main-header {
    padding: 2rem 0 1.5rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 2rem;
}
.main-header h1 {
    font-family: var(--mono);
    font-size: 1.6rem;
    font-weight: 600;
    color: var(--accent);
    letter-spacing: -0.02em;
    margin: 0;
}
.main-header p {
    color: var(--text-dim);
    font-size: 0.85rem;
    margin: 0.3rem 0 0;
    font-family: var(--mono);
}

/* Section labels */
.section-label {
    font-family: var(--mono);
    font-size: 0.7rem;
    letter-spacing: 0.15em;
    color: var(--accent);
    text-transform: uppercase;
    margin-bottom: 0.8rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--border);
}

/* Cards */
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1.2rem;
    margin-bottom: 1rem;
}

/* Shift badges */
.badge-d { background: #1a3a5c; color: #4f8ef7; padding: 2px 8px; border-radius: 3px; font-family: var(--mono); font-size: 0.75rem; font-weight: 600; }
.badge-e { background: #3a2a10; color: #f0a040; padding: 2px 8px; border-radius: 3px; font-family: var(--mono); font-size: 0.75rem; font-weight: 600; }
.badge-n { background: #1a1a3a; color: #8080f0; padding: 2px 8px; border-radius: 3px; font-family: var(--mono); font-size: 0.75rem; font-weight: 600; }
.badge-off { background: #1a2a1a; color: #54c78a; padding: 2px 8px; border-radius: 3px; font-family: var(--mono); font-size: 0.75rem; font-weight: 600; }

/* Schedule grid */
.schedule-grid {
    font-family: var(--mono);
    font-size: 0.78rem;
    border-collapse: collapse;
    width: 100%;
}
.schedule-grid th {
    background: var(--surface2);
    color: var(--text-dim);
    padding: 6px 10px;
    font-weight: 600;
    text-align: center;
    border: 1px solid var(--border);
    font-size: 0.7rem;
    letter-spacing: 0.05em;
}
.schedule-grid td {
    padding: 5px 8px;
    border: 1px solid var(--border);
    text-align: center;
    background: var(--surface);
}
.schedule-grid tr:hover td { background: var(--surface2); }
.th-holiday { color: var(--accent2) !important; }
.cell-d { color: #4f8ef7; font-weight: 600; }
.cell-e { color: #f0a040; font-weight: 600; }
.cell-n { color: #8080f0; font-weight: 600; }
.cell-off { color: var(--text-dim); }
.cell-request { outline: 1px solid var(--accent2); }

/* Stats table */
.stats-table { width: 100%; font-family: var(--mono); font-size: 0.8rem; border-collapse: collapse; }
.stats-table th { color: var(--text-dim); font-size: 0.68rem; letter-spacing: 0.1em; text-align: center; padding: 6px; border-bottom: 1px solid var(--border); }
.stats-table td { text-align: center; padding: 6px 10px; border-bottom: 1px solid var(--border); }
.stats-table tr:last-child td { border-bottom: none; }

/* Streamlit overrides */
.stButton > button {
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 4px;
    font-family: var(--mono);
    font-weight: 600;
    font-size: 0.85rem;
    padding: 0.5rem 1.5rem;
    transition: opacity 0.15s;
}
.stButton > button:hover { opacity: 0.85; }

div[data-testid="stNumberInput"] input,
div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] select,
div[data-testid="stDateInput"] input {
    background: var(--surface2);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 4px;
    font-family: var(--mono);
}

div[data-testid="stNumberInput"] label,
div[data-testid="stTextInput"] label,
div[data-testid="stDateInput"] label,
div[data-testid="stFileUploader"] label,
.stSlider label {
    color: var(--text) !important;
    font-family: var(--mono);
}

.stTabs [data-baseweb="tab-list"] {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    gap: 0;
}
.stTabs [data-baseweb="tab"] {
    font-family: var(--mono);
    font-size: 0.8rem;
    color: var(--text-dim);
    background: transparent;
    border: none;
    padding: 0.6rem 1.2rem;
}
.stTabs [aria-selected="true"] {
    color: var(--accent);
    border-bottom: 2px solid var(--accent);
}

.stDataFrame { font-family: var(--mono); }
.stSlider > div > div { background: var(--border); }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: var(--surface);
    border-right: 1px solid var(--border);
    color: var(--text);
}
section[data-testid="stSidebar"] .block-container { padding: 1rem; }
section[data-testid="stSidebar"] .stButton > button {
    font-size: 0.7rem;
    padding: 0.3rem 0.8rem;
}

/* Status messages */
.status-ok { color: var(--accent3); font-family: var(--mono); font-size: 0.85rem; }
.status-err { color: var(--accent2); font-family: var(--mono); font-size: 0.85rem; }
.status-warn { color: var(--accent4); font-family: var(--mono); font-size: 0.85rem; }

/* Solution navigator */
.sol-nav {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.6rem 1rem;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 4px;
    font-family: var(--mono);
    font-size: 0.8rem;
    margin-bottom: 1rem;
}
.sol-nav span { color: var(--text-dim); }
.sol-nav strong { color: var(--accent); }
</style>
""", unsafe_allow_html=True)


# ── Session state init ───────────────────────────────────────────────────────
def _init_state():
    # Calculate default start date and number of days for current month
    today = date.today()
    start_of_month = today.replace(day=1)
    _, last_day = calendar.monthrange(today.year, today.month)
    num_days_in_month = last_day

    defaults = {
        "doctors": [],
        "num_days": num_days_in_month,
        "start_date": start_of_month,
        "day_types": {},          # {day_idx: '평일'|'토'|'일'|'공'}
        "duty_requests": {},      # {day_idx: [D, E, N]}
        "shift_requests": {},     # {(n,d): set of 'd'|'e'|'n' (못하는)}
        "shift_requests1": {},    # {(n,d): str (원하는) or ''}
        "rules": {},              # {n: {rule_key: value}}
        "shift_adj": {},          # {n: int}
        "solutions": [],
        "summaries": [],
        "sol_idx": 0,
        "solved": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ── Helpers ──────────────────────────────────────────────────────────────────
DAY_LABELS = ['일','월','화','수','목','금','토']
SHIFT_COLORS = {'d': 'cell-d', 'e': 'cell-e', 'n': 'cell-n', '': 'cell-off'}

def get_day_label(start: date, idx: int) -> str:
    d = start + timedelta(days=idx)
    return DAY_LABELS[d.weekday() % 7 if d.weekday() != 6 else 0]
    # Python: Mon=0..Sun=6 → we want 일=0,월=1..토=6
    # weekday: Mon=0 → +1; Sun=6 → 0
    wd = d.weekday()
    return DAY_LABELS[(wd + 1) % 7]

def get_day_label(start: date, idx: int) -> str:
    d = start + timedelta(days=idx)
    wd = d.weekday()  # 0=Mon … 6=Sun
    kr = (wd + 1) % 7  # 0=Sun, 1=Mon … 6=Sat
    return DAY_LABELS[kr]

def is_holiday(start: date, idx: int) -> bool:
    d = start + timedelta(days=idx)
    wd = d.weekday()
    return wd >= 5  # Sat or Sun

def auto_day_types(start: date, num_days: int) -> dict:
    types = {}
    for i in range(num_days):
        lbl = get_day_label(start, i)
        types[i] = lbl if lbl in ('토', '일') else '평일'
    return types

def max_avr(x):
    if x == int(x):
        return int(x)
    return int(x) + 1

CHUNK = 15  # Number of days per chunk for display


# ── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="section-label">⚙ 기본 설정</div>', unsafe_allow_html=True)

    prev_start = st.session_state.start_date
    start_d = st.date_input("시작 날짜", value=prev_start, key="sb_start")
    if start_d != prev_start:
        st.session_state.start_date = start_d
        # start_date가 바뀌면 요일 계산도 다시 (토/일 자동 설정)
        st.session_state.day_types = auto_day_types(start_d, st.session_state.num_days)

    num_days = st.number_input("총 일수", min_value=7, max_value=60, value=st.session_state.num_days, step=1)
    st.session_state.num_days = int(num_days)

    st.divider()
    st.markdown('<div class="section-label">👨‍⚕️ 의사 관리</div>', unsafe_allow_html=True)

    with st.form("add_doctor_form"):
        new_name = st.text_input("이름 추가", placeholder="홍길동", key="new_doc_name")
        submitted = st.form_submit_button("추가")
        if submitted:
            name = new_name.strip()
            if name and name not in [d["name"] for d in st.session_state.doctors]:
                n = len(st.session_state.doctors)
                st.session_state.doctors.append({
                    "name": name,
                    "shift_adj": 0,
                })
                st.session_state.rules[n] = {
                    "rule0": 1, "rule1": 1, "rule2": 1,
                    "rule3": 1, "rule4": 1, "rule5": 5,
                    "rule6": 0, "rule7": 1, "rule8": 2,
                }
                st.session_state.shift_adj[n] = 0
                st.rerun()

    if st.session_state.doctors:
        for i, doc in enumerate(st.session_state.doctors):
            if st.session_state.get("editing_doctor") == i:
                # Edit mode
                col1, col2, col3 = st.columns([3, 1, 1])
                new_name = col1.text_input("새 이름", value=doc['name'], key=f"edit_name_{i}")
                if col2.button("확인", key=f"confirm_edit_{i}"):
                    if new_name.strip() and new_name.strip() not in [d["name"] for j, d in enumerate(st.session_state.doctors) if j != i]:
                        st.session_state.doctors[i]["name"] = new_name.strip()
                        st.session_state["editing_doctor"] = None
                        st.rerun()
                    else:
                        st.error("이름이 비어있거나 중복됩니다.")
                if col3.button("취소", key=f"cancel_edit_{i}"):
                    st.session_state["editing_doctor"] = None
                    st.rerun()
            else:
                # Normal mode
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.caption(f"[{i}] {doc['name']}")
                if col2.button("수정", key=f"edit_{i}"):
                    st.session_state["editing_doctor"] = i
                    st.rerun()
                if col3.button("✕", key=f"del_{i}"):
                    st.session_state.doctors.pop(i)
                    st.session_state["editing_doctor"] = None
                    st.rerun()

    st.divider()
    st.markdown('<div class="section-label">🔧 솔버 설정</div>', unsafe_allow_html=True)
    solver_mode = st.selectbox("모드", ["최적해 1개 (main)", "다중 솔루션 탐색 (main_alt)"], key="solver_mode")
    time_max = st.slider("최대 탐색 시간 (초)", 10, 300, 60, key="time_max")
    if solver_mode.startswith("다중"):
        sol_limit = st.number_input("최대 솔루션 수", 1, 20, 5, key="sol_limit")
        adv_limit = st.number_input("최소 편차에 추가 허용 편차", 0, 20, 0, key="adv_limit")
        st.markdown("*여기를 늘리면 최저 편차(최적값)보다 조금 더 높은 편차도 포함하여 더 많은 해를 탐색합니다.*")
    else:
        sol_limit = 1
        adv_limit = 0

    st.divider()
    st.markdown('<div class="section-label">💾 설정 저장/불러오기</div>', unsafe_allow_html=True)

    # ── [기존] JSON 대신 [변경] Excel 저장/불러오기 로직 ──
    col_save, col_load = st.columns(2)
    # ── [저장 로직: 보기 편한 Excel] ──────────────────────────────────────────
    if col_save.button("💾 설정 Excel 저장", use_container_width=True):
        # 1. 표시용 데이터 준비
        start_date = st.session_state.start_date # 시작 날짜 변수
        doctor_names = [d['name'] for d in st.session_state.doctors]
        num_days = len(st.session_state.duty_requests)
        date_list = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(num_days)]
        
        # 2. 데이터프레임 생성
        df_doctors = pd.DataFrame(st.session_state.doctors)
        
        df_rules = pd.DataFrame.from_dict(st.session_state.rules, orient='index')
        df_rules.index = doctor_names  # 인덱스를 의사 이름으로
        
        df_duty = pd.DataFrame.from_dict(st.session_state.duty_requests, orient='index', columns=['D', 'E', 'N'])
        df_duty.index = date_list      # 인덱스를 날짜로
        
        df_shift = pd.DataFrame(st.session_state.shift_requests, index=date_list, columns=doctor_names)
        df_shift = df_shift.fillna('') # 빈칸은 공백으로

        # 3. 엑셀 저장
        towrite = BytesIO()
        with pd.ExcelWriter(towrite, engine='openpyxl') as writer:
            df_doctors.to_excel(writer, sheet_name='Doctors', index=False)
            df_rules.to_excel(writer, sheet_name='Rules')
            df_duty.to_excel(writer, sheet_name='DutyRequests')
            df_shift.to_excel(writer, sheet_name='ShiftRequests')
        
        st.download_button(
            label="📥 설정 파일 다운로드 (.xlsx)",
            data=towrite.getvalue(),
            file_name="scheduler_config.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # ── [불러오기 로직: 정확한 위치 기반 매핑] ─────────────────────────────────
    uploaded_file = col_load.file_uploader("설정 Excel 불러오기", type="xlsx")
    if uploaded_file is not None and col_load.button("📤 불러오기 적용"):
        try:
            # 데이터 읽기
            df_doctors = pd.read_excel(uploaded_file, sheet_name='Doctors')
            df_rules = pd.read_excel(uploaded_file, sheet_name='Rules', index_col=0)
            df_duty = pd.read_excel(uploaded_file, sheet_name='DutyRequests', index_col=0)
            df_shift = pd.read_excel(uploaded_file, sheet_name='ShiftRequests', index_col=0)
            
            # [핵심] 위치 기반으로 세션 상태 갱신
            st.session_state.doctors = df_doctors.to_dict('records')
            
            # 순서(index) 보존하며 딕셔너리 재구성
            st.session_state.rules = {i: df_rules.iloc[i].to_dict() for i in range(len(df_rules))}
            st.session_state.duty_requests = {i: df_duty.iloc[i].tolist() for i in range(len(df_duty))}
            st.session_state.shift_requests = df_shift.fillna('').values.tolist()
            
            st.success("✅ 설정이 엑셀에서 성공적으로 적용되었습니다!")
            st.rerun()
        except Exception as e:
            st.error(f"불러오기 실패 (형식이 올바른지 확인하세요): {e}")


    st.divider()

    # Schedule generation button
    if st.button("🚀 스케줄 생성", use_container_width=True, key="btn_solve"):
        st.session_state["trigger_solve"] = True
        st.rerun()

    st.caption("by DS Choi 2026.03.19")


# ── MAIN AREA ────────────────────────────────────────────────────────────────
st.markdown('<div class="main-header"><h1>🏥 SHIFT SCHEDULER</h1><p>의료진 근무표 최적화 시스템 · OR-Tools CP-SAT, by DSCHOI </p></div>', unsafe_allow_html=True)

doctors = st.session_state.doctors
num_days = st.session_state.num_days
start_date = st.session_state.start_date

if not doctors:
    st.info("← 왼쪽 사이드바에서 의사를 추가해 주세요.")
    st.stop()

# Auto-fill day types
if not st.session_state.day_types or len(st.session_state.day_types) != num_days:
    st.session_state.day_types = auto_day_types(start_date, num_days)

if not st.session_state.duty_requests or len(st.session_state.duty_requests) != num_days:
    st.session_state.duty_requests = {i: [1, 1, 1] for i in range(num_days)}

tab1, tab2, tab3, tab4 = st.tabs(["📅 근무 요청 / 날짜 설정", "📋 Duty 설정", "⚙ 개인 규칙", "📊 결과"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: Shift requests + Day types
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    st.markdown('<div class="section-label">날짜 유형 & 개인 근무 요청</div>', unsafe_allow_html=True)
    st.caption("셀을 클릭해서 날짜 유형과 의사별로 원하는/못하는 근무를 설정합니다.")

    # Combined table: Day types + Per-doctor shift requests
    st.markdown("**날짜 유형 & 개인별 근무 요청** · `d/e/n` = 못하는 근무 | `D/E/N` = 원하는 근무 | `x` = 전체 불가")
    SHIFT_OPTIONS = ['', 'd', 'e', 'n', 'x', 'de', 'dn', 'en', 'den', 'D', 'E', 'N']
    day_type_options = ['평일', '토', '일', '공']


    for chunk_start in range(0, num_days, CHUNK):
        chunk_end = min(chunk_start + CHUNK, num_days)
        cols = st.columns(CHUNK + 1)  # Always 16 columns (1 + 15)

        # First row: Day types
        cols[0].markdown(f"<span style='font-family:var(--mono);font-size:0.7rem;color:var(--text-dim);font-weight:600'>날짜유형</span>", unsafe_allow_html=True)
        for ci in range(CHUNK):
            di = chunk_start + ci
            if di < num_days:
                d = start_date + timedelta(days=di)
                lbl = get_day_label(start_date, di)
                default_type = st.session_state.day_types.get(di, '평일')
                color = "#e05c5c" if default_type in ('토','일','공') else "#4f8ef7"
                cols[ci+1].markdown(f"<div style='text-align:center;font-family:var(--mono);font-size:0.72rem'><span style='color:{color}'>{d.strftime('%m/%d')}</span><br><span style='color:#6b7280'>{lbl}</span></div>", unsafe_allow_html=True)
                new_type = cols[ci+1].selectbox(
                    f"d{di}", day_type_options,
                    index=day_type_options.index(default_type),
                    label_visibility="collapsed", key=f"dtype_{di}"
                )
                st.session_state.day_types[di] = new_type
            else:
                cols[ci+1].empty()  # Empty cell for missing days

        # Subsequent rows: Per-doctor shift requests
        for ni, doc in enumerate(doctors):
            cols2 = st.columns(CHUNK + 1)  # Always 16 columns
            cols2[0].markdown(f"<span style='font-family:var(--mono);font-size:0.8rem;color:var(--accent);font-weight:600'>[{ni}] {doc['name']}</span>", unsafe_allow_html=True)
            for ci in range(CHUNK):
                di = chunk_start + ci
                if di < num_days:
                    key = f"sr_{ni}_{di}"
                    cur = st.session_state.shift_requests.get((ni, di), '')
                    options = SHIFT_OPTIONS
                    if cur and cur not in options:
                        options = [cur] + options
                    idx = options.index(cur) if cur in options else 0
                    new_val = cols2[ci+1].selectbox(
                        f"sr{ni}{di}", options,
                        index=idx,
                        label_visibility="collapsed", key=key
                    )
                    st.session_state.shift_requests[(ni, di)] = new_val
                else:
                    cols2[ci+1].empty()  # Empty cell for missing days

        st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: Duty requests (how many D/E/N per day)
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.markdown('<div class="section-label">날짜별 필요 인원 설정</div>', unsafe_allow_html=True)
    st.caption("각 날짜마다 Day / Evening / Night 에 필요한 의사 수를 설정합니다.")

    for chunk_start in range(0, num_days, CHUNK):
        cols = st.columns(CHUNK + 1)  # Always 16 columns (1 + 15)
        cols[0].markdown("<span style='font-family:var(--mono);font-size:0.7rem;color:var(--text-dim)'>Duty</span>", unsafe_allow_html=True)

        # Header row
        for ci in range(CHUNK):
            di = chunk_start + ci
            if di < num_days:
                d = start_date + timedelta(days=di)
                lbl = get_day_label(start_date, di)
                dtype = st.session_state.day_types.get(di, '평일')
                color = "#e05c5c" if dtype in ('토','일','공') else "#4f8ef7"
                cols[ci+1].markdown(
                    f"<div style='text-align:center;font-size:0.72rem;font-family:var(--mono)'>"
                    f"<span style='color:{color}'>{d.strftime('%m/%d')}</span><br>"
                    f"<span style='color:#6b7280'>{lbl}</span></div>",
                    unsafe_allow_html=True
                )
            else:
                cols[ci+1].empty()

        # D / E / N rows
        for shift_i, shift_lbl in enumerate(['D (Day)', 'E (Evening)', 'N (Night)']):
            cols2 = st.columns(CHUNK + 1)  # Always 16 columns
            cols2[0].markdown(f"<span style='font-family:var(--mono);font-size:0.75rem;color:{'#4f8ef7' if shift_i==0 else '#f0a040' if shift_i==1 else '#8080f0'}'>{shift_lbl}</span>", unsafe_allow_html=True)
            for ci in range(CHUNK):
                di = chunk_start + ci
                if di < num_days:
                    cur_val = st.session_state.duty_requests.get(di, [1,1,1])[shift_i]
                    new_val = cols2[ci+1].number_input(
                        f"duty_{di}_{shift_i}", min_value=0, max_value=len(doctors),
                        value=cur_val, label_visibility="collapsed",
                        key=f"duty_{di}_{shift_i}"
                    )
                    if di not in st.session_state.duty_requests:
                        st.session_state.duty_requests[di] = [1,1,1]
                    st.session_state.duty_requests[di][shift_i] = int(new_val)
                else:
                    cols2[ci+1].empty()

        st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: Per-doctor rules
# ─────────────────────────────────────────────────────────────────────────────
RULE0_OPTIONS = [1, 2, 3, 4, 5]
RULE0_LABELS = ["1회만", "2회 허용", "3회 허용", "공휴일만 2회", "공휴일만 3회"]
RULE5_OPTIONS = [0, 3, 4, 5, 6]
RULE5_LABELS = ["제한없음", "3일", "4일", "5일", "6일"]

# Ensure defaults exist for each doctor
for ni in range(len(doctors)):
    if ni not in st.session_state.rules:
        st.session_state.rules[ni] = {
            "rule0": 2, "rule1": 1, "rule2": 1,
            "rule3": 1, "rule4": 1, "rule5": 5,
            "rule6": 0, "rule7": 1, "rule8": 3,
        }
    if ni not in st.session_state.shift_adj:
        st.session_state.shift_adj[ni] = 0

with tab3:
    st.markdown('<div class="section-label">개인별 근무 규칙 설정</div>', unsafe_allow_html=True)
    st.caption("표에서 각 의사별로 근무 규칙을 한 번에 설정할 수 있습니다.")

    doc_names = [d["name"] for d in doctors]

    RULE_DEFS = [
        ("rule0", "하루 근무 횟수", "select", RULE0_OPTIONS, RULE0_LABELS),
        ("rule1", "야간 후 휴무일 수(0이면 2N가능)", "number", 0, 3),
        ("rule2", "Evening 후 Day 금지", "bool", None, None),
        ("rule3", "Evening 3연속 금지", "bool", None, None),
        ("rule4", "4일내 Evening 3회 금지", "bool", None, None),
        ("rule5", "연속 근무 금지 (일수)", "select", RULE5_OPTIONS, RULE5_LABELS),
        ("rule6", "7일내 최대 근무수 (0=무제한)", "number", 0, 7),
        ("rule7", "Day 3연속 금지", "bool", None, None),
        ("rule8", "야간 후 n일간 N금지 (0=제한없음)", "number", 0, 5),
    ]

    # Header row (rule name + doctor columns)
    header_cols = st.columns(len(doc_names) + 1)
    header_cols[0].markdown("**규칙**")
    for ni, name in enumerate(doc_names):
        header_cols[ni + 1].markdown(f"**{name}**")

    # shift_adj row
    row_cols = st.columns(len(doc_names) + 1)
    row_cols[0].markdown("근무 조정값 (평균 근무수 +-n개)")
    for ni in range(len(doc_names)):
        cur = int(st.session_state.shift_adj.get(ni, 0))
        new_val = row_cols[ni + 1].number_input(
            f"shift_adj_{ni}", min_value=-10, max_value=10,
            value=cur, label_visibility="collapsed"
        )
        st.session_state.shift_adj[ni] = int(new_val)

    # rule rows
    for key, label, rtype, opt1, opt2 in RULE_DEFS:
        row_cols = st.columns(len(doc_names) + 1)
        row_cols[0].markdown(label)
        for ni in range(len(doc_names)):
            rules = st.session_state.rules.get(ni, {})
            if rtype == "select":
                opts, labels = opt1, opt2
                cur = int(rules.get(key, opts[0]))
                idx = opts.index(cur) if cur in opts else 0
                new_val = row_cols[ni + 1].selectbox(
                    f"rule_{key}_{ni}", options=labels, index=idx, label_visibility="collapsed"
                )
                st.session_state.rules[ni][key] = opts[labels.index(new_val)]
            elif rtype == "number":
                cur = int(rules.get(key, opt1))
                new_val = row_cols[ni + 1].number_input(
                    f"rule_{key}_{ni}", min_value=opt1, max_value=opt2,
                    value=cur, label_visibility="collapsed"
                )
                st.session_state.rules[ni][key] = int(new_val)
            elif rtype == "bool":
                cur = bool(rules.get(key, 0))
                new_val = row_cols[ni + 1].checkbox(
                    "", value=cur, label_visibility="collapsed",
                    key=f"rule_{key}_{ni}"
                )
                st.session_state.rules[ni][key] = 1 if new_val else 0


# ─────────────────────────────────────────────────────────────────────────────
# SOLVER (triggered from sidebar button)
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.get("trigger_solve"):
    st.session_state["trigger_solve"] = False

    if not doctors:
        st.error("의사를 먼저 추가해 주세요.")
    else:
        with st.spinner("최적 스케줄을 계산 중입니다..."):
            try:
                from scheduler import build_and_solve

                params = {
                    "doctors": [d["name"] for d in doctors],
                    "num_days": num_days,
                    "start_date": str(start_date),
                    "day_types": st.session_state.day_types,
                    "duty_requests": st.session_state.duty_requests,
                    "shift_requests": {f"{k[0]},{k[1]}": v for k, v in st.session_state.shift_requests.items()},
                    "rules": {str(k): v for k, v in st.session_state.rules.items()},
                    "shift_adj": {str(k): v for k, v in st.session_state.shift_adj.items()},
                    "solver_mode": st.session_state.solver_mode,
                    "time_max": st.session_state.time_max,
                    "sol_limit": int(st.session_state.get("sol_limit", 1)),
                    "adv_limit": int(st.session_state.get("adv_limit", 999)),
                }

                solutions, summaries, metrics = build_and_solve(params)
                st.session_state.solutions = solutions
                st.session_state.summaries = summaries
                st.session_state.metrics = metrics
                st.session_state.sol_idx = 0
                st.session_state.solved = True
                st.success(f"✅ {len(solutions)}개의 솔루션을 찾았습니다! (adv ≤ {params['adv_limit']})")
            except Exception as e:
                st.error(f"오류 발생: {e}")
                import traceback
                st.code(traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: Results
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    if not st.session_state.solved or not st.session_state.solutions:
        st.info("← 사이드바에서 **🚀 스케줄 생성** 버튼을 눌러 최적화를 실행하세요.")
    else:
        solutions = st.session_state.solutions
        summaries = st.session_state.summaries
        metrics = st.session_state.metrics
        sol_idx = st.session_state.sol_idx
        total = len(solutions)

        sol = solutions[sol_idx]
        summary = summaries[sol_idx]

        # Excel 내보내기용 데이터 준비
        date_cols = []
        for di in range(num_days):
            d = start_date + timedelta(days=di)
            lbl = get_day_label(start_date, di)
            date_cols.append(f"{d.strftime('%m/%d')} ({lbl})")

        export_rows = []
        for ni, doc in enumerate(doctors):
            row = {"Name": doc['name']}
            for di, col in enumerate(date_cols):
                row[col] = sol.get((ni, di), '').upper() if sol.get((ni, di), '') else ''
            export_rows.append(row)

        export_df = pd.DataFrame(export_rows).set_index('Name')

        towrite = BytesIO()
        with pd.ExcelWriter(towrite, engine='openpyxl') as writer:
            export_df.to_excel(writer, sheet_name='Schedule')
            summary.to_excel(writer, sheet_name='Summary', index=False)
            if metrics and sol_idx < len(metrics):
                pd.DataFrame([metrics[sol_idx]]).to_excel(writer, sheet_name='Metrics', index=False)
        towrite.seek(0)

        # Summary stats
        st.markdown('<div class="section-label">근무 통계</div>', unsafe_allow_html=True)
        try:
            st.dataframe(
                summary.style.background_gradient(subset=['Total'], cmap='Blues')
                             .background_gradient(subset=['N'], cmap='Purples')
                             .background_gradient(subset=['Holiday'], cmap='Oranges'),
                use_container_width=True, hide_index=True
            )
        except ImportError:
            st.dataframe(summary, use_container_width=True, hide_index=True)

        # 편차 정보 (k (DE), k1 (holiday), k2 (N), k3 (total))
        if metrics and sol_idx < len(metrics):
            m = metrics[sol_idx]
            st.markdown(
                f"<div style='font-size:0.85rem; color:var(--text-dim);'>** 편차*가중치 합={m.get('adv')} | **k (D/E 편차):** {m.get('k')} | **k1 (휴일 편차):** {m.get('k1')} | **k2 (N 편차):** {m.get('k2')} | **k3 (총 근무 편차):** {m.get('k3')}</div>",
                unsafe_allow_html=True
            )

        st.divider()

        # Schedule grid
        st.markdown('<div class="section-label">근무 일정표</div>', unsafe_allow_html=True)

        holiday_days = [d for d, t in st.session_state.day_types.items() if t in ('토','일','공')]

        # Build HTML table
        header_row = "<tr><th>이름</th>"
        for di in range(num_days):
            d = start_date + timedelta(days=di)
            lbl = get_day_label(start_date, di)
            is_hol = di in holiday_days
            cls = ' class="th-holiday"' if is_hol else ''
            header_row += f"<th{cls}>{d.strftime('%m/%d')}<br><span style='font-weight:400;font-size:0.65rem'>{lbl}</span></th>"
        header_row += "</tr>"

        body_rows = ""
        for ni, doc in enumerate(doctors):
            body_rows += f"<tr><td style='text-align:left;font-weight:600;color:var(--text);padding:5px 10px'>{doc['name']}</td>"
            for di in range(num_days):
                val = sol.get((ni, di), '')
                req = st.session_state.shift_requests.get((ni, di), '')
                is_hol = di in holiday_days
                hol_style = "border-left: 2px solid #e05c5c44;" if is_hol else ""
                cell_cls = SHIFT_COLORS.get(val, 'cell-off')
                req_style = "outline: 1px solid #e05c5c;" if req and val else ""

                shift_html = val.upper() if val else "·"
                body_rows += f"<td class='{cell_cls}' style='{hol_style}{req_style}'>{shift_html}</td>"
            body_rows += "</tr>"

        table_html = f"""
        <div style="overflow-x:auto; max-width:100%;">
        <table class="schedule-grid">
        <thead>{header_row}</thead>
        <tbody>{body_rows}</tbody>
        </table>
        </div>
        """
        st.markdown(table_html, unsafe_allow_html=True)

        # Navigator (schedule grid 아래)
        nav_col1, nav_col2, nav_col3, nav_col4, nav_col5 = st.columns([1,1,2,2,1])
        if nav_col1.button("◀ 이전", key="nav_prev") and sol_idx > 0:
            st.session_state.sol_idx -= 1
            st.rerun()
        if nav_col2.button("다음 ▶", key="nav_next") and sol_idx < total - 1:
            st.session_state.sol_idx += 1
            st.rerun()
        nav_col3.markdown(f"<div style='font-family:var(--mono);font-size:0.85rem;padding-top:0.4rem'>솔루션 <strong style='color:var(--accent)'>{sol_idx+1}</strong> / {total}</div>", unsafe_allow_html=True)
        jump = nav_col4.number_input("이동", min_value=1, max_value=total, value=sol_idx+1, key="nav_jump", label_visibility="collapsed")
        if int(jump) - 1 != sol_idx:
            st.session_state.sol_idx = int(jump) - 1
            st.rerun()

        nav_col5.download_button(
            "Excel 내보내기",
            data=towrite.getvalue(),
            file_name=f"schedule_{sol_idx+1}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="download_excel"
        )

        st.divider()
        st.markdown('<div class="section-label">범례</div>', unsafe_allow_html=True)
        leg_cols = st.columns(5)
        leg_cols[0].markdown('<span class="badge-d">D Day</span>', unsafe_allow_html=True)
        leg_cols[1].markdown('<span class="badge-e">E Evening</span>', unsafe_allow_html=True)
        leg_cols[2].markdown('<span class="badge-n">N Night</span>', unsafe_allow_html=True)
        leg_cols[3].markdown('<span class="badge-off">· Off</span>', unsafe_allow_html=True)
        leg_cols[4].markdown('<span style="font-family:var(--mono);font-size:0.75rem;color:#e05c5c">🔴 = 휴일</span>', unsafe_allow_html=True)
