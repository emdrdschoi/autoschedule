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
    "weight_grade_dev": 3,       # objective weight for grade imbalance per duty
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
    fixed_total_info = get_fixed_total_summary()
    d_total = sum(st.session_state.duty_requests.get(di, [0, 0, 0])[0] for di in range(num_days))
    e_total = sum(st.session_state.duty_requests.get(di, [0, 0, 0])[1] for di in range(num_days))
    n_total = sum(st.session_state.duty_requests.get(di, [0, 0, 0])[2] for di in range(num_days))
    remaining = fixed_total_info["remaining"]
    st.markdown(
        f"""
        <div style='font-family:var(--mono);font-size:0.78rem;line-height:1.45;
                    padding:0.55rem 0.7rem;border:1px solid var(--border);border-radius:4px;
                    background:var(--surface);margin:0.7rem 0;'>
        Duty 총합: <b>{fixed_total_info['total_duty']}</b>
        <span style='color:var(--text-dim)'>(D {d_total} / E {e_total} / N {n_total})</span>
        &nbsp;|&nbsp; fixed_total 합: <b>{fixed_total_info['fixed_sum']}</b>
        &nbsp;|&nbsp; fixed_total 미지정 인원: <b>{fixed_total_info['free_count']}</b>
        &nbsp;|&nbsp; 남은 근무수: <b style='color:{'#e05c5c' if remaining < 0 else '#54c78a'}'>{remaining}</b>
        </div>
        """,
        unsafe_allow_html=True
    )
    if fixed_total_info["fixed_count"] > 0:
        if remaining < 0:
            st.error(f"fixed_total 합이 Duty 총합보다 {-remaining}개 많습니다. Duty 설정에서 총 근무를 {-remaining}개 추가하거나 fixed_total을 줄여야 합니다.")
        elif fixed_total_info["free_count"] == 0 and remaining != 0:
            st.error(f"모든 의사의 fixed_total이 지정되어 있는데 Duty 총합과 {remaining}개 차이가 납니다. Duty 설정 또는 fixed_total을 맞춰주세요.")
        elif fixed_total_info["free_count"] > 0:
            st.info(f"fixed_total이 없는 {fixed_total_info['free_count']}명에게 남은 근무수 {remaining}개가 자동 배분됩니다.")

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


