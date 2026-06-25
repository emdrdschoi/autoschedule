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
    c = cell.lower()
    if 'x' in c or 'den' in c:
        return (True, True, True)
    return (
        'd' in c and 'D' not in cell,
        'e' in c and 'E' not in cell,
        'n' in c and 'N' not in cell,
    )


def _parse_shift_wish(cell: str):
    """Return (want_d, want_e, want_n) booleans from uppercase D/E/N."""
    return ('D' in cell, 'E' in cell, 'N' in cell)


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
    rules_raw    = {int(k): v for k, v in params["rules"].items()}
    shift_adj    = {int(k): int(v) for k, v in params["shift_adj"].items()}
    grades       = {int(k): int(v) for k, v in params.get("grades", {}).items()}
    grade_rules_raw = params.get("grade_rules", {}) or {}
    default_grade_rules = {
        "senior_min_grade": 2,
        "senior_min_count": 1,
        "junior_max_grade": 1,
        "junior_soft_max_count": 1,
        "junior_penalty_weight": 1,
        "weight_de_dev": 1,
        "weight_holiday_dev": 3,
        "weight_total_dev": 5,
        "weight_n_dev": 5,
    }
    grade_rules = {
        key: int(grade_rules_raw.get(key, default))
        for key, default in default_grade_rules.items()
    }
    solver_mode  = params["solver_mode"]
    time_max     = int(params["time_max"])
    sol_limit    = int(params["sol_limit"])
    adv_limit    = int(params["adv_limit"])

    num_doctors = len(names)
    num_shifts  = 3
    all_doctors = range(num_doctors)
    all_days    = range(num_days)
    all_shifts  = range(num_shifts)

    # Existing/old configs may not have grade values. Default grade 2 keeps legacy schedules feasible.
    for n in all_doctors:
        grades.setdefault(n, 2)

    senior_min_grade = grade_rules["senior_min_grade"]
    senior_min_count = grade_rules["senior_min_count"]
    junior_max_grade = grade_rules["junior_max_grade"]
    junior_soft_max_count = grade_rules["junior_soft_max_count"]
    junior_penalty_weight = grade_rules["junior_penalty_weight"]
    weight_de_dev = grade_rules["weight_de_dev"]
    weight_holiday_dev = grade_rules["weight_holiday_dev"]
    weight_total_dev = grade_rules["weight_total_dev"]
    weight_n_dev = grade_rules["weight_n_dev"]

    senior_doctors = [n for n in all_doctors if grades.get(n, 2) >= senior_min_grade]
    junior_doctors = [n for n in all_doctors if grades.get(n, 2) <= junior_max_grade]

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

    # shift_requests[n][d][s] = 1 if doctor n cannot work shift s on day d
    shift_requests  = [[[0]*3 for _ in all_days] for _ in all_doctors]
    shift_requests1 = [[[0]*3 for _ in all_days] for _ in all_doctors]
    for key, cell in sr_raw.items():
        if not cell:
            continue
        n_str, d_str = key.split(",")
        n, d = int(n_str), int(d_str)
        if n >= num_doctors or d >= num_days:
            continue
        cant = _parse_shift_request(cell)
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
    adj_sum = sum(shift_adj.get(n, 0) for n in all_doctors)

    s_rate     = [total_s[s] / total_duty if total_duty else 0 for s in all_shifts]
    hol_rate   = total_holiday_demand / total_duty if total_duty else 0

    avr_duty    = (total_duty - adj_sum) / num_doctors
    avr_s       = [(total_s[s] - adj_sum * s_rate[s]) / num_doctors for s in all_shifts]
    avr_holiday = (total_holiday_demand - adj_sum * hol_rate) / num_doctors

    # ── Build model ───────────────────────────────────────────────────────────
    model = cp_model.CpModel()

    shifts = {}
    for n in all_doctors:
        for d in all_days:
            for s in all_shifts:
                shifts[(n, d, s)] = model.NewBoolVar(f"s_{n}_{d}_{s}")

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
        n_rest    = get_rule(n, "rule_n_rest", 1)         # Mandatory rest days after N-block
        n_gap     = get_rule(n, "rule_n_gap", 0)          # Min gap before next N after N-block

        # rule0: max shifts per day
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
            for d in range(num_days - 1):
                model.Add(sum(shifts[(n,d+p,s)] for p in range(2) for s in all_shifts) < 4)
        elif r0 in (3, 5):
            for d in all_days:
                model.AddBoolOr([shifts[(n,d,0)].Not(), shifts[(n,d,1)], shifts[(n,d,2)].Not()])
            if r0 == 5:
                for d in [x for x in all_days if x not in holiday]:
                    model.AddAtMostOne(shifts[(n,d,s)] for s in all_shifts)
            for d in range(num_days - 1):
                model.Add(sum(shifts[(n,d+p,s)] for p in range(2) for s in all_shifts) < 4)

        # ── N-block constraints ───────────────────────────────────────────────
        # n_max  : N 연속 최대 허용 길이 (1=NN불가, 2=NNN불가, 3=NNNN불가)
        # n_rest : N뭉치 끝난 후 완전 Off 의무일 수
        # n_gap  : N뭉치 끝난 날로부터 총 며칠 후 N이 가능한지 (n_gap >= n_rest)
        #
        # 예) n_max=2, n_rest=2, n_gap=3
        #   N N | O O | D/E가능 | N가능  (3일째부터 N)

        # 1) Max N block length: (n_max+1)개 연속 N 금지
        block_len = n_max + 1
        if block_len <= num_days:
            for d in range(num_days - block_len + 1):
                model.Add(
                    sum(shifts[(n, d+i, 2)] for i in range(block_len)) < block_len
                )

        # 2) 뭉치 끝 지점(e) 감지: N[e]=True AND (e==마지막날 OR N[e+1]=False)
        #    → end+1..end+n_rest: 완전 Off
        #    → end+n_rest+1..end+n_gap: N만 금지
        #
        #    "N[e]=T and N[e+1]=F → 제약" 을
        #    CP-SAT 로: AddBoolOr([N[e].Not, N[e+1], shifts[dd,s].Not])
        #    마지막 날(e=num_days-1): AddBoolOr([N[e].Not, shifts[dd,s].Not])

        for e in range(num_days):  # e = 뭉치 마지막 날 후보
            # 완전 휴무
            for r in range(1, n_rest + 1):
                dd = e + r
                if dd >= num_days:
                    break
                for s in all_shifts:
                    if e + 1 < num_days:
                        # N[e]=T and N[e+1]=F → shifts[dd,s]=F
                        model.AddBoolOr([shifts[(n,e,2)].Not(), shifts[(n,e+1,2)], shifts[(n,dd,s)].Not()])
                    else:
                        # 마지막날 N이면 무조건
                        model.AddBoolOr([shifts[(n,e,2)].Not(), shifts[(n,dd,s)].Not()])

            # N만 금지
            for g in range(n_rest + 1, n_gap + 1):
                dd = e + g
                if dd >= num_days:
                    break
                if e + 1 < num_days:
                    model.AddBoolOr([shifts[(n,e,2)].Not(), shifts[(n,e+1,2)], shifts[(n,dd,2)].Not()])
                else:
                    model.AddBoolOr([shifts[(n,e,2)].Not(), shifts[(n,dd,2)].Not()])

        # rule2: no D after E
        if r2:
            for d in range(num_days - 1):
                model.Add(shifts[(n,d+1,0)] == 0).OnlyEnforceIf(shifts[(n,d,1)])

        # rule3: no EEE
        if r3:
            for d in range(num_days - 2):
                model.AddBoolOr([shifts[(n,d,1)].Not(), shifts[(n,d+1,1)].Not(), shifts[(n,d+2,1)].Not()])

        # rule4: no 3 evenings in 4 days
        if r4:
            for d in range(num_days - 3):
                model.AddBoolOr([shifts[(n,d,1)].Not(), shifts[(n,d+1,1)].Not(), shifts[(n,d+2,1)], shifts[(n,d+3,1)].Not()])
                model.AddBoolOr([shifts[(n,d,1)].Not(), shifts[(n,d+1,1)], shifts[(n,d+2,1)].Not(), shifts[(n,d+3,1)].Not()])

        # rule5: max consecutive working days
        # r5 means "up to r5 consecutive working days are allowed".
        # Therefore we forbid any (r5 + 1)-day window in which all days are worked.
        # Example: r5=6 allows 6 consecutive working days, but not 7.
        if r5 in (3,4,5,6,7) and num_days >= r5 + 1:
            for d in range(num_days - r5):
                worked_days = []
                for p in range(r5 + 1):
                    worked = model.NewBoolVar(f"worked_{n}_{d}_{p}")
                    model.AddMaxEquality(worked, [shifts[(n, d+p, s)] for s in all_shifts])
                    worked_days.append(worked)
                model.Add(sum(worked_days) <= r5)

        # rule6: max shifts in any 7-day window
        # r6 means "up to r6 shifts are allowed in a 7-day window".
        # Example: r6=6 allows 6 shifts, but not 7.
        if r6 > 0 and num_days >= 7:
            for d in range(num_days - 6):
                model.Add(sum(shifts[(n,d+p,s)] for p in range(7) for s in all_shifts) <= r6)

        # rule7: no DDD
        if r7:
            for d in range(num_days - 2):
                model.AddBoolOr([shifts[(n,d,0)].Not(), shifts[(n,d+1,0)].Not(), shifts[(n,d+2,0)].Not()])

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

    # ── Soft balancing (deviation minimization) ───────────────────────────────
    k  = model.NewIntVar(0, 6, 'k_DE')
    k1 = model.NewIntVar(0, 6, 'k1_holiday')
    k2 = model.NewIntVar(0, 6, 'k2_total')
    k3 = model.NewIntVar(0, 6, 'k3_N')

    for n in all_doctors:
        adj = shift_adj.get(n, 0)

        num_s = [sum(shifts[(n,d,s)] for d in all_days) for s in all_shifts]
        num_total = sum(num_s)
        hol_worked = sum(shifts[(n,d,s)] for d in holiday for s in all_shifts)

        dev_de   = [model.NewIntVar(0, 6, f'dde_{n}_{x}') for x in range(2)]
        dev_hol  = [model.NewIntVar(0, 6, f'dhol_{n}_{x}') for x in range(2)]
        dev_tot  = [model.NewIntVar(0, 6, f'dtot_{n}_{x}') for x in range(2)]
        dev_N    = [model.NewIntVar(0, 6, f'dN_{n}_{x}') for x in range(2)]

        sum_de  = model.NewIntVar(0, 12, f'sde_{n}')
        sum_hol = model.NewIntVar(0, 12, f'shol_{n}')
        sum_tot = model.NewIntVar(0, 12, f'stot_{n}')
        sum_N   = model.NewIntVar(0, 12, f'sN_{n}')

        model.Add(sum_de  == dev_de[0]  + dev_de[1]);  model.Add(sum_de  <= k)
        model.Add(sum_hol == dev_hol[0] + dev_hol[1]); model.Add(sum_hol <= k1)
        model.Add(sum_tot == dev_tot[0] + dev_tot[1]); model.Add(sum_tot <= k2)
        model.Add(sum_N   == dev_N[0]   + dev_N[1]);   model.Add(sum_N   <= k3)

        # total
        model.Add(int(avr_duty + adj) - dev_tot[0] <= num_total)
        model.Add(num_total <= _max_avr(avr_duty + adj) + dev_tot[1])

        # D
        model.Add(int(avr_s[0] + adj * s_rate[0]) - dev_de[0] <= num_s[0])
        model.Add(num_s[0] <= _max_avr(avr_s[0] + adj * s_rate[0]) + dev_de[1])

        # E
        model.Add(int(avr_s[1] + adj * s_rate[1]) - dev_de[0] <= num_s[1])
        model.Add(num_s[1] <= _max_avr(avr_s[1] + adj * s_rate[1]) + dev_de[1])

        # N
        model.Add(int(avr_s[2] + adj * s_rate[2]) - dev_N[0] <= num_s[2])
        model.Add(num_s[2] <= _max_avr(avr_s[2] + adj * s_rate[2]) + dev_N[1])

        # Holiday
        model.Add(int(avr_holiday + adj * hol_rate) - dev_hol[0] <= hol_worked)
        model.Add(hol_worked <= _max_avr(avr_holiday + adj * hol_rate) + dev_hol[1])

    # ── Objective ─────────────────────────────────────────────────────────────
    junior_excess_total = sum(junior_excess_vars) if junior_excess_vars else 0
    junior_penalty = junior_excess_total * junior_penalty_weight
    balance_penalty = (
        k * weight_de_dev
        + k1 * weight_holiday_dev
        + k2 * weight_total_dev
        + k3 * weight_n_dev
    )
    adv = balance_penalty + junior_penalty
    is_multi = "다중" in solver_mode

    # In main mode, minimize adv; in multi mode, treat adv as a constraint only.
    if not is_multi:
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
            tue_n = sum(sol_fn(shifts[(n,d,2)]) for d in all_days if day_names_list[d] == '화')
            fri_n = sum(sol_fn(shifts[(n,d,2)]) for d in all_days if day_names_list[d] == '금')
            rows.append({
                'Name': names[n],
                'Grade': grades.get(n, 2),
                'Senior': 'Y' if grades.get(n, 2) >= senior_min_grade else '',
                'Junior': 'Y' if grades.get(n, 2) <= junior_max_grade else '',
                'D': d_cnt, 'E': e_cnt, 'N': n_cnt,
                'Total': tot, 'Holiday': hol,
                'Tue_N': tue_n, 'Fri_N': fri_n,
                '주간평균hr': round((d_cnt*8 + e_cnt*9 + n_cnt*8) / num_days * 7, 2),
            })
        return sol, pd.DataFrame(rows)

    metrics = []

    def _metric_value(expr_or_int):
        return int(expr_or_int) if isinstance(expr_or_int, int) else solver.Value(expr_or_int)

    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.UNKNOWN):
        raise RuntimeError("최적해가 없습니다.")

    if not is_multi:
        sol, summ = _extract(solver.Value)
        solutions.append(sol)
        summaries.append(summ)
        metrics.append({
            "adv": solver.Value(adv),
            "k": solver.Value(k),
            "k1": solver.Value(k1),
            "k2": solver.Value(k2),
            "k3": solver.Value(k3),
            "junior_excess": _metric_value(junior_excess_total),
            "junior_penalty": _metric_value(junior_penalty),
            "senior_min_grade": senior_min_grade,
            "senior_min_count": senior_min_count,
            "junior_max_grade": junior_max_grade,
            "junior_soft_max_count": junior_soft_max_count,
            "junior_penalty_weight": junior_penalty_weight,
            "weight_de_dev": weight_de_dev,
            "weight_holiday_dev": weight_holiday_dev,
            "weight_total_dev": weight_total_dev,
            "weight_n_dev": weight_n_dev,
            "balance_penalty": solver.Value(balance_penalty),
        })
    else:
        model.Add(adv <= adv_limit)
        solver.parameters.enumerate_all_solutions = True

        class _CB(cp_model.CpSolverSolutionCallback):
            def __init__(self):
                super().__init__()
                self._count = 0

            def on_solution_callback(self):
                sol, summ = _extract(self.Value)
                solutions.append(sol)
                summaries.append(summ)
                metrics.append({
                    "adv": self.Value(adv),
                    "k": self.Value(k),
                    "k1": self.Value(k1),
                    "k2": self.Value(k2),
                    "k3": self.Value(k3),
                    "junior_excess": self.Value(junior_excess_total) if junior_excess_vars else 0,
                    "junior_penalty": self.Value(junior_penalty) if junior_excess_vars else 0,
                    "senior_min_grade": senior_min_grade,
                    "senior_min_count": senior_min_count,
                    "junior_max_grade": junior_max_grade,
                    "junior_soft_max_count": junior_soft_max_count,
                    "junior_penalty_weight": junior_penalty_weight,
                    "weight_de_dev": weight_de_dev,
                    "weight_holiday_dev": weight_holiday_dev,
                    "weight_total_dev": weight_total_dev,
                    "weight_n_dev": weight_n_dev,
                    "balance_penalty": self.Value(balance_penalty),
                })
                self._count += 1
                if self._count >= sol_limit:
                    self.StopSearch()

        cb = _CB()
        solver.Solve(model, cb)

        if not solutions:
            raise RuntimeError("조건을 만족하는 솔루션이 없습니다. adv_limit 또는 규칙을 완화해 보세요.")

    return solutions, summaries, metrics