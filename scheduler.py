"""
scheduler.py
OR-Tools CP-SAT solver for medical shift scheduling.
Translated from the Google Colab prototype.
"""

from __future__ import annotations
from typing import Any
import pandas as pd
from datetime import date, timedelta

try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False


DAY_LABELS = ['일', '월', '화', '수', '목', '금', '토']


def _get_day_label(start: date, idx: int) -> str:
    d = start + timedelta(days=idx)
    wd = d.weekday()          # 0=Mon … 6=Sun
    kr = (wd + 1) % 7         # 0=Sun, 1=Mon … 6=Sat
    return DAY_LABELS[kr]


def _max_avr(x: float) -> int:
    if x == int(x):
        return int(x)
    return int(x) + 1


def _parse_shift_request(cell: str):
    """Return (cannot_d, cannot_e, cannot_n) booleans from a cell string."""
    c = str(cell).strip().lower()
    if 'a' in c or 'x' in c or 'den' in c:
        return (True, True, True)
    return (
        'd' in c and 'D' not in cell,
        'e' in c and 'E' not in cell,
        'n' in c and 'N' not in cell,
    )


def _parse_shift_wish(cell: str):
    """Return (want_d, want_e, want_n) booleans from uppercase D/E/N."""
    return ('D' in cell, 'E' in cell, 'N' in cell)


def _parse_actual_shift(cell: str):
    """Return worked D/E/N flags from an already-completed schedule cell."""
    c = str(cell or '').strip().upper().replace(' ', '')
    if c in {'', 'A', 'O', 'OFF', 'X', '-', 'NONE', 'NAN'}:
        return (False, False, False)
    return ('D' in c, 'E' in c, 'N' in c)


