import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
from pathlib import Path
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
.cell-public-holiday {
    background-color: rgba(240, 160, 64, 0.14) !important;
}
.lock-marker { color: var(--text-dim); font-size: 0.55rem; margin-right: 1px; vertical-align: 1px; }
.fixed-request-note {
    background: #3a2a1026;
    border: 1px solid #f0a04066;
    color: var(--accent4);
    border-radius: 4px;
    padding: 2px 3px;
    margin-bottom: 2px;
    text-align: center;
    font-family: var(--mono);
    font-size: 0.58rem;
    line-height: 1.15;
}
.fixed-request-note span {
    color: var(--text-dim);
    font-size: 0.52rem;
}

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
    padding: 0.3rem 0.8rem;
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
        "shift_requests": {},     # combined view: base_shift_requests + fixed_shift_requests
        "base_shift_requests": {}, # user-entered wanted/cannot schedule
        "fixed_shift_requests": {},# result-cell locks overlaid on top of base requests
        "shift_requests1": {},    # legacy key; wishes are parsed from shift_requests
        "rules": {},              # {n: {rule_key: value}}
        "shift_adj": {},          # {n: int}
        "shift_counts": {},       # {n: {"D": -1|int, "E": -1|int, "N": -1|int, "Total": -1|int}}
        "grade_rules": {          # Global grade/balancing policy; not per-doctor
            "senior_min_grade": 2,
            "senior_min_count": 1,
            "junior_max_grade": 1,
            "junior_soft_max_count": 1,
            "junior_penalty_weight": 1,
            "ultra_junior_max_grade": 1,
            "ultra_junior_max_count": 0,
            "weight_de_dev": 1,
            "weight_holiday_dev": 3,
            "weight_total_dev": 5,
            "weight_n_dev": 5,
            "weight_grade_dev": 3,
        },
        "solutions": [],
        "summaries": [],
        "sol_idx": 0,
        "solved": False,
        "shift_req_version": 0,  # key versioning for shift_request widgets
        "duty_req_version": 0,   # key versioning for duty number_input widgets
        "shift_count_version": 0, # key versioning for fixed Total/D/E/N count widgets
        "grade_version": 0,       # key versioning for individual grade widgets
        "grade_rule_version": 0,  # key versioning for global grade rule widgets
        "solve_failed": False,
        "solve_failure_message": "",
        "diagnostic_results": None,
        "fixed_counts_editor_pending_df": None,  # 화면에만 반영된 자동계산 preview table
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
GRADE_MIN_VALUE = 1
GRADE_MAX_VALUE = 10

def bounded_int(value, default: int, min_value: int, max_value: int) -> int:
    """Convert to int and keep Streamlit number_input values inside allowed bounds."""
    try:
        if value is None or pd.isna(value):
            val = int(default)
        else:
            val = int(value)
    except (TypeError, ValueError):
        val = int(default)
    return max(int(min_value), min(int(max_value), val))


def parse_fixed_count_value(value, default: int = -1, max_value: int = 60) -> int:
    """Parse fixed count table values. Blank means automatic (-1), 0 means fixed zero."""
    try:
        if value is None or pd.isna(value):
            return -1
    except TypeError:
        pass
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none", "auto", "automatic", "자동"}:
        return -1
    try:
        # Accept values pasted from Excel such as 3.0.
        val = int(float(text))
    except (TypeError, ValueError):
        return int(default)
    if val < 0:
        return -1
    return min(int(max_value), val)


def fixed_count_display_value(value) -> str:
    """Display internal -1 automatic values as a blank cell for easier editing."""
    val = parse_fixed_count_value(value)
    return "" if val < 0 else str(val)


def fixed_count_excel_value(value):
    """Save automatic fixed counts as blank in Excel; keep 0 and positive counts."""
    val = parse_fixed_count_value(value)
    return "" if val < 0 else int(val)

DEFAULT_GRADE_RULES = {
    "senior_min_grade": 2,       # grade >= this is treated as senior
    "senior_min_count": 1,       # hard: at least this many seniors per duty
    "junior_max_grade": 1,       # grade <= this is treated as junior
    "junior_soft_max_count": 1,  # soft: try not to exceed this many juniors per duty
    "junior_penalty_weight": 1,  # soft penalty weight per excess junior assignment
    "ultra_junior_max_grade": 1, # grade <= this is treated as ultra-junior for hard rule
    "ultra_junior_max_count": 0, # 0=disabled; maximum ultra-juniors allowed in one active duty
    "weight_de_dev": 1,          # objective weight for D/E imbalance
    "weight_holiday_dev": 3,     # objective weight for holiday imbalance
    "weight_total_dev": 5,       # objective weight for total-duty imbalance
    "weight_n_dev": 5,           # objective weight for night-duty imbalance
    "weight_grade_dev": 3,       # objective weight for grade imbalance per duty
}
GRADE_RULE_LABELS = {
    "senior_min_grade": "고년차 기준 grade 이상",
    "senior_min_count": "각 duty별 고년차 최소 인원 (hard)",
    "junior_max_grade": "저년차 기준 grade 이하",
    "junior_soft_max_count": "각 duty별 저년차 권장 최대 인원 (soft)",
    "junior_penalty_weight": "저년차 초과 penalty 가중치",
    "ultra_junior_max_grade": "초저년차 기준 grade 이하",
    "ultra_junior_max_count": "초저년차 duty당 최대 허용 인원 (hard, 0=사용안함)",
    "weight_de_dev": "D/E 편차 가중치",
    "weight_holiday_dev": "휴일 편차 가중치",
    "weight_total_dev": "총 근무 편차 가중치",
    "weight_n_dev": "N 편차 가중치",
    "weight_grade_dev": "Grade 편차 가중치",
}

def normalize_doctors():
    """Backfill grade/shift_adj for old config files and current sessions."""
    for doc in st.session_state.doctors:
        if "grade" not in doc or pd.isna(doc.get("grade")):
            doc["grade"] = DEFAULT_DOCTOR_GRADE
        else:
            doc["grade"] = bounded_int(doc.get("grade", DEFAULT_DOCTOR_GRADE), DEFAULT_DOCTOR_GRADE, GRADE_MIN_VALUE, GRADE_MAX_VALUE)
        if "shift_adj" not in doc or pd.isna(doc.get("shift_adj")):
            doc["shift_adj"] = 0
        else:
            doc["shift_adj"] = int(doc.get("shift_adj", 0))

def normalize_grade_rules():
    """Ensure global GradeRules exist and stay within Streamlit widget bounds."""
    if "grade_rules" not in st.session_state or not isinstance(st.session_state.grade_rules, dict):
        st.session_state.grade_rules = DEFAULT_GRADE_RULES.copy()
    # Backward compatibility: older configs used ultra_junior_forbid_at_or_above.
    # Old X meant "X명 이상 불가", so it becomes max_count = X - 1.
    if "ultra_junior_max_count" not in st.session_state.grade_rules and "ultra_junior_forbid_at_or_above" in st.session_state.grade_rules:
        old_cutoff = bounded_int(st.session_state.grade_rules.get("ultra_junior_forbid_at_or_above", 0), 0, 0, 10)
        st.session_state.grade_rules["ultra_junior_max_count"] = max(0, old_cutoff - 1) if old_cutoff > 0 else 0
    bounds = {
        "senior_min_grade": (GRADE_MIN_VALUE, GRADE_MAX_VALUE),
        "senior_min_count": (0, 10),
        "junior_max_grade": (GRADE_MIN_VALUE, GRADE_MAX_VALUE),
        "junior_soft_max_count": (0, 10),
        "junior_penalty_weight": (0, 100),
        "ultra_junior_max_grade": (GRADE_MIN_VALUE, GRADE_MAX_VALUE),
        "ultra_junior_max_count": (0, 10),
        "weight_de_dev": (0, 100),
        "weight_holiday_dev": (0, 100),
        "weight_total_dev": (0, 100),
        "weight_n_dev": (0, 100),
        "weight_grade_dev": (0, 100),
    }
    for key, default in DEFAULT_GRADE_RULES.items():
        min_v, max_v = bounds.get(key, (-10_000, 10_000))
        st.session_state.grade_rules[key] = bounded_int(
            st.session_state.grade_rules.get(key, default), default, min_v, max_v
        )

def normalize_shift_counts():
    """Ensure per-doctor fixed D/E/N/Total counts exist. -1 means automatic."""
    if "shift_counts" not in st.session_state or not isinstance(st.session_state.shift_counts, dict):
        st.session_state.shift_counts = {}
    for ni in range(len(st.session_state.get("doctors", []))):
        sc = st.session_state.shift_counts.get(ni, {})
        if not isinstance(sc, dict):
            sc = {}
        for key in ("D", "E", "N", "Total"):
            try:
                sc[key] = int(sc.get(key, -1))
            except (TypeError, ValueError):
                sc[key] = -1
        st.session_state.shift_counts[ni] = sc

def sync_live_total_summary_inputs(num_days: int | None = None):
    """Synchronize live number_input widget values before rendering fixed_total summary.

    Streamlit executes the page from top to bottom. The fixed_total summary is drawn
    above the Duty/Total input grids, so without this sync it can show the previous
    run's values until another widget triggers a rerun. Reading the widget keys here
    makes the summary reflect the most recent DutyRequests and fixed_Total edits.
    """
    if num_days is None:
        num_days = int(st.session_state.get("num_days", 0))

    # DutyRequests widgets live in Tab 2.
    if "duty_requests" not in st.session_state or not isinstance(st.session_state.duty_requests, dict):
        st.session_state.duty_requests = {}
    duty_ver = st.session_state.get("duty_req_version", 0)
    for di in range(int(num_days)):
        vals = list(st.session_state.duty_requests.get(di, [1, 1, 1]))
        if len(vals) < 3:
            vals = (vals + [1, 1, 1])[:3]
        for shift_i in range(3):
            widget_key = f"duty_{di}_{shift_i}_v{duty_ver}"
            if widget_key in st.session_state:
                vals[shift_i] = bounded_int(st.session_state.get(widget_key), vals[shift_i], 0, max(0, len(st.session_state.get("doctors", []))))
        st.session_state.duty_requests[di] = [int(vals[0]), int(vals[1]), int(vals[2])]

    # fixed_Total/D/E/N are edited in the fixed count table and applied only when
    # the user presses the save/apply button. Do not read unsaved editor state here;
    # otherwise every cell edit behaves like it has already been committed.
    normalize_shift_counts()
    # Backward compatibility: if an older page version still has per-doctor D/E/N
    # number_input keys in session_state, read them safely. New versions edit these
    # values in the fixed count table above.
    sc_ver = st.session_state.get("shift_count_version", 0)
    for ni in range(len(st.session_state.get("doctors", []))):
        if ni not in st.session_state.shift_counts:
            st.session_state.shift_counts[ni] = {"D": -1, "E": -1, "N": -1, "Total": -1}
        for shift_key in ("D", "E", "N"):
            widget_key = f"sc_{shift_key}_{ni}_v{sc_ver}"
            if widget_key in st.session_state:
                st.session_state.shift_counts[ni][shift_key] = bounded_int(st.session_state.get(widget_key), -1, -1, 60)


def sync_duty_request_widget(di: int, shift_i: int, widget_key: str):
    """Callback: immediately write a Duty number_input value into duty_requests."""
    if "duty_requests" not in st.session_state or not isinstance(st.session_state.duty_requests, dict):
        st.session_state.duty_requests = {}
    vals = list(st.session_state.duty_requests.get(di, [1, 1, 1]))
    if len(vals) < 3:
        vals = (vals + [1, 1, 1])[:3]
    vals[shift_i] = bounded_int(st.session_state.get(widget_key), vals[shift_i], 0, max(0, len(st.session_state.get("doctors", []))))
    st.session_state.duty_requests[di] = [int(vals[0]), int(vals[1]), int(vals[2])]


def sync_shift_count_widget(ni: int, shift_key: str, widget_key: str):
    """Callback: immediately write a fixed Total/D/E/N value into shift_counts."""
    normalize_shift_counts()
    if ni not in st.session_state.shift_counts:
        st.session_state.shift_counts[ni] = {"D": -1, "E": -1, "N": -1, "Total": -1}
    st.session_state.shift_counts[ni][shift_key] = bounded_int(st.session_state.get(widget_key), -1, -1, 60)


def get_fixed_total_editor_key() -> str:
    """Versioned key for the fixed count table editor."""
    return f"fixed_counts_editor_v{st.session_state.get('shift_count_version', 0)}"


def get_estimated_average_total() -> float:
    """Estimated average total duty count per doctor from current DutyRequests."""
    doctor_count = len(st.session_state.get("doctors", []))
    if doctor_count <= 0:
        return 0.0
    return get_total_duty_count() / doctor_count


def round_shift_adj_diff(diff: float) -> int:
    """Round a total-duty difference to an integer shift_adj.

    A difference below 1 duty is treated as 0 so tiny fractional average effects
    do not create confusing +/-1 adjustments.  Larger differences are rounded to
    the nearest integer, away from zero at .5.
    """
    try:
        diff = float(diff)
    except (TypeError, ValueError):
        return 0
    if abs(diff) < 1:
        return 0
    return int(diff + 0.5) if diff > 0 else int(diff - 0.5)


def recommended_shift_adj_for_doc(fixed_total: int, annual_count: int, estimated_average: float) -> int:
    """Return the recommended explicit shift_adj for one doctor.

    - If fixed_Total is set, use fixed_Total - estimated average.
    - If fixed_Total is blank, use -annual leave count.

    Annual leave and fixed_Total no longer create hidden internal adjustment in
    scheduler.py. This helper only fills the visible shift_adj field when the
    user presses the auto-calculate button.
    """
    if fixed_total >= 0:
        return bounded_int(round_shift_adj_diff(fixed_total - estimated_average), 0, -60, 60)
    return bounded_int(-int(annual_count or 0), 0, -60, 60)


def calculate_shift_adj_preview_df(current_df: pd.DataFrame | None) -> tuple[pd.DataFrame, float, int]:
    """Return a table with recommended shift_adj filled into the visible column.

    This does not save anything to st.session_state.shift_adj or shift_counts.
    The returned table is a screen preview; users must press 저장 to commit it.
    """
    if current_df is None or getattr(current_df, "empty", True):
        out_df = build_fixed_total_editor_df()
    else:
        out_df = current_df.copy()

    estimated_average = get_estimated_average_total()
    updated = 0
    if "근무조정값" not in out_df.columns:
        out_df["근무조정값"] = 0

    for pos, idx in enumerate(out_df.index):
        if pos >= len(st.session_state.get("doctors", [])):
            continue
        fixed_total = parse_fixed_count_value(out_df.at[idx, "fixed_Total"] if "fixed_Total" in out_df.columns else "")
        annual_count = bounded_int(out_df.at[idx, "연차(a)"] if "연차(a)" in out_df.columns else 0, 0, 0, 60)
        out_df.at[idx, "근무조정값"] = recommended_shift_adj_for_doc(fixed_total, annual_count, estimated_average)
        updated += 1
    return out_df, estimated_average, updated


def pending_fixed_total_editor_df_is_valid(pending_df: object, base_df: pd.DataFrame) -> bool:
    """Check whether a screen-only preview table still matches the current doctor list."""
    if not isinstance(pending_df, pd.DataFrame):
        return False
    if len(pending_df) != len(base_df):
        return False
    for col in ("No", "Name"):
        if col not in pending_df.columns or col not in base_df.columns:
            return False
        if list(pending_df[col].astype(str)) != list(base_df[col].astype(str)):
            return False
    return True


