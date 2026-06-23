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
    solver_mode  = params["solver_mode"]
    time_max     = int(params["time_max"])
    sol_limit    = int(params["sol_limit"])
    adv_limit    = int(params["adv_limit"])

    num_doctors = len(names)
    num_shifts  = 3
    all_doctors = range(num_doctors)
    all_days    = range(num_days)
    all_shifts  = range(num_shifts)

    day_names_list = [_get_day_label(start_date, d) for d in all_days]

    # duty_requests[d][s]
    duty_requests = [[duty_req_raw.get(d, [1,1,1])[s] for s in all_shifts] for d in all_days]

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

    # Night → next day only N or off (no D or E after N)
    for n in all_doctors:
        for d in range(num_days - 1):
            model.AddBoolOr([shifts[(n,d,2)].Not(), shifts[(n,d+1,0)].Not()])
            model.AddBoolOr([shifts[(n,d,2)].Not(), shifts[(n,d+1,1)].Not()])

    # Per-doctor rules
    for n in all_doctors:
        r0        = get_rule(n, "rule0", 1)
        r2        = get_rule(n, "rule2", 1)
        r3        = get_rule(n, "rule3", 1)
        r4        = get_rule(n, "rule4", 1)
        r5        = get_rule(n, "rule5", 5)
        r6        = get_rule(n, "rule6", 0)
        r7        = get_rule(n, "rule7", 1)
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
        # 1) Max N block length
        #    n_max=1 → NN 금지,  n_max=2 → NNN 금지,  n_max=3 → NNNN 금지
        block_len = n_max + 1  # forbidden run length
        if block_len <= num_days:
            for d in range(num_days - block_len + 1):
                model.Add(
                    sum(shifts[(n, d+i, 2)] for i in range(block_len)) < block_len
                )

        # 2) After an N-block ends (i.e. day d is N but day d+block is not N,
        #    meaning the block just finished), enforce:
        #      a) n_rest days of full rest (no D/E/N)  -- already guaranteed by
        #         the base rule "N→next day only N or off", but n_rest > block means
        #         extra rest beyond the block itself.
        #      b) n_gap days before next N is allowed.
        #
        # Strategy: for every possible N-block end position, add the post-block
        # constraints.  We identify "block of exactly length L ending at day e"
        # by requiring shifts[n,e-L+1..e] all N AND shifts[n,e+1] not N (or e==num_days-1).
        # To keep the model tractable we use a simpler sufficient condition:
        # For each day d that is N, look back to find the block it belongs to and
        # enforce rest/gap after the block end.
        #
        # Practical encoding: for each day d and block length L (1..n_max),
        # "block of length L starting at d": N[d..d+L-1] all true, N[d-1]=False (or d=0), N[d+L]=False (or end).
        # Then forbid work during rest period and N during gap period.

        for blen in range(1, n_max + 1):
            for d in range(num_days):
                end = d + blen - 1  # last night of the block
                if end >= num_days:
                    break

                # Conditions that identify this exact block
                block_vars = [shifts[(n, d+i, 2)] for i in range(blen)]

                # rest days after block end
                if n_rest > 0:
                    for r in range(1, n_rest + 1):
                        dd = end + r
                        if dd < num_days:
                            for s in all_shifts:
                                # If all block_vars are True → shifts[dd,s] must be 0
                                model.AddBoolOr(
                                    [v.Not() for v in block_vars] + [shifts[(n, dd, s)].Not()]
                                )

                # gap before next N (n_gap days after rest period ends)
                if n_gap > 0:
                    gap_start = end + n_rest + 1
                    for g in range(n_gap):
                        dd = gap_start + g
                        if dd < num_days:
                            model.AddBoolOr(
                                [v.Not() for v in block_vars] + [shifts[(n, dd, 2)].Not()]
                            )

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
        if r5 in (3,4,5,6):
            for d in range(num_days - (r5 - 1)):
                model.Add(sum(shifts[(n,d+p,s)] for p in range(r5) for s in all_shifts) < r5)

        # rule6: max shifts in 7 days
        if r6 > 0:
            for d in range(num_days - 7):
                model.Add(sum(shifts[(n,d+p,s)] for p in range(7) for s in all_shifts) < r6)

        # rule7: no DDD
        if r7:
            for d in range(num_days - 2):
                model.AddBoolOr([shifts[(n,d,0)].Not(), shifts[(n,d+1,0)].Not(), shifts[(n,d+2,0)].Not()])

    # Duty demand constraints
    for d in all_days:
        for s in all_shifts:
            model.Add(sum(shifts[(n,d,s)] for n in all_doctors) == duty_requests[d][s])

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
    adv = k + k1*3 + k2*5 + k3*5
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
                'Name': names[n], 'D': d_cnt, 'E': e_cnt, 'N': n_cnt,
                'Total': tot, 'Holiday': hol,
                'Tue_N': tue_n, 'Fri_N': fri_n,
                '주간평균hr': round((d_cnt*8 + e_cnt*9 + n_cnt*8) / num_days * 7, 2),
            })
        return sol, pd.DataFrame(rows)

    metrics = []

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
                })
                self._count += 1
                if self._count >= sol_limit:
                    self.StopSearch()

        cb = _CB()
        solver.Solve(model, cb)

        if not solutions:
            raise RuntimeError("조건을 만족하는 솔루션이 없습니다. adv_limit 또는 규칙을 완화해 보세요.")

    return solutions, summaries, metrics