def build_and_solve(params: dict[str, Any]):
    """
    Main entry-point called from app.py.

    params keys:
        doctors       : list[str]
        num_days      : int
        start_date    : str  (YYYY-MM-DD)
        day_types     : dict {str(day_idx) -> '평일'|'토'|'일'|'공'}
        duty_requests : dict {str(day_idx) -> [D, E, N]}
        shift_requests: dict {"n,d" -> cell_str}
        previous_schedule: dict {"n,h" -> actual shift}, h=0 oldest of preceding days
        previous_schedule_days: int (default 5)
        rules         : dict {str(n) -> {rule_key: value}}
        shift_adj     : dict {str(n) -> int}
        grades        : dict {str(n) -> int}
        grade_rules   : dict with senior/junior policy
        solver_mode   : str
        time_max      : int
        sol_limit     : int
        adv_limit     : int

    Returns:
        solutions : list of dicts {(n, d) -> shift_str}
        summaries : list of pd.DataFrame
    """
    if not ORTOOLS_AVAILABLE:
        raise ImportError("ortools 패키지가 설치되어 있지 않습니다. pip install ortools")

    # ── Unpack params ────────────────────────────────────────────────────────
    names        = params["doctors"]
    num_days     = int(params["num_days"])
    start_date   = date.fromisoformat(params["start_date"])
    day_types    = {int(k): v for k, v in params["day_types"].items()}
    duty_req_raw = {int(k): list(v) for k, v in params["duty_requests"].items()}
    sr_raw       = params["shift_requests"]   # {"n,d": cell_str}
    previous_schedule_days = max(0, int(params.get("previous_schedule_days", 5)))
    previous_schedule_raw = params.get("previous_schedule", {}) or {}
    rules_raw    = {int(k): v for k, v in params["rules"].items()}
    shift_adj    = {int(k): int(v) for k, v in params["shift_adj"].items()}
    # shift_counts: {n: {"D": -1|int, "E": -1|int, "N": -1|int}}, -1 = auto balance
    shift_counts_raw = params.get("shift_counts", {})
    shift_counts = {}
    for k, v in shift_counts_raw.items():
        sc = {sk: int(sv) for sk, sv in v.items()}
        for sk in ("D", "E", "N", "Total"):
            sc.setdefault(sk, -1)
        shift_counts[int(k)] = sc
    grades       = {int(k): int(v) for k, v in params.get("grades", {}).items()}
    grade_rules_raw = params.get("grade_rules", {}) or {}
    default_grade_rules = {
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
        "weight_grade_dev": 3,   # duty별 grade 평균 편차 가중치
    }
    grade_rules = {
        key: int(grade_rules_raw.get(key, default))
        for key, default in default_grade_rules.items()
    }
    # Backward compatibility with older app/config versions:
    # old ultra_junior_forbid_at_or_above = X meant "X명 이상 불가",
    # which is equivalent to new ultra_junior_max_count = X - 1.
    if "ultra_junior_max_count" not in grade_rules_raw and "ultra_junior_forbid_at_or_above" in grade_rules_raw:
        old_cutoff = int(grade_rules_raw.get("ultra_junior_forbid_at_or_above", 0))
        grade_rules["ultra_junior_max_count"] = max(0, old_cutoff - 1) if old_cutoff > 0 else 0
    solver_mode  = params["solver_mode"]
    time_max     = int(params["time_max"])
    sol_limit    = int(params["sol_limit"])
    adv_limit    = int(params["adv_limit"])

    num_doctors = len(names)
    num_shifts  = 3
    all_doctors = range(num_doctors)
    all_days    = range(num_days)
    all_shifts  = range(num_shifts)

    # Previous schedule is fixed historical context only. It does not contribute
    # to current-month duty counts or balancing, but sequence rules can span the boundary.
    previous_schedule = [[[0] * num_shifts for _ in range(previous_schedule_days)] for _ in all_doctors]
    for key, cell in previous_schedule_raw.items():
        try:
            n_str, h_str = str(key).split(",", 1)
            n, h = int(n_str), int(h_str)
        except (TypeError, ValueError):
            continue
        if not (0 <= n < num_doctors and 0 <= h < previous_schedule_days):
            continue
        flags = _parse_actual_shift(cell)
        for s in all_shifts:
            previous_schedule[n][h][s] = int(flags[s])

    # Existing/old configs may not have grade values. Default grade 2 keeps legacy schedules feasible.
    for n in all_doctors:
        grades.setdefault(n, 2)

    senior_min_grade = grade_rules["senior_min_grade"]
    senior_min_count = grade_rules["senior_min_count"]
    junior_max_grade = grade_rules["junior_max_grade"]
    junior_soft_max_count = grade_rules["junior_soft_max_count"]
    junior_penalty_weight = grade_rules["junior_penalty_weight"]
    ultra_junior_max_grade = grade_rules["ultra_junior_max_grade"]
    ultra_junior_max_count = grade_rules["ultra_junior_max_count"]
    weight_de_dev      = grade_rules["weight_de_dev"]
    weight_holiday_dev = grade_rules["weight_holiday_dev"]
    weight_total_dev   = grade_rules["weight_total_dev"]
    weight_n_dev       = grade_rules["weight_n_dev"]
    weight_grade_dev   = grade_rules["weight_grade_dev"]

    senior_doctors = [n for n in all_doctors if grades.get(n, 2) >= senior_min_grade]
    junior_doctors = [n for n in all_doctors if grades.get(n, 2) <= junior_max_grade]
    ultra_junior_doctors = [n for n in all_doctors if grades.get(n, 2) <= ultra_junior_max_grade]
    non_ultra_junior_doctors = [n for n in all_doctors if n not in ultra_junior_doctors]

    day_names_list = [_get_day_label(start_date, d) for d in all_days]

    # duty_requests[d][s]
    duty_requests = [[duty_req_raw.get(d, [1,1,1])[s] for s in all_shifts] for d in all_days]

    # Validate senior hard rule before building the full model.
    if senior_min_count > 0:
        if len(senior_doctors) < senior_min_count:
            raise RuntimeError(
                f"고년차 hard rule 불가능: grade >= {senior_min_grade} 인원이 {len(senior_doctors)}명인데, "
                f"각 duty마다 최소 {senior_min_count}명이 필요합니다."
            )
        for d in all_days:
            for s in all_shifts:
                if duty_requests[d][s] > 0 and senior_min_count > duty_requests[d][s]:
                    raise RuntimeError(
                        f"고년차 hard rule 불가능: day {d+1}, shift {['D','E','N'][s]} 필요 인원은 "
                        f"{duty_requests[d][s]}명인데 고년차 최소 {senior_min_count}명으로 설정되어 있습니다."
                    )

    # Validate ultra-junior hard rule before building the full model.
    # ultra_junior_max_count = maximum ultra-juniors allowed in one active D/E/N duty.
    # 0 disables this hard rule; 1 means at most one ultra-junior per duty.
    if ultra_junior_max_count > 0:
        max_possible_staff = len(non_ultra_junior_doctors) + min(len(ultra_junior_doctors), ultra_junior_max_count)
        for d in all_days:
            for s in all_shifts:
                if duty_requests[d][s] > max_possible_staff:
                    raise RuntimeError(
                        f"초저년차 hard rule 불가능: day {d+1}, shift {['D','E','N'][s]} 필요 인원은 "
                        f"{duty_requests[d][s]}명인데, grade <= {ultra_junior_max_grade} 인원은 "
                        f"한 duty에 최대 {ultra_junior_max_count}명까지만 허용되도록 설정되어 있습니다. "
                        f"현재 조건에서는 이 duty에 최대 {max_possible_staff}명까지만 배정 가능합니다."
                    )

    # shift_requests[n][d][s] = 1 if doctor n cannot work shift s on day d
    shift_requests  = [[[0]*3 for _ in all_days] for _ in all_doctors]
    shift_requests1 = [[[0]*3 for _ in all_days] for _ in all_doctors]
    annual_leave_counts = {n: 0 for n in all_doctors}
    for key, cell in sr_raw.items():
        if not cell:
            continue
        n_str, d_str = key.split(",")
        n, d = int(n_str), int(d_str)
        if n >= num_doctors or d >= num_days:
            continue
        cell_text = str(cell).strip()
        if 'a' in cell_text.lower():
            annual_leave_counts[n] += 1
        cant = _parse_shift_request(cell_text)
        wish = _parse_shift_wish(cell)
        for s in range(3):
            if cant[s]:
                shift_requests[n][d][s] = 1
            if wish[s]:
                shift_requests1[n][d][s] = 1

    # holidays (list of day indices)
    holiday = [d for d, t in day_types.items() if t in ('토', '일', '공')]

    # rules[n][key]
    def get_rule(n, key, default=0):
        return int(rules_raw.get(n, {}).get(key, default))

    # ── Averages ─────────────────────────────────────────────────────────────
    total_duty = sum(sum(duty_requests[d]) for d in all_days)
    total_s    = [sum(duty_requests[d][s] for d in all_days) for s in all_shifts]
    total_holiday_demand = sum(
        duty_requests[d][s] for d in holiday for s in all_shifts
    )

    s_rate   = [total_s[s] / total_duty if total_duty else 0 for s in all_shifts]
    hol_rate = total_holiday_demand / total_duty if total_duty else 0

    # ── fixed_total validation / average ─────────────────────────────────────
    # shift_counts[n]["Total"] >= 0 means the doctor's total number of shifts is hard-fixed.
    fixed_total_by_doc = {
        n: int(shift_counts.get(n, {}).get("Total", -1))
        for n in all_doctors
        if int(shift_counts.get(n, {}).get("Total", -1)) >= 0
    }
    fixed_total_sum = sum(fixed_total_by_doc.values())
    free_total_doctors = [n for n in all_doctors if n not in fixed_total_by_doc]

    if fixed_total_sum > total_duty:
        raise RuntimeError(
            f"fixed_total 합({fixed_total_sum})이 Duty 총합({total_duty})보다 {fixed_total_sum - total_duty}개 많습니다. "
            f"Duty 설정에서 총 근무를 추가하거나 fixed_total을 줄여주세요."
        )
    if not free_total_doctors and fixed_total_sum != total_duty:
        raise RuntimeError(
            f"모든 의사의 fixed_total이 지정되어 있지만 합({fixed_total_sum})이 Duty 총합({total_duty})과 다릅니다. "
            f"차이={total_duty - fixed_total_sum}개입니다."
        )

    for n, fixed_total in fixed_total_by_doc.items():
        sc = shift_counts.get(n, {})
        fixed_shift_sum = sum(int(sc.get(sk, -1)) for sk in ("D", "E", "N") if int(sc.get(sk, -1)) >= 0)
        if fixed_shift_sum > fixed_total:
            raise RuntimeError(
                f"{names[n]}의 fixed_D/E/N 합({fixed_shift_sum})이 fixed_total({fixed_total})보다 큽니다."
            )
        if all(int(sc.get(sk, -1)) >= 0 for sk in ("D", "E", "N")) and fixed_shift_sum != fixed_total:
            raise RuntimeError(
                f"{names[n]}의 fixed_D+fixed_E+fixed_N={fixed_shift_sum}인데 fixed_total={fixed_total}입니다. "
                f"모두 고정한 경우 두 값이 같아야 합니다."
            )

    # Annual leave ('a') is treated as hard off like x and counted in the summary,
    # but it no longer creates a hidden internal shift_adj effect.  If annual leave
    # or fixed_Total should change balancing targets, app.py can write the explicit
    # value into the visible shift_adj table via the auto-calculate button.
    balance_shift_adj = {
        n: shift_adj.get(n, 0)
        for n in all_doctors
    }

    free_total_adj = sum(balance_shift_adj.get(n, 0) for n in free_total_doctors)
    avr_total_free = (
        (total_duty - fixed_total_sum - free_total_adj) / len(free_total_doctors)
        if free_total_doctors else 0.0
    )

    # ── Shift별 독립 평균 계산 ────────────────────────────────────────────────
    # D/E/N 각각: fix된 사람 제외 후 나머지 인원 기준으로 평균 계산
    # Holiday: fix 여부 무관 전체 인원 기준 유지
    # shift_counts: {n: {"D": -1|int, "E": -1|int, "N": -1|int}}, -1 = free

    def _shift_avr(shift_idx: int, shift_key: str):
        """fix 안 된 인원 기준으로 해당 shift 평균 계산."""
        fixed_sum = sum(
            shift_counts.get(n, {}).get(shift_key, -1)
            for n in all_doctors
            if shift_counts.get(n, {}).get(shift_key, -1) >= 0
        )
        free_ns = [
            n for n in all_doctors
            if shift_counts.get(n, {}).get(shift_key, -1) < 0
        ]
        if not free_ns:
            return 0.0, []
        free_adj = sum(balance_shift_adj.get(n, 0) for n in free_ns)
        avr = (total_s[shift_idx] - fixed_sum - free_adj * s_rate[shift_idx]) / len(free_ns)
        return avr, free_ns

    avr_d, free_d_doctors = _shift_avr(0, "D")
    avr_e, free_e_doctors = _shift_avr(1, "E")
    avr_n, free_n_doctors = _shift_avr(2, "N")

    # Total 평균: 세 shift 평균 합 (인원별로 자기가 free인 shift 평균의 합)
    # Holiday 평균: 전체 인원 기준 유지
    adj_sum = sum(balance_shift_adj.get(n, 0) for n in all_doctors)
    avr_holiday = (total_holiday_demand - adj_sum * hol_rate) / num_doctors

    # ── Build model ───────────────────────────────────────────────────────────
    model = cp_model.CpModel()

    shifts = {}
    for n in all_doctors:
        for d in all_days:
            for s in all_shifts:
                shifts[(n, d, s)] = model.NewBoolVar(f"s_{n}_{d}_{s}")

    # Fixed BoolVars for the already-completed preceding days let the same CP-SAT
    # sequence expressions span the month boundary without counting history as demand.
    history_shifts = {}
    for n in all_doctors:
        for h in range(previous_schedule_days):
            for s in all_shifts:
                var = model.NewBoolVar(f"hist_{n}_{h}_{s}")
                model.Add(var == previous_schedule[n][h][s])
                history_shifts[(n, h, s)] = var

    timeline_len = previous_schedule_days + num_days
    current_offset = previous_schedule_days

    def timeline_shift(n: int, t: int, s: int):
        if t < current_offset:
            return history_shifts[(n, t, s)]
        return shifts[(n, t - current_offset, s)]

    def sequence_window_starts(window_len: int):
        """Starts of windows that contain at least one current-month day."""
        if window_len <= 0 or timeline_len < window_len:
            return range(0)
        first = max(0, current_offset - window_len + 1)
        return range(first, timeline_len - window_len + 1)

    timeline_worked = {}
    for n in all_doctors:
        for t in range(timeline_len):
            worked = model.NewBoolVar(f"worked_timeline_{n}_{t}")
            model.AddMaxEquality(worked, [timeline_shift(n, t, s) for s in all_shifts])
            timeline_worked[(n, t)] = worked

    # ── Hard constraints ──────────────────────────────────────────────────────

    # Per-doctor rules
    for n in all_doctors:
        r0        = get_rule(n, "rule_max_shifts_per_day", 1)
        r2        = get_rule(n, "rule_no_day_after_eve", 1)
        r3        = get_rule(n, "rule_no_3eve_consec", 1)
        r4        = get_rule(n, "rule_no_3eve_in_4days", 1)
        r5        = get_rule(n, "rule_max_consec_days", 5)
        r6        = get_rule(n, "rule_max_shifts_per_week", 0)
        r7        = get_rule(n, "rule_no_3day_consec", 1)
        n_max     = get_rule(n, "rule_n_block_max", 1)   # Max N block length (1/2/3)
        n_rest    = get_rule(n, "rule_n_rest", 1)        # Mandatory rest days after N-block
        n_gap     = get_rule(n, "rule_n_gap", 0)         # Min gap before next N after N-block

        # rule0: max shifts per day (current month); the 2-day cap spans history.
        if r0 == 1:
            for d in all_days:
                model.AddAtMostOne(shifts[(n,d,s)] for s in all_shifts)
        elif r0 in (2, 4):
            for d in all_days:
                model.AddBoolOr([shifts[(n,d,0)].Not(), shifts[(n,d,1)], shifts[(n,d,2)].Not()])
                model.AddBoolOr([shifts[(n,d,0)].Not(), shifts[(n,d,1)].Not(), shifts[(n,d,2)].Not()])
            if r0 == 4:
                for d in [x for x in all_days if x not in holiday]:
                    model.AddAtMostOne(shifts[(n,d,s)] for s in all_shifts)
            for t in sequence_window_starts(2):
                model.Add(sum(timeline_shift(n, t+p, s) for p in range(2) for s in all_shifts) < 4)
        elif r0 in (3, 5):
            for d in all_days:
                model.AddBoolOr([shifts[(n,d,0)].Not(), shifts[(n,d,1)], shifts[(n,d,2)].Not()])
            if r0 == 5:
                for d in [x for x in all_days if x not in holiday]:
                    model.AddAtMostOne(shifts[(n,d,s)] for s in all_shifts)
            for t in sequence_window_starts(2):
                model.Add(sum(timeline_shift(n, t+p, s) for p in range(2) for s in all_shifts) < 4)

        # ── N-block constraints ───────────────────────────────────────────────
        # All windows containing a current day include the fixed previous schedule.
        block_len = n_max + 1
        for t in sequence_window_starts(block_len):
            model.Add(sum(timeline_shift(n, t+i, 2) for i in range(block_len)) < block_len)

        # Detect an N-block end anywhere in the available history/current timeline.
        # Only consequences landing in the current month are added.
        for e in range(timeline_len):
            for r in range(1, n_rest + 1):
                dd = e + r
                if dd >= timeline_len:
                    break
                if dd < current_offset:
                    continue
                for s in all_shifts:
                    if e + 1 < timeline_len:
                        model.AddBoolOr([
                            timeline_shift(n,e,2).Not(),
                            timeline_shift(n,e+1,2),
                            timeline_shift(n,dd,s).Not(),
                        ])
                    else:
                        model.AddBoolOr([timeline_shift(n,e,2).Not(), timeline_shift(n,dd,s).Not()])

            for g in range(n_rest + 1, n_gap + 1):
                dd = e + g
                if dd >= timeline_len:
                    break
                if dd < current_offset:
                    continue
                if e + 1 < timeline_len:
                    model.AddBoolOr([
                        timeline_shift(n,e,2).Not(),
                        timeline_shift(n,e+1,2),
                        timeline_shift(n,dd,2).Not(),
                    ])
                else:
                    model.AddBoolOr([timeline_shift(n,e,2).Not(), timeline_shift(n,dd,2).Not()])

        # rule2: no D after E, including previous-month final day -> current day 1.
        if r2:
            for t in sequence_window_starts(2):
                model.Add(timeline_shift(n,t+1,0) == 0).OnlyEnforceIf(timeline_shift(n,t,1))

        # rule3: no EEE across the boundary.
        if r3:
            for t in sequence_window_starts(3):
                model.AddBoolOr([
                    timeline_shift(n,t,1).Not(),
                    timeline_shift(n,t+1,1).Not(),
                    timeline_shift(n,t+2,1).Not(),
                ])

        # rule4: preserve the original two forbidden 3-in-4 E patterns, now cross-boundary.
        if r4:
            for t in sequence_window_starts(4):
                model.AddBoolOr([
                    timeline_shift(n,t,1).Not(),
                    timeline_shift(n,t+1,1).Not(),
                    timeline_shift(n,t+2,1),
                    timeline_shift(n,t+3,1).Not(),
                ])
                model.AddBoolOr([
                    timeline_shift(n,t,1).Not(),
                    timeline_shift(n,t+1,1),
                    timeline_shift(n,t+2,1).Not(),
                    timeline_shift(n,t+3,1).Not(),
                ])

        # rule5: max consecutive working days across the month boundary.
        if r5 in (3,4,5,6,7):
            for t in sequence_window_starts(r5 + 1):
                model.Add(sum(timeline_worked[(n, t+p)] for p in range(r5 + 1)) <= r5)

        # rule6: max shifts in any available 7-day window across the boundary.
        if r6 > 0:
            for t in sequence_window_starts(7):
                model.Add(sum(timeline_shift(n,t+p,s) for p in range(7) for s in all_shifts) <= r6)

        # rule7: no DDD across the boundary.
        if r7:
            for t in sequence_window_starts(3):
                model.AddBoolOr([
                    timeline_shift(n,t,0).Not(),
                    timeline_shift(n,t+1,0).Not(),
                    timeline_shift(n,t+2,0).Not(),
                ])

    # Duty demand constraints
    for d in all_days:
        for s in all_shifts:
            model.Add(sum(shifts[(n,d,s)] for n in all_doctors) == duty_requests[d][s])

    # Grade hard rule: each active duty must include enough senior doctors.
    if senior_min_count > 0:
        for d in all_days:
            for s in all_shifts:
                if duty_requests[d][s] > 0:
                    model.Add(sum(shifts[(n,d,s)] for n in senior_doctors) >= senior_min_count)

    # Ultra-junior hard rule: maximum ultra-juniors allowed in the same active duty.
    # Example: max_count=1 means at most one ultra-junior per D/E/N duty.
    if ultra_junior_max_count > 0 and ultra_junior_doctors:
        for d in all_days:
            for s in all_shifts:
                if duty_requests[d][s] > 0:
                    model.Add(sum(shifts[(n,d,s)] for n in ultra_junior_doctors) <= ultra_junior_max_count)

    # Cannot-work constraints
    for n in all_doctors:
        for d in all_days:
            for s in all_shifts:
                if shift_requests[n][d][s] == 1:
                    model.Add(shifts[(n,d,s)] == 0)

    # Must-work constraints
    for n in all_doctors:
        for d in all_days:
            for s in all_shifts:
                if shift_requests1[n][d][s] == 1:
                    model.Add(shifts[(n,d,s)] == 1)

    # Grade soft rule: spread junior doctors. Excess juniors are allowed but penalized.
    junior_excess_vars = []
    if junior_penalty_weight > 0 and junior_doctors:
        for d in all_days:
            for s in all_shifts:
                if duty_requests[d][s] <= 0:
                    continue
                max_excess = max(0, duty_requests[d][s] - junior_soft_max_count)
                if max_excess <= 0:
                    continue
                junior_count = sum(shifts[(n,d,s)] for n in junior_doctors)
                excess = model.NewIntVar(0, max_excess, f"junior_excess_{d}_{s}")
                model.Add(excess >= junior_count - junior_soft_max_count)
                junior_excess_vars.append(excess)

    # ── Grade 평균 편차 (duty별) ─────────────────────────────────────────────
    # 기존 D/E/N 편차와 동일한 방식:
    # "각 duty의 grade 평균이 전체 평균에서 최대 k4만큼 벗어날 수 있다"
    #
    # 10배 스케일로 정수화 (k4=5 → 실제 편차 0.5)
    # grade_avg(d,s) × 10 = grade_sum(d,s) × 10 / r
    # 전체 평균 × 10 = total_grade × 10 / num_doctors (정수 근사)
    # CP-SAT: 양변에 r × num_doctors 곱해서 정수 비교
    # grade_sum × num_doctors × 10  vs  total_grade × r × 10
    # → grade_sum × num_doctors  vs  total_grade × r  (10 약분)
    # 편차 upper bound: grade_sum × num_doctors ≤ total_grade × r + k4 × r
    # 편차 lower bound: grade_sum × num_doctors ≥ total_grade × r - k4 × r
    # 즉 k4 단위 = num_doctors × 1/10 grade (10배 스케일)

    # 더 직관적으로: 양변을 num_doctors로 나누면
    # grade_sum / r ≤ total_grade/num_doctors + k4/10
    # k4=5 이면 평균 grade에서 ±0.5 허용

    max_grade   = max(grades.get(n, 2) for n in all_doctors) if num_doctors > 0 else 3
    total_grade = sum(grades.get(n, 2) for n in all_doctors)
    # 10배 스케일 전체 평균 (정수 근사)
    avr_grade_10 = (total_grade * 10) // num_doctors if num_doctors > 0 else 20

    # k4 범위: 최대 ±max_grade (10배 스케일이므로 ×10)
    k4 = model.NewIntVar(0, max_grade * 10, 'k4_grade_dev')

    if weight_grade_dev > 0 and num_doctors > 0:
        for d in all_days:
            for s in all_shifts:
                r = duty_requests[d][s]
                if r <= 0:
                    continue

                # grade_sum × 10 / r 가 avr_grade_10 ± k4 이내
                # CP-SAT: 양변 × r → grade_sum × 10 이 avr_grade_10×r ± k4×r 이내
                grade_sum_10 = sum(shifts[(n,d,s)] * grades.get(n, 2) * 10 for n in all_doctors)

                # avr_grade_10 × r - k4 × r ≤ grade_sum_10 ≤ avr_grade_10 × r + k4 × r
                # → grade_sum_10 ≤ (avr_grade_10 + k4) × r
                # → grade_sum_10 ≥ (avr_grade_10 - k4) × r
                #
                # CP-SAT AddBoolOr 방식 대신 직접 부등식:
                # 단, k4가 변수이므로 선형 표현 필요
                # grade_sum_10 - avr_grade_10 * r ≤ k4 * r
                # avr_grade_10 * r - grade_sum_10 ≤ k4 * r

                max_gs10 = max_grade * 10 * r
                gs10_var = model.NewIntVar(0, max_gs10, f"gs10_{d}_{s}")
                model.Add(gs10_var == grade_sum_10)

                dev_up = model.NewIntVar(0, max_gs10, f"gup_{d}_{s}")
                dev_dn = model.NewIntVar(0, max_gs10, f"gdn_{d}_{s}")
                model.Add(dev_up - dev_dn == gs10_var - avr_grade_10 * r)

                # k4 × r ≥ dev_up  and  k4 × r ≥ dev_dn
                # → k4 이 "grade 평균 편차의 최대값 (×10 스케일)"
                # r로 나눠야 하지만 CP-SAT 정수 → r 곱한 채로 k4에 반영
                # 대신 k4를 r배 스케일로 정의하지 않고,
                # 편차를 r로 나눈 값이 k4 이하가 되도록:
                # dev_up ≤ k4 × r  (즉 dev_up/r ≤ k4)
                model.Add(dev_up <= k4 * r)
                model.Add(dev_dn <= k4 * r)

    # ── Soft balancing (deviation minimization) ───────────────────────────────
    # 각 balance 항목을 아래쪽/위쪽 편차로 분리한다.
    # 예: 목표 19~20일 때 19~21은 상방 1, 18~20은 하방 1, 17~22는 하방 2+상방 2로 계산.
    k_de_low  = model.NewIntVar(0, 6, 'k_DE_low')
    k_de_high = model.NewIntVar(0, 6, 'k_DE_high')
    k1_low    = model.NewIntVar(0, 6, 'k1_holiday_low')
    k1_high   = model.NewIntVar(0, 6, 'k1_holiday_high')
    k2_low    = model.NewIntVar(0, 6, 'k2_total_low')
    k2_high   = model.NewIntVar(0, 6, 'k2_total_high')
    k3_low    = model.NewIntVar(0, 6, 'k3_N_low')
    k3_high   = model.NewIntVar(0, 6, 'k3_N_high')

    k  = model.NewIntVar(0, 12, 'k_DE_sum')
    k1 = model.NewIntVar(0, 12, 'k1_holiday_sum')
    k2 = model.NewIntVar(0, 12, 'k2_total_sum')
    k3 = model.NewIntVar(0, 12, 'k3_N_sum')
    model.Add(k  == k_de_low + k_de_high)
    model.Add(k1 == k1_low + k1_high)
    model.Add(k2 == k2_low + k2_high)
    model.Add(k3 == k3_low + k3_high)

    for n in all_doctors:
        adj     = balance_shift_adj.get(n, 0)
        sc      = shift_counts.get(n, {})
        fixed_d = sc.get("D", -1)
        fixed_e = sc.get("E", -1)
        fixed_n = sc.get("N", -1)
        fixed_total = sc.get("Total", -1)
        is_total_fixed = fixed_total >= 0
        is_fully_fixed = (fixed_d >= 0 and fixed_e >= 0 and fixed_n >= 0)

        num_s = [sum(shifts[(n,d,s)] for d in all_days) for s in all_shifts]
        num_total = sum(num_s)
        hol_worked = sum(shifts[(n,d,s)] for d in holiday for s in all_shifts)

        # ── 고정 개수 hard constraint ─────────────────────────────────────────
        if fixed_d >= 0: model.Add(num_s[0] == fixed_d)
        if fixed_e >= 0: model.Add(num_s[1] == fixed_e)
        if fixed_n >= 0: model.Add(num_s[2] == fixed_n)
        if fixed_total >= 0: model.Add(num_total == fixed_total)

        dev_de  = [model.NewIntVar(0, 6, f'dde_{n}_{x}') for x in range(2)]
        dev_hol = [model.NewIntVar(0, 6, f'dhol_{n}_{x}') for x in range(2)]
        dev_tot = [model.NewIntVar(0, 6, f'dtot_{n}_{x}') for x in range(2)]
        dev_N   = [model.NewIntVar(0, 6, f'dN_{n}_{x}') for x in range(2)]

        sum_de  = model.NewIntVar(0, 12, f'sde_{n}')
        sum_hol = model.NewIntVar(0, 12, f'shol_{n}')
        sum_tot = model.NewIntVar(0, 12, f'stot_{n}')
        sum_N   = model.NewIntVar(0, 12, f'sN_{n}')

        model.Add(sum_de  == dev_de[0]  + dev_de[1])
        model.Add(sum_hol == dev_hol[0] + dev_hol[1])
        model.Add(sum_tot == dev_tot[0] + dev_tot[1])
        model.Add(sum_N   == dev_N[0]   + dev_N[1])

        # 하방/상방 편차를 따로 최적화한다. 같은 weight 하나를 (low+high)에 적용한다.
        model.Add(dev_de[0]  <= k_de_low);   model.Add(dev_de[1]  <= k_de_high)
        model.Add(dev_hol[0] <= k1_low);     model.Add(dev_hol[1] <= k1_high)
        model.Add(dev_tot[0] <= k2_low);     model.Add(dev_tot[1] <= k2_high)
        model.Add(dev_N[0]   <= k3_low);     model.Add(dev_N[1]   <= k3_high)

        if is_fully_fixed:
            # 전체 fix → deviation 전부 0, 평준화 제외 (holiday만 유지)
            for dv in [dev_de, dev_tot, dev_N]:
                model.Add(dv[0] == 0); model.Add(dv[1] == 0)
            # holiday는 fix 여부 무관 전체 인원 기준
            model.Add(int(avr_holiday + adj * hol_rate) - dev_hol[0] <= hol_worked)
            model.Add(hol_worked <= _max_avr(avr_holiday + adj * hol_rate) + dev_hol[1])
        else:
            # D — 각 shift별 독립 평균 (avr_d/avr_e/avr_n)
            if fixed_d >= 0:
                model.Add(dev_de[0] == 0); model.Add(dev_de[1] == 0)
            else:
                model.Add(int(avr_d + adj * s_rate[0]) - dev_de[0] <= num_s[0])
                model.Add(num_s[0] <= _max_avr(avr_d + adj * s_rate[0]) + dev_de[1])

            # E (dev_de 공유)
            if fixed_e < 0:
                model.Add(int(avr_e + adj * s_rate[1]) - dev_de[0] <= num_s[1])
                model.Add(num_s[1] <= _max_avr(avr_e + adj * s_rate[1]) + dev_de[1])

            # N
            if fixed_n >= 0:
                model.Add(dev_N[0] == 0); model.Add(dev_N[1] == 0)
            else:
                model.Add(int(avr_n + adj * s_rate[2]) - dev_N[0] <= num_s[2])
                model.Add(num_s[2] <= _max_avr(avr_n + adj * s_rate[2]) + dev_N[1])

            # Total — fixed_total이 있으면 hard count이므로 total deviation에서 제외.
            # fixed_total이 없는 사람끼리 남은 총근무수를 평준화한다.
            if is_total_fixed:
                model.Add(dev_tot[0] == 0); model.Add(dev_tot[1] == 0)
            else:
                model.Add(int(avr_total_free + adj) - dev_tot[0] <= num_total)
                model.Add(num_total <= _max_avr(avr_total_free + adj) + dev_tot[1])

            # Holiday — fix 무관 전체 인원 기준
            model.Add(int(avr_holiday + adj * hol_rate) - dev_hol[0] <= hol_worked)
            model.Add(hol_worked <= _max_avr(avr_holiday + adj * hol_rate) + dev_hol[1])


    # ── Objective ─────────────────────────────────────────────────────────────
    junior_excess_total = sum(junior_excess_vars) if junior_excess_vars else 0
    junior_penalty = junior_excess_total * junior_penalty_weight
    balance_penalty = (
        k  * weight_de_dev
        + k1 * weight_holiday_dev
        + k2 * weight_total_dev
        + k3 * weight_n_dev
        + k4 * weight_grade_dev
    )
    adv = balance_penalty + junior_penalty
    is_multi = "다중" in solver_mode

    # Always solve once with objective minimization first.
    # In multi mode, this first pass finds the best objective value, then we enumerate
    # solutions with adv <= best_adv + adv_limit.
    model.Minimize(adv)

    # ── Solve ─────────────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_max
    solver.parameters.linearization_level = 0

    solutions = []
    summaries = []

    def _extract(sol_fn):
        """Extract solution dict and summary DataFrame from current solver values."""
        sol = {}
        for n in all_doctors:
            for d in all_days:
                vals = [sol_fn(shifts[(n,d,s)]) for s in all_shifts]
                key = (vals[0], vals[1], vals[2])
                SHIFT_MAP = {
                    (0,0,0): '', (0,0,1): 'n', (0,1,0): 'e', (0,1,1): 'en',
                    (1,0,0): 'd', (1,0,1): 'dn', (1,1,0): 'de', (1,1,1): 'den'
                }
                sol[(n, d)] = SHIFT_MAP.get(key, '')

        rows = []
        for n in all_doctors:
            d_cnt = sum(sol_fn(shifts[(n,d,0)]) for d in all_days)
            e_cnt = sum(sol_fn(shifts[(n,d,1)]) for d in all_days)
            n_cnt = sum(sol_fn(shifts[(n,d,2)]) for d in all_days)
            tot   = d_cnt + e_cnt + n_cnt
            hol   = sum(sol_fn(shifts[(n,d,s)]) for d in holiday for s in all_shifts)
            fri_n = sum(sol_fn(shifts[(n,d,2)]) for d in all_days if day_names_list[d] == '금')
            annual_cnt = annual_leave_counts.get(n, 0)
            rows.append({
                'Name': names[n],
                'Grade': grades.get(n, 2),
                'Senior': 'Y' if grades.get(n, 2) >= senior_min_grade else '',
                'Junior': 'Y' if grades.get(n, 2) <= junior_max_grade else '',
                '초저년차': 'Y' if grades.get(n, 2) <= ultra_junior_max_grade else '',
                'D': d_cnt, 'E': e_cnt, 'N': n_cnt,
                'Total': tot, '연차': annual_cnt, 'Holiday': hol,
                'Fri_N': fri_n,
                '주간평균hr': round((d_cnt*8 + e_cnt*9 + n_cnt*8) / num_days * 7, 2),
            })
        return sol, pd.DataFrame(rows)

    metrics = []

    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("최적해가 없습니다.")

    best_adv = solver.Value(adv)
    allowed_adv = best_adv + adv_limit if is_multi else best_adv

    def _metric_dict(value_fn):
        return {
            "adv": value_fn(adv),
            "k": value_fn(k),
            "k_low": value_fn(k_de_low),
            "k_high": value_fn(k_de_high),
            "k1": value_fn(k1),
            "k1_low": value_fn(k1_low),
            "k1_high": value_fn(k1_high),
            "k2": value_fn(k2),
            "k2_low": value_fn(k2_low),
            "k2_high": value_fn(k2_high),
            "k3": value_fn(k3),
            "k3_low": value_fn(k3_low),
            "k3_high": value_fn(k3_high),
            "k4": value_fn(k4),
            "junior_excess": value_fn(junior_excess_total) if junior_excess_vars else 0,
            "junior_penalty": value_fn(junior_penalty) if junior_excess_vars else 0,
            "senior_min_grade": senior_min_grade,
            "senior_min_count": senior_min_count,
            "junior_max_grade": junior_max_grade,
            "junior_soft_max_count": junior_soft_max_count,
            "junior_penalty_weight": junior_penalty_weight,
            "ultra_junior_max_grade": ultra_junior_max_grade,
            "ultra_junior_max_count": ultra_junior_max_count,
            "weight_de_dev": weight_de_dev,
            "weight_holiday_dev": weight_holiday_dev,
            "weight_total_dev": weight_total_dev,
            "weight_n_dev": weight_n_dev,
            "weight_grade_dev": weight_grade_dev,
            "balance_penalty": value_fn(balance_penalty),
            "best_adv": best_adv,
            "allowed_adv": allowed_adv,
            "adv_extra_allowed": adv_limit if is_multi else 0,
            "optimization_status": solver.StatusName(status),
        }

    if not is_multi:
        sol, summ = _extract(solver.Value)
        solutions.append(sol)
        summaries.append(summ)
        metrics.append(_metric_dict(solver.Value))
    else:
        # 2-stage multi-solution search:
        #   step 1: minimize adv and record best_adv
        #   step 2: enumerate schedules with adv <= best_adv + adv_limit
        model.Add(adv <= allowed_adv)
        try:
            model.ClearObjective()
        except AttributeError:
            pass

        solver.parameters.enumerate_all_solutions = True

        class _CB(cp_model.CpSolverSolutionCallback):
            def __init__(self):
                super().__init__()
                self._count = 0

            def on_solution_callback(self):
                sol, summ = _extract(self.Value)
                solutions.append(sol)
                summaries.append(summ)
                metrics.append(_metric_dict(self.Value))
                self._count += 1
                if self._count >= sol_limit:
                    self.StopSearch()

        cb = _CB()
        solver.Solve(model, cb)

        if not solutions:
            raise RuntimeError(
                f"조건을 만족하는 다중 솔루션이 없습니다. 최적 편차={best_adv}, "
                f"허용 상한={allowed_adv}입니다. 추가 허용 편차 또는 탐색 시간을 늘려 보세요."
            )

    return solutions, summaries, metrics