def get_fixed_total_editor_display_df() -> pd.DataFrame:
    """Use pending auto-calculation preview table if available; otherwise use committed state."""
    base_df = build_fixed_total_editor_df()
    pending_df = st.session_state.get("fixed_counts_editor_pending_df")
    if pending_fixed_total_editor_df_is_valid(pending_df, base_df):
        return pending_df.copy()
    st.session_state["fixed_counts_editor_pending_df"] = None
    return base_df


def build_fixed_total_editor_df() -> pd.DataFrame:
    """Build an input-order fixed Total/D/E/N table similar to the result summary table."""
    normalize_doctors()
    normalize_grade_rules()
    normalize_shift_counts()
    gr = st.session_state.grade_rules
    senior_min_grade = int(gr.get("senior_min_grade", DEFAULT_GRADE_RULES["senior_min_grade"]))
    junior_max_grade = int(gr.get("junior_max_grade", DEFAULT_GRADE_RULES["junior_max_grade"]))
    ultra_max_grade = int(gr.get("ultra_junior_max_grade", DEFAULT_GRADE_RULES.get("ultra_junior_max_grade", 1)))

    annual_counts = get_annual_leave_counts_by_doc()
    estimated_average = get_estimated_average_total()

    rows = []
    for ni, doc in enumerate(st.session_state.get("doctors", [])):
        grade = bounded_int(doc.get("grade", DEFAULT_DOCTOR_GRADE), DEFAULT_DOCTOR_GRADE, GRADE_MIN_VALUE, GRADE_MAX_VALUE)
        sc = st.session_state.shift_counts.get(ni, {})
        fixed_total_val = parse_fixed_count_value(sc.get("Total", -1))
        annual_count = int(annual_counts.get(ni, 0))
        rows.append({
            "No": ni + 1,
            "Name": doc.get("name", ""),
            "Grade": grade,
            "Senior": "Y" if grade >= senior_min_grade else "",
            "Junior": "Y" if grade <= junior_max_grade else "",
            "초저년차": "Y" if grade <= ultra_max_grade else "",
            "연차(a)": annual_count,
            "근무조정값": int(st.session_state.shift_adj.get(ni, doc.get("shift_adj", 0))),
            "fixed_D": fixed_count_display_value(sc.get("D", -1)),
            "fixed_E": fixed_count_display_value(sc.get("E", -1)),
            "fixed_N": fixed_count_display_value(sc.get("N", -1)),
            "fixed_Total": fixed_count_display_value(sc.get("Total", -1)),
        })
    return pd.DataFrame(rows)


def sync_fixed_total_editor_widget():
    """Callback/sync hook: apply edits from the fixed Total/D/E/N table editor.

    Streamlit's data_editor stores edits in session_state as an edit-delta
    dictionary (edited_rows) in recent versions, while some versions can expose
    a DataFrame-like value.  Read both formats so the fixed count table is the
    single source of truth before summaries, pre-checks, diagnostics, and solver
    params are calculated.
    """
    key = get_fixed_total_editor_key()
    editor_state = st.session_state.get(key)
    normalize_shift_counts()

    editable_cols = (("fixed_D", "D"), ("fixed_E", "E"), ("fixed_N", "N"), ("fixed_Total", "Total"))

    # Format used by st.data_editor widget state: only changed cells are present.
    if isinstance(editor_state, dict):
        edited_rows = editor_state.get("edited_rows", {}) or {}
        for row_idx, changes in edited_rows.items():
            try:
                ni = int(row_idx)
            except (TypeError, ValueError):
                continue
            if ni < 0 or ni >= len(st.session_state.get("doctors", [])):
                continue
            if isinstance(changes, dict):
                if "근무조정값" in changes:
                    adj = bounded_int(changes.get("근무조정값"), 0, -60, 60)
                    st.session_state.shift_adj[ni] = adj
                    if ni < len(st.session_state.get("doctors", [])):
                        st.session_state.doctors[ni]["shift_adj"] = adj
                for col, shift_key in editable_cols:
                    if col in changes:
                        st.session_state.shift_counts[ni][shift_key] = parse_fixed_count_value(changes.get(col))
        return

    # Defensive compatibility for Streamlit versions or testing paths where the
    # widget state is a full table rather than an edit-delta dictionary.
    if isinstance(editor_state, pd.DataFrame):
        apply_fixed_total_editor_df(editor_state)
        return
    if isinstance(editor_state, list):
        try:
            apply_fixed_total_editor_df(pd.DataFrame(editor_state))
        except Exception:
            return


def apply_fixed_total_editor_df(edited_df: pd.DataFrame):
    """Apply the returned data_editor DataFrame to fixed Total/D/E/N shift_counts."""
    editable_cols = (("fixed_D", "D"), ("fixed_E", "E"), ("fixed_N", "N"), ("fixed_Total", "Total"))
    if edited_df is None or edited_df.empty:
        return
    if not any(col in edited_df.columns for col, _ in editable_cols):
        return
    normalize_shift_counts()
    for pos, (_, row) in enumerate(edited_df.iterrows()):
        if pos >= len(st.session_state.get("doctors", [])):
            break
        if "근무조정값" in edited_df.columns:
            adj = bounded_int(row.get("근무조정값", st.session_state.shift_adj.get(pos, 0)), 0, -60, 60)
            st.session_state.shift_adj[pos] = adj
            st.session_state.doctors[pos]["shift_adj"] = adj
        for col, shift_key in editable_cols:
            if col in edited_df.columns:
                st.session_state.shift_counts[pos][shift_key] = parse_fixed_count_value(row.get(col, ""))


def render_fixed_total_editor_table():
    """Render a batched fixed Total/D/E/N editor below the Duty/fixed_total summary.

    The editor is inside a form so Streamlit does not apply every single cell edit
    immediately.  Users can paste/edit many cells, then press one button to commit
    the values to session_state.shift_counts.
    """
    estimated_average = get_estimated_average_total()
    st.caption(
        "아래 표에서 연차(a) 개수, 근무 조정값과 fixed_D / fixed_E / fixed_N / fixed_Total을 함께 확인/수정합니다. "
        "연차(a)는 현재 근무 요청의 a 개수입니다. 자동계산 버튼을 누르면 연차(a) 또는 fixed_Total 기준 권장값이 화면의 근무조정값 칸에 계산됩니다. 저장을 눌러야 실제 반영됩니다. "
        "fixed count는 빈칸 = 자동 평준화, 0 = 해당 근무 없음, 1 이상 = 그 개수로 고정입니다. "
        f"현재 estimated average는 약 {estimated_average:.1f}개/명입니다."
    )
    key = get_fixed_total_editor_key()
    df = get_fixed_total_editor_display_df()

    if st.session_state.get("fixed_counts_editor_pending_df") is not None:
        st.info("자동계산 결과가 화면 표에만 반영되어 있습니다. 실제 설정에 반영하려면 저장을 누르세요.")

    with st.form("fixed_counts_editor_form", clear_on_submit=False):
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            submitted = st.form_submit_button("저장", use_container_width=True)
        with btn_col2:
            auto_submitted = st.form_submit_button("자동계산", use_container_width=True)

        edited_df = st.data_editor(
            df,
            hide_index=True,
            use_container_width=True,
            key=key,
            disabled=["No", "Name", "Grade", "Senior", "Junior", "초저년차", "연차(a)"],
            column_config={
                "No": st.column_config.NumberColumn("No", width="small", disabled=True),
                "Name": st.column_config.TextColumn("Name", width="medium", disabled=True),
                "Grade": st.column_config.NumberColumn("Grade", width="small", disabled=True),
                "Senior": st.column_config.TextColumn("Senior", width="small", disabled=True),
                "Junior": st.column_config.TextColumn("Junior", width="small", disabled=True),
                "초저년차": st.column_config.TextColumn("초저년차", width="small", disabled=True),
                "연차(a)": st.column_config.NumberColumn(
                    "연차(a)",
                    width="small",
                    disabled=True,
                    help="현재 근무 요청에서 a로 입력된 연차 개수입니다. solver 내부에서 자동 shift_adj로 처리하지 않습니다.",
                ),
                "근무조정값": st.column_config.NumberColumn(
                    "근무조정값",
                    width="small",
                    min_value=-60,
                    max_value=60,
                    step=1,
                    format="%d",
                    help="근무 평균 목표를 조정합니다. +1은 목표 근무를 1개 늘리고, -1은 1개 줄이는 효과입니다.",
                ),
                "fixed_D": st.column_config.TextColumn(
                    "fixed_D",
                    width="small",
                    help="빈칸 = 자동 평준화, 0 = Day 근무 없음, 1 이상 = Day 근무 수 고정",
                ),
                "fixed_E": st.column_config.TextColumn(
                    "fixed_E",
                    width="small",
                    help="빈칸 = 자동 평준화, 0 = Evening 근무 없음, 1 이상 = Evening 근무 수 고정",
                ),
                "fixed_N": st.column_config.TextColumn(
                    "fixed_N",
                    width="small",
                    help="빈칸 = 자동 평준화, 0 = Night 근무 없음, 1 이상 = Night 근무 수 고정",
                ),
                "fixed_Total": st.column_config.TextColumn(
                    "fixed_Total",
                    width="small",
                    help="빈칸 = 자동 평준화, 0 = 총근무 없음, 1 이상 = 총 D/E/N 근무 수 고정",
                ),
            },
        )
    if auto_submitted:
        preview_df, avg, updated = calculate_shift_adj_preview_df(edited_df)
        st.session_state["fixed_counts_editor_pending_df"] = preview_df
        st.toast(f"✅ estimated average 약 {avg:.1f}개/명 기준으로 {updated}명의 근무조정값을 화면 표에 계산했습니다. 저장을 눌러야 실제 반영됩니다.", icon="✅")
        # Recreate the editor using the preview table. Do not commit to solver inputs yet.
        st.session_state["shift_count_version"] = st.session_state.get("shift_count_version", 0) + 1
        st.rerun()

    if submitted:
        apply_fixed_total_editor_df(edited_df)
        st.session_state["fixed_counts_editor_pending_df"] = None
        st.toast("✅ 저장되었습니다.", icon="✅")
        # Recreate the editor from committed values and refresh the summary boxes above.
        st.session_state["shift_count_version"] = st.session_state.get("shift_count_version", 0) + 1
        st.rerun()


def get_total_duty_count() -> int:
    """Total number of required assignments in DutyRequests."""
    return int(sum(sum(map(int, st.session_state.duty_requests.get(di, [0, 0, 0]))) for di in range(st.session_state.num_days)))

def get_fixed_total_summary():
    """Return summary of per-doctor fixed_total constraints."""
    normalize_shift_counts()
    fixed = {}
    for ni in range(len(st.session_state.get("doctors", []))):
        val = int(st.session_state.shift_counts.get(ni, {}).get("Total", -1))
        if val >= 0:
            fixed[ni] = val
    total_duty = get_total_duty_count()
    fixed_sum = sum(fixed.values())
    free_count = max(0, len(st.session_state.get("doctors", [])) - len(fixed))
    remaining = total_duty - fixed_sum
    return {
        "total_duty": total_duty,
        "fixed_sum": fixed_sum,
        "fixed_count": len(fixed),
        "free_count": free_count,
        "remaining": remaining,
        "fixed": fixed,
    }