HARD_SHIFT_VALUES = {"D", "E", "N", "x"}

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
            row["fixed_D"] = sc.get("D", -1)
            row["fixed_E"] = sc.get("E", -1)
            row["fixed_N"] = sc.get("N", -1)
            row["fixed_Total"] = sc.get("Total", -1)
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
                df_doctors = pd.read_excel(xls, sheet_name='Doctors')
                df_rules = pd.read_excel(xls, sheet_name='Rules', index_col=0)
                df_duty = pd.read_excel(xls, sheet_name='DutyRequests', index_col=0)
                df_shift = pd.read_excel(xls, sheet_name='ShiftRequests', index_col=0)
                df_fixed_shift = pd.read_excel(xls, sheet_name='FixedShiftRequests', index_col=0) if 'FixedShiftRequests' in xls.sheet_names else pd.DataFrame()
                df_grade_rules = pd.read_excel(xls, sheet_name='GradeRules') if 'GradeRules' in xls.sheet_names else pd.DataFrame()

                # 1) 의사 정보: grade 포함해서 읽기 (없으면 기본값)
                new_doctors = []
                for _, row in df_doctors.iterrows():
                    name = str(row.get('name', '')).strip()
                    if not name:
                        continue
                    grade = int(row['grade']) if 'grade' in row and pd.notna(row.get('grade')) else DEFAULT_DOCTOR_GRADE
                    adj = int(row['shift_adj']) if 'shift_adj' in row and pd.notna(row.get('shift_adj')) else 0
                    new_doctors.append({"name": name, "shift_adj": adj, "grade": grade})
                st.session_state.doctors = new_doctors

                # 2) Rules + shift_counts
                new_rules = {}
                new_shift_counts = {}
                for i in range(len(df_rules)):
                    row = df_rules.iloc[i]
                    new_rules[i] = {key: int(row[key]) if key in row.index and pd.notna(row[key]) else DEFAULT_RULES.get(key, 0)
                                    for key in RULE_COL_ORDER}
                    new_shift_counts[i] = {
                        "D": int(row["fixed_D"]) if "fixed_D" in row.index and pd.notna(row["fixed_D"]) else -1,
                        "E": int(row["fixed_E"]) if "fixed_E" in row.index and pd.notna(row["fixed_E"]) else -1,
                        "N": int(row["fixed_N"]) if "fixed_N" in row.index and pd.notna(row["fixed_N"]) else -1,
                        "Total": int(row["fixed_Total"]) if "fixed_Total" in row.index and pd.notna(row["fixed_Total"]) else -1,
                    }
                st.session_state.rules = new_rules
                st.session_state.shift_counts = new_shift_counts
                normalize_shift_counts()

                # shift_adj도 Doctors 시트에서 복원
                st.session_state.shift_adj = {
                    i: int(st.session_state.doctors[i].get('shift_adj', 0))
                    for i in range(len(st.session_state.doctors))
                }

                # GradeRules
                st.session_state.grade_rules = grade_rules_from_df(df_grade_rules)
                normalize_grade_rules()

                # 3) DutyRequests
                loaded_duty = {i: [int(df_duty.iloc[i]['D']), int(df_duty.iloc[i]['E']), int(df_duty.iloc[i]['N'])]
                               for i in range(len(df_duty))}
                st.session_state.duty_requests = loaded_duty
                st.session_state.num_days = len(loaded_duty)
                st.session_state.day_types = auto_day_types(st.session_state.start_date, st.session_state.num_days)
                st.session_state["duty_req_version"] = st.session_state.get("duty_req_version", 0) + 1

                # 4) ShiftRequests
                name_to_doc_idx = {doc['name']: i for i, doc in enumerate(st.session_state.doctors)}

                def _grid_to_shift_dict(df_grid, hard_only=False):
                    out = {}
                    if df_grid is None or df_grid.empty:
                        return out
                    max_days = min(len(df_grid.columns), st.session_state.num_days)
                    for row_name, row in df_grid.iterrows():
                        doc_name = str(row_name).strip()
                        if doc_name not in name_to_doc_idx:
                            continue
                        doc_idx = name_to_doc_idx[doc_name]
                        for day_idx in range(max_days):
                            val = _clean_shift_request_value(row.iloc[day_idx])
                            if not val:
                                continue
                            if hard_only and val not in HARD_SHIFT_VALUES:
                                continue
                            out[(doc_idx, day_idx)] = val
                    return out

                # ShiftRequests = user-entered base layer.
                # FixedShiftRequests = result-grid lock overlay.
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

    # Schedule generation button
    if st.button("🚀 스케줄 생성", use_container_width=True, key="btn_solve"):
        st.session_state["trigger_solve"] = True
        st.rerun()

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

