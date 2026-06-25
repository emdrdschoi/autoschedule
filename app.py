import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
import calendar
import json
import locale
import streamlit as st

# 시스템 로케일을 한국어로 설정
try:
    locale.setlocale(locale.LC_TIME, 'ko_KR.UTF-8')
except:
    # 윈도우 환경이거나 ko_KR.UTF-8이 없는 경우를 대비한 대체 코드
    try:
        locale.setlocale(locale.LC_TIME, 'ko_KR')
    except:
        pass # 설정 실패 시 시스템 기본값 사용

    
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
    font-size: 0.68rem;
    border-collapse: collapse;
    width: auto;
    table-layout: auto;
}
.schedule-grid th {
    background: var(--surface2);
    color: var(--text-dim);
    padding: 2px 3px;
    font-weight: 600;
    text-align: center;
    border: 1px solid var(--border);
    font-size: 0.6rem;
    white-space: nowrap;
    min-width: 24px;
    max-width: 32px;
}
.schedule-grid td {
    padding: 2px 3px;
    border: 1px solid var(--border);
    text-align: center;
    background: var(--surface);
    font-size: 0.7rem;
    font-weight: 700;
    white-space: nowrap;
    min-width: 24px;
    max-width: 32px;
}
.schedule-grid td.name-col {
    text-align: left;
    font-weight: 600;
    color: var(--text);
    padding: 2px 6px;
    white-space: nowrap;
    min-width: unset;
    max-width: unset;
    font-size: 0.68rem;
}
.schedule-grid tr:hover td { background: var(--surface2); }
.th-holiday { color: var(--accent2) !important; }
.cell-d { color: #4f8ef7; font-weight: 600; }
.cell-e { color: #f0a040; font-weight: 600; }
.cell-n { color: #8080f0; font-weight: 600; }
.cell-off { color: var(--text-dim); }
.cell-request { outline: 1px solid var(--accent2); }

.grade-separator td {
    background: var(--surface2) !important;
    color: var(--accent);
    font-family: var(--mono);
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-align: left !important;
    padding: 4px 8px !important;
    border-top: 2px solid var(--accent) !important;
    border-bottom: 1px solid var(--border) !important;
}
.grade-name-badge {
    color: var(--text-dim);
    font-size: 0.62rem;
    font-weight: 600;
    margin-left: 0.35rem;
}

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
        "grade_rules": {          # Global grade/balancing policy; not per-doctor
            "senior_min_grade": 2,
            "senior_min_count": 1,
            "junior_max_grade": 1,
            "junior_soft_max_count": 1,
            "junior_penalty_weight": 1,
            "weight_de_dev": 1,
            "weight_holiday_dev": 3,
            "weight_total_dev": 5,
            "weight_n_dev": 5,
        },
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

# 기본 규칙값 — 단일 상수로 관리 (사이드바 추가 / tab3 fallback 공통 사용)
DEFAULT_RULES = {
    "rule_max_shifts_per_day":  1,
    "rule_n_block_max":         1,
    "rule_n_rest":              2,
    "rule_n_gap":               3,
    "rule_no_day_after_eve":    1,
    "rule_no_3eve_consec":      0,
    "rule_no_3eve_in_4days":    0,
    "rule_max_consec_days":     6,
    "rule_max_shifts_per_week": 6,
    "rule_no_3day_consec":      0,
}

DEFAULT_DOCTOR_GRADE = 2
DEFAULT_GRADE_RULES = {
    "senior_min_grade": 2,       # grade >= this is treated as senior
    "senior_min_count": 1,       # hard: at least this many seniors per duty
    "junior_max_grade": 1,       # grade <= this is treated as junior
    "junior_soft_max_count": 1,  # soft: try not to exceed this many juniors per duty
    "junior_penalty_weight": 1,  # soft penalty weight per excess junior assignment
    "weight_de_dev": 1,          # objective weight for D/E imbalance
    "weight_holiday_dev": 3,     # objective weight for holiday imbalance
    "weight_total_dev": 5,       # objective weight for total-duty imbalance
    "weight_n_dev": 5,           # objective weight for night-duty imbalance
}
GRADE_RULE_LABELS = {
    "senior_min_grade": "고년차 기준 grade 이상",
    "senior_min_count": "각 duty별 고년차 최소 인원 (hard)",
    "junior_max_grade": "저년차 기준 grade 이하",
    "junior_soft_max_count": "각 duty별 저년차 권장 최대 인원 (soft)",
    "junior_penalty_weight": "저년차 초과 penalty 가중치",
    "weight_de_dev": "D/E 편차 가중치",
    "weight_holiday_dev": "휴일 편차 가중치",
    "weight_total_dev": "총 근무 편차 가중치",
    "weight_n_dev": "N 편차 가중치",
}

def normalize_doctors():
    """Backfill grade/shift_adj for old config files and current sessions."""
    for doc in st.session_state.doctors:
        if "grade" not in doc or pd.isna(doc.get("grade")):
            doc["grade"] = DEFAULT_DOCTOR_GRADE
        else:
            doc["grade"] = int(doc.get("grade", DEFAULT_DOCTOR_GRADE))
        if "shift_adj" not in doc or pd.isna(doc.get("shift_adj")):
            doc["shift_adj"] = 0
        else:
            doc["shift_adj"] = int(doc.get("shift_adj", 0))

def normalize_grade_rules():
    """Ensure global GradeRules exist and are integers."""
    if "grade_rules" not in st.session_state or not isinstance(st.session_state.grade_rules, dict):
        st.session_state.grade_rules = DEFAULT_GRADE_RULES.copy()
    for key, default in DEFAULT_GRADE_RULES.items():
        val = st.session_state.grade_rules.get(key, default)
        try:
            st.session_state.grade_rules[key] = int(val)
        except (TypeError, ValueError):
            st.session_state.grade_rules[key] = default

def grade_rules_to_df(grade_rules: dict) -> pd.DataFrame:
    return pd.DataFrame([
        {"key": key, "value": int(grade_rules.get(key, default)), "description": GRADE_RULE_LABELS.get(key, "")}
        for key, default in DEFAULT_GRADE_RULES.items()
    ])

def grade_rules_from_df(df: pd.DataFrame) -> dict:
    rules = DEFAULT_GRADE_RULES.copy()
    if df is None or df.empty:
        return rules
    if {"key", "value"}.issubset(df.columns):
        for _, row in df.iterrows():
            key = str(row.get("key", "")).strip()
            if key in rules and pd.notna(row.get("value")):
                rules[key] = int(row.get("value"))
    return rules


def build_schedule_excel_bytes(
    *,
    doctors,
    num_days: int,
    start_date: date,
    sol: dict,
    summary_display: pd.DataFrame,
    metrics: list,
    sol_idx: int,
    display_order: list[int],
) -> bytes:
    """Build the result Excel file lazily, only when the user requests export."""
    date_cols = []
    for di in range(num_days):
        d = start_date + timedelta(days=di)
        lbl = get_day_label(start_date, di)
        date_cols.append(f"{d.strftime('%m/%d')} ({lbl})")

    export_rows = []
    for ni in display_order:
        doc = doctors[ni]
        row = {"Name": doc["name"], "Grade": int(doc.get("grade", DEFAULT_DOCTOR_GRADE))}
        for di, col in enumerate(date_cols):
            val = sol.get((ni, di), "")
            row[col] = val.upper() if val else ""
        export_rows.append(row)
    export_df = pd.DataFrame(export_rows).set_index("Name")

    rule_col_order = [
        "rule_max_shifts_per_day", "rule_n_block_max", "rule_n_rest", "rule_n_gap",
        "rule_no_day_after_eve", "rule_no_3eve_consec", "rule_no_3eve_in_4days",
        "rule_max_consec_days", "rule_max_shifts_per_week", "rule_no_3day_consec",
    ]
    rule_col_labels = {
        "rule_max_shifts_per_day": "하루 근무 횟수",
        "rule_n_block_max": "N뭉치 최대 길이",
        "rule_n_rest": "N뭉치 후 완전Off 의무일",
        "rule_n_gap": "N뭉치 후 다음N까지 총 간격",
        "rule_no_day_after_eve": "Evening 후 Day 금지",
        "rule_no_3eve_consec": "Evening 3연속 금지",
        "rule_no_3eve_in_4days": "4일내 Evening 3회 금지",
        "rule_max_consec_days": "최대 연속 근무일수",
        "rule_max_shifts_per_week": "7일 구간 최대 근무수",
        "rule_no_3day_consec": "Day 3연속 금지",
    }

    rules_rows = []
    for ni, doc in enumerate(doctors):
        r = st.session_state.rules.get(ni, {})
        row = {
            "이름": doc["name"],
            "grade": int(doc.get("grade", DEFAULT_DOCTOR_GRADE)),
            "shift_adj": st.session_state.shift_adj.get(ni, 0),
        }
        for key in rule_col_order:
            row[rule_col_labels[key]] = r.get(key, "")
        rules_rows.append(row)
    rules_df = pd.DataFrame(rules_rows)

    towrite = BytesIO()
    with pd.ExcelWriter(towrite, engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="Schedule")
        summary_display.to_excel(writer, sheet_name="Summary", index=False)
        rules_df.to_excel(writer, sheet_name="Rules", index=False)
        grade_rules_to_df(st.session_state.grade_rules).to_excel(writer, sheet_name="GradeRules", index=False)
        if metrics and sol_idx < len(metrics):
            pd.DataFrame([metrics[sol_idx]]).to_excel(writer, sheet_name="Metrics", index=False)
    towrite.seek(0)
    return towrite.getvalue()

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

CHUNK = 7  # Number of days per chunk for display

# Normalize early so sidebar save/display also works with older sessions.
normalize_doctors()
normalize_grade_rules()


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
                    "grade": DEFAULT_DOCTOR_GRADE,
                })
                st.session_state.rules[n] = DEFAULT_RULES.copy()
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
                col1.caption(f"{doc['name']}")
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

    # UI 순서와 동일한 rule 컬럼 정의 (저장/불러오기 공통)
    RULE_COL_ORDER = [
        "rule_max_shifts_per_day", "rule_n_block_max", "rule_n_rest", "rule_n_gap",
        "rule_no_day_after_eve", "rule_no_3eve_consec", "rule_no_3eve_in_4days", "rule_max_consec_days", "rule_max_shifts_per_week", "rule_no_3day_consec",
    ]

    col_save, col_load = st.columns(2)

    # 1. [저장] Excel 내보내기
    if col_save.button("💾 설정 Excel 저장", use_container_width=True):
        start_date = st.session_state.start_date
        doctor_names = [d['name'] for d in st.session_state.doctors]
        num_days = len(st.session_state.duty_requests)
        date_list = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(num_days)]

        # Rules: RULE_COL_ORDER 순서로 컬럼 정렬
        rules_rows = []
        for ni in range(len(doctor_names)):
            r = st.session_state.rules.get(ni, {})
            row = {key: r.get(key, '') for key in RULE_COL_ORDER}
            rules_rows.append(row)
        df_rules = pd.DataFrame(rules_rows, index=doctor_names)
        df_rules.index.name = 'Name'

        df_duty = pd.DataFrame.from_dict(st.session_state.duty_requests, orient='index', columns=['D', 'E', 'N'])
        df_duty.index = date_list

        # ShiftRequests: 행=의사, 열=날짜 구조로 저장
        # 다른 시트처럼 첫 번째 열이 의사 이름이 되도록 하여 복사/붙여넣기를 쉽게 한다.
        shift_grid = pd.DataFrame('', index=doctor_names, columns=date_list)
        shift_grid.index.name = 'Name'
        for (doc_idx, day_idx), val in st.session_state.shift_requests.items():
            if day_idx < len(date_list) and doc_idx < len(doctor_names):
                shift_grid.iloc[doc_idx, day_idx] = val

        df_grade_rules = grade_rules_to_df(st.session_state.grade_rules)

        towrite = BytesIO()
        with pd.ExcelWriter(towrite, engine='openpyxl') as writer:
            pd.DataFrame(st.session_state.doctors).to_excel(writer, sheet_name='Doctors', index=False)
            df_rules.to_excel(writer, sheet_name='Rules')
            df_grade_rules.to_excel(writer, sheet_name='GradeRules', index=False)
            df_duty.to_excel(writer, sheet_name='DutyRequests')
            shift_grid.to_excel(writer, sheet_name='ShiftRequests')

        st.download_button(
            label="📥 설정 파일 다운로드 (.xlsx)",
            data=towrite.getvalue(),
            file_name="scheduler_config.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # 2. [불러오기] Excel 가져오기
    uploaded_file = col_load.file_uploader("설정 Excel 불러오기", type="xlsx")
    if uploaded_file is not None and col_load.button("📤 불러오기 적용"):
        try:
            xls = pd.ExcelFile(uploaded_file)
            df_doctors = pd.read_excel(xls, sheet_name='Doctors')
            df_rules = pd.read_excel(xls, sheet_name='Rules', index_col=0)
            df_duty = pd.read_excel(xls, sheet_name='DutyRequests', index_col=0)
            df_shift = pd.read_excel(xls, sheet_name='ShiftRequests', index_col=0)
            df_grade_rules = pd.read_excel(xls, sheet_name='GradeRules') if 'GradeRules' in xls.sheet_names else pd.DataFrame()

            # 1) 의사 정보: 기존 설정 파일에 grade가 없으면 기본 grade로 보정
            new_doctors = []
            for _, row in df_doctors.iterrows():
                name = str(row.get('name', '')).strip()
                if not name:
                    continue
                grade = int(row.get('grade', DEFAULT_DOCTOR_GRADE)) if pd.notna(row.get('grade', None)) else DEFAULT_DOCTOR_GRADE
                adj = int(row.get('shift_adj', 0)) if pd.notna(row.get('shift_adj', None)) else 0
                new_doctors.append({"name": name, "shift_adj": adj, "grade": grade})
            st.session_state.doctors = new_doctors

            # 2) Rules: 컬럼명 기반으로 읽어서 RULE_COL_ORDER 키로 매핑
            new_rules = {}
            for i in range(len(df_rules)):
                row = df_rules.iloc[i]
                new_rules[i] = {key: int(row[key]) if key in row.index and pd.notna(row[key]) else DEFAULT_RULES.get(key, 0)
                                for key in RULE_COL_ORDER}
            st.session_state.rules = new_rules

            # shift_adj 도 Doctors 시트에서 복원
            st.session_state.shift_adj = {
                i: int(st.session_state.doctors[i].get('shift_adj', 0))
                for i in range(len(st.session_state.doctors))
            }

            # GradeRules: 전체 grade 정책 복원. 없는 옛 설정 파일은 기본값 사용.
            st.session_state.grade_rules = grade_rules_from_df(df_grade_rules)
            normalize_grade_rules()

            # 3) DutyRequests — 길이만 참조, 시작날짜는 사이드바 기준
            loaded_duty = {i: [int(df_duty.iloc[i]['D']), int(df_duty.iloc[i]['E']), int(df_duty.iloc[i]['N'])]
                           for i in range(len(df_duty))}
            st.session_state.duty_requests = loaded_duty
            st.session_state.num_days = len(loaded_duty)
            # day_types는 사이드바 start_date 기준으로 재생성
            st.session_state.day_types = auto_day_types(st.session_state.start_date, st.session_state.num_days)

            # 4) ShiftRequests
            # 새 형식만 지원: 행=의사(Name), 열=날짜.
            # 행 이름으로 의사를 매칭하므로 시트에서 의사 행 순서를 바꿔도 안전하다.
            name_to_doc_idx = {doc['name']: i for i, doc in enumerate(st.session_state.doctors)}
            new_shift = {}
            max_days = min(len(df_shift.columns), st.session_state.num_days)
            for row_name, row in df_shift.iterrows():
                doc_name = str(row_name).strip()
                if doc_name not in name_to_doc_idx:
                    continue
                doc_idx = name_to_doc_idx[doc_name]
                for day_idx in range(max_days):
                    val = row.iloc[day_idx]
                    new_shift[(doc_idx, day_idx)] = str(val).strip() if pd.notna(val) else ''
            st.session_state.shift_requests = new_shift

            st.toast("✅ 설정 적용 완료!", icon="✅")
            st.rerun()
        except Exception as e:
            st.error(f"불러오기 실패: {e}")

    st.divider()

    # Schedule generation button
    if st.button("🚀 스케줄 생성", use_container_width=True, key="btn_solve"):
        st.session_state["trigger_solve"] = True
        st.rerun()

    st.caption("by DS Choi 2026.03.19")


# ── MAIN AREA ────────────────────────────────────────────────────────────────
st.markdown('<div class="main-header"><h1>🏥 SHIFT SCHEDULER</h1><p>의료진 근무표 최적화 시스템 · OR-Tools CP-SAT, by DSCHOI </p></div>', unsafe_allow_html=True)

normalize_doctors()
normalize_grade_rules()

doctors = st.session_state.doctors
num_days = st.session_state.num_days
start_date = st.session_state.start_date

if not doctors:
    st.info("← 왼쪽 사이드바에서 의사를 추가해 주세요.")
    st.stop()

# Auto-fill day types
if not st.session_state.day_types or len(st.session_state.day_types) != num_days:
    st.session_state.day_types = auto_day_types(start_date, num_days)

if not st.session_state.duty_requests or len(st.session_state.duty_requests) != st.session_state.num_days:
    st.session_state.duty_requests = {i: [1, 1, 1] for i in range(st.session_state.num_days)}

tab1, tab2, tab3, tab4 = st.tabs(["📅 근무 요청 / 날짜 설정", "📋 Duty 설정", "⚙ 개인 규칙 / Grade", "📊 결과"])

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
        cols = st.columns(CHUNK + 1)  # Always 8 columns (1 + 7)

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
        cols = st.columns(CHUNK + 1)  # Always 8 columns (1 + 7)
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
RULE5_OPTIONS = [0, 3, 4, 5, 6, 7]
RULE5_LABELS = ["제한없음", "3일", "4일", "5일", "6일", "7일"]

# Ensure defaults exist for each doctor
for ni in range(len(doctors)):
    if ni not in st.session_state.rules:
        st.session_state.rules[ni] = DEFAULT_RULES.copy()
    if ni not in st.session_state.shift_adj:
        st.session_state.shift_adj[ni] = 0

with tab3:
    st.markdown('<div class="section-label">Grade 정책 설정</div>', unsafe_allow_html=True)
    st.caption("Grade는 개인 속성이고, 고년차/저년차 기준과 objective 가중치는 전체 스케줄에 적용되는 전역 rule입니다.")

    gr = st.session_state.grade_rules
    gcol1, gcol2, gcol3, gcol4, gcol5 = st.columns(5)
    gr["senior_min_grade"] = int(gcol1.number_input(
        "고년차 기준 grade ≥", min_value=1, max_value=5,
        value=int(gr.get("senior_min_grade", DEFAULT_GRADE_RULES["senior_min_grade"])),
        key="grade_senior_min_grade"
    ))
    gr["senior_min_count"] = int(gcol2.number_input(
        "Duty별 고년차 최소", min_value=0, max_value=10,
        value=int(gr.get("senior_min_count", DEFAULT_GRADE_RULES["senior_min_count"])),
        key="grade_senior_min_count"
    ))
    gr["junior_max_grade"] = int(gcol3.number_input(
        "저년차 기준 grade ≤", min_value=1, max_value=5,
        value=int(gr.get("junior_max_grade", DEFAULT_GRADE_RULES["junior_max_grade"])),
        key="grade_junior_max_grade"
    ))
    gr["junior_soft_max_count"] = int(gcol4.number_input(
        "Duty별 저년차 권장 최대", min_value=0, max_value=10,
        value=int(gr.get("junior_soft_max_count", DEFAULT_GRADE_RULES["junior_soft_max_count"])),
        key="grade_junior_soft_max_count"
    ))
    gr["junior_penalty_weight"] = int(gcol5.number_input(
        "저년차 초과 penalty", min_value=0, max_value=100,
        value=int(gr.get("junior_penalty_weight", DEFAULT_GRADE_RULES["junior_penalty_weight"])),
        key="grade_junior_penalty_weight"
    ))

    st.markdown('<div class="section-label">편차 가중치 설정</div>', unsafe_allow_html=True)
    st.caption("Objective = D/E 편차×가중치 + 휴일 편차×가중치 + 총근무 편차×가중치 + N 편차×가중치 + 저년차 초과×가중치")
    wcol1, wcol2, wcol3, wcol4 = st.columns(4)
    gr["weight_de_dev"] = int(wcol1.number_input(
        "D/E 편차 가중치", min_value=0, max_value=100,
        value=int(gr.get("weight_de_dev", DEFAULT_GRADE_RULES["weight_de_dev"])),
        key="weight_de_dev"
    ))
    gr["weight_holiday_dev"] = int(wcol2.number_input(
        "휴일 편차 가중치", min_value=0, max_value=100,
        value=int(gr.get("weight_holiday_dev", DEFAULT_GRADE_RULES["weight_holiday_dev"])),
        key="weight_holiday_dev"
    ))
    gr["weight_total_dev"] = int(wcol3.number_input(
        "총 근무 편차 가중치", min_value=0, max_value=100,
        value=int(gr.get("weight_total_dev", DEFAULT_GRADE_RULES["weight_total_dev"])),
        key="weight_total_dev"
    ))
    gr["weight_n_dev"] = int(wcol4.number_input(
        "N 편차 가중치", min_value=0, max_value=100,
        value=int(gr.get("weight_n_dev", DEFAULT_GRADE_RULES["weight_n_dev"])),
        key="weight_n_dev"
    ))
    st.session_state.grade_rules = gr
    st.markdown(
        f"<div style='font-size:0.82rem; color:var(--text-dim);'>"
        f"Hard: 각 duty마다 <b>grade ≥ {gr['senior_min_grade']}</b> 인원이 최소 <b>{gr['senior_min_count']}</b>명 필요합니다. "
        f"Soft: <b>grade ≤ {gr['junior_max_grade']}</b> 인원이 duty별 <b>{gr['junior_soft_max_count']}</b>명을 초과하면 "
        f"초과 1건당 <b>{gr['junior_penalty_weight']}</b>점 penalty를 줍니다."
        f"</div>",
        unsafe_allow_html=True
    )

    st.divider()
    st.markdown('<div class="section-label">개인별 Grade & 근무 규칙 설정</div>', unsafe_allow_html=True)
    st.caption("7명씩 나눠서 표시됩니다. Grade와 규칙명 옆으로 의사별 설정을 입력하세요.")

    doc_names = [d["name"] for d in doctors]
    DOC_CHUNK = 7

    RULE_DEFS = [
        ("rule_max_shifts_per_day",  "하루 근무 횟수",                          "select", RULE0_OPTIONS, RULE0_LABELS),
        ("rule_n_block_max",         "N 뭉치 최대 길이",                        "select", [1,2,3], ["1개(NN불가)","2개(NNN불가)","3개(NNNN불가)"]),
        ("rule_n_rest",              "N뭉치 후 완전 Off 의무일",                "number", 0, 5),
        ("rule_n_gap",               "N뭉치 후 다음 N까지 총 간격",             "number", 0, 10),
        ("rule_no_day_after_eve",    "Evening 후 Day 금지",                     "bool",   None, None),
        ("rule_no_3eve_consec",      "Evening 3연속 금지",                      "bool",   None, None),
        ("rule_no_3eve_in_4days",    "4일내 Evening 3회 금지",                  "bool",   None, None),
        ("rule_max_consec_days", "최대 연속 근무일수", "number", 0, 30),
        ("rule_max_shifts_per_week", "7일 구간 최대 근무수 (0=무제한)",             "number", 0, 7),
        ("rule_no_3day_consec",      "Day 3연속 금지",                          "bool",   None, None),
    ]

    for chunk_start in range(0, len(doc_names), DOC_CHUNK):
        chunk_end = min(chunk_start + DOC_CHUNK, len(doc_names))
        chunk_names = doc_names[chunk_start:chunk_end]
        chunk_size = len(chunk_names)

        st.markdown(
            f"<div style='font-family:var(--mono);font-size:0.75rem;color:var(--accent);margin:1rem 0 0.4rem'>"
            f"의사 {chunk_start+1} ~ {chunk_end}</div>",
            unsafe_allow_html=True
        )

        # 헤더
        header_cols = st.columns([2] + [1] * chunk_size)
        header_cols[0].markdown("<span style='font-family:var(--mono);font-size:0.75rem;color:var(--text-dim)'>규칙</span>", unsafe_allow_html=True)
        for ci, name in enumerate(chunk_names):
            header_cols[ci+1].markdown(f"<span style='font-family:var(--mono);font-size:0.78rem;font-weight:600;color:var(--accent)'>{name}</span>", unsafe_allow_html=True)

        # grade
        grade_cols = st.columns([2] + [1] * chunk_size)
        grade_cols[0].markdown("<span style='font-size:0.75rem'>Grade</span>", unsafe_allow_html=True)
        for ci, ni in enumerate(range(chunk_start, chunk_end)):
            cur_grade = int(doctors[ni].get("grade", DEFAULT_DOCTOR_GRADE))
            new_grade = grade_cols[ci+1].number_input(
                f"grade_{ni}", min_value=1, max_value=5,
                value=cur_grade, label_visibility="collapsed", key=f"doc_grade_{ni}"
            )
            doctors[ni]["grade"] = int(new_grade)

        # shift_adj
        adj_cols = st.columns([2] + [1] * chunk_size)
        adj_cols[0].markdown("<span style='font-size:0.75rem'>근무 조정값</span>", unsafe_allow_html=True)
        for ci, ni in enumerate(range(chunk_start, chunk_end)):
            cur = int(st.session_state.shift_adj.get(ni, doctors[ni].get("shift_adj", 0)))
            new_val = adj_cols[ci+1].number_input(
                f"adj_{ni}", min_value=-10, max_value=10,
                value=cur, label_visibility="collapsed", key=f"shift_adj_{ni}"
            )
            st.session_state.shift_adj[ni] = int(new_val)
            doctors[ni]["shift_adj"] = int(new_val)

        # 규칙 rows
        for key, label, rtype, opt1, opt2 in RULE_DEFS:
            row_cols = st.columns([2] + [1] * chunk_size)
            row_cols[0].markdown(f"<span style='font-size:0.75rem'>{label}</span>", unsafe_allow_html=True)
            for ci, ni in enumerate(range(chunk_start, chunk_end)):
                rules = st.session_state.rules.get(ni, DEFAULT_RULES.copy())
                if rtype == "select":
                    opts, labels = opt1, opt2
                    cur = int(rules.get(key, opts[0]))
                    idx = opts.index(cur) if cur in opts else 0
                    new_val = row_cols[ci+1].selectbox(
                        f"r_{key}_{ni}", options=labels, index=idx, label_visibility="collapsed"
                    )
                    st.session_state.rules[ni][key] = opts[labels.index(new_val)]
                elif rtype == "number":
                    cur = int(rules.get(key, opt1))
                    new_val = row_cols[ci+1].number_input(
                        f"r_{key}_{ni}", min_value=opt1, max_value=opt2,
                        value=cur, label_visibility="collapsed"
                    )
                    st.session_state.rules[ni][key] = int(new_val)
                elif rtype == "bool":
                    cur = bool(rules.get(key, 0))
                    new_val = row_cols[ci+1].checkbox(
                        "", value=cur, key=f"r_{key}_{ni}", label_visibility="collapsed"
                    )
                    st.session_state.rules[ni][key] = 1 if new_val else 0

        st.divider()


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
                    "grades": {str(i): int(d.get("grade", DEFAULT_DOCTOR_GRADE)) for i, d in enumerate(doctors)},
                    "grade_rules": {k: int(v) for k, v in st.session_state.grade_rules.items()},
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
                st.session_state.pop("prepared_excel_export", None)
                st.toast(f"✅ {len(solutions)}개의 솔루션을 찾았습니다!", icon="✅")
            except Exception as e:
                st.toast(f"❌ 오류 발생: {e}", icon="❌")
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

        # 화면/Excel 표시 순서: grade 높은 순서로 묶고, 같은 grade 안에서는 기존 입력 순서 유지
        display_order = sorted(
            range(len(doctors)),
            key=lambda ni: (-int(doctors[ni].get("grade", DEFAULT_DOCTOR_GRADE)), ni)
        )
        name_to_grade = {doc["name"]: int(doc.get("grade", DEFAULT_DOCTOR_GRADE)) for doc in doctors}
        name_to_display_order = {doctors[ni]["name"]: order for order, ni in enumerate(display_order)}

        summary_display = summary.copy()
        if "Grade" not in summary_display.columns:
            summary_display.insert(1, "Grade", summary_display["Name"].map(name_to_grade).fillna(DEFAULT_DOCTOR_GRADE).astype(int))
        summary_display["_display_order"] = summary_display["Name"].map(name_to_display_order).fillna(9999).astype(int)
        summary_display = (
            summary_display
            .sort_values(["Grade", "_display_order"], ascending=[False, True], kind="stable")
            .drop(columns=["_display_order"])
        )

        # Excel export는 화면 이동 때마다 만들지 않고, 아래의 "Excel 준비" 버튼을 눌렀을 때만 생성합니다.

        # Summary stats
        st.markdown('<div class="section-label">근무 통계</div>', unsafe_allow_html=True)
        try:
            st.dataframe(
                summary_display.style.background_gradient(subset=['Total'], cmap='Blues')
                             .background_gradient(subset=['N'], cmap='Purples')
                             .background_gradient(subset=['Holiday'], cmap='Oranges'),
                use_container_width=True, hide_index=True
            )
        except ImportError:
            st.dataframe(summary_display, use_container_width=True, hide_index=True)

        # 편차 정보 (k (DE), k1 (holiday), k2 (N), k3 (total))
        if metrics and sol_idx < len(metrics):
            m = metrics[sol_idx]
            st.markdown(
                f"<div style='font-size:0.85rem; color:var(--text-dim);'>"
                f"** 편차*가중치 합={m.get('adv')} | **balance penalty:** {m.get('balance_penalty', 'NA')} "
                f"| **k D/E:** {m.get('k')}×{m.get('weight_de_dev', gr.get('weight_de_dev', 1))} "
                f"| **k1 휴일:** {m.get('k1')}×{m.get('weight_holiday_dev', gr.get('weight_holiday_dev', 3))} "
                f"| **k2 총근무:** {m.get('k2')}×{m.get('weight_total_dev', gr.get('weight_total_dev', 5))} "
                f"| **k3 N:** {m.get('k3')}×{m.get('weight_n_dev', gr.get('weight_n_dev', 5))} "
                f"| **저년차 초과:** {m.get('junior_excess', 0)}×{m.get('junior_penalty_weight', gr.get('junior_penalty_weight', 1))} "
                f"= **{m.get('junior_penalty', 0)}**</div>",
                unsafe_allow_html=True
            )

        st.divider()

        # Schedule grid
        st.markdown('<div class="section-label">근무 일정표</div>', unsafe_allow_html=True)

        holiday_days = [d for d, t in st.session_state.day_types.items() if t in ('토','일','공')]

        # Build HTML table
        header_row = "<tr><th style='text-align:left;white-space:nowrap;padding:2px 6px'>이름 / Grade</th>"
        for di in range(num_days):
            d = start_date + timedelta(days=di)
            lbl = get_day_label(start_date, di)
            is_hol = di in holiday_days
            cls = ' class="th-holiday"' if is_hol else ''
            header_row += f"<th{cls}>{d.strftime('%m/%d')}<br><span style='font-weight:400;font-size:0.58rem'>{lbl}</span></th>"
        header_row += "</tr>"

        body_rows = ""
        current_grade = None
        total_cols = num_days + 1
        for ni in display_order:
            doc = doctors[ni]
            grade = int(doc.get("grade", DEFAULT_DOCTOR_GRADE))
            if grade != current_grade:
                current_grade = grade
                body_rows += (
                    f"<tr class='grade-separator'>"
                    f"<td colspan='{total_cols}'>Grade {grade}</td>"
                    f"</tr>"
                )
            body_rows += (
                f"<tr><td class='name-col'>{doc['name']}"
                f"<span class='grade-name-badge'>G{grade}</span></td>"
            )
            for di in range(num_days):
                val = sol.get((ni, di), '')
                req = st.session_state.shift_requests.get((ni, di), '')
                is_hol = di in holiday_days
                hol_style = "border-left: 2px solid #e05c5c44;" if is_hol else ""
                cell_cls = SHIFT_COLORS.get(val, 'cell-off')
                shift_html = val.upper() if val else "·"
                body_rows += f"<td class='{cell_cls}' style='{hol_style}'>{shift_html}</td>"
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

        prepared = st.session_state.get("prepared_excel_export")
        prepared_matches_current = prepared and prepared.get("sol_idx") == sol_idx

        if nav_col5.button("Excel 준비", use_container_width=True, key=f"prepare_excel_{sol_idx}"):
            excel_bytes = build_schedule_excel_bytes(
                doctors=doctors,
                num_days=num_days,
                start_date=start_date,
                sol=sol,
                summary_display=summary_display,
                metrics=metrics,
                sol_idx=sol_idx,
                display_order=display_order,
            )
            st.session_state.prepared_excel_export = {
                "sol_idx": sol_idx,
                "filename": f"schedule_{sol_idx+1}.xlsx",
                "bytes": excel_bytes,
            }
            prepared = st.session_state.prepared_excel_export
            prepared_matches_current = True

        if prepared_matches_current:
            nav_col5.download_button(
                "다운로드",
                data=prepared["bytes"],
                file_name=prepared["filename"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=f"download_excel_{sol_idx}",
            )

        st.divider()
        st.markdown('<div class="section-label">범례</div>', unsafe_allow_html=True)
        leg_cols = st.columns(5)
        leg_cols[0].markdown('<span class="badge-d">D Day</span>', unsafe_allow_html=True)
        leg_cols[1].markdown('<span class="badge-e">E Evening</span>', unsafe_allow_html=True)
        leg_cols[2].markdown('<span class="badge-n">N Night</span>', unsafe_allow_html=True)
        leg_cols[3].markdown('<span class="badge-off">· Off</span>', unsafe_allow_html=True)
        leg_cols[4].markdown('<span style="font-family:var(--mono);font-size:0.75rem;color:#e05c5c">🔴 = 휴일</span>', unsafe_allow_html=True)