def render_fixed_total_duty_summary(num_days: int):
    """Render a compact mismatch/remaining summary for DutyRequests vs fixed_total."""
    sync_live_total_summary_inputs(num_days)
    fixed_total_info = get_fixed_total_summary()
    d_total = sum(st.session_state.duty_requests.get(di, [0, 0, 0])[0] for di in range(num_days))
    e_total = sum(st.session_state.duty_requests.get(di, [0, 0, 0])[1] for di in range(num_days))
    n_total = sum(st.session_state.duty_requests.get(di, [0, 0, 0])[2] for di in range(num_days))
    annual_total = int(sum(get_annual_leave_counts_by_doc().values()))
    remaining = fixed_total_info["remaining"]
    diff_text = f"{remaining:+d}"
    free_count = int(fixed_total_info.get("free_count", 0))
    remaining_per_free_text = ""
    if free_count > 0 and remaining >= 0:
        remaining_per_free = remaining / free_count
        remaining_per_free_text = f"약 {remaining_per_free:.1f}개/명"

    if fixed_total_info["fixed_count"] == 0:
        if free_count > 0:
            total_per_free = fixed_total_info["total_duty"] / free_count
            comment = (
                f"fixed_total이 지정된 사람이 없습니다. 총근무 수는 전체 {free_count}명에게 자동 평준화됩니다 "
                f"(약 {total_per_free:.1f}개/명)."
            )
        else:
            comment = "fixed_total이 지정된 사람이 없습니다. 총근무 수는 자동 평준화됩니다."
    elif remaining == 0:
        comment = "차이 0: Duty 총합과 fixed_total 합이 정확히 맞습니다."
    elif remaining > 0:
        if free_count > 0:
            comment = (
                f"차이 {diff_text}: Duty 총합이 fixed_total 합보다 {remaining}개 많습니다. "
                f"현재는 fixed_total 미지정 인원 {free_count}명에게 {remaining}개가 자동 배분됩니다 "
                f"({remaining_per_free_text}). "
                f"모든 인원의 Total을 고정하려면 Duty를 {remaining}개 줄이거나 fixed_total을 {remaining}개 늘리세요."
            )
        else:
            comment = (
                f"차이 {diff_text}: Duty 총합이 fixed_total 합보다 {remaining}개 많습니다. "
                f"Duty를 {remaining}개 줄이거나 fixed_total을 {remaining}개 늘려야 합니다."
            )
    else:
        over = -remaining
        comment = (
            f"차이 {diff_text}: fixed_total 합이 Duty 총합보다 {over}개 많습니다. "
            f"Duty를 {over}개 늘리거나 fixed_total을 {over}개 줄여야 합니다."
        )

    st.markdown(
        f"""
        <div style='font-family:var(--mono);font-size:0.80rem;line-height:1.55;
                    padding:0.65rem 0.8rem;border:1px solid #4b5563;border-radius:5px;
                    background:#1f2937;color:#ffffff;margin:0.7rem 0;'>
            <div>
                <span style='color:#ffffff;'>Duty 총합:</span> <b style='color:#ffffff;'>{fixed_total_info['total_duty']}</b>
                <span style='color:#e5e7eb;'>(D {d_total} / E {e_total} / N {n_total})</span>
                &nbsp;|&nbsp; <span style='color:#ffffff;'>연차(a) 총합:</span> <b style='color:#ffffff;'>{annual_total}</b>
                &nbsp;|&nbsp; <span style='color:#ffffff;'>fixed_total 합:</span> <b style='color:#ffffff;'>{fixed_total_info['fixed_sum']}</b>
                &nbsp;|&nbsp; <span style='color:#ffffff;'>fixed_total 미지정 인원:</span> <b style='color:#ffffff;'>{fixed_total_info['free_count']}</b>
                &nbsp;|&nbsp; <span style='color:#ffffff;'>차이:</span> <b style='color:#ffffff;'>{diff_text}</b>
                &nbsp;|&nbsp; <span style='color:#ffffff;'>남은 근무수:</span> <b style='color:#ffffff;'>{remaining}</b>
            </div>
            <div style='margin-top:0.35rem;color:#ffffff;font-weight:600;'>💬 {comment}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    if fixed_total_info["fixed_count"] > 0:
        if remaining < 0:
            st.error(f"fixed_total 합이 Duty 총합보다 {-remaining}개 많습니다. Duty를 {-remaining}개 늘리거나 fixed_total을 {-remaining}개 줄여야 합니다.")
        elif fixed_total_info["free_count"] == 0 and remaining > 0:
            st.error(f"모든 의사의 fixed_total이 지정되어 있는데 Duty 총합이 fixed_total 합보다 {remaining}개 많습니다. Duty를 {remaining}개 줄이거나 fixed_total을 {remaining}개 늘려야 합니다.")
        elif fixed_total_info["free_count"] > 0 and remaining >= 0:
            avg_msg = f" (약 {remaining / fixed_total_info['free_count']:.1f}개/명)" if fixed_total_info['free_count'] else ""
            st.info(f"fixed_total이 없는 {fixed_total_info['free_count']}명에게 남은 근무수 {remaining}개가 자동 배분됩니다{avg_msg}.")

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
        old_ultra_cutoff = None
        for _, row in df.iterrows():
            key = str(row.get("key", "")).strip()
            if key == "ultra_junior_forbid_at_or_above" and pd.notna(row.get("value")):
                old_ultra_cutoff = int(row.get("value"))
            if key in rules and pd.notna(row.get("value")):
                rules[key] = int(row.get("value"))
        if "ultra_junior_max_count" not in set(str(k).strip() for k in df.get("key", [])) and old_ultra_cutoff is not None:
            rules["ultra_junior_max_count"] = max(0, old_ultra_cutoff - 1) if old_ultra_cutoff > 0 else 0
    return rules


def read_config_sheet(xls: pd.ExcelFile, sheet_name: str, index_col=None) -> pd.DataFrame:
    """Read an optional config sheet. Missing old-version sheets become empty DataFrames."""
    if sheet_name not in xls.sheet_names:
        return pd.DataFrame()
    try:
        return pd.read_excel(xls, sheet_name=sheet_name, index_col=index_col)
    except Exception:
        return pd.DataFrame()


def _norm_col_name(col) -> str:
    return str(col).strip().lower().replace(" ", "_")


def row_get_any(row, names, default=None):
    """Return the first non-empty value from row using case/space-insensitive aliases."""
    if row is None:
        return default
    normalized = {_norm_col_name(c): c for c in row.index}
    for name in names:
        key = _norm_col_name(name)
        if key in normalized:
            val = row[normalized[key]]
            if pd.notna(val):
                return val
    return default


def safe_int(value, default: int = 0, min_value: int | None = None, max_value: int | None = None) -> int:
    """Safe int conversion for old Excel files with blanks/NaN/text."""
    try:
        if value is None or pd.isna(value):
            val = int(default)
        else:
            val = int(value)
    except (TypeError, ValueError):
        val = int(default)
    if min_value is not None:
        val = max(int(min_value), val)
    if max_value is not None:
        val = min(int(max_value), val)
    return int(val)


def find_row_by_name_or_position(df: pd.DataFrame, name: str, pos: int):
    """Find a settings row by doctor name first, then by row position."""
    if df is None or df.empty:
        return None
    target = str(name).strip()
    for i, idx in enumerate(df.index):
        if str(idx).strip() == target:
            return df.iloc[i]
    if 0 <= pos < len(df):
        return df.iloc[pos]
    return None


def derive_doctor_names_from_old_config(*dfs) -> list[str]:
    """Fallback for very old config files that do not have a Doctors sheet."""
    names = []
    for df in dfs:
        if df is None or df.empty:
            continue
        for idx in df.index:
            text = str(idx).strip()
            if not text or text.lower() in {"nan", "none"}:
                continue
            if text not in names:
                names.append(text)
        if names:
            break
    return names


def duty_value_from_row(row, shift_label: str, fallback_pos: int) -> int:
    """Read D/E/N from either named columns or the first 3 columns of older files."""
    if row is None:
        return 1
    val = row_get_any(row, [shift_label, shift_label.upper(), shift_label.lower()], default=None)
    if val is None and fallback_pos < len(row.index):
        val = row.iloc[fallback_pos]
    return safe_int(val, 1, 0, max(0, len(st.session_state.get("doctors", []))))


def parse_start_date_from_duty_index(df_duty: pd.DataFrame, fallback: date) -> date:
    """Use the first DutyRequests index as start_date when it looks like a date."""
    if df_duty is None or df_duty.empty:
        return fallback
    try:
        parsed = pd.to_datetime(df_duty.index[0], errors="coerce")
        if pd.notna(parsed):
            return parsed.date()
    except Exception:
        pass
    return fallback


HARD_SHIFT_VALUES = {"D", "E", "N", "x", "a"}

def _clean_shift_request_value(val) -> str:
    """Normalize empty/NaN values from widgets and Excel."""
    if val is None:
        return ""
    if isinstance(val, float) and pd.isna(val):
        return ""
    text = str(val).strip()
    return "" if text.lower() == "nan" else text

def normalize_shift_request_layers():
    """
    Split schedule requests into two layers.
    - base_shift_requests: user-entered wanted/cannot schedule from Tab 1 or Excel.
    - fixed_shift_requests: locks created from the result grid.

    The solver receives the combined overlay. Removing a fixed lock restores the
    original user-entered base value, such as d/en/blank.
    """
    if not st.session_state.get("shift_request_layers_initialized", False):
        existing = {k: _clean_shift_request_value(v) for k, v in st.session_state.get("shift_requests", {}).items()}
        existing = {k: v for k, v in existing.items() if v}
        st.session_state["base_shift_requests"] = dict(existing)
        st.session_state["fixed_shift_requests"] = {}
        st.session_state["shift_request_layers_initialized"] = True

    if "base_shift_requests" not in st.session_state or not isinstance(st.session_state.base_shift_requests, dict):
        st.session_state.base_shift_requests = {}
    if "fixed_shift_requests" not in st.session_state or not isinstance(st.session_state.fixed_shift_requests, dict):
        st.session_state.fixed_shift_requests = {}

    st.session_state.base_shift_requests = {
        k: _clean_shift_request_value(v)
        for k, v in st.session_state.base_shift_requests.items()
        if _clean_shift_request_value(v)
    }
    st.session_state.fixed_shift_requests = {
        k: _clean_shift_request_value(v)
        for k, v in st.session_state.fixed_shift_requests.items()
        if _clean_shift_request_value(v) in HARD_SHIFT_VALUES
    }
    refresh_combined_shift_requests()

def get_combined_shift_requests() -> dict:
    """Return base requests with result-fixed locks overlaid."""
    base = dict(st.session_state.get("base_shift_requests", {}))
    fixed = dict(st.session_state.get("fixed_shift_requests", {}))
    combined = {k: v for k, v in base.items() if _clean_shift_request_value(v)}
    combined.update({k: v for k, v in fixed.items() if _clean_shift_request_value(v) in HARD_SHIFT_VALUES})
    return combined

def refresh_combined_shift_requests() -> dict:
    combined = get_combined_shift_requests()
    st.session_state.shift_requests = combined
    return combined

def is_hard_shift_request_value(val) -> bool:
    return _clean_shift_request_value(val) in HARD_SHIFT_VALUES

def lock_prefix_for_request(val) -> str:
    return "<span class='lock-marker'>🔒</span>" if is_hard_shift_request_value(val) else ""


def get_annual_leave_counts_by_doc() -> dict:
    """Count annual leave requests ('a') by doctor from the effective request layer.

    This is calculated in app.py as a display/export safety net so the Summary
    table still shows 연차 even when an older solved summary is present in
    session_state or a legacy scheduler result did not include the column.
    Fixed request layer overlays base requests, matching the solver input.
    """
    counts = {ni: 0 for ni in range(len(st.session_state.get("doctors", [])))}
    for (ni, _di), val in get_combined_shift_requests().items():
        if 0 <= int(ni) < len(counts) and "a" in _clean_shift_request_value(val).lower():
            counts[int(ni)] += 1
    return counts




def _diagnostic_request_flags(val: str):
    """Return request flags for diagnostic availability checks."""
    text = _clean_shift_request_value(val)
    low = text.lower()
    must = ["D" in text, "E" in text, "N" in text]
    annual = "a" in low
    full_off = annual or "x" in low or "den" in low
    if full_off:
        cant = [True, True, True]
    else:
        cant = [
            ("d" in low and "D" not in text),
            ("e" in low and "E" not in text),
            ("n" in low and "N" not in text),
        ]
    return text, low, must, cant, annual, full_off


def _diagnostic_availability_for_shift(ni: int, di: int, si: int, combined_req: dict):
    """Return (available: bool, reason: str) for one doctor/day/shift.

    This is a pre-solve diagnostic approximation. It reflects request/fixed cells
    and grade hard rules are evaluated at the group level by the caller. Sequence
    constraints such as N-rest are handled only in the window-level rough checks.
    """
    val = combined_req.get((ni, di), "")
    text, low, must, cant, annual, full_off = _diagnostic_request_flags(val)
    shift_key = ["D", "E", "N"][si]
    if annual:
        return False, "연차(a)"
    if "x" in low or "den" in low:
        return False, "x/전체불가"
    if any(must) and not must[si]:
        fixed_to = "/".join([k for k, flag in zip(["D", "E", "N"], must) if flag])
        return False, f"다른 duty 고정({fixed_to})"
    if cant[si]:
        return False, f"{shift_key} 불가"
    return True, "가능"


def _diagnostic_max_workdays_without_consecutive_run(window_len: int, max_consec: int) -> int:
    """Upper-bound workdays in a window if max_consec consecutive workdays is enforced."""
    if max_consec <= 0 or window_len <= max_consec:
        return window_len
    # In every block of max_consec+1 days, at least one day must be off.
    return window_len - (window_len // (max_consec + 1))


def _diagnostic_max_shift_count_without_long_blocks(window_len: int, max_block: int) -> int:
    """Upper-bound same-shift count if max_block consecutive shifts is enforced."""
    if max_block <= 0 or window_len <= max_block:
        return window_len
    return window_len - (window_len // (max_block + 1))


def run_hard_bottleneck_diagnostics() -> dict:
    """Run lightweight 1st/2nd-level infeasibility diagnostics.

    1차: 날짜·Duty별 후보 부족, 고년차 부족, 초저년차 제한, hard fixed 초과.
    2차: 3/5/7일 및 전체 구간에서 필요 근무수와 단순 가능 최대치 비교.
    """
    normalize_doctors()
    normalize_grade_rules()
    normalize_shift_counts()
    sync_live_total_summary_inputs(st.session_state.num_days)
    combined_req = refresh_combined_shift_requests()

    doctors_local = st.session_state.get("doctors", [])
    n_docs = len(doctors_local)
    n_days = int(st.session_state.get("num_days", 0))
    start = st.session_state.get("start_date", date.today())
    duty_requests = st.session_state.get("duty_requests", {})
    grade_rules = st.session_state.grade_rules
    senior_min_grade = int(grade_rules.get("senior_min_grade", DEFAULT_GRADE_RULES["senior_min_grade"]))
    senior_min_count = int(grade_rules.get("senior_min_count", DEFAULT_GRADE_RULES["senior_min_count"]))
    ultra_max_grade = int(grade_rules.get("ultra_junior_max_grade", DEFAULT_GRADE_RULES["ultra_junior_max_grade"]))
    ultra_max_count = int(grade_rules.get("ultra_junior_max_count", DEFAULT_GRADE_RULES["ultra_junior_max_count"]))

    shift_keys = ["D", "E", "N"]
    duty_rows = []

    for di in range(n_days):
        d = start + timedelta(days=di)
        lbl = get_day_label(start, di)
        date_label = f"{d.strftime('%m/%d')}({lbl})"
        needs = list(duty_requests.get(di, [0, 0, 0]))
        if len(needs) < 3:
            needs = (needs + [0, 0, 0])[:3]
        for si, shift_key in enumerate(shift_keys):
            required = int(needs[si])
            if required <= 0:
                continue
            candidates = []
            excluded_reasons = []
            forced = []
            for ni, doc in enumerate(doctors_local):
                available, reason = _diagnostic_availability_for_shift(ni, di, si, combined_req)
                text, _low, must, _cant, _annual, _full_off = _diagnostic_request_flags(combined_req.get((ni, di), ""))
                if available:
                    candidates.append(ni)
                    if must[si]:
                        forced.append(ni)
                else:
                    excluded_reasons.append(reason)

            senior_candidates = [ni for ni in candidates if int(doctors_local[ni].get("grade", DEFAULT_DOCTOR_GRADE)) >= senior_min_grade]
            ultra_candidates = [ni for ni in candidates if int(doctors_local[ni].get("grade", DEFAULT_DOCTOR_GRADE)) <= ultra_max_grade]
            non_ultra_candidates = [ni for ni in candidates if ni not in ultra_candidates]
            forced_ultra = [ni for ni in forced if ni in ultra_candidates]
            effective_possible = len(candidates)
            if ultra_max_count > 0:
                effective_possible = len(non_ultra_candidates) + min(len(ultra_candidates), ultra_max_count)

            issues = []
            status = "가능"
            if len(forced) > required:
                issues.append(f"hard fixed {len(forced)}명 > 필요 {required}명")
            if len(candidates) < required:
                issues.append(f"가능 후보 {len(candidates)}명 < 필요 {required}명")
            if senior_min_count > 0 and len(senior_candidates) < senior_min_count:
                issues.append(f"고년차 후보 {len(senior_candidates)}명 < 최소 {senior_min_count}명")
            if ultra_max_count > 0 and len(forced_ultra) > ultra_max_count:
                issues.append(f"초저년차 hard fixed {len(forced_ultra)}명 > 최대 {ultra_max_count}명")
            if ultra_max_count > 0 and effective_possible < required:
                issues.append(f"초저년차 제한 적용 후 가능 {effective_possible}명 < 필요 {required}명")

            if issues:
                status = "불가능 후보"
            elif len(candidates) == required or effective_possible == required or (senior_min_count > 0 and len(senior_candidates) == senior_min_count):
                status = "빠듯함"
            else:
                continue

            reason_counts = pd.Series(excluded_reasons).value_counts().to_dict() if excluded_reasons else {}
            reason_text = ", ".join(f"{k} {v}명" for k, v in reason_counts.items())
            candidate_text = ", ".join(
                f"{doctors_local[ni]['name']}[{int(doctors_local[ni].get('grade', DEFAULT_DOCTOR_GRADE))}]"
                for ni in candidates
            )
            duty_rows.append({
                "상태": status,
                "날짜": date_label,
                "Duty": shift_key,
                "필요": required,
                "가능후보": len(candidates),
                "고년차후보": len(senior_candidates),
                "초저년차후보": len(ultra_candidates),
                "초저년차제한후가능": effective_possible,
                "hard fixed": len(forced),
                "주요 이슈": "; ".join(issues) if issues else "여유 없음/빠듯함",
                "제외 주요 원인": reason_text,
                "가능 후보": candidate_text,
            })

    # 개인 fixed count feasibility check.
    fixed_rows = []
    for ni, doc in enumerate(doctors_local):
        sc = st.session_state.shift_counts.get(ni, {})
        name = doc.get("name", f"doctor_{ni}")
        for shift_key, si in [("D", 0), ("E", 1), ("N", 2)]:
            fixed_val = int(sc.get(shift_key, -1)) if isinstance(sc, dict) else -1
            if fixed_val >= 0:
                possible = sum(1 for di in range(n_days) if _diagnostic_availability_for_shift(ni, di, si, combined_req)[0])
                if fixed_val > possible:
                    fixed_rows.append({
                        "이름": name,
                        "항목": f"fixed_{shift_key}",
                        "고정값": fixed_val,
                        "단순 가능 최대": possible,
                        "부족": fixed_val - possible,
                        "설명": f"{shift_key} 가능 날짜가 고정값보다 적습니다.",
                    })
        fixed_total = int(sc.get("Total", -1)) if isinstance(sc, dict) else -1
        if fixed_total >= 0:
            possible_days = 0
            for di in range(n_days):
                if any(_diagnostic_availability_for_shift(ni, di, si, combined_req)[0] for si in range(3)):
                    possible_days += 1
            r = st.session_state.rules.get(ni, DEFAULT_RULES.copy())
            r6 = int(r.get("rule_max_shifts_per_week", DEFAULT_RULES["rule_max_shifts_per_week"]))
            r5 = int(r.get("rule_max_consec_days", DEFAULT_RULES["rule_max_consec_days"]))
            possible_total = possible_days
            if n_days <= 7 and r6 > 0:
                possible_total = min(possible_total, r6)
            possible_total = min(possible_total, _diagnostic_max_workdays_without_consecutive_run(n_days, r5))
            if fixed_total > possible_total:
                fixed_rows.append({
                    "이름": name,
                    "항목": "fixed_Total",
                    "고정값": fixed_total,
                    "단순 가능 최대": possible_total,
                    "부족": fixed_total - possible_total,
                    "설명": "연차/x/불가요청 및 연속근무/주간상한을 고려한 단순 최대보다 fixed_Total이 큽니다.",
                })

    # 2차: window-level bottlenecks. This uses upper-bound availability, so if demand
    # exceeds this value the window is structurally impossible under current hard inputs.
    window_rows = []
    window_lengths = []
    for length in (3, 5, 7, n_days):
        if 1 <= length <= n_days and length not in window_lengths:
            window_lengths.append(length)

    for length in window_lengths:
        for start_di in range(0, n_days - length + 1):
            end_di = start_di + length - 1
            sdate = start + timedelta(days=start_di)
            edate = start + timedelta(days=end_di)
            label = f"{sdate.strftime('%m/%d')}~{edate.strftime('%m/%d')}"

            total_need = 0
            shift_need = {"D": 0, "E": 0, "N": 0}
            for di in range(start_di, end_di + 1):
                needs = list(duty_requests.get(di, [0, 0, 0]))
                if len(needs) < 3:
                    needs = (needs + [0, 0, 0])[:3]
                for si, sk in enumerate(shift_keys):
                    shift_need[sk] += int(needs[si])
                    total_need += int(needs[si])

            total_possible = 0
            shift_possible = {"D": 0, "E": 0, "N": 0}
            for ni in range(n_docs):
                r = st.session_state.rules.get(ni, DEFAULT_RULES.copy())
                r6 = int(r.get("rule_max_shifts_per_week", DEFAULT_RULES["rule_max_shifts_per_week"]))
                r5 = int(r.get("rule_max_consec_days", DEFAULT_RULES["rule_max_consec_days"]))
                n_max = int(r.get("rule_n_block_max", DEFAULT_RULES["rule_n_block_max"]))

                available_work_days = 0
                for di in range(start_di, end_di + 1):
                    if any(_diagnostic_availability_for_shift(ni, di, si, combined_req)[0] for si in range(3)):
                        available_work_days += 1
                person_possible = available_work_days
                if length <= 7 and r6 > 0:
                    person_possible = min(person_possible, r6)
                person_possible = min(person_possible, _diagnostic_max_workdays_without_consecutive_run(length, r5))
                total_possible += person_possible

                for si, sk in enumerate(shift_keys):
                    avail_shift_days = sum(
                        1 for di in range(start_di, end_di + 1)
                        if _diagnostic_availability_for_shift(ni, di, si, combined_req)[0]
                    )
                    if sk == "N":
                        avail_shift_days = min(avail_shift_days, _diagnostic_max_shift_count_without_long_blocks(length, n_max))
                    if length <= 7 and r6 > 0:
                        avail_shift_days = min(avail_shift_days, r6)
                    shift_possible[sk] += avail_shift_days

            if total_need > total_possible:
                window_rows.append({
                    "구간": label,
                    "길이": length,
                    "항목": "전체근무",
                    "필요": total_need,
                    "단순 가능 최대": total_possible,
                    "부족": total_need - total_possible,
                    "설명": "x/a/불가요청, 주간상한, 최대연속근무를 반영한 단순 최대보다 필요 근무가 많습니다.",
                })
            for sk in shift_keys:
                if shift_need[sk] > shift_possible[sk]:
                    window_rows.append({
                        "구간": label,
                        "길이": length,
                        "항목": sk,
                        "필요": shift_need[sk],
                        "단순 가능 최대": shift_possible[sk],
                        "부족": shift_need[sk] - shift_possible[sk],
                        "설명": f"{sk} 가능 후보의 구간 내 단순 최대보다 {sk} 필요 개수가 많습니다.",
                    })

    duty_df = pd.DataFrame(duty_rows)
    fixed_df = pd.DataFrame(fixed_rows)
    window_df = pd.DataFrame(window_rows)
    return {
        "duty_df": duty_df,
        "fixed_df": fixed_df,
        "window_df": window_df,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": "이 진단은 1차/2차 병목 후보를 찾는 사전 검사입니다. N-rest, E→D 금지, 연속근무 등 전체 조합 충돌은 일부만 근사하므로, 원인 후보로 해석하세요.",
    }


def render_hard_bottleneck_diagnostics(results: dict):
    """Render diagnostic result tables."""
    if not results:
        return
    st.markdown('<div class="section-label">🧪 진단모드 결과</div>', unsafe_allow_html=True)
    st.caption(results.get("note", ""))
    st.caption(f"생성 시각: {results.get('generated_at', '')}")

    duty_df = results.get("duty_df", pd.DataFrame())
    fixed_df = results.get("fixed_df", pd.DataFrame())
    window_df = results.get("window_df", pd.DataFrame())

    st.markdown("**1차 진단 · 날짜/Duty별 후보 부족**")
    if duty_df is None or duty_df.empty:
        st.success("날짜·Duty 단위에서 바로 보이는 후보 부족은 발견되지 않았습니다.")
    else:
        st.dataframe(duty_df, use_container_width=True, hide_index=True)

    st.markdown("**1차 진단 · 개인 fixed_Total / fixed_D/E/N 가능성**")
    if fixed_df is None or fixed_df.empty:
        st.success("개인 fixed count가 단순 가능 최대를 초과하는 경우는 발견되지 않았습니다.")
    else:
        st.dataframe(fixed_df, use_container_width=True, hide_index=True)

    st.markdown("**2차 진단 · 구간별 병목 후보**")
    if window_df is None or window_df.empty:
        st.success("3/5/7일 및 전체 구간의 단순 가능 최대 부족은 발견되지 않았습니다.")
    else:
        st.dataframe(window_df, use_container_width=True, hide_index=True)



# ── Diagnostic mode helpers ──────────────────────────────────────────────────
SHIFT_SHORT = ["D", "E", "N"]


def _diagnostic_rule_value(doctor_idx: int, key: str, default: int) -> int:
    try:
        return int(st.session_state.rules.get(doctor_idx, {}).get(key, default))
    except (TypeError, ValueError):
        return int(default)


def _diagnostic_daily_capacity_limit(doctor_idx: int, day_idx: int) -> int:
    """Approximate maximum number of shifts a doctor can take on a day for diagnostic capacity."""
    r0 = _diagnostic_rule_value(doctor_idx, "rule_max_shifts_per_day", DEFAULT_RULES["rule_max_shifts_per_day"])
    dtype = st.session_state.day_types.get(day_idx, "평일")
    is_hol = dtype in ("토", "일", "공")
    if r0 == 1:
        return 1
    if r0 == 2:
        return 2
    if r0 == 3:
        return 3
    if r0 == 4:
        return 2 if is_hol else 1
    if r0 == 5:
        return 3 if is_hol else 1
    return max(1, min(3, int(r0)))


def _diagnostic_cell_reason(cell_value, target_shift: str) -> tuple[bool, str]:
    """Return (can_work_target_shift, reason_if_excluded) from a request cell."""
    text = _clean_shift_request_value(cell_value)
    if not text:
        return True, ""
    lower = text.lower()

    if "a" in lower:
        return False, "연차(a)"
    if "x" in lower or "den" in lower:
        return False, "전체불가(x/den)"

    # Uppercase D/E/N are treated as hard wanted/fixed assignment for diagnosis.
    hard_shifts = [sh for sh in SHIFT_SHORT if sh in text]
    if hard_shifts:
        if target_shift in hard_shifts:
            return True, ""
        return False, f"다른 duty 고정/희망({''.join(hard_shifts)})"

    if target_shift.lower() in lower:
        return False, f"{target_shift} 불가"
    return True, ""


def _diagnostic_can_work_shift(doctor_idx: int, day_idx: int, shift_idx: int, combined_req: dict) -> tuple[bool, str]:
    target = SHIFT_SHORT[shift_idx]
    return _diagnostic_cell_reason(combined_req.get((doctor_idx, day_idx), ""), target)


def _max_senior_selectable_with_ultra_cap(candidates: list[int], need: int, grades: dict[int, int], senior_min_grade: int, ultra_max_grade: int, ultra_max_count: int) -> int:
    """Maximum number of seniors selectable among `need` staff under optional ultra-junior cap."""
    if need <= 0 or not candidates:
        return 0
    if ultra_max_count <= 0:
        return min(need, sum(1 for n in candidates if grades.get(n, DEFAULT_DOCTOR_GRADE) >= senior_min_grade))

    ultra = [n for n in candidates if grades.get(n, DEFAULT_DOCTOR_GRADE) <= ultra_max_grade]
    non_ultra = [n for n in candidates if n not in set(ultra)]
    senior_ultra = sum(1 for n in ultra if grades.get(n, DEFAULT_DOCTOR_GRADE) >= senior_min_grade)
    senior_non_ultra = sum(1 for n in non_ultra if grades.get(n, DEFAULT_DOCTOR_GRADE) >= senior_min_grade)

    best = -1
    max_ultra_taken = min(len(ultra), ultra_max_count, need)
    for ultra_taken in range(max_ultra_taken + 1):
        non_ultra_taken = need - ultra_taken
        if non_ultra_taken < 0 or non_ultra_taken > len(non_ultra):
            continue
        seniors = min(senior_ultra, ultra_taken) + min(senior_non_ultra, non_ultra_taken)
        best = max(best, seniors)
    return max(0, best)


def _diagnostic_local_grade_messages(candidates: list[int], need: int, grades: dict[int, int], gr: dict) -> list[str]:
    """Return local hard-rule messages for one date-duty candidate pool."""
    messages = []
    if need <= 0:
        return messages

    senior_min_grade = int(gr.get("senior_min_grade", DEFAULT_GRADE_RULES["senior_min_grade"]))
    senior_min_count = int(gr.get("senior_min_count", DEFAULT_GRADE_RULES["senior_min_count"]))
    ultra_max_grade = int(gr.get("ultra_junior_max_grade", DEFAULT_GRADE_RULES["ultra_junior_max_grade"]))
    ultra_max_count = int(gr.get("ultra_junior_max_count", DEFAULT_GRADE_RULES["ultra_junior_max_count"]))

    if len(candidates) < need:
        messages.append(f"가능 후보 {len(candidates)}명 < 필요 {need}명")

    if senior_min_count > 0:
        max_seniors = _max_senior_selectable_with_ultra_cap(
            candidates, need, grades, senior_min_grade, ultra_max_grade, ultra_max_count
        )
        if max_seniors < senior_min_count:
            senior_pool = sum(1 for n in candidates if grades.get(n, DEFAULT_DOCTOR_GRADE) >= senior_min_grade)
            messages.append(
                f"고년차 부족: grade≥{senior_min_grade} 후보 {senior_pool}명, 선택 가능 최대 {max_seniors}명 < 필요 {senior_min_count}명"
            )

    if ultra_max_count > 0:
        ultra_count = sum(1 for n in candidates if grades.get(n, DEFAULT_DOCTOR_GRADE) <= ultra_max_grade)
        non_ultra_count = len(candidates) - ultra_count
        max_staff_under_ultra_rule = non_ultra_count + min(ultra_count, ultra_max_count)
        if max_staff_under_ultra_rule < need:
            messages.append(
                f"초저년차 제한 병목: grade≤{ultra_max_grade} 최대 {ultra_max_count}명 허용 시 최대 {max_staff_under_ultra_rule}명만 배치 가능"
            )
    return messages


def run_hard_rule_diagnostics() -> dict:
    """Run 1st/2nd-stage hard-rule bottleneck diagnostics without solving the full schedule."""
    normalize_doctors()
    normalize_grade_rules()
    normalize_shift_counts()
    combined_req = refresh_combined_shift_requests()

    doctors = st.session_state.doctors
    num_docs = len(doctors)
    num_days = int(st.session_state.num_days)
    start_date = st.session_state.start_date
    grades = {ni: int(doc.get("grade", DEFAULT_DOCTOR_GRADE)) for ni, doc in enumerate(doctors)}
    gr = st.session_state.grade_rules

    # 1차: 날짜/Duty별 후보 부족 진단
    day_rows = []
    availability_cache = {}
    for di in range(num_days):
        d = start_date + timedelta(days=di)
        dtype = st.session_state.day_types.get(di, "평일")
        for si, shift_label in enumerate(SHIFT_SHORT):
            need = int(st.session_state.duty_requests.get(di, [0, 0, 0])[si])
            if need <= 0:
                continue
            candidates = []
            excluded_reasons = {}
            forced = []
            for ni, doc in enumerate(doctors):
                can_work, reason = _diagnostic_can_work_shift(ni, di, si, combined_req)
                availability_cache[(ni, di, si)] = can_work
                cell = _clean_shift_request_value(combined_req.get((ni, di), ""))
                if can_work:
                    candidates.append(ni)
                    if shift_label in cell:
                        forced.append(ni)
                else:
                    excluded_reasons[reason or "기타"] = excluded_reasons.get(reason or "기타", 0) + 1

            hard_messages = _diagnostic_local_grade_messages(candidates, need, grades, gr)
            if len(forced) > need:
                hard_messages.append(f"{shift_label} 고정/희망 인원 {len(forced)}명 > 필요 {need}명")

            if hard_messages:
                status = "불가능"
            elif len(candidates) == need:
                status = "빠듯함"
            elif len(candidates) <= need + 2:
                status = "주의"
            else:
                status = "가능"

            candidate_names = ", ".join(f"{doctors[n]['name']} [{grades.get(n, DEFAULT_DOCTOR_GRADE)}]" for n in candidates[:12])
            if len(candidates) > 12:
                candidate_names += f" 외 {len(candidates)-12}명"
            excluded_summary = ", ".join(f"{k} {v}명" for k, v in sorted(excluded_reasons.items()))
            day_rows.append({
                "날짜": f"{d.strftime('%m/%d')}({get_day_label(start_date, di)})",
                "DayIdx": di + 1,
                "유형": dtype,
                "Duty": shift_label,
                "필요": need,
                "가능 후보": len(candidates),
                "고정/희망": len(forced),
                "상태": status,
                "병목 이유": "; ".join(hard_messages),
                "가능자": candidate_names,
                "제외 요약": excluded_summary,
            })

    day_df = pd.DataFrame(day_rows)
    if not day_df.empty:
        status_rank = {"불가능": 0, "빠듯함": 1, "주의": 2, "가능": 3}
        day_df["_rank"] = day_df["상태"].map(status_rank).fillna(9).astype(int)
        day_df = day_df.sort_values(["_rank", "DayIdx", "Duty"], kind="stable").drop(columns=["_rank"])

    # 2차: 구간별 필요 근무수 vs 단순 가능 최대 진단
    def possible_shifts_for_doc_day(ni: int, di: int) -> list[int]:
        out = []
        for si in range(3):
            if int(st.session_state.duty_requests.get(di, [0, 0, 0])[si]) <= 0:
                continue
            can_work, _ = _diagnostic_can_work_shift(ni, di, si, combined_req)
            if can_work:
                out.append(si)
        return out

    def window_capacity(days: list[int], shift_filter: str) -> int:
        total = 0
        for ni in range(num_docs):
            daily_caps = []
            for di in days:
                if shift_filter in SHIFT_SHORT:
                    si = SHIFT_SHORT.index(shift_filter)
                    daily_caps.append(1 if _diagnostic_can_work_shift(ni, di, si, combined_req)[0] and int(st.session_state.duty_requests.get(di, [0,0,0])[si]) > 0 else 0)
                else:
                    daily_caps.append(min(len(possible_shifts_for_doc_day(ni, di)), _diagnostic_daily_capacity_limit(ni, di)))
            doc_cap = sum(daily_caps)
            r6 = _diagnostic_rule_value(ni, "rule_max_shifts_per_week", DEFAULT_RULES["rule_max_shifts_per_week"])
            if r6 > 0 and len(days) <= 7:
                doc_cap = min(doc_cap, r6)
            fixed_total = int(st.session_state.shift_counts.get(ni, {}).get("Total", -1))
            if fixed_total >= 0:
                # fixed_Total itself should not create interval proof, but it is still an upper bound on total shifts.
                doc_cap = min(doc_cap, fixed_total)
            total += doc_cap
        return int(total)

    def demand_for_days(days: list[int], shift_filter: str) -> int:
        if shift_filter in SHIFT_SHORT:
            si = SHIFT_SHORT.index(shift_filter)
            return int(sum(st.session_state.duty_requests.get(di, [0,0,0])[si] for di in days))
        return int(sum(sum(st.session_state.duty_requests.get(di, [0,0,0])) for di in days))

    interval_rows = []
    window_sizes = [3, 5, 7]
    if num_days not in window_sizes:
        window_sizes.append(num_days)
    for w in window_sizes:
        if w <= 0 or w > num_days:
            continue
        starts = [0] if w == num_days else list(range(0, num_days - w + 1))
        for start in starts:
            days = list(range(start, start + w))
            # 전체, D/E/N separately
            for item in ["전체", "D", "E", "N"]:
                demand = demand_for_days(days, item)
                if demand <= 0:
                    continue
                cap = window_capacity(days, item)
                shortage = max(0, demand - cap)
                util = round(demand / cap, 2) if cap > 0 else None
                if shortage > 0:
                    status = "부족"
                elif cap > 0 and demand / cap >= 0.9:
                    status = "빡빡함"
                elif cap > 0 and demand / cap >= 0.8:
                    status = "주의"
                else:
                    status = "가능"
                if status == "가능":
                    continue
                start_d = start_date + timedelta(days=start)
                end_d = start_date + timedelta(days=start + w - 1)
                interval_rows.append({
                    "구간": f"{start_d.strftime('%m/%d')}~{end_d.strftime('%m/%d')}",
                    "일수": w,
                    "항목": item,
                    "필요": demand,
                    "단순 가능 최대": cap,
                    "부족": shortage,
                    "사용률": "∞" if util is None else f"{int(round(util*100))}%",
                    "상태": status,
                    "설명": "N-rest/연속근무/전후일 규칙은 완전 반영 전의 빠른 구간 진단입니다.",
                })

            holiday_days = [di for di in days if st.session_state.day_types.get(di, "평일") in ("토", "일", "공")]
            if holiday_days:
                demand = demand_for_days(holiday_days, "전체")
                cap = window_capacity(holiday_days, "전체")
                shortage = max(0, demand - cap)
                util = round(demand / cap, 2) if cap > 0 else None
                if shortage > 0:
                    status = "부족"
                elif cap > 0 and demand / cap >= 0.9:
                    status = "빡빡함"
                elif cap > 0 and demand / cap >= 0.8:
                    status = "주의"
                else:
                    status = "가능"
                if status != "가능":
                    start_d = start_date + timedelta(days=holiday_days[0])
                    end_d = start_date + timedelta(days=holiday_days[-1])
                    interval_rows.append({
                        "구간": f"{start_d.strftime('%m/%d')}~{end_d.strftime('%m/%d')}",
                        "일수": len(holiday_days),
                        "항목": "휴일전체",
                        "필요": demand,
                        "단순 가능 최대": cap,
                        "부족": shortage,
                        "사용률": "∞" if util is None else f"{int(round(util*100))}%",
                        "상태": status,
                        "설명": "해당 구간 안의 토/일/공 날짜만 모아 계산했습니다.",
                    })

    interval_df = pd.DataFrame(interval_rows)
    if not interval_df.empty:
        status_rank = {"부족": 0, "빡빡함": 1, "주의": 2, "가능": 3}
        interval_df["_rank"] = interval_df["상태"].map(status_rank).fillna(9).astype(int)
        interval_df = (
            interval_df
            .sort_values(["_rank", "부족", "일수"], ascending=[True, False, True], kind="stable")
            .drop(columns=["_rank"])
            .head(80)
        )

    impossible_count = int((day_df["상태"] == "불가능").sum()) if not day_df.empty else 0
    tight_count = int(day_df["상태"].isin(["빠듯함", "주의"]).sum()) if not day_df.empty else 0
    interval_shortage_count = int((interval_df["상태"] == "부족").sum()) if not interval_df.empty else 0

    return {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "day_duty": day_df,
        "intervals": interval_df,
        "summary": {
            "날짜/Duty 불가능": impossible_count,
            "날짜/Duty 빠듯/주의": tight_count,
            "구간 부족": interval_shortage_count,
        },
    }


def render_hard_rule_diagnostics(diag: dict):
    """Render stored diagnostic tables in the Results tab."""
    if not diag:
        return
    st.markdown('<div class="section-label">🩺 진단모드 결과</div>', unsafe_allow_html=True)
    st.caption(
        "진단모드는 해가 없을 때 원인 후보를 빠르게 좁히는 도구입니다. "
        "1차는 날짜/Duty별 후보 부족, 2차는 3·5·7일/전체 구간의 필요 근무수와 단순 가능 최대를 봅니다. "
        "N-rest, 연속근무, 전후일 관계처럼 순서가 얽힌 모든 hard rule을 완전 증명하는 것은 아닙니다."
    )
    summary = diag.get("summary", {})
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("날짜/Duty 불가능", summary.get("날짜/Duty 불가능", 0))
    sc2.metric("날짜/Duty 빠듯/주의", summary.get("날짜/Duty 빠듯/주의", 0))
    sc3.metric("구간 부족", summary.get("구간 부족", 0))

    day_df = diag.get("day_duty", pd.DataFrame())
    interval_df = diag.get("intervals", pd.DataFrame())

    st.markdown("**1차: 날짜/Duty별 후보 부족**")
    if day_df is None or day_df.empty:
        st.success("날짜/Duty 단독 후보 부족은 발견되지 않았습니다.")
    else:
        important_day = day_df[day_df["상태"].isin(["불가능", "빠듯함", "주의"])].copy()
        if important_day.empty:
            st.success("날짜/Duty 단독 후보 부족은 발견되지 않았습니다.")
        else:
            st.dataframe(important_day, use_container_width=True, hide_index=True)
        with st.expander("전체 날짜/Duty 후보표 보기"):
            st.dataframe(day_df, use_container_width=True, hide_index=True)

    st.markdown("**2차: 구간별 병목 검사**")
    if interval_df is None or interval_df.empty:
        st.success("3·5·7일/전체 구간에서 단순 capacity 부족은 발견되지 않았습니다.")
    else:
        st.dataframe(interval_df, use_container_width=True, hide_index=True)

def read_readme_text() -> str:
    """Load README.md from the same directory as app.py for the in-app guide."""
    readme_path = Path(__file__).with_name("README.md")
    try:
        return readme_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "README.md 파일을 app.py와 같은 폴더에 두면 이곳에 사용 설명서가 표시됩니다."
    except Exception as exc:
        return f"README.md를 읽는 중 오류가 발생했습니다: {exc}"


def render_readme_guide(expanded: bool = False):
    """Render the user guide near the top of the Streamlit app."""
    st.markdown('<div class="section-label">📘 사용 가이드</div>', unsafe_allow_html=True)
    with st.expander("처음 사용하는 경우: 전체 사용법 / README 보기", expanded=expanded):
        st.markdown(read_readme_text())


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
        row = {
            "No": int(ni) + 1,
            "Name": doc["name"],
            "Grade": int(doc.get("grade", DEFAULT_DOCTOR_GRADE)),
        }
        combined_req = refresh_combined_shift_requests()
        for di, col in enumerate(date_cols):
            req = _clean_shift_request_value(combined_req.get((ni, di), ""))
            if req.lower() == "a":
                row[col] = "A"
            else:
                val = sol.get((ni, di), "")
                row[col] = val.upper() if val else ""
        export_rows.append(row)
    export_df = pd.DataFrame(export_rows)

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
        export_df.to_excel(writer, sheet_name="Schedule", index=False)
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
normalize_shift_counts()
normalize_shift_request_layers()


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

    with st.form("add_doctor_form", clear_on_submit=True):
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
                st.session_state.shift_counts[n] = {"D": -1, "E": -1, "N": -1, "Total": -1}
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
        sol_limit = st.number_input("최대 솔루션 수", 1, 100, 5, key="sol_limit")
        adv_limit = st.number_input("최소 편차에 추가 허용 편차", 0, 100, 0, key="adv_limit")
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

        # Rules: RULE_COL_ORDER 순서 + D/E/N 고정 개수
        rules_rows = []
        for ni in range(len(doctor_names)):
            r  = st.session_state.rules.get(ni, {})
            sc = st.session_state.shift_counts.get(ni, {"D": -1, "E": -1, "N": -1, "Total": -1})
            row = {key: r.get(key, '') for key in RULE_COL_ORDER}
            row["fixed_D"] = fixed_count_excel_value(sc.get("D", -1))
            row["fixed_E"] = fixed_count_excel_value(sc.get("E", -1))
            row["fixed_N"] = fixed_count_excel_value(sc.get("N", -1))
            row["fixed_Total"] = fixed_count_excel_value(sc.get("Total", -1))
            rules_rows.append(row)
        df_rules = pd.DataFrame(rules_rows, index=doctor_names)
        df_rules.index.name = 'Name'

        df_duty = pd.DataFrame.from_dict(st.session_state.duty_requests, orient='index', columns=['D', 'E', 'N'])
        df_duty.index = date_list

        # ShiftRequests: 행=의사, 열=날짜 구조로 저장
        # 사용자가 원래 입력한 wanted/cannot schedule만 저장한다.
        # 결과표에서 추가로 고정한 셀은 FixedShiftRequests 시트에 따로 저장한다.
        shift_grid = pd.DataFrame('', index=doctor_names, columns=date_list)
        shift_grid.index.name = 'Name'
        for (doc_idx, day_idx), val in st.session_state.base_shift_requests.items():
            if day_idx < len(date_list) and doc_idx < len(doctor_names):
                shift_grid.iloc[doc_idx, day_idx] = val

        fixed_grid = pd.DataFrame('', index=doctor_names, columns=date_list)
        fixed_grid.index.name = 'Name'
        for (doc_idx, day_idx), val in st.session_state.fixed_shift_requests.items():
            if day_idx < len(date_list) and doc_idx < len(doctor_names):
                fixed_grid.iloc[doc_idx, day_idx] = val

        df_grade_rules = grade_rules_to_df(st.session_state.grade_rules)

        towrite = BytesIO()
        with pd.ExcelWriter(towrite, engine='openpyxl') as writer:
            pd.DataFrame(st.session_state.doctors).to_excel(writer, sheet_name='Doctors', index=False)
            df_rules.to_excel(writer, sheet_name='Rules')
            df_grade_rules.to_excel(writer, sheet_name='GradeRules', index=False)
            df_duty.to_excel(writer, sheet_name='DutyRequests')
            shift_grid.to_excel(writer, sheet_name='ShiftRequests')
            fixed_grid.to_excel(writer, sheet_name='FixedShiftRequests')

        st.download_button(
            label="📥 설정 파일 다운로드 (.xlsx)",
            data=towrite.getvalue(),
            file_name="scheduler_config.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # 2. [불러오기] Excel 가져오기
    # 2. [불러오기] Excel 가져오기
    uploaded_file = st.file_uploader("설정 Excel 불러오기", type="xlsx", key="upload_xlsx")
    if uploaded_file is not None:
        if st.button("📤 불러오기 적용", use_container_width=True, key="btn_load_config"):
            try:
                xls = pd.ExcelFile(uploaded_file)

                # 이전 버전 config 호환: 새 시트/컬럼이 없어도 empty/default로 처리한다.
                df_doctors = read_config_sheet(xls, 'Doctors')
                df_rules = read_config_sheet(xls, 'Rules', index_col=0)
                df_duty = read_config_sheet(xls, 'DutyRequests', index_col=0)
                df_shift = read_config_sheet(xls, 'ShiftRequests', index_col=0)
                df_fixed_shift = read_config_sheet(xls, 'FixedShiftRequests', index_col=0)
                df_grade_rules = read_config_sheet(xls, 'GradeRules')

                # 1) 의사 정보: Doctors 시트가 없거나 grade/shift_adj 컬럼이 없어도 기본값으로 복원
                new_doctors = []
                if df_doctors is not None and not df_doctors.empty:
                    for row_pos, row in df_doctors.iterrows():
                        name_val = row_get_any(row, ['name', 'Name', '이름', 'doctor', 'Doctor'], default=None)
                        # 아주 오래된 파일에서 첫 번째 컬럼이 이름인 경우까지 허용
                        if name_val is None and len(row.index) > 0:
                            name_val = row.iloc[0]
                        name = str(name_val).strip() if name_val is not None else ''
                        if not name or name.lower() in {'nan', 'none'}:
                            continue
                        grade = safe_int(row_get_any(row, ['grade', 'Grade'], DEFAULT_DOCTOR_GRADE), DEFAULT_DOCTOR_GRADE, GRADE_MIN_VALUE, GRADE_MAX_VALUE)
                        adj = safe_int(row_get_any(row, ['shift_adj', 'Shift_adj', '근무 조정값', 'adjustment'], 0), 0, -60, 60)
                        new_doctors.append({"name": name, "shift_adj": adj, "grade": grade})
                else:
                    fallback_names = derive_doctor_names_from_old_config(df_rules, df_shift, df_fixed_shift)
                    new_doctors = [
                        {"name": name, "shift_adj": 0, "grade": DEFAULT_DOCTOR_GRADE}
                        for name in fallback_names
                    ]

                if not new_doctors:
                    raise ValueError("Doctors 시트 또는 Rules/ShiftRequests 행 이름에서 의사 이름을 찾을 수 없습니다.")

                st.session_state.doctors = new_doctors
                normalize_doctors()

                # 2) Rules + shift_counts: 새 rule/fixed_Total 컬럼이 없으면 현재 앱 기본값 사용
                rule_aliases = {
                    "rule_max_shifts_per_day": ["rule_max_shifts_per_day", "하루 근무 횟수"],
                    "rule_n_block_max": ["rule_n_block_max", "N 뭉치 최대 길이"],
                    "rule_n_rest": ["rule_n_rest", "N뭉치 후 완전 Off 의무일", "N뭉치 후 완전Off 의무일"],
                    "rule_n_gap": ["rule_n_gap", "N뭉치 후 다음 N까지 총 간격", "N뭉치 후 다음N까지 총 간격"],
                    "rule_no_day_after_eve": ["rule_no_day_after_eve", "Evening 후 Day 금지"],
                    "rule_no_3eve_consec": ["rule_no_3eve_consec", "Evening 3연속 금지"],
                    "rule_no_3eve_in_4days": ["rule_no_3eve_in_4days", "4일내 Evening 3회 금지"],
                    "rule_max_consec_days": ["rule_max_consec_days", "최대 연속 근무일수"],
                    "rule_max_shifts_per_week": ["rule_max_shifts_per_week", "7일 구간 최대 근무수", "7일 구간 최대 근무수 (0=무제한)"],
                    "rule_no_3day_consec": ["rule_no_3day_consec", "Day 3연속 금지"],
                }
                fixed_aliases = {
                    "D": ["fixed_D", "fixed_d", "D 고정"],
                    "E": ["fixed_E", "fixed_e", "E 고정"],
                    "N": ["fixed_N", "fixed_n", "N 고정"],
                    "Total": ["fixed_Total", "fixed_total", "fixed_TOTAL", "Total 고정", "fixed total"],
                }

                new_rules = {}
                new_shift_counts = {}
                for i, doc in enumerate(st.session_state.doctors):
                    row = find_row_by_name_or_position(df_rules, doc['name'], i)
                    base_rule = DEFAULT_RULES.copy()
                    for key in RULE_COL_ORDER:
                        base_rule[key] = safe_int(
                            row_get_any(row, rule_aliases.get(key, [key]), DEFAULT_RULES.get(key, 0)),
                            DEFAULT_RULES.get(key, 0),
                            0,
                            60,
                        )
                    new_rules[i] = base_rule
                    new_shift_counts[i] = {
                        shift_key: safe_int(row_get_any(row, aliases, -1), -1, -1, 60)
                        for shift_key, aliases in fixed_aliases.items()
                    }

                st.session_state.rules = new_rules
                st.session_state.shift_counts = new_shift_counts
                normalize_shift_counts()
                # Excel 불러오기 후 Total/D/E/N 고정 개수 입력 위젯이 이전 값을 붙잡지 않도록 key version 갱신
                st.session_state["shift_count_version"] = st.session_state.get("shift_count_version", 0) + 1

                # shift_adj도 Doctors 시트에서 복원. 없으면 0.
                st.session_state.shift_adj = {
                    i: safe_int(st.session_state.doctors[i].get('shift_adj', 0), 0, -60, 60)
                    for i in range(len(st.session_state.doctors))
                }

                # GradeRules: 시트/새 key가 없으면 DEFAULT_GRADE_RULES로 채움
                st.session_state.grade_rules = grade_rules_from_df(df_grade_rules)
                normalize_grade_rules()
                # Excel 불러오기 후 GradeRules/개인 Grade number_input이 이전 값을 붙잡지 않도록 key version 갱신
                st.session_state["grade_rule_version"] = st.session_state.get("grade_rule_version", 0) + 1
                st.session_state["grade_version"] = st.session_state.get("grade_version", 0) + 1

                # 3) DutyRequests: D/E/N 컬럼 또는 첫 3개 컬럼을 읽고, 없으면 기본 1/1/1
                loaded_duty = {}
                if df_duty is not None and not df_duty.empty:
                    parsed_start = parse_start_date_from_duty_index(df_duty, st.session_state.start_date)
                    st.session_state.start_date = parsed_start
                    for i in range(len(df_duty)):
                        row = df_duty.iloc[i]
                        loaded_duty[i] = [
                            duty_value_from_row(row, 'D', 0),
                            duty_value_from_row(row, 'E', 1),
                            duty_value_from_row(row, 'N', 2),
                        ]
                else:
                    fallback_days = int(st.session_state.get("num_days", 31))
                    loaded_duty = {i: [1, 1, 1] for i in range(fallback_days)}

                st.session_state.duty_requests = loaded_duty
                st.session_state.num_days = len(loaded_duty)
                st.session_state.day_types = auto_day_types(st.session_state.start_date, st.session_state.num_days)
                st.session_state["duty_req_version"] = st.session_state.get("duty_req_version", 0) + 1

                # 4) ShiftRequests: 없으면 빈 요청으로 시작. FixedShiftRequests도 optional.
                name_to_doc_idx = {doc['name']: i for i, doc in enumerate(st.session_state.doctors)}

                def _grid_to_shift_dict(df_grid, hard_only=False):
                    out = {}
                    if df_grid is None or df_grid.empty:
                        return out
                    max_days = min(len(df_grid.columns), st.session_state.num_days)
                    for row_pos, (row_name, row) in enumerate(df_grid.iterrows()):
                        doc_name = str(row_name).strip()
                        if doc_name in name_to_doc_idx:
                            doc_idx = name_to_doc_idx[doc_name]
                        elif 0 <= row_pos < len(st.session_state.doctors):
                            # index 이름이 깨진 오래된 파일은 행 순서 기준으로 복원
                            doc_idx = row_pos
                        else:
                            continue
                        for day_idx in range(max_days):
                            val = _clean_shift_request_value(row.iloc[day_idx])
                            if not val:
                                continue
                            if hard_only and val not in HARD_SHIFT_VALUES:
                                continue
                            out[(doc_idx, day_idx)] = val
                    return out

                # ShiftRequests = user-entered base layer. FixedShiftRequests = result-grid lock overlay.
                st.session_state.base_shift_requests = _grid_to_shift_dict(df_shift, hard_only=False)
                st.session_state.fixed_shift_requests = _grid_to_shift_dict(df_fixed_shift, hard_only=True)
                st.session_state["shift_request_layers_initialized"] = True
                refresh_combined_shift_requests()
                st.session_state["shift_req_version"] = st.session_state.get("shift_req_version", 0) + 1

                st.toast("✅ 설정 적용 완료!", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"불러오기 실패: {e}")
                import traceback
                st.code(traceback.format_exc())

    st.divider()

    # Schedule generation button: two-step confirmation so users save forms first.
    st.caption("스케줄 생성은 각 탭에서 저장된 설정만 사용합니다.")
    if st.button("🚀 스케줄 생성", use_container_width=True, key="btn_solve"):
        st.session_state["trigger_solve"] = True
        st.rerun()

    i

    st.caption("by DS Choi 2026.03.19")


# ── MAIN AREA ────────────────────────────────────────────────────────────────
st.markdown('<div class="main-header"><h1>🏥 SHIFT SCHEDULER</h1><p>의료진 근무표 최적화 시스템 · OR-Tools CP-SAT, by DSCHOI </p></div>', unsafe_allow_html=True)

normalize_doctors()
normalize_grade_rules()
normalize_shift_request_layers()

doctors = st.session_state.doctors
num_days = st.session_state.num_days
start_date = st.session_state.start_date

render_readme_guide(expanded=(not bool(doctors)))

if not doctors:
    st.info("← 왼쪽 사이드바에서 의사를 추가해 주세요.")
    st.stop()

# Auto-fill day types
if not st.session_state.day_types or len(st.session_state.day_types) != num_days:
    st.session_state.day_types = auto_day_types(start_date, num_days)

if not st.session_state.duty_requests or len(st.session_state.duty_requests) != st.session_state.num_days:
    st.session_state.duty_requests = {i: [1, 1, 1] for i in range(st.session_state.num_days)}

st.info("각 탭의 변경사항은 저장 버튼을 눌러야 반영됩니다. 스케줄 생성 전에는 관련 탭을 저장했는지 확인하세요.")
tab1, tab2, tab3, tab4 = st.tabs(["📅 근무 요청 / 날짜 설정", "📋 Duty 설정", "⚙ 개인 규칙 / Grade", "📊 결과"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: Shift requests + Day types
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    st.markdown('<div class="section-label">날짜 유형 & 개인 근무 요청</div>', unsafe_allow_html=True)
    st.caption("셀을 클릭해서 날짜 유형과 의사별로 원하는/못하는 근무를 설정합니다.")

    with st.form("shift_requests_form", clear_on_submit=False):
        save_shift_requests = st.form_submit_button("저장", use_container_width=True)
        st.caption("여러 칸을 수정한 뒤 저장을 눌러야 실제 설정에 반영됩니다.")
        # Combined table: Day types + Per-doctor shift requests
        st.markdown("**날짜 유형 & 개인별 근무 요청** · `d/e/n` = 못하는 근무 | `D/E/N` = 원하는 근무 | `x` = 전체 불가 | `a` = 연차/off, 근무조정값 자동계산 버튼으로 반영 가능")
        st.caption("🔒 fixed 표시가 있는 칸은 결과표에서 고정된 셀이므로 여기서는 수정할 수 없습니다. 결과 탭에서 고정 해제 후 수정하세요.")
        SHIFT_OPTIONS = ['', 'd', 'e', 'n', 'x', 'a', 'de', 'dn', 'en', 'den', 'D', 'E', 'N']
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
                        ver = st.session_state.get("shift_req_version", 0)
                        key = f"sr_{ni}_{di}_v{ver}"
                        base_val = st.session_state.base_shift_requests.get((ni, di), '')
                        fixed_val = st.session_state.fixed_shift_requests.get((ni, di), '')
                        cur = fixed_val if fixed_val else base_val
                        options = SHIFT_OPTIONS
                        if cur and cur not in options:
                            options = [cur] + options
                        idx = options.index(cur) if cur in options else 0

                        if fixed_val:
                            base_label = base_val if base_val else "빈칸"
                            cols2[ci+1].markdown(
                                f"<div class='fixed-request-note'>🔒 fixed {fixed_val}<br><span>원래 입력: {base_label}</span></div>",
                                unsafe_allow_html=True,
                            )
                            cols2[ci+1].selectbox(
                                f"sr{ni}{di}", options,
                                index=idx,
                                label_visibility="collapsed", key=key,
                                disabled=True,
                                help="결과표에서 고정된 셀입니다. 수정하려면 결과 탭에서 먼저 고정 해제하세요.",
                            )
                        else:
                            new_val = cols2[ci+1].selectbox(
                                f"sr{ni}{di}", options,
                                index=idx,
                                label_visibility="collapsed", key=key
                            )
                            if new_val:
                                st.session_state.base_shift_requests[(ni, di)] = new_val
                            else:
                                st.session_state.base_shift_requests.pop((ni, di), None)
                        refresh_combined_shift_requests()
                    else:
                        cols2[ci+1].empty()  # Empty cell for missing days

            st.divider()



    if save_shift_requests:
        refresh_combined_shift_requests()
        st.session_state["shift_req_version"] = st.session_state.get("shift_req_version", 0) + 1
        st.toast("✅ 근무 요청 / 날짜 설정이 저장되었습니다.", icon="✅")
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: Duty requests (how many D/E/N per day)
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    with st.form("duty_settings_form", clear_on_submit=False):
        save_duty_settings = st.form_submit_button("저장", use_container_width=True)
        st.caption("Duty 숫자를 여러 칸 수정한 뒤 저장을 눌러야 실제 설정에 반영됩니다.")
        st.markdown('<div class="section-label">날짜별 필요 인원 설정</div>', unsafe_allow_html=True)
        st.caption("각 날짜마다 Day / Evening / Night 에 필요한 의사 수를 설정합니다.")
        st.caption("아래 요약에서 Duty 총합과 fixed_total 합을 먼저 확인하세요. 숫자가 맞지 않으면 solver가 해를 찾을 수 없습니다.")
        render_fixed_total_duty_summary(num_days)

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
                        duty_ver = st.session_state.get("duty_req_version", 0)
                        duty_key = f"duty_{di}_{shift_i}_v{duty_ver}"
                        new_val = cols2[ci+1].number_input(
                            f"duty_{di}_{shift_i}", min_value=0, max_value=len(doctors),
                            value=cur_val, label_visibility="collapsed",
                            key=duty_key,
                        )
                        if di not in st.session_state.duty_requests:
                            st.session_state.duty_requests[di] = [1,1,1]
                        st.session_state.duty_requests[di][shift_i] = int(new_val)
                    else:
                        cols2[ci+1].empty()

            st.divider()



    if save_duty_settings:
        st.session_state["duty_req_version"] = st.session_state.get("duty_req_version", 0) + 1
        st.toast("✅ Duty 설정이 저장되었습니다.", icon="✅")
        st.rerun()

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
    with st.form("grade_rule_settings_form", clear_on_submit=False):
        save_grade_rule_settings = st.form_submit_button("저장", use_container_width=True)
        st.caption("Grade 정책, 가중치, 개인별 Grade/규칙은 여러 항목을 수정한 뒤 저장을 눌러야 실제 설정에 반영됩니다.")
        st.markdown('<div class="section-label">Grade 정책 설정</div>', unsafe_allow_html=True)
        st.caption("Grade는 개인 속성이고, 고년차/저년차 기준과 objective 가중치는 전체 스케줄에 적용되는 전역 rule입니다.")

        gr = st.session_state.grade_rules
        gr_ver = st.session_state.get("grade_rule_version", 0)
        gcol1, gcol2, gcol3, gcol4, gcol5 = st.columns(5)
        gr["senior_min_grade"] = int(gcol1.number_input(
            "고년차 기준 grade ≥", min_value=GRADE_MIN_VALUE, max_value=GRADE_MAX_VALUE,
            value=bounded_int(gr.get("senior_min_grade", DEFAULT_GRADE_RULES["senior_min_grade"]), DEFAULT_GRADE_RULES["senior_min_grade"], GRADE_MIN_VALUE, GRADE_MAX_VALUE),
            key=f"grade_senior_min_grade_v{gr_ver}"
        ))
        gr["senior_min_count"] = int(gcol2.number_input(
            "Duty별 고년차 최소", min_value=0, max_value=10,
            value=bounded_int(gr.get("senior_min_count", DEFAULT_GRADE_RULES["senior_min_count"]), DEFAULT_GRADE_RULES["senior_min_count"], 0, 10),
            key=f"grade_senior_min_count_v{gr_ver}"
        ))
        gr["junior_max_grade"] = int(gcol3.number_input(
            "저년차 기준 grade ≤", min_value=GRADE_MIN_VALUE, max_value=GRADE_MAX_VALUE,
            value=bounded_int(gr.get("junior_max_grade", DEFAULT_GRADE_RULES["junior_max_grade"]), DEFAULT_GRADE_RULES["junior_max_grade"], GRADE_MIN_VALUE, GRADE_MAX_VALUE),
            key=f"grade_junior_max_grade_v{gr_ver}"
        ))
        gr["junior_soft_max_count"] = int(gcol4.number_input(
            "Duty별 저년차 권장 최대", min_value=0, max_value=10,
            value=bounded_int(gr.get("junior_soft_max_count", DEFAULT_GRADE_RULES["junior_soft_max_count"]), DEFAULT_GRADE_RULES["junior_soft_max_count"], 0, 10),
            key=f"grade_junior_soft_max_count_v{gr_ver}"
        ))
        gr["junior_penalty_weight"] = int(gcol5.number_input(
            "저년차 초과 penalty", min_value=0, max_value=100,
            value=bounded_int(gr.get("junior_penalty_weight", DEFAULT_GRADE_RULES["junior_penalty_weight"]), DEFAULT_GRADE_RULES["junior_penalty_weight"], 0, 100),
            key=f"grade_junior_penalty_weight_v{gr_ver}"
        ))

        st.caption("초저년차 hard rule도 Grade 정책 안에서 함께 설정합니다. 0이면 사용하지 않고, 1이면 한 duty에 초저년차 최대 1명까지만 허용합니다.")
        ucol1, ucol2, ucol3 = st.columns([1, 1, 3])
        gr["ultra_junior_max_grade"] = int(ucol1.number_input(
            "초저년차 기준 grade ≤", min_value=GRADE_MIN_VALUE, max_value=GRADE_MAX_VALUE,
            value=bounded_int(gr.get("ultra_junior_max_grade", DEFAULT_GRADE_RULES["ultra_junior_max_grade"]), DEFAULT_GRADE_RULES["ultra_junior_max_grade"], GRADE_MIN_VALUE, GRADE_MAX_VALUE),
            key=f"grade_ultra_junior_max_grade_v{gr_ver}"
        ))
        gr["ultra_junior_max_count"] = int(ucol2.number_input(
            "초저년차 최대 허용", min_value=0, max_value=10,
            value=bounded_int(gr.get("ultra_junior_max_count", DEFAULT_GRADE_RULES["ultra_junior_max_count"]), DEFAULT_GRADE_RULES["ultra_junior_max_count"], 0, 10),
            key=f"grade_ultra_junior_max_count_v{gr_ver}"
        ))
        if gr["ultra_junior_max_count"] > 0:
            ucol3.info(
                f"Hard: grade ≤ {gr['ultra_junior_max_grade']} 인원은 같은 날짜·같은 D/E/N duty에 "
                f"최대 {gr['ultra_junior_max_count']}명까지만 허용됩니다."
            )
        else:
            ucol3.caption("0이면 초저년차 동시근무 hard rule은 적용하지 않습니다.")

        st.markdown('<div class="section-label">편차 가중치 설정</div>', unsafe_allow_html=True)
        st.caption("Objective = D/E 편차×가중치 + 휴일 편차×가중치 + 총근무 편차×가중치 + N 편차×가중치 + Grade 편차×가중치 + 저년차 초과×가중치")
        wcol1, wcol2, wcol3, wcol4, wcol5 = st.columns(5)
        gr["weight_de_dev"] = int(wcol1.number_input(
            "D/E 편차 가중치", min_value=0, max_value=100,
            value=bounded_int(gr.get("weight_de_dev", DEFAULT_GRADE_RULES["weight_de_dev"]), DEFAULT_GRADE_RULES["weight_de_dev"], 0, 100),
            key=f"weight_de_dev_v{gr_ver}"
        ))
        gr["weight_holiday_dev"] = int(wcol2.number_input(
            "휴일 편차 가중치", min_value=0, max_value=100,
            value=bounded_int(gr.get("weight_holiday_dev", DEFAULT_GRADE_RULES["weight_holiday_dev"]), DEFAULT_GRADE_RULES["weight_holiday_dev"], 0, 100),
            key=f"weight_holiday_dev_v{gr_ver}"
        ))
        gr["weight_total_dev"] = int(wcol3.number_input(
            "총 근무 편차 가중치", min_value=0, max_value=100,
            value=bounded_int(gr.get("weight_total_dev", DEFAULT_GRADE_RULES["weight_total_dev"]), DEFAULT_GRADE_RULES["weight_total_dev"], 0, 100),
            key=f"weight_total_dev_v{gr_ver}"
        ))
        gr["weight_n_dev"] = int(wcol4.number_input(
            "N 편차 가중치", min_value=0, max_value=100,
            value=bounded_int(gr.get("weight_n_dev", DEFAULT_GRADE_RULES["weight_n_dev"]), DEFAULT_GRADE_RULES["weight_n_dev"], 0, 100),
            key=f"weight_n_dev_v{gr_ver}"
        ))
        gr["weight_grade_dev"] = int(wcol5.number_input(
            "Grade 편차 가중치", min_value=0, max_value=100,
            value=bounded_int(gr.get("weight_grade_dev", DEFAULT_GRADE_RULES.get("weight_grade_dev", 3)), DEFAULT_GRADE_RULES.get("weight_grade_dev", 3), 0, 100),
            key=f"weight_grade_dev_v{gr_ver}"
        ))
        st.session_state.grade_rules = gr
        st.markdown(
            f"<div style='font-size:0.82rem; color:var(--text-dim);'>"
            f"Hard: 각 duty마다 <b>grade ≥ {gr['senior_min_grade']}</b> 인원이 최소 <b>{gr['senior_min_count']}</b>명 필요합니다. "
            f"Soft: <b>grade ≤ {gr['junior_max_grade']}</b> 인원이 duty별 <b>{gr['junior_soft_max_count']}</b>명을 초과하면 "
            f"초과 1건당 <b>{gr['junior_penalty_weight']}</b>점 penalty를 줍니다. "
            f"Ultra-hard: <b>grade ≤ {gr.get('ultra_junior_max_grade', 1)}</b> 인원은 duty별 "
            f"최대 <b>{gr.get('ultra_junior_max_count', 0)}</b>명까지 허용합니다(0=사용안함)."
            f"</div>",
            unsafe_allow_html=True
        )


        st.divider()
        st.markdown('<div class="section-label">개인별 Grade & 근무 규칙 설정</div>', unsafe_allow_html=True)
        st.caption("7명씩 나눠서 표시됩니다. Grade와 개인 rule을 입력하세요. 근무 조정값과 fixed count는 위 표에서 수정합니다.")

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
                grade_ver = st.session_state.get("grade_version", 0)
                cur_grade = bounded_int(doctors[ni].get("grade", DEFAULT_DOCTOR_GRADE), DEFAULT_DOCTOR_GRADE, GRADE_MIN_VALUE, GRADE_MAX_VALUE)
                new_grade = grade_cols[ci+1].number_input(
                    f"grade_{ni}", min_value=GRADE_MIN_VALUE, max_value=GRADE_MAX_VALUE,
                    value=cur_grade, label_visibility="collapsed", key=f"doc_grade_{ni}_v{grade_ver}"
                )
                doctors[ni]["grade"] = int(new_grade)

            # 근무 조정값과 fixed Total/D/E/N counts are edited in the table above.

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



    if save_grade_rule_settings:
        st.session_state["grade_rule_version"] = st.session_state.get("grade_rule_version", 0) + 1
        st.session_state["grade_version"] = st.session_state.get("grade_version", 0) + 1
        st.toast("✅ 개인 규칙 / Grade 설정이 저장되었습니다.", icon="✅")
        st.rerun()

    st.divider()
    st.markdown('<div class="section-label">근무 조정값 & fixed D/E/N/Total / Duty 총합 확인</div>', unsafe_allow_html=True)
    st.caption("근무 조정값과 fixed_D/E/N/Total은 아래 표에서 한 번에 수정한 뒤 저장합니다. Duty 필요 인원과 fixed_Total 요약도 여기서 확인합니다.")
    render_fixed_total_duty_summary(num_days)
    render_fixed_total_editor_table()

# ─────────────────────────────────────────────────────────────────────────────
# SOLVER (triggered from sidebar button)
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.get("trigger_solve"):
    st.session_state["trigger_solve"] = False

    # New solve attempt: clear previous diagnostic state.
    st.session_state["diagnostic_results"] = None
    st.session_state["solve_failed"] = False
    st.session_state["solve_failure_message"] = ""

    if not doctors:
        st.error("의사를 먼저 추가해 주세요.")
    else:
        # Make sure the editable fixed count table and duty inputs are reflected
        # before pre-checks and solver parameters are built. This prevents a
        # recently edited fixed_D/E/N/Total value from being missed when the user
        # immediately clicks "스케줄 생성".
        sync_live_total_summary_inputs(num_days)
        fixed_total_info = get_fixed_total_summary()
        precheck_error = ""
        if fixed_total_info["fixed_count"] > 0 and fixed_total_info["remaining"] < 0:
            precheck_error = (
                f"fixed_total 합이 Duty 총합보다 {-fixed_total_info['remaining']}개 많습니다. "
                f"Duty 설정에서 총 근무를 {-fixed_total_info['remaining']}개 추가하거나 fixed_total을 줄여주세요."
            )
        elif fixed_total_info["fixed_count"] > 0 and fixed_total_info["free_count"] == 0 and fixed_total_info["remaining"] != 0:
            precheck_error = (
                f"모든 의사의 fixed_total이 지정되어 있는데 Duty 총합과 {fixed_total_info['remaining']}개 차이가 납니다. "
                "Duty 설정 또는 fixed_total을 맞춰주세요."
            )

        if precheck_error:
            st.session_state.solved = False
            st.session_state.solutions = []
            st.session_state.summaries = []
            st.session_state.metrics = []
            st.session_state["solve_failed"] = True
            st.session_state["solve_failure_message"] = precheck_error
            st.error(precheck_error)
            st.info("📋 Duty 설정 또는 개인 규칙 / Grade 탭의 fixed_total 요약을 확인하세요. 결과 탭에서 진단모드를 실행할 수도 있습니다.")
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
                        "shift_requests": {f"{k[0]},{k[1]}": v for k, v in refresh_combined_shift_requests().items()},
                        "rules": {str(k): v for k, v in st.session_state.rules.items()},
                        "shift_adj": {str(k): v for k, v in st.session_state.shift_adj.items()},
                        "shift_counts": {str(k): v for k, v in st.session_state.shift_counts.items()},
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
                    st.session_state["solve_failed"] = False
                    st.session_state["solve_failure_message"] = ""
                    st.session_state["diagnostic_results"] = None
                    st.session_state.pop("prepared_excel_export", None)
                    st.toast(f"✅ {len(solutions)}개의 솔루션을 찾았습니다!", icon="✅")
                except RuntimeError as e:
                    msg = str(e)
                    st.session_state.solved = False
                    st.session_state.solutions = []
                    st.session_state.summaries = []
                    st.session_state.metrics = []
                    st.session_state["solve_failed"] = True
                    st.session_state["solve_failure_message"] = msg
                    st.toast(f"❌ 조건을 만족하는 해가 없습니다: {msg}", icon="❌")
                except Exception as e:
                    st.session_state.solved = False
                    st.session_state.solutions = []
                    st.session_state.summaries = []
                    st.session_state.metrics = []
                    st.session_state["solve_failed"] = True
                    st.session_state["solve_failure_message"] = str(e)
                    st.toast(f"❌ 오류 발생: {e}", icon="❌")
                    import traceback
                    st.code(traceback.format_exc())



# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: Results
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    if not st.session_state.solved or not st.session_state.solutions:
        if st.session_state.get("solve_failed"):
            st.error("조건을 만족하는 스케줄을 찾지 못했습니다.")
            if st.session_state.get("solve_failure_message"):
                st.caption(st.session_state.get("solve_failure_message"))
            st.info("진단모드는 자동으로 실행하지 않습니다. 아래 버튼을 누르면 1차/2차 hard-rule 병목 후보만 계산합니다.")
            if st.button("🧪 진단모드 실행", key="btn_run_diagnostics"):
                sync_live_total_summary_inputs(num_days)
                st.session_state["diagnostic_results"] = run_hard_bottleneck_diagnostics()
                st.rerun()
            if st.session_state.get("diagnostic_results") is not None:
                render_hard_bottleneck_diagnostics(st.session_state.get("diagnostic_results"))
        else:
            st.info("← 사이드바에서 **🚀 스케줄 생성** 버튼을 눌러 최적화를 실행하세요.")
    else:
        solutions = st.session_state.solutions
        summaries = st.session_state.summaries
        metrics = st.session_state.metrics
        sol_idx = st.session_state.sol_idx
        total = len(solutions)

        sol = solutions[sol_idx]
        summary = summaries[sol_idx]

        # 화면/Excel 표시 순서: 의사 입력 순서 그대로 유지
        # Grade는 표시하되, Grade 값으로 재정렬하지 않는다.
        # 즉 근무 요청/날짜 설정 탭에서 보이는 의사 순서와 결과표/Excel 순서가 동일하다.
        display_order = list(range(len(doctors)))
        name_to_grade = {doc["name"]: int(doc.get("grade", DEFAULT_DOCTOR_GRADE)) for doc in doctors}
        name_to_display_order = {doctors[ni]["name"]: order for order, ni in enumerate(display_order)}

        summary_display = summary.copy()
        if "Grade" not in summary_display.columns:
            summary_display.insert(1, "Grade", summary_display["Name"].map(name_to_grade).fillna(DEFAULT_DOCTOR_GRADE).astype(int))
        # Summary도 Name 정렬이 아니라 근무 요청/날짜 설정 탭의 입력 순서 그대로 표시한다.
        # 맨 왼쪽 No는 사용자가 입력/Excel에서 보는 의사 순서(1-based index)이다.
        summary_display["_display_order"] = summary_display["Name"].map(name_to_display_order).fillna(9999).astype(int)
        summary_display = (
            summary_display
            .sort_values(["_display_order"], ascending=[True], kind="stable")
            .drop(columns=["_display_order"])
        )
        if "No" in summary_display.columns:
            summary_display = summary_display.drop(columns=["No"])
        summary_display.insert(
            0,
            "No",
            summary_display["Name"].map(lambda nm: name_to_display_order.get(nm, -1) + 1 if nm in name_to_display_order else "")
        )
        # Tue_N은 더 이상 표시하지 않고, 연차는 Total 바로 옆에 둔다.
        if "Tue_N" in summary_display.columns:
            summary_display = summary_display.drop(columns=["Tue_N"])

        # 연차는 solver summary에 이미 들어오더라도, 표시/export 단계에서 다시 계산해 보강한다.
        # 이렇게 하면 이전 solved session이나 legacy summary에도 항상 연차 컬럼이 보인다.
        annual_counts = get_annual_leave_counts_by_doc()
        name_to_annual = {doctors[ni]["name"]: int(annual_counts.get(ni, 0)) for ni in range(len(doctors))}
        annual_col = summary_display["Name"].map(name_to_annual).fillna(0).astype(int)
        if "연차" in summary_display.columns:
            summary_display = summary_display.drop(columns=["연차"])
        if "Total+연차" in summary_display.columns:
            summary_display = summary_display.drop(columns=["Total+연차"])
        insert_at = list(summary_display.columns).index("Total") + 1 if "Total" in summary_display.columns else min(6, len(summary_display.columns))
        summary_display.insert(insert_at, "연차", annual_col)
        if "Total" in summary_display.columns:
            total_numeric = pd.to_numeric(summary_display["Total"], errors="coerce").fillna(0).astype(int)
            summary_display.insert(insert_at + 1, "Total+연차", total_numeric + annual_col)

        # Excel export는 화면 이동 때마다 만들지 않고, 아래의 "Excel 준비" 버튼을 눌렀을 때만 생성합니다.

        # Summary stats
        st.markdown('<div class="section-label">근무 통계</div>', unsafe_allow_html=True)
        st.caption("No는 근무 요청/날짜 설정 탭 및 Excel 입력 순서 기준입니다. 연차와 Total+연차는 현재 근무 요청의 a 개수 기준입니다.")
        try:
            gradient_subsets = [col for col in ['Total', 'Total+연차'] if col in summary_display.columns]
            styled_summary = summary_display.style
            if gradient_subsets:
                styled_summary = styled_summary.background_gradient(subset=gradient_subsets, cmap='Blues')
            if 'N' in summary_display.columns:
                styled_summary = styled_summary.background_gradient(subset=['N'], cmap='Purples')
            if 'Holiday' in summary_display.columns:
                styled_summary = styled_summary.background_gradient(subset=['Holiday'], cmap='Oranges')
            st.dataframe(
                styled_summary,
                use_container_width=True, hide_index=True
            )
        except ImportError:
            st.dataframe(summary_display, use_container_width=True, hide_index=True)

        # 편차 정보 (k (DE), k1 (holiday), k2 (N), k3 (total), k4 (grade))
        if metrics and sol_idx < len(metrics):
            m = metrics[sol_idx]
            def _side_metric(label, total_key, low_key, high_key, weight_key, default_weight):
                low = m.get(low_key)
                high = m.get(high_key)
                total = m.get(total_key)
                weight = m.get(weight_key, gr.get(weight_key, default_weight))
                if low is None or high is None:
                    return f"| **{label}:** {total}×{weight} "
                return f"| **{label}:** ↓{low}+↑{high}={total}×{weight} "

            st.markdown(
                f"<div style='font-size:0.85rem; color:var(--text-dim);'>"
                f"** 편차*가중치 합={m.get('adv')} "
                f"| **최적 편차:** {m.get('best_adv', m.get('adv'))} "
                f"| **허용 상한:** {m.get('allowed_adv', m.get('adv'))} "
                f"| **balance penalty:** {m.get('balance_penalty', 'NA')} "
                f"{_side_metric('k D/E', 'k', 'k_low', 'k_high', 'weight_de_dev', 1)}"
                f"{_side_metric('k1 휴일', 'k1', 'k1_low', 'k1_high', 'weight_holiday_dev', 3)}"
                f"{_side_metric('k2 총근무', 'k2', 'k2_low', 'k2_high', 'weight_total_dev', 5)}"
                f"{_side_metric('k3 N', 'k3', 'k3_low', 'k3_high', 'weight_n_dev', 5)}"
                f"| **k4 Grade편차:** {m.get('k4', 0)} (실제±{round(m.get('k4',0)/10,1)})×{m.get('weight_grade_dev', gr.get('weight_grade_dev', 3))} "
                f"| **저년차 초과:** {m.get('junior_excess', 0)}×{m.get('junior_penalty_weight', gr.get('junior_penalty_weight', 1))} "
                f"= **{m.get('junior_penalty', 0)}** "
                f"| **초저년차 hard:** grade≤{m.get('ultra_junior_max_grade', gr.get('ultra_junior_max_grade', 1))}, "
                f"최대 {m.get('ultra_junior_max_count', gr.get('ultra_junior_max_count', 0))}명 허용</div>",
                unsafe_allow_html=True
            )

        st.divider()

        # ── 통합 근무표: 표시 + 셀 선택/고정 ────────────────────────────────
        st.markdown('<div class="section-label">근무 일정표 / 셀 선택 & 고정</div>', unsafe_allow_html=True)
        st.caption(
            "근무 요청/날짜 설정 탭의 의사 입력 순서 그대로 표시합니다. Grade는 이름 옆에 G값으로 표시하지만 Grade순 정렬은 하지 않습니다. "
            "셀을 클릭(또는 드래그)해 선택한 뒤 **선택 셀 고정**을 누르면 현재 결과값이 hard request로 고정됩니다. "
            "🔒 표시는 이미 base request 또는 fixed layer로 하드코딩된 셀입니다. "
            "날짜는 `일자+요일` 형식이며, `*`는 평일 공휴일입니다. 표 높이는 인원 수에 맞춰 자동으로 늘어납니다."
        )

        holiday_days = [d for d, t in st.session_state.day_types.items() if t in ('토','일','공')]
        combined_req = refresh_combined_shift_requests()

        # Compact date columns for 30-day / 20-30-person view.
        # Keep labels very short: 2목, 3금, 4토. Weekday public holidays get *: 6월*.
        # Cell shading still applies to all holiday-type days: 토/일/공.
        date_cols = []
        holiday_cols = []
        public_holiday_cols = []
        for di in range(num_days):
            d = start_date + timedelta(days=di)
            lbl = get_day_label(start_date, di)
            dtype = st.session_state.day_types.get(di, '평일')
            is_weekday_public_holiday = (dtype == '공' and lbl not in ('토', '일'))
            col_label = f"{d.day}{lbl}{'*' if is_weekday_public_holiday else ''}"
            date_cols.append(col_label)
            if dtype in ('토', '일', '공'):
                holiday_cols.append(col_label)
            if is_weekday_public_holiday:
                public_holiday_cols.append(col_label)

        editor_row_order = []  # [(doctor_idx, row_label)]
        editor_rows = {}
        for ni in display_order:
            doc = doctors[ni]
            grade_val = int(doc.get("grade", DEFAULT_DOCTOR_GRADE))
            # Grade는 표시만 하고, 정렬 기준으로 사용하지 않는다.
            # 행 순서는 근무 요청/날짜 설정 탭의 의사 입력 순서와 동일하다.
            row_label = f"{doc['name']} [G{grade_val}]"
            editor_row_order.append((ni, row_label))
            editor_rows[row_label] = []
            for di in range(num_days):
                raw_val = sol.get((ni, di), '')
                display_val = raw_val.upper() if raw_val else '·'
                req = combined_req.get((ni, di), '')
                if _clean_shift_request_value(req).lower() == 'a':
                    display_val = 'A'
                if is_hard_shift_request_value(req):
                    display_val = f"🔒{display_val}"
                editor_rows[row_label].append(display_val)

        editor_df = pd.DataFrame(editor_rows, index=date_cols).T

        def _style_compact_schedule(df):
            styles = pd.DataFrame('', index=df.index, columns=df.columns)
            base = (
                'font-size: 10px; line-height: 1.0; padding: 0px 1px; '
                'text-align: center; white-space: nowrap; min-width: 22px; max-width: 28px;'
            )
            styles.loc[:, :] = base
            for col in holiday_cols:
                if col in styles.columns:
                    styles[col] = base + ' background-color: rgba(240, 160, 64, 0.16);'
            return styles

        editor_view = (
            editor_df.style
            .apply(_style_compact_schedule, axis=None)
            .set_table_styles([
                {'selector': 'th', 'props': [
                    ('font-size', '9px'), ('line-height', '1.0'), ('padding', '0px 1px'),
                    ('text-align', 'center'), ('white-space', 'nowrap')
                ]},
                {'selector': 'td', 'props': [
                    ('font-size', '10px'), ('line-height', '1.0'), ('padding', '0px 1px'),
                    ('text-align', 'center'), ('white-space', 'nowrap')
                ]},
            ])
        )

        compact_column_config = {
            col: st.column_config.TextColumn(col, width=34)
            for col in date_cols
        }
        # Make the selectable schedule grid tall enough to avoid an inner vertical scrollbar.
        # st.dataframe keeps a relatively fixed row height internally, so pandas CSS cannot
        # reliably shrink rows. Instead, calculate the widget height from the number of
        # displayed doctors. This keeps roughly 20-30 doctors visible at once.
        compact_row_height = 35
        compact_header_height = 42
        compact_height = min(1280, max(420, compact_header_height + compact_row_height * (len(editor_df.index) + 1)))

        event = st.dataframe(
            editor_view,
            use_container_width=True,
            height=compact_height,
            column_config=compact_column_config,
            on_select="rerun",
            selection_mode="multi-cell",
            key=f"schedule_selector_{sol_idx}",
        )

        selected_cells = event.selection.get("cells", [])
        if selected_cells:
            st.caption(f"선택된 셀: {len(selected_cells)}개 → 고정/해제 버튼을 사용할 수 있습니다.")

        def _selected_to_positions(selected_cells):
            """Convert Streamlit dataframe selection payload to (doctor_idx, day_idx) pairs."""
            positions = []
            row_label_map = {lbl: i for i, (_, lbl) in enumerate(editor_row_order)}
            for cell in selected_cells:
                # Streamlit 버전에 따라 형식이 다름:
                # - dict: {"row": r, "column": c}
                # - tuple/list: (row_idx, col_idx) 또는 (row_label, date_col)
                if isinstance(cell, dict):
                    row_idx = cell.get("row", -1)
                    col_idx = cell.get("column", -1)
                elif isinstance(cell, (tuple, list)) and len(cell) >= 2:
                    r, c = cell[0], cell[1]
                    row_idx = r if isinstance(r, int) else row_label_map.get(str(r), -1)
                    col_idx = c if isinstance(c, int) else (date_cols.index(str(c)) if str(c) in date_cols else -1)
                else:
                    continue

                if row_idx < 0 or col_idx < 0 or row_idx >= len(editor_row_order) or col_idx >= num_days:
                    continue
                ni, _ = editor_row_order[row_idx]
                positions.append((ni, col_idx))
            return positions

        pending_locks = dict(st.session_state.get("pending_result_fixed_locks", {}))
        pending_releases = set(st.session_state.get("pending_result_fixed_releases", set()))
        pending_count = len(pending_locks) + len(pending_releases)
        if pending_count:
            st.info(f"결과 고정 변경 예정: {pending_count}개. 저장을 눌러야 근무 요청/fixed layer에 반영됩니다.")

        lock_col1, lock_col2, lock_col3, lock_col4 = st.columns([1, 1, 1, 3])
        if lock_col1.button("🔒 고정 예정", key="btn_lock_apply"):
            positions = _selected_to_positions(selected_cells)
            if not positions:
                st.warning("선택된 셀이 없어요. 고정할 셀을 먼저 클릭해서 선택해주세요.")
            else:
                for ni, di in positions:
                    current_req = _clean_shift_request_value(combined_req.get((ni, di), ''))
                    if current_req.lower() == 'a':
                        pending_locks[(ni, di)] = 'a'
                    else:
                        val = sol.get((ni, di), '')
                        pending_locks[(ni, di)] = val.upper() if val else 'x'
                    pending_releases.discard((ni, di))
                st.session_state["pending_result_fixed_locks"] = pending_locks
                st.session_state["pending_result_fixed_releases"] = pending_releases
                st.toast(f"🔒 {len(positions)}개 셀을 고정 예정으로 표시했습니다. 저장을 눌러 반영하세요.", icon="🔒")
                st.rerun()

        if lock_col2.button("🔓 해제 예정", key="btn_lock_release"):
            positions = _selected_to_positions(selected_cells)
            if not positions:
                st.warning("선택된 셀이 없어요. 해제할 셀을 먼저 클릭해서 선택해주세요.")
            else:
                changed = 0
                for ni, di in positions:
                    if (ni, di) in pending_locks:
                        pending_locks.pop((ni, di), None)
                        changed += 1
                    elif (ni, di) in st.session_state.fixed_shift_requests:
                        pending_releases.add((ni, di))
                        changed += 1
                st.session_state["pending_result_fixed_locks"] = pending_locks
                st.session_state["pending_result_fixed_releases"] = pending_releases
                if changed:
                    st.toast(f"🔓 {changed}개 셀을 해제 예정으로 표시했습니다. 저장을 눌러 반영하세요.", icon="🔓")
                else:
                    st.toast("선택한 셀에는 저장된 fixed layer가 없어요.", icon="ℹ️")
                st.rerun()

        if lock_col3.button("저장", key="btn_result_fixed_save"):
            new_fixed_req = dict(st.session_state.fixed_shift_requests)
            for pos in pending_releases:
                new_fixed_req.pop(pos, None)
            for pos, val in pending_locks.items():
                new_fixed_req[pos] = val
            st.session_state.fixed_shift_requests = new_fixed_req
            combined_req = refresh_combined_shift_requests()

            # 모든 날이 hard-coded 된 의사는 shift_counts 자동 계산
            new_shift_counts = dict(st.session_state.shift_counts)
            for ni, row_label in editor_row_order:
                total_fixed = sum(
                    1 for di in range(num_days)
                    if combined_req.get((ni, di), '') in ('D', 'E', 'N', 'x', 'a')
                )
                if total_fixed == num_days:
                    d_cnt = sum(1 for di in range(num_days) if combined_req.get((ni, di), '') == 'D')
                    e_cnt = sum(1 for di in range(num_days) if combined_req.get((ni, di), '') == 'E')
                    n_cnt = sum(1 for di in range(num_days) if combined_req.get((ni, di), '') == 'N')
                    new_shift_counts[ni] = {"D": d_cnt, "E": e_cnt, "N": n_cnt, "Total": d_cnt + e_cnt + n_cnt}
            st.session_state.shift_counts = new_shift_counts
            st.session_state["pending_result_fixed_locks"] = {}
            st.session_state["pending_result_fixed_releases"] = set()
            st.session_state["shift_req_version"] = st.session_state.get("shift_req_version", 0) + 1
            st.toast("✅ 결과 고정 변경사항이 저장되었습니다.", icon="✅")
            st.rerun()

        lock_col4.caption(
            "결과표 고정/해제는 먼저 예정으로 표시한 뒤 저장을 눌러야 fixed layer에 반영됩니다. "
            "해제하면 기존 사용자 입력값(d/en/빈칸 등)이 다시 적용됩니다."
        )

        # ── 날짜별 duty 구성 요약 ─────────────────────────────────────────────
        st.markdown('<div class="section-label">Daily duty 구성 요약</div>', unsafe_allow_html=True)
        st.caption("각 날짜·D/E/N별 실제 배정 인원, 필요 인원, 평균 grade, 근무자를 확인합니다.")

        duty_summary_rows = []
        shift_labels = [('D', 'Day'), ('E', 'Evening'), ('N', 'Night')]
        for di in range(num_days):
            d = start_date + timedelta(days=di)
            lbl = get_day_label(start_date, di)
            dtype = st.session_state.day_types.get(di, '평일')
            is_weekday_public_holiday = (dtype == '공' and lbl not in ('토', '일'))
            date_label = f"{d.strftime('%m/%d')} ({lbl}{'·휴' if is_weekday_public_holiday else ''})"
            is_holiday_type = dtype in ('토', '일', '공')
            for si, (shift_key, shift_name) in enumerate(shift_labels):
                staff = [ni for ni in range(len(doctors)) if sol.get((ni, di), '') == shift_key.lower()]
                grades_for_shift = [int(doctors[ni].get('grade', DEFAULT_DOCTOR_GRADE)) for ni in staff]
                avg_grade = round(sum(grades_for_shift) / len(grades_for_shift), 2) if grades_for_shift else None
                required = st.session_state.duty_requests.get(di, [0, 0, 0])[si]
                staff_with_grade = ", ".join(
                    f"{doctors[ni]['name']} [{int(doctors[ni].get('grade', DEFAULT_DOCTOR_GRADE))}]"
                    for ni in staff
                )
                duty_summary_rows.append({
                    "날짜": date_label,
                    "유형": dtype,
                    "Duty": shift_key,
                    "인원/필요": f"{len(staff)}/{required}",
                    "평균 Grade": avg_grade if avg_grade is not None else "-",
                    "근무자": staff_with_grade,
                    "_is_holiday": is_holiday_type,
                })

        duty_summary_df = pd.DataFrame(duty_summary_rows)
        if not duty_summary_df.empty:
            holiday_row_flags = duty_summary_df['_is_holiday'].tolist() if '_is_holiday' in duty_summary_df.columns else []
            display_duty_summary_df = duty_summary_df.drop(columns=['_is_holiday'], errors='ignore')
            def _style_duty_summary(row):
                if row.name < len(holiday_row_flags) and bool(holiday_row_flags[row.name]):
                    return ['background-color: rgba(240, 160, 64, 0.12);'] * len(row)
                return [''] * len(row)
            st.dataframe(display_duty_summary_df.style.apply(_style_duty_summary, axis=1), use_container_width=True, hide_index=True)
        else:
            st.dataframe(duty_summary_df, use_container_width=True, hide_index=True)

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
        leg_cols[4].markdown('<span style="font-family:var(--mono);font-size:0.75rem;color:#f0a040">음영 = 토/일/공 휴일</span>', unsafe_allow_html=True)