tab1, tab2, tab3, tab4 = st.tabs(["📅 근무 요청 / 날짜 설정", "📋 Duty 설정", "⚙ 개인 규칙 / Grade", "📊 결과"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: Shift requests + Day types
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    st.markdown('<div class="section-label">날짜 유형 & 개인 근무 요청</div>', unsafe_allow_html=True)
    st.caption("셀을 클릭해서 날짜 유형과 의사별로 원하는/못하는 근무를 설정합니다.")

    # Combined table: Day types + Per-doctor shift requests
    st.markdown("**날짜 유형 & 개인별 근무 요청** · `d/e/n` = 못하는 근무 | `D/E/N` = 원하는 근무 | `x` = 전체 불가")
    st.caption("🔒 fixed 표시가 있는 칸은 결과표에서 고정된 셀이므로 여기서는 수정할 수 없습니다. 결과 탭에서 고정 해제 후 수정하세요.")
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
                    duty_ver = st.session_state.get("duty_req_version", 0)
                    new_val = cols2[ci+1].number_input(
                        f"duty_{di}_{shift_i}", min_value=0, max_value=len(doctors),
                        value=cur_val, label_visibility="collapsed",
                        key=f"duty_{di}_{shift_i}_v{duty_ver}"
                    )
                    if di not in st.session_state.duty_requests:
                        st.session_state.duty_requests[di] = [1,1,1]
                    st.session_state.duty_requests[di][shift_i] = int(new_val)
                else:
                    cols2[ci+1].empty()

        st.divider()

    render_fixed_total_duty_summary(num_days)


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
    st.caption("Objective = D/E 편차×가중치 + 휴일 편차×가중치 + 총근무 편차×가중치 + N 편차×가중치 + Grade 편차×가중치 + 저년차 초과×가중치")
    wcol1, wcol2, wcol3, wcol4, wcol5 = st.columns(5)
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
    gr["weight_grade_dev"] = int(wcol5.number_input(
        "Grade 편차 가중치", min_value=0, max_value=100,
        value=int(gr.get("weight_grade_dev", DEFAULT_GRADE_RULES.get("weight_grade_dev", 3))),
        key="weight_grade_dev"
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

        # Total/D/E/N 고정 개수 (-1 = 평준화)
        st.markdown(
            "<span style='font-family:var(--mono);font-size:0.68rem;color:var(--text-dim)'>"
            "▸ Total/D/E/N 고정 개수 (-1 = 자동 평준화)</span>",
            unsafe_allow_html=True
        )
        for shift_key, shift_label in [("Total", "Total 고정"), ("D", "D 고정"), ("E", "E 고정"), ("N", "N 고정")]:
            sc_cols = st.columns([2] + [1] * chunk_size)
            sc_cols[0].markdown(f"<span style='font-size:0.75rem'>{shift_label}</span>", unsafe_allow_html=True)
            for ci, ni in enumerate(range(chunk_start, chunk_end)):
                if ni not in st.session_state.shift_counts:
                    st.session_state.shift_counts[ni] = {"D": -1, "E": -1, "N": -1, "Total": -1}
                if "Total" not in st.session_state.shift_counts[ni]:
                    st.session_state.shift_counts[ni]["Total"] = -1
                cur = int(st.session_state.shift_counts[ni].get(shift_key, -1))
                new_val = sc_cols[ci+1].number_input(
                    f"sc_{shift_key}_{ni}", min_value=-1, max_value=60,
                    value=cur, label_visibility="collapsed", key=f"sc_{shift_key}_{ni}"
                )
                st.session_state.shift_counts[ni][shift_key] = int(new_val)

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

        # 화면/Excel 표시 순서: 의사 입력 순서 그대로 유지
        # Grade는 표시하되, Grade 값으로 재정렬하지 않는다.
        # 즉 근무 요청/날짜 설정 탭에서 보이는 의사 순서와 결과표/Excel 순서가 동일하다.
        display_order = list(range(len(doctors)))
        name_to_grade = {doc["name"]: int(doc.get("grade", DEFAULT_DOCTOR_GRADE)) for doc in doctors}
        name_to_display_order = {doctors[ni]["name"]: order for order, ni in enumerate(display_order)}

        summary_display = summary.copy()
        if "Grade" not in summary_display.columns:
            summary_display.insert(1, "Grade", summary_display["Name"].map(name_to_grade).fillna(DEFAULT_DOCTOR_GRADE).astype(int))
        summary_display["_display_order"] = summary_display["Name"].map(name_to_display_order).fillna(9999).astype(int)
        summary_display = (
            summary_display
            .sort_values(["_display_order"], ascending=[True], kind="stable")
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

        # 편차 정보 (k (DE), k1 (holiday), k2 (N), k3 (total), k4 (grade))
        if metrics and sol_idx < len(metrics):
            m = metrics[sol_idx]
            st.markdown(
                f"<div style='font-size:0.85rem; color:var(--text-dim);'>"
                f"** 편차*가중치 합={m.get('adv')} "
                f"| **최적 편차:** {m.get('best_adv', m.get('adv'))} "
                f"| **허용 상한:** {m.get('allowed_adv', m.get('adv'))} "
                f"| **balance penalty:** {m.get('balance_penalty', 'NA')} "
                f"| **k D/E:** {m.get('k')}×{m.get('weight_de_dev', gr.get('weight_de_dev', 1))} "
                f"| **k1 휴일:** {m.get('k1')}×{m.get('weight_holiday_dev', gr.get('weight_holiday_dev', 3))} "
                f"| **k2 총근무:** {m.get('k2')}×{m.get('weight_total_dev', gr.get('weight_total_dev', 5))} "
                f"| **k3 N:** {m.get('k3')}×{m.get('weight_n_dev', gr.get('weight_n_dev', 5))} "
                f"| **k4 Grade편차:** {m.get('k4', 0)} (실제±{round(m.get('k4',0)/10,1)})×{m.get('weight_grade_dev', gr.get('weight_grade_dev', 3))} "
                f"| **저년차 초과:** {m.get('junior_excess', 0)}×{m.get('junior_penalty_weight', gr.get('junior_penalty_weight', 1))} "
                f"= **{m.get('junior_penalty', 0)}**</div>",
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

        lock_col1, lock_col2, lock_col3 = st.columns([1, 1, 3])
        if lock_col1.button("🔒 선택 셀 고정", key="btn_lock_apply"):
            positions = _selected_to_positions(selected_cells)
            if not positions:
                st.warning("선택된 셀이 없어요. 고정할 셀을 먼저 클릭해서 선택해주세요.")
            else:
                new_fixed_req = dict(st.session_state.fixed_shift_requests)
                for ni, di in positions:
                    val = sol.get((ni, di), '')
                    new_fixed_req[(ni, di)] = val.upper() if val else 'x'

                st.session_state.fixed_shift_requests = new_fixed_req
                combined_req = refresh_combined_shift_requests()

                # 모든 날이 hard-coded 된 의사는 shift_counts 자동 계산
                new_shift_counts = dict(st.session_state.shift_counts)
                for ni, row_label in editor_row_order:
                    total_fixed = sum(
                        1 for di in range(num_days)
                        if combined_req.get((ni, di), '') in ('D', 'E', 'N', 'x')
                    )
                    if total_fixed == num_days:
                        d_cnt = sum(1 for di in range(num_days) if combined_req.get((ni, di), '') == 'D')
                        e_cnt = sum(1 for di in range(num_days) if combined_req.get((ni, di), '') == 'E')
                        n_cnt = sum(1 for di in range(num_days) if combined_req.get((ni, di), '') == 'N')
                        new_shift_counts[ni] = {"D": d_cnt, "E": e_cnt, "N": n_cnt, "Total": d_cnt + e_cnt + n_cnt}
                st.session_state.shift_counts = new_shift_counts
                st.session_state["shift_req_version"] = st.session_state.get("shift_req_version", 0) + 1
                st.toast(f"🔒 {len(positions)}개 셀 고정 완료!", icon="🔒")
                st.rerun()

        if lock_col2.button("🔓 선택 셀 고정 해제", key="btn_lock_release"):
            positions = _selected_to_positions(selected_cells)
            if not positions:
                st.warning("선택된 셀이 없어요. 해제할 셀을 먼저 클릭해서 선택해주세요.")
            else:
                released = 0
                for ni, di in positions:
                    if (ni, di) in st.session_state.fixed_shift_requests:
                        st.session_state.fixed_shift_requests.pop((ni, di), None)
                        released += 1
                refresh_combined_shift_requests()
                st.session_state["shift_req_version"] = st.session_state.get("shift_req_version", 0) + 1
                if released > 0:
                    st.toast(f"🔓 {released}개 셀 고정 해제 완료! 원래 사용자 입력값으로 돌아갑니다.", icon="🔓")
                else:
                    st.toast("선택한 셀에는 결과표에서 추가한 fixed layer가 없어요. 원래 사용자 입력값은 근무 요청 탭에서 수정하세요.", icon="ℹ️")
                st.rerun()

        lock_col3.caption(
            "고정은 결과표 위에 fixed layer로 저장됩니다. 해제하면 기존 사용자 입력값(d/en/빈칸 등)이 다시 적용됩니다. "
            "🔒가 붙은 request 칸은 근무 요청 탭에서도 잠겨 보입니다."
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
                duty_summary_rows.append({
                    "날짜": date_label,
                    "유형": dtype,
                    "Duty": shift_key,
                    "인원/필요": f"{len(staff)}/{required}",
                    "평균 Grade": avg_grade if avg_grade is not None else "-",
                    "근무자": ", ".join(doctors[ni]['name'] for ni in staff),
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