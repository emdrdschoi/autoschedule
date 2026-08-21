"""
scheduler.py
OR-Tools CP-SAT solver for medical shift scheduling.
Translated from the Google Colab prototype.
"""

from __future__ import annotations
from typing import Any
import pandas as pd
import time
import threading
from datetime import date, timedelta

SCHEDULER_API_VERSION = '2026-08-21-v12.19-search-diagnostics'

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


def _build_personal_hard_model(params: dict[str, Any], n: int, *, total_target: int | None = None,
                               objective: str | None = None):
    """Build a one-person CP-SAT model that mirrors the scheduler's personal hard rules.

    This is used only by diagnostic mode.  It deliberately excludes group-level staffing/
    grade constraints and soft balancing, but includes every hard condition that can limit
    one person's monthly total:
      - PreviousSchedule boundary context
      - D/E/N/x/a requests
      - closed duties (DutyRequests == 0)
      - all personal sequence rules
      - fixed_D/E/N, minimum_N, maximum_N and maximum_total

    fixed_Total itself is *not* added unless ``total_target`` is supplied.  This lets the
    diagnostic solver ask both "is this exact fixed_Total feasible?" and "what is the true
    personal maximum/minimum under the other hard rules?".
    """
    if not ORTOOLS_AVAILABLE:
        return None, None, None, "ORTOOLS_UNAVAILABLE"

    names = list(params.get("doctors", []))
    if not (0 <= n < len(names)):
        return None, None, None, "INVALID_DOCTOR"

    num_days = max(0, int(params.get("num_days", 0)))
    previous_days = max(0, int(params.get("previous_schedule_days", 5)))
    day_types = {int(k): v for k, v in (params.get("day_types", {}) or {}).items()}
    duty_raw = {int(k): list(v) for k, v in (params.get("duty_requests", {}) or {}).items()}
    sr_raw = params.get("shift_requests", {}) or {}
    previous_raw = params.get("previous_schedule", {}) or {}
    rules_raw = {int(k): (v or {}) for k, v in (params.get("rules", {}) or {}).items()}
    shift_counts_raw = params.get("shift_counts", {}) or {}
    shift_counts = {int(k): (v or {}) for k, v in shift_counts_raw.items()}
    maximum_total = {int(k): int(v) for k, v in (params.get("maximum_total", {}) or {}).items()}
    minimum_n = {int(k): int(v) for k, v in (params.get("minimum_N", {}) or {}).items()}
    maximum_n = {int(k): int(v) for k, v in (params.get("maximum_N", {}) or {}).items()}

    def get_rule(key: str, default: int) -> int:
        try:
            return int(rules_raw.get(n, {}).get(key, default))
        except (TypeError, ValueError):
            return int(default)

    model = cp_model.CpModel()
    all_days = range(num_days)
    all_shifts = range(3)
    shifts = {(d, s): model.NewBoolVar(f"diag_s_{n}_{d}_{s}") for d in all_days for s in all_shifts}

    # Fixed previous-schedule context.
    history = [[0, 0, 0] for _ in range(previous_days)]
    for key, cell in previous_raw.items():
        try:
            n_str, h_str = str(key).split(",", 1)
            nn, h = int(n_str), int(h_str)
        except (TypeError, ValueError):
            continue
        if nn == n and 0 <= h < previous_days:
            history[h] = [int(x) for x in _parse_actual_shift(cell)]

    history_vars = {}
    for h in range(previous_days):
        for s in all_shifts:
            v = model.NewBoolVar(f"diag_hist_{n}_{h}_{s}")
            model.Add(v == int(history[h][s]))
            history_vars[(h, s)] = v

    timeline_len = previous_days + num_days
    current_offset = previous_days

    def timeline_shift(t: int, s: int):
        if t < current_offset:
            return history_vars[(t, s)]
        return shifts[(t - current_offset, s)]

    def sequence_window_starts(window_len: int):
        if window_len <= 0 or timeline_len < window_len:
            return range(0)
        first = max(0, current_offset - window_len + 1)
        return range(first, timeline_len - window_len + 1)

    timeline_worked = {}
    for t in range(timeline_len):
        worked = model.NewBoolVar(f"diag_worked_{n}_{t}")
        model.AddMaxEquality(worked, [timeline_shift(t, s) for s in all_shifts])
        timeline_worked[t] = worked

    # Personal rules -- intentionally kept in lockstep with build_and_solve().
    r0 = get_rule("rule_max_shifts_per_day", 1)
    r2 = get_rule("rule_no_day_after_eve", 1)
    r3 = get_rule("rule_no_3eve_consec", 0)
    r4 = get_rule("rule_no_3eve_in_4days", 0)
    r5 = get_rule("rule_max_consec_days", 5)
    r6 = get_rule("rule_max_shifts_per_week", 5)
    r7 = get_rule("rule_no_3day_consec", 0)
    n_max = get_rule("rule_n_block_max", 2)
    n_rest = get_rule("rule_n_rest", 2)
    n_gap = get_rule("rule_n_gap", 4)

    holiday = [d for d, t in day_types.items() if t in ("토", "일", "공")]

    if r0 == 1:
        for d in all_days:
            model.AddAtMostOne(shifts[(d, s)] for s in all_shifts)
    elif r0 in (2, 4):
        for d in all_days:
            model.AddBoolOr([shifts[(d,0)].Not(), shifts[(d,1)], shifts[(d,2)].Not()])
            model.AddBoolOr([shifts[(d,0)].Not(), shifts[(d,1)].Not(), shifts[(d,2)].Not()])
        if r0 == 4:
            for d in [x for x in all_days if x not in holiday]:
                model.AddAtMostOne(shifts[(d, s)] for s in all_shifts)
        for t in sequence_window_starts(2):
            model.Add(sum(timeline_shift(t+p, s) for p in range(2) for s in all_shifts) < 4)
    elif r0 in (3, 5):
        for d in all_days:
            model.AddBoolOr([shifts[(d,0)].Not(), shifts[(d,1)], shifts[(d,2)].Not()])
        if r0 == 5:
            for d in [x for x in all_days if x not in holiday]:
                model.AddAtMostOne(shifts[(d, s)] for s in all_shifts)
        for t in sequence_window_starts(2):
            model.Add(sum(timeline_shift(t+p, s) for p in range(2) for s in all_shifts) < 4)

    block_len = n_max + 1
    for t in sequence_window_starts(block_len):
        model.Add(sum(timeline_shift(t+i, 2) for i in range(block_len)) < block_len)

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
                        timeline_shift(e,2).Not(), timeline_shift(e+1,2), timeline_shift(dd,s).Not()
                    ])
                else:
                    model.AddBoolOr([timeline_shift(e,2).Not(), timeline_shift(dd,s).Not()])
        for g in range(n_rest + 1, n_gap + 1):
            dd = e + g
            if dd >= timeline_len:
                break
            if dd < current_offset:
                continue
            if e + 1 < timeline_len:
                model.AddBoolOr([
                    timeline_shift(e,2).Not(), timeline_shift(e+1,2), timeline_shift(dd,2).Not()
                ])
            else:
                model.AddBoolOr([timeline_shift(e,2).Not(), timeline_shift(dd,2).Not()])

    if r2:
        for t in sequence_window_starts(2):
            model.Add(timeline_shift(t+1,0) == 0).OnlyEnforceIf(timeline_shift(t,1))
    if r3:
        for t in sequence_window_starts(3):
            model.AddBoolOr([timeline_shift(t,1).Not(), timeline_shift(t+1,1).Not(), timeline_shift(t+2,1).Not()])
    if r4:
        for t in sequence_window_starts(4):
            model.AddBoolOr([
                timeline_shift(t,1).Not(), timeline_shift(t+1,1).Not(), timeline_shift(t+2,1), timeline_shift(t+3,1).Not()
            ])
            model.AddBoolOr([
                timeline_shift(t,1).Not(), timeline_shift(t+1,1), timeline_shift(t+2,1).Not(), timeline_shift(t+3,1).Not()
            ])
    if r5 in (3, 4, 5, 6, 7):
        for t in sequence_window_starts(r5 + 1):
            model.Add(sum(timeline_worked[t+p] for p in range(r5 + 1)) <= r5)
    if r6 > 0:
        for t in sequence_window_starts(7):
            model.Add(sum(timeline_shift(t+p, s) for p in range(7) for s in all_shifts) <= r6)
    if r7:
        for t in sequence_window_starts(3):
            model.AddBoolOr([timeline_shift(t,0).Not(), timeline_shift(t+1,0).Not(), timeline_shift(t+2,0).Not()])

    # Current-month request / closed-duty hard constraints.
    for d in all_days:
        cell = str(sr_raw.get(f"{n},{d}", "") or "").strip()
        cannot = _parse_shift_request(cell)
        must = _parse_shift_wish(cell)
        needs = list(duty_raw.get(d, [0, 0, 0]))
        if len(needs) < 3:
            needs = (needs + [0, 0, 0])[:3]
        for s in all_shifts:
            if int(needs[s]) <= 0:
                model.Add(shifts[(d, s)] == 0)
            if cannot[s]:
                model.Add(shifts[(d, s)] == 0)
            if must[s]:
                model.Add(shifts[(d, s)] == 1)

    sc = shift_counts.get(n, {}) if isinstance(shift_counts.get(n, {}), dict) else {}
    num_s = []
    for s, sk in enumerate(("D", "E", "N")):
        count_var = model.NewIntVar(0, num_days, f"diag_count_{n}_{sk}")
        model.Add(count_var == sum(shifts[(d, s)] for d in all_days))
        num_s.append(count_var)
        try:
            fixed_val = int(sc.get(sk, -1))
        except (TypeError, ValueError):
            fixed_val = -1
        if fixed_val >= 0:
            model.Add(count_var == fixed_val)

    num_total = model.NewIntVar(0, num_days * 3, f"diag_total_{n}")
    model.Add(num_total == sum(num_s))

    min_n = int(minimum_n.get(n, -1))
    if min_n >= 0:
        model.Add(num_s[2] >= min_n)
    max_n = int(maximum_n.get(n, -1))
    if max_n >= 0:
        model.Add(num_s[2] <= max_n)
    max_total = int(maximum_total.get(n, -1))
    if max_total >= 0:
        model.Add(num_total <= max_total)
    if total_target is not None:
        model.Add(num_total == int(total_target))

    if objective == "max":
        model.Maximize(num_total)
    elif objective == "min":
        model.Minimize(num_total)

    return model, num_total, (r0, r2, r3, r4, r5, r6, r7, n_max, n_rest, n_gap), "OK"


def _solve_personal_total_model(params: dict[str, Any], n: int, *, total_target: int | None = None,
                                objective: str | None = None) -> dict[str, Any]:
    """Solve the exact one-person diagnostic model."""
    model, num_total, rule_tuple, build_status = _build_personal_hard_model(
        params, n, total_target=total_target, objective=objective
    )
    if build_status != "OK":
        return {"status": build_status, "value": None, "optimal": False, "rules": rule_tuple}

    solver = cp_model.CpSolver()
    # One-person models are tiny.  A short but generous limit avoids diagnostic mode
    # becoming slow even with many nurses while still giving an exact optimum in practice.
    solver.parameters.max_time_in_seconds = 3.0
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    status_name = solver.StatusName(status)
    feasible = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    value = int(solver.Value(num_total)) if feasible else None
    return {
        "status": status_name,
        "value": value,
        "optimal": status == cp_model.OPTIMAL,
        "feasible": feasible,
        "rules": rule_tuple,
    }


def _personal_diagnostic_limit_summary(params: dict[str, Any], n: int) -> str:
    """Compact human-readable summary of the major personal hard limits."""
    start_date = date.fromisoformat(str(params.get("start_date")))
    num_days = max(0, int(params.get("num_days", 0)))
    sr_raw = params.get("shift_requests", {}) or {}
    rules_raw = {int(k): (v or {}) for k, v in (params.get("rules", {}) or {}).items()}
    previous_days = max(0, int(params.get("previous_schedule_days", 5)))
    previous_raw = params.get("previous_schedule", {}) or {}

    def get_rule(key: str, default: int) -> int:
        try:
            return int(rules_raw.get(n, {}).get(key, default))
        except (TypeError, ValueError):
            return int(default)

    full_off_dates = []
    for d in range(num_days):
        cell = str(sr_raw.get(f"{n},{d}", "") or "").strip()
        if all(_parse_shift_request(cell)):
            full_off_dates.append((start_date + timedelta(days=d)).strftime("%m/%d"))

    history_txt = []
    for h in range(previous_days):
        cell = previous_raw.get(f"{n},{h}", "")
        flags = _parse_actual_shift(cell)
        label = "".join(sk for sk, v in zip(("D","E","N"), flags) if v) or "OFF"
        hist_date = start_date - timedelta(days=previous_days - h)
        history_txt.append(f"{hist_date.strftime('%m/%d')} {label}")

    r5 = get_rule("rule_max_consec_days", 5)
    r6 = get_rule("rule_max_shifts_per_week", 5)
    n_max = get_rule("rule_n_block_max", 2)
    n_rest = get_rule("rule_n_rest", 2)
    n_gap = get_rule("rule_n_gap", 4)

    bits = []
    if full_off_dates:
        shown = ", ".join(full_off_dates[:8])
        if len(full_off_dates) > 8:
            shown += f" 외 {len(full_off_dates)-8}일"
        bits.append(f"완전휴무 요청 {len(full_off_dates)}일({shown})")
    if r6 > 0:
        bits.append(f"7일 최대 {r6}근무")
    if r5 > 0:
        bits.append(f"연속근무 최대 {r5}일")
    bits.append(f"N block≤{n_max}, N-rest={n_rest}, N-gap={n_gap}")
    if history_txt:
        bits.append("직전=" + " / ".join(history_txt))
    return "; ".join(bits)



def diagnose_hard_conflicts(params: dict[str, Any]) -> pd.DataFrame:
    """Detect definite contradictions among hard-coded inputs before solving.

    This intentionally reports only *provable* conflicts from fixed/known facts:
    - completed previous schedule,
    - uppercase D/E/N must-work requests,
    - x/a/lowercase cannot-work requests,
    - zero duty demand,
    - fixed D/E/N/Total, maximum_N and maximum_total,
    - personal sequence hard rules that are already forced by those facts.

    It does not claim that an otherwise empty/optional day will be worked, so the
    table is conservative: rows shown here are genuine contradictions, while an
    empty table does not guarantee the full model is feasible.
    """
    names = list(params.get("doctors", []))
    num_doctors = len(names)
    num_days = max(0, int(params.get("num_days", 0)))
    start_date = date.fromisoformat(str(params.get("start_date")))
    previous_days = max(0, int(params.get("previous_schedule_days", 5)))
    previous_raw = params.get("previous_schedule", {}) or {}
    sr_raw = params.get("shift_requests", {}) or {}
    rules_raw = {int(k): (v or {}) for k, v in (params.get("rules", {}) or {}).items()}
    day_types = {int(k): v for k, v in (params.get("day_types", {}) or {}).items()}
    duty_raw = {int(k): list(v) for k, v in (params.get("duty_requests", {}) or {}).items()}
    shift_counts_raw = params.get("shift_counts", {}) or {}
    shift_counts = {int(k): (v or {}) for k, v in shift_counts_raw.items()}
    maximum_total = {int(k): int(v) for k, v in (params.get("maximum_total", {}) or {}).items()}
    minimum_n = {int(k): int(v) for k, v in (params.get("minimum_N", {}) or {}).items()}
    maximum_n = {int(k): int(v) for k, v in (params.get("maximum_N", {}) or {}).items()}

    shift_keys = ["D", "E", "N"]
    rows: list[dict[str, Any]] = []
    seen: set[tuple] = set()

    def get_rule(n: int, key: str, default: int) -> int:
        try:
            return int(rules_raw.get(n, {}).get(key, default))
        except (TypeError, ValueError):
            return int(default)

    def date_for_t(t: int) -> date:
        return start_date + timedelta(days=t - previous_days)

    def dlabel(t: int) -> str:
        d = date_for_t(t)
        return f"{d.strftime('%m/%d')}({_get_day_label(d, 0)})"

    def shift_text(flags) -> str:
        txt = "".join(k for k, v in zip(shift_keys, flags) if v)
        return txt or "OFF"

    def add_conflict(n: int, *, day_t: int | None, rule: str, explanation: str,
                     related: str = "", suggestion: str = ""):
        key = (n, day_t, rule, explanation, related)
        if key in seen:
            return
        seen.add(key)
        rows.append({
            "상태": "확정 충돌",
            "이름": names[n] if 0 <= n < len(names) else f"doctor_{n}",
            "날짜": dlabel(day_t) if day_t is not None else "월 전체",
            "충돌 규칙": rule,
            "설명": explanation,
            "관련 일정": related,
            "수정 제안": suggestion,
        })

    # Exact completed history.
    history = [[[0, 0, 0] for _ in range(previous_days)] for _ in range(num_doctors)]
    for key, cell in previous_raw.items():
        try:
            n_str, h_str = str(key).split(",")
            n, h = int(n_str), int(h_str)
        except (ValueError, TypeError):
            continue
        if 0 <= n < num_doctors and 0 <= h < previous_days:
            history[n][h] = [int(x) for x in _parse_actual_shift(cell)]

    timeline_len = previous_days + num_days
    current_offset = previous_days

    def sequence_window_starts(window_len: int):
        if window_len <= 0 or timeline_len < window_len:
            return range(0)
        first = max(0, current_offset - window_len + 1)
        return range(first, timeline_len - window_len + 1)

    for n in range(num_doctors):
        r0 = get_rule(n, "rule_max_shifts_per_day", 1)
        r2 = get_rule(n, "rule_no_day_after_eve", 1)
        r3 = get_rule(n, "rule_no_3eve_consec", 0)
        r4 = get_rule(n, "rule_no_3eve_in_4days", 0)
        r5 = get_rule(n, "rule_max_consec_days", 5)
        r6 = get_rule(n, "rule_max_shifts_per_week", 5)
        r7 = get_rule(n, "rule_no_3day_consec", 0)
        n_max = get_rule(n, "rule_n_block_max", 2)
        n_rest = get_rule(n, "rule_n_rest", 2)
        n_gap = get_rule(n, "rule_n_gap", 4)

        sc = shift_counts.get(n, {}) if isinstance(shift_counts.get(n, {}), dict) else {}
        fixed_shift = {}
        for sk in shift_keys:
            try:
                fixed_shift[sk] = int(sc.get(sk, -1))
            except (TypeError, ValueError):
                fixed_shift[sk] = -1
        try:
            fixed_total = int(sc.get("Total", -1))
        except (TypeError, ValueError):
            fixed_total = -1
        max_total = int(maximum_total.get(n, -1))
        min_n = int(minimum_n.get(n, -1))
        max_n = int(maximum_n.get(n, -1))

        # minimum forced/current facts and definitely-impossible shifts.
        on = [[0, 0, 0] for _ in range(timeline_len)]
        off = [[False, False, False] for _ in range(timeline_len)]
        for h in range(previous_days):
            for s_idx in range(3):
                on[h][s_idx] = int(history[n][h][s_idx])
                off[h][s_idx] = not bool(history[n][h][s_idx])

        current_forced_counts = [0, 0, 0]
        current_forced_total = 0

        for d in range(num_days):
            t = current_offset + d
            cell = str(sr_raw.get(f"{n},{d}", "") or "").strip()
            forced = [int(x) for x in _parse_shift_wish(cell)]
            cannot = [bool(x) for x in _parse_shift_request(cell)]
            needs = list(duty_raw.get(d, [0, 0, 0]))
            if len(needs) < 3:
                needs = (needs + [0, 0, 0])[:3]

            for s_idx in range(3):
                on[t][s_idx] = forced[s_idx]
                off[t][s_idx] = cannot[s_idx] or int(needs[s_idx]) <= 0
                if fixed_shift[shift_keys[s_idx]] == 0:
                    off[t][s_idx] = True
                if fixed_total == 0 or max_total == 0:
                    off[t][s_idx] = True

                if forced[s_idx]:
                    current_forced_counts[s_idx] += 1
                    current_forced_total += 1
                    if cannot[s_idx]:
                        add_conflict(
                            n, day_t=t, rule="근무 요청 자체 충돌",
                            explanation=f"{shift_keys[s_idx]}가 대문자로 hard-fixed되어 있지만 같은 셀에서 근무불가(a/x/소문자 불가)도 적용됩니다.",
                            related=f"{dlabel(t)} 요청='{cell}'",
                            suggestion="대문자 고정근무와 불가표시 중 하나를 제거하세요.",
                        )
                    if int(needs[s_idx]) <= 0:
                        add_conflict(
                            n, day_t=t, rule="Duty 필요인원=0 vs hard-fixed",
                            explanation=f"{shift_keys[s_idx]} 필요인원이 0명인데 {shift_keys[s_idx]}가 hard-fixed되어 있습니다.",
                            related=f"{dlabel(t)} {shift_keys[s_idx]} 필요={int(needs[s_idx])}, 요청='{cell}'",
                            suggestion="해당 hard-fixed를 제거하거나 Duty 필요인원을 1명 이상으로 변경하세요.",
                        )

            # rule_max_shifts_per_day may make non-forced shifts definitely OFF.
            forced_count = sum(forced)
            dtype = day_types.get(d, "평일")
            is_holiday = dtype in ("토", "일", "공")
            same_day_bad = False
            why = ""
            if r0 == 1 and forced_count > 1:
                same_day_bad, why = True, "하루 최대 1근무인데 여러 근무가 동시에 hard-fixed되었습니다."
            elif r0 in (2, 4):
                if forced_count == 3:
                    same_day_bad, why = True, "D/E/N 3개 동시근무는 허용되지 않습니다."
                elif forced[0] and forced[2] and not forced[1]:
                    same_day_bad, why = True, "D+N 조합은 E 없이 허용되지 않습니다."
                elif r0 == 4 and not is_holiday and forced_count > 1:
                    same_day_bad, why = True, "평일에는 하루 1근무만 허용됩니다."
            elif r0 in (3, 5):
                if forced[0] and forced[2] and not forced[1]:
                    same_day_bad, why = True, "D+N 조합은 E 없이 허용되지 않습니다."
                elif r0 == 5 and not is_holiday and forced_count > 1:
                    same_day_bad, why = True, "평일에는 하루 1근무만 허용됩니다."
            if same_day_bad:
                add_conflict(
                    n, day_t=t, rule="하루 근무 횟수 rule",
                    explanation=why,
                    related=f"{dlabel(t)} hard-fixed={shift_text(forced)}, rule_max_shifts_per_day={r0}",
                    suggestion="해당 날짜의 대문자 D/E/N 고정 중 일부를 해제하세요.",
                )

            if r0 == 1 and forced_count >= 1:
                for s_idx in range(3):
                    if not forced[s_idx]:
                        off[t][s_idx] = True
            elif r0 in (4, 5) and not is_holiday and forced_count >= 1:
                for s_idx in range(3):
                    if not forced[s_idx]:
                        off[t][s_idx] = True

        # Count-level contradictions among forced assignments and exact/maximum counts.
        for s_idx, sk in enumerate(shift_keys):
            fv = fixed_shift[sk]
            if fv >= 0 and current_forced_counts[s_idx] > fv:
                add_conflict(
                    n, day_t=None, rule=f"fixed_{sk} vs hard-fixed {sk}",
                    explanation=f"대문자 {sk} hard-fixed가 {current_forced_counts[s_idx]}개인데 fixed_{sk}={fv}입니다.",
                    related=f"hard-fixed {sk}={current_forced_counts[s_idx]}, fixed_{sk}={fv}",
                    suggestion=f"대문자 {sk} 일부를 해제하거나 fixed_{sk}를 늘리세요.",
                )
        if fixed_total >= 0 and current_forced_total > fixed_total:
            add_conflict(
                n, day_t=None, rule="fixed_Total vs hard-fixed 근무",
                explanation=f"대문자 hard-fixed 근무가 {current_forced_total}개인데 fixed_Total={fixed_total}입니다.",
                related=f"hard-fixed total={current_forced_total}, fixed_Total={fixed_total}",
                suggestion="대문자 고정근무 일부를 해제하거나 fixed_Total을 늘리세요.",
            )
        if max_total >= 0 and current_forced_total > max_total:
            add_conflict(
                n, day_t=None, rule="maximum_total vs hard-fixed 근무",
                explanation=f"대문자 hard-fixed 근무가 {current_forced_total}개인데 maximum_total={max_total}입니다.",
                related=f"hard-fixed total={current_forced_total}, maximum_total={max_total}",
                suggestion="대문자 고정근무 일부를 해제하거나 maximum_total을 늘리세요.",
            )
        if min_n >= 0 and max_n >= 0 and min_n > max_n:
            add_conflict(
                n, day_t=None, rule="minimum_N vs maximum_N",
                explanation=f"minimum_N={min_n}인데 maximum_N={max_n}입니다.",
                related=f"minimum_N={min_n}, maximum_N={max_n}",
                suggestion="minimum_N을 줄이거나 maximum_N을 늘리세요.",
            )
        if fixed_shift["N"] >= 0 and min_n >= 0 and fixed_shift["N"] < min_n:
            add_conflict(
                n, day_t=None, rule="fixed_N vs minimum_N",
                explanation=f"fixed_N={fixed_shift['N']}은 정확한 N 개수인데 minimum_N={min_n}보다 작습니다.",
                related=f"fixed_N={fixed_shift['N']}, minimum_N={min_n}",
                suggestion="fixed_N을 늘리거나 minimum_N을 줄이세요.",
            )
        if max_n >= 0 and current_forced_counts[2] > max_n:
            add_conflict(
                n, day_t=None, rule="maximum_N vs hard-fixed N",
                explanation=f"대문자 N hard-fixed가 {current_forced_counts[2]}개인데 maximum_N={max_n}입니다.",
                related=f"hard-fixed N={current_forced_counts[2]}, maximum_N={max_n}",
                suggestion="대문자 N 일부를 해제하거나 maximum_N을 늘리세요.",
            )
        if fixed_shift["N"] >= 0 and max_n >= 0 and fixed_shift["N"] > max_n:
            add_conflict(
                n, day_t=None, rule="fixed_N vs maximum_N",
                explanation=f"fixed_N={fixed_shift['N']}은 정확한 N 개수인데 maximum_N={max_n}보다 큽니다.",
                related=f"fixed_N={fixed_shift['N']}, maximum_N={max_n}",
                suggestion="fixed_N을 줄이거나 maximum_N을 늘리세요.",
            )
        fixed_positive_sum = sum(v for v in fixed_shift.values() if v >= 0)
        if fixed_total >= 0 and fixed_positive_sum > fixed_total:
            add_conflict(
                n, day_t=None, rule="fixed_D/E/N 합 vs fixed_Total",
                explanation=f"fixed_D/E/N 지정 합이 {fixed_positive_sum}인데 fixed_Total={fixed_total}입니다.",
                related=f"fixed D/E/N 합={fixed_positive_sum}, fixed_Total={fixed_total}",
                suggestion="fixed_D/E/N 또는 fixed_Total 값을 조정하세요.",
            )
        if max_total >= 0 and fixed_positive_sum > max_total:
            add_conflict(
                n, day_t=None, rule="fixed_D/E/N 합 vs maximum_total",
                explanation=f"fixed_D/E/N 지정 합이 {fixed_positive_sum}인데 maximum_total={max_total}입니다.",
                related=f"fixed D/E/N 합={fixed_positive_sum}, maximum_total={max_total}",
                suggestion="fixed_D/E/N을 줄이거나 maximum_total을 늘리세요.",
            )
        if fixed_total >= 0 and max_total >= 0 and fixed_total > max_total:
            add_conflict(
                n, day_t=None, rule="fixed_Total vs maximum_total",
                explanation=f"fixed_Total={fixed_total}은 정확한 근무수인데 maximum_total={max_total}보다 큽니다.",
                related=f"fixed_Total={fixed_total}, maximum_total={max_total}",
                suggestion="fixed_Total을 줄이거나 maximum_total을 늘리세요.",
            )

        # If a shift is known ON/OFF, these helpers make rule checks easy to read.
        def is_on(t: int, s_idx: int) -> bool:
            return 0 <= t < timeline_len and bool(on[t][s_idx])

        def is_off(t: int, s_idx: int) -> bool:
            return 0 <= t < timeline_len and bool(off[t][s_idx])

        def is_forced_work(t: int) -> bool:
            return 0 <= t < timeline_len and any(on[t])

        def related_window(ts) -> str:
            return " → ".join(f"{dlabel(t)} {shift_text(on[t])}" for t in ts)

        # Two-day total cap used by r0 2/3/4/5.
        if r0 in (2, 3, 4, 5):
            for t in sequence_window_starts(2):
                minimum_shifts = sum(sum(on[t+p]) for p in range(2))
                if minimum_shifts >= 4:
                    add_conflict(
                        n, day_t=max(current_offset, t), rule="2일간 근무수 상한",
                        explanation=f"연속 2일의 확정 근무가 이미 {minimum_shifts}개로, solver의 '< 4' hard rule을 위반합니다.",
                        related=related_window([t, t+1]),
                        suggestion="두 날짜의 hard-fixed 근무 중 일부를 해제하세요.",
                    )

        # N block maximum.
        block_len = n_max + 1
        if block_len > 0:
            for t in sequence_window_starts(block_len):
                if all(is_on(t+i, 2) for i in range(block_len)):
                    add_conflict(
                        n, day_t=max(current_offset, t), rule="N block 최대 길이",
                        explanation=f"N이 {block_len}일 연속으로 확정되어 있으나 N block 최대는 {n_max}일입니다.",
                        related=related_window(range(t, t+block_len)),
                        suggestion="대문자 N 중 하나를 해제하거나 N block 최대 길이를 조정하세요.",
                    )

        # N-block end consequences. An end is definite only when the following day's N is known OFF.
        for e in range(timeline_len):
            if not is_on(e, 2):
                continue
            if e + 1 >= timeline_len or not is_off(e + 1, 2):
                continue
            end_date = dlabel(e)
            for r in range(1, n_rest + 1):
                dd = e + r
                if dd >= timeline_len:
                    break
                if dd < current_offset:
                    continue
                if is_forced_work(dd):
                    forced_txt = shift_text(on[dd])
                    add_conflict(
                        n, day_t=dd, rule="N block 후 mandatory OFF",
                        explanation=(f"{end_date}에 N block이 확정 종료되어 이후 {n_rest}일은 완전 OFF여야 하지만 "
                                     f"{dlabel(dd)}에 {forced_txt}가 hard-fixed되어 있습니다."),
                        related=f"N block 종료={end_date}; mandatory OFF day {r}/{n_rest}={dlabel(dd)}; hard-fixed={forced_txt}",
                        suggestion=f"{dlabel(dd)}의 대문자 {forced_txt}를 빈칸/x로 바꾸거나 직전 스케줄/N-rest 설정을 확인하세요.",
                    )
            for g in range(n_rest + 1, n_gap + 1):
                dd = e + g
                if dd >= timeline_len:
                    break
                if dd < current_offset:
                    continue
                if is_on(dd, 2):
                    add_conflict(
                        n, day_t=dd, rule="N block 후 다음 N 간격",
                        explanation=(f"{end_date}에 N block이 확정 종료되어 다음 N은 gap 규칙상 아직 불가능하지만 "
                                     f"{dlabel(dd)} N이 hard-fixed되어 있습니다."),
                        related=f"N block 종료={end_date}; n_rest={n_rest}, n_gap={n_gap}; hard-fixed N={dlabel(dd)}",
                        suggestion=f"{dlabel(dd)}의 대문자 N을 해제하거나 n_gap 설정을 확인하세요.",
                    )

        if r2:
            for t in sequence_window_starts(2):
                if is_on(t, 1) and is_on(t+1, 0):
                    add_conflict(
                        n, day_t=t+1, rule="Evening 후 Day 금지",
                        explanation=f"{dlabel(t)} E 다음 날인 {dlabel(t+1)}에 D가 hard-fixed되어 있습니다.",
                        related=related_window([t, t+1]),
                        suggestion=f"{dlabel(t+1)} D 고정을 해제하거나 개인 E→D rule을 확인하세요.",
                    )

        if r3:
            for t in sequence_window_starts(3):
                if all(is_on(t+i, 1) for i in range(3)):
                    add_conflict(
                        n, day_t=max(current_offset, t), rule="Evening 3연속 금지",
                        explanation="E가 3일 연속으로 확정되어 있습니다.",
                        related=related_window([t, t+1, t+2]),
                        suggestion="대문자 E 중 하나를 해제하거나 해당 rule을 확인하세요.",
                    )

        if r4:
            for t in sequence_window_starts(4):
                if is_on(t,1) and is_on(t+1,1) and is_off(t+2,1) and is_on(t+3,1):
                    add_conflict(
                        n, day_t=max(current_offset, t), rule="4일 내 Evening 3회 금지",
                        explanation="E-E-(E불가)-E 패턴이 hard input으로 확정되어 있습니다.",
                        related=related_window([t, t+1, t+2, t+3]),
                        suggestion="대문자 E/불가표시 중 하나를 조정하세요.",
                    )
                if is_on(t,1) and is_off(t+1,1) and is_on(t+2,1) and is_on(t+3,1):
                    add_conflict(
                        n, day_t=max(current_offset, t), rule="4일 내 Evening 3회 금지",
                        explanation="E-(E불가)-E-E 패턴이 hard input으로 확정되어 있습니다.",
                        related=related_window([t, t+1, t+2, t+3]),
                        suggestion="대문자 E/불가표시 중 하나를 조정하세요.",
                    )

        if r5 in (3, 4, 5, 6, 7):
            for t in sequence_window_starts(r5 + 1):
                if all(is_forced_work(t+p) for p in range(r5 + 1)):
                    add_conflict(
                        n, day_t=max(current_offset, t), rule="최대 연속 근무일수",
                        explanation=f"{r5 + 1}일 연속 근무가 hard input으로 확정되어 있으나 최대 허용은 {r5}일입니다.",
                        related=related_window(range(t, t+r5+1)),
                        suggestion="해당 구간의 대문자 고정근무 중 하나를 해제하세요.",
                    )

        if r6 > 0:
            for t in sequence_window_starts(7):
                forced_count = sum(sum(on[t+p]) for p in range(7))
                if forced_count > r6:
                    add_conflict(
                        n, day_t=max(current_offset, t), rule="7일 구간 최대 근무수",
                        explanation=f"7일 구간의 확정 근무가 {forced_count}개로 최대 {r6}개를 초과합니다.",
                        related=related_window(range(t, t+7)),
                        suggestion="해당 7일 구간의 hard-fixed 근무를 줄이거나 주간 상한을 조정하세요.",
                    )

        if r7:
            for t in sequence_window_starts(3):
                if all(is_on(t+i, 0) for i in range(3)):
                    add_conflict(
                        n, day_t=max(current_offset, t), rule="Day 3연속 금지",
                        explanation="D가 3일 연속으로 hard input으로 확정되어 있습니다.",
                        related=related_window([t, t+1, t+2]),
                        suggestion="대문자 D 중 하나를 해제하거나 해당 rule을 확인하세요.",
                    )

    # Exact per-person fixed_Total feasibility.
    # The lightweight app-side estimate used to miss sliding 7-day limits and
    # PreviousSchedule/N-rest interactions.  Here we ask CP-SAT directly using
    # the same personal hard constraints as the real scheduler.
    if ORTOOLS_AVAILABLE:
        for n in range(num_doctors):
            sc = shift_counts.get(n, {}) if isinstance(shift_counts.get(n, {}), dict) else {}
            try:
                fixed_total = int(sc.get("Total", -1))
            except (TypeError, ValueError):
                fixed_total = -1
            if fixed_total < 0:
                continue

            exact = _solve_personal_total_model(params, n, total_target=fixed_total)
            if exact.get("feasible"):
                continue
            # UNKNOWN is not a proof of infeasibility, so do not report it as a conflict.
            if str(exact.get("status", "")).upper() == "UNKNOWN":
                continue

            max_res = _solve_personal_total_model(params, n, objective="max")
            min_res = _solve_personal_total_model(params, n, objective="min")
            max_val = max_res.get("value") if max_res.get("optimal") else None
            min_val = min_res.get("value") if min_res.get("optimal") else None
            limits = _personal_diagnostic_limit_summary(params, n)

            if max_val is not None and fixed_total > max_val:
                add_conflict(
                    n,
                    day_t=None,
                    rule="fixed_Total 달성 불가 · 정확 개인별 최대",
                    explanation=(
                        f"fixed_Total={fixed_total}은 정확히 채워야 하지만, 현재 개인 hard rule을 모두 적용하면 "
                        f"이 사람의 월 최대 가능 근무수는 {max_val}개입니다. 따라서 최소 {fixed_total - max_val}개가 부족합니다."
                    ),
                    related=f"fixed_Total={fixed_total}; 정확 최대={max_val}; {limits}",
                    suggestion=(
                        "fixed_Total을 줄이는 것이 아니라, fixed_Total을 유지해야 한다면 x/a/불가요청 또는 "
                        "7일 최대근무·연속근무·N-rest/N-gap 등 개인 hard rule 중 실제 조정 가능한 조건을 확인하세요."
                    ),
                )
            elif min_val is not None and fixed_total < min_val:
                add_conflict(
                    n,
                    day_t=None,
                    rule="fixed_Total 달성 불가 · 정확 개인별 최소",
                    explanation=(
                        f"fixed_Total={fixed_total}은 정확값이지만, 현재 hard-fixed D/E/N 및 fixed_D/E/N 등을 적용하면 "
                        f"최소 {min_val}개는 근무해야 합니다."
                    ),
                    related=f"fixed_Total={fixed_total}; 정확 최소={min_val}; {limits}",
                    suggestion="대문자 D/E/N 또는 fixed_D/E/N을 확인하세요.",
                )
            elif max_val is not None and min_val is not None:
                # Rare discrete-pattern case: target lies inside [min,max] but is still not attainable.
                add_conflict(
                    n,
                    day_t=None,
                    rule="fixed_Total 정확값 달성 불가",
                    explanation=(
                        f"개인 hard rule상 가능한 총근무 범위는 {min_val}~{max_val}이지만 fixed_Total={fixed_total} "
                        "정확값을 만드는 조합은 존재하지 않습니다."
                    ),
                    related=f"fixed_Total={fixed_total}; 개인 가능 범위={min_val}~{max_val}; {limits}",
                    suggestion="fixed_D/E/N, 대문자 고정근무 및 sequence rule 조합을 확인하세요.",
                )
            elif str(max_res.get("status", "")).upper() == "INFEASIBLE":
                add_conflict(
                    n,
                    day_t=None,
                    rule="개인 hard rule 조합 자체 불가능",
                    explanation=(
                        "fixed_Total을 잠시 제외해도 이 사람의 fixed_D/E/N·근무요청·직전 스케줄·sequence rule을 "
                        "동시에 만족하는 개인 스케줄이 없습니다."
                    ),
                    related=limits,
                    suggestion="fixed_D/E/N, 대문자 D/E/N, x/a 및 직전 5일과 sequence rule을 함께 확인하세요.",
                )

    columns = ["상태", "이름", "날짜", "충돌 규칙", "설명", "관련 일정", "수정 제안"]
    if not rows:
        return pd.DataFrame(columns=columns)
    out = pd.DataFrame(rows, columns=columns)
    return out.sort_values(["이름", "날짜", "충돌 규칙"], kind="stable").reset_index(drop=True)


def evaluate_additional_availability(params: dict[str, Any], sol: dict[tuple[int, int], str]):
    """Return extra D/E/N shifts that can be added without violating personal hard rules.

    This intentionally ignores duty headcount and group-level grade composition, because
    it is meant as a backup/extra-work availability view after a complete schedule exists.
    It *does* enforce the doctor's requests, previous-five-day sequence context, all
    per-doctor sequence rules, fixed D/E/N/Total counts, minimum_N, maximum_N, and maximum_total.

    Returns a dict {(doctor_idx, day_idx): ["D", "E", "N", ...]} for candidates.
    """
    names = list(params.get("doctors", []))
    num_doctors = len(names)
    num_days = int(params.get("num_days", 0))
    previous_days = max(0, int(params.get("previous_schedule_days", 5)))
    previous_raw = params.get("previous_schedule", {}) or {}
    sr_raw = params.get("shift_requests", {}) or {}
    rules_raw = {int(k): v for k, v in (params.get("rules", {}) or {}).items()}
    day_types = {int(k): v for k, v in (params.get("day_types", {}) or {}).items()}
    shift_counts_raw = params.get("shift_counts", {}) or {}
    shift_counts = {int(k): {sk: int(sv) for sk, sv in v.items()} for k, v in shift_counts_raw.items()}
    maximum_total = {int(k): int(v) for k, v in (params.get("maximum_total", {}) or {}).items()}
    minimum_n = {int(k): int(v) for k, v in (params.get("minimum_N", {}) or {}).items()}
    maximum_n = {int(k): int(v) for k, v in (params.get("maximum_N", {}) or {}).items()}

    history = [[[0, 0, 0] for _ in range(previous_days)] for _ in range(num_doctors)]
    for key, cell in previous_raw.items():
        try:
            n_str, h_str = str(key).split(",")
            n, h = int(n_str), int(h_str)
        except (ValueError, TypeError):
            continue
        if 0 <= n < num_doctors and 0 <= h < previous_days:
            history[n][h] = [int(x) for x in _parse_actual_shift(cell)]

    def get_rule(n: int, key: str, default: int) -> int:
        return int(rules_raw.get(n, {}).get(key, default))

    def sequence_window_starts(timeline_len: int, window_len: int):
        if window_len <= 0 or timeline_len < window_len:
            return range(0)
        first = max(0, previous_days - window_len + 1)
        return range(first, timeline_len - window_len + 1)

    def personal_rules_ok(n: int, current_flags: list[list[int]]) -> bool:
        timeline = [list(x) for x in history[n]] + [list(x) for x in current_flags]
        timeline_len = len(timeline)
        r0 = get_rule(n, "rule_max_shifts_per_day", 1)
        r2 = get_rule(n, "rule_no_day_after_eve", 1)
        r3 = get_rule(n, "rule_no_3eve_consec", 0)
        r4 = get_rule(n, "rule_no_3eve_in_4days", 0)
        r5 = get_rule(n, "rule_max_consec_days", 5)
        r6 = get_rule(n, "rule_max_shifts_per_week", 5)
        r7 = get_rule(n, "rule_no_3day_consec", 0)
        n_max = get_rule(n, "rule_n_block_max", 2)
        n_rest = get_rule(n, "rule_n_rest", 2)
        n_gap = get_rule(n, "rule_n_gap", 4)

        # Same-day / two-day multiplicity rules.
        for d, flags in enumerate(current_flags):
            cnt = sum(flags)
            if r0 == 1 and cnt > 1:
                return False
            if r0 in (2, 4):
                if flags[0] and flags[2] and not flags[1]:  # DN without E
                    return False
                if all(flags):
                    return False
                if r0 == 4 and day_types.get(d, "평일") not in ("토", "일", "공") and cnt > 1:
                    return False
            if r0 in (3, 5):
                if flags[0] and flags[2] and not flags[1]:  # DN requires E too
                    return False
                if r0 == 5 and day_types.get(d, "평일") not in ("토", "일", "공") and cnt > 1:
                    return False
        if r0 in (2, 3, 4, 5):
            for t in sequence_window_starts(timeline_len, 2):
                if sum(sum(timeline[t+p]) for p in range(2)) >= 4:
                    return False

        # N block maximum.
        block_len = n_max + 1
        for t in sequence_window_starts(timeline_len, block_len):
            if sum(timeline[t+i][2] for i in range(block_len)) >= block_len:
                return False

        # N-block end consequences, matching the solver's current-month enforcement.
        for e in range(timeline_len):
            if not timeline[e][2]:
                continue
            next_is_n = (e + 1 < timeline_len and timeline[e+1][2])
            if next_is_n:
                continue
            for r in range(1, n_rest + 1):
                dd = e + r
                if dd >= timeline_len:
                    break
                if dd < previous_days:
                    continue
                if any(timeline[dd]):
                    return False
            for g in range(n_rest + 1, n_gap + 1):
                dd = e + g
                if dd >= timeline_len:
                    break
                if dd < previous_days:
                    continue
                if timeline[dd][2]:
                    return False

        if r2:
            for t in sequence_window_starts(timeline_len, 2):
                if timeline[t][1] and timeline[t+1][0]:
                    return False
        if r3:
            for t in sequence_window_starts(timeline_len, 3):
                if timeline[t][1] and timeline[t+1][1] and timeline[t+2][1]:
                    return False
        if r4:
            for t in sequence_window_starts(timeline_len, 4):
                es = [timeline[t+i][1] for i in range(4)]
                if es[0] and es[1] and (not es[2]) and es[3]:
                    return False
                if es[0] and (not es[1]) and es[2] and es[3]:
                    return False
        if r5 in (3, 4, 5, 6, 7):
            for t in sequence_window_starts(timeline_len, r5 + 1):
                if sum(1 if any(timeline[t+p]) else 0 for p in range(r5 + 1)) > r5:
                    return False
        if r6 > 0:
            for t in sequence_window_starts(timeline_len, 7):
                if sum(sum(timeline[t+p]) for p in range(7)) > r6:
                    return False
        if r7:
            for t in sequence_window_starts(timeline_len, 3):
                if timeline[t][0] and timeline[t+1][0] and timeline[t+2][0]:
                    return False
        return True

    result: dict[tuple[int, int], list[str]] = {}
    shift_keys = ["D", "E", "N"]
    for n in range(num_doctors):
        current_flags = []
        for d in range(num_days):
            current_flags.append([int(x) for x in _parse_actual_shift(sol.get((n, d), ""))])
        current_counts = [sum(current_flags[d][s] for d in range(num_days)) for s in range(3)]
        current_total = sum(current_counts)
        sc = shift_counts.get(n, {})
        fixed_total = int(sc.get("Total", -1))
        max_total = int(maximum_total.get(n, -1))
        max_n = int(maximum_n.get(n, -1))

        # Exact fixed total means no extra assignment can be added without breaking it.
        if fixed_total >= 0 and current_total >= fixed_total:
            continue
        if max_total >= 0 and current_total >= max_total:
            continue

        for d in range(num_days):
            req_cell = str(sr_raw.get(f"{n},{d}", "") or "")
            cannot = _parse_shift_request(req_cell)
            candidates = []
            for s, shift_key in enumerate(shift_keys):
                if current_flags[d][s]:
                    continue
                if cannot[s]:
                    continue

                # Exact per-shift and total counts remain hard constraints.
                fixed_shift = int(sc.get(shift_key, -1))
                if fixed_shift >= 0 and current_counts[s] + 1 > fixed_shift:
                    continue
                if s == 2 and max_n >= 0 and current_counts[2] + 1 > max_n:
                    continue
                if fixed_total >= 0 and current_total + 1 > fixed_total:
                    continue
                if max_total >= 0 and current_total + 1 > max_total:
                    continue

                trial = [list(x) for x in current_flags]
                trial[d][s] = 1
                if personal_rules_ok(n, trial):
                    candidates.append(shift_key)
            if candidates:
                result[(n, d)] = candidates
    return result

def build_and_solve(params: dict[str, Any]):
    """
    Main entry-point called from app.py.

    params keys:
        doctors       : list[str]
        num_days      : int
        start_date    : str  (YYYY-MM-DD)
        day_types     : dict {str(day_idx) -> '평일'|'토'|'일'|'공'}
        duty_requests : dict {str(day_idx) -> [D, E, N]}  # hard minimum staffing per duty
        ideal_duty_requests: dict {str(day_idx) -> [D, E, N]}  # optional soft staffing; -1/missing = unused
        shift_requests: dict {"n,d" -> cell_str}
        previous_schedule: dict {"n,h" -> actual shift}, h=0 oldest of preceding days
        previous_schedule_days: int (default 5)
        rules         : dict {str(n) -> {rule_key: value}}
        shift_adj     : optional hidden/legacy soft balance offset {str(n) -> int}; normally 0
        maximum_total : dict {str(n) -> -1|int}; -1 = no total maximum
        maximum_N     : dict {str(n) -> -1|int}; -1 = no Night maximum
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
    ideal_duty_req_raw = {int(k): list(v) for k, v in (params.get("ideal_duty_requests", {}) or {}).items()}
    sr_raw       = params["shift_requests"]   # {"n,d": cell_str}
    previous_schedule_days = max(0, int(params.get("previous_schedule_days", 5)))
    previous_schedule_raw = params.get("previous_schedule", {}) or {}
    rules_raw    = {int(k): v for k, v in params["rules"].items()}
    shift_adj    = {int(k): int(v) for k, v in (params.get("shift_adj", {}) or {}).items()}
    maximum_total_raw = params.get("maximum_total", {}) or {}
    maximum_total = {int(k): int(v) for k, v in maximum_total_raw.items()}
    minimum_n_raw = params.get("minimum_N", {}) or {}
    minimum_n = {int(k): int(v) for k, v in minimum_n_raw.items()}
    maximum_n_raw = params.get("maximum_N", {}) or {}
    maximum_n = {int(k): int(v) for k, v in maximum_n_raw.items()}
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

    # Optional efficiency monitor. OFF by default.
    early_stop_on_plateau = bool(params.get("early_stop_on_plateau", False))
    plateau_seconds = max(20.0, float(params.get("plateau_seconds", 60) or 60))
    plateau_min_runtime = max(
        15.0,
        min(
            float(params.get("plateau_min_runtime", 30) or 30),
            max(15.0, float(time_max) * 0.5),
        ),
    )

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

    # duty_requests[d][s] are HARD minimums.
    # Ideal is OPTIONAL: -1/missing means "no Ideal preference" for that date/shift.
    # When explicitly entered, it is clamped to >= Minimal and acts only in placement.
    duty_requests = [[int(duty_req_raw.get(d, [1,1,1])[s]) for s in all_shifts] for d in all_days]
    ideal_duty_requests = []
    ideal_duty_enabled = []
    for d in all_days:
        raw_ideal = list(ideal_duty_req_raw.get(d, [-1, -1, -1]))
        if len(raw_ideal) < 3:
            raw_ideal = (raw_ideal + [-1, -1, -1])[:3]
        row = []
        enabled_row = []
        for s in all_shifts:
            minimum = int(duty_requests[d][s])
            try:
                raw_value = int(raw_ideal[s])
            except (TypeError, ValueError):
                raw_value = -1
            enabled = minimum > 0 and raw_value >= 0
            if enabled:
                row.append(min(num_doctors, max(minimum, raw_value)))
                enabled_row.append(True)
            else:
                # Store Minimal only as an arithmetic placeholder; this cell does NOT
                # create Ideal shortfall/over-Ideal penalties.
                row.append(max(0, minimum))
                enabled_row.append(False)
        ideal_duty_requests.append(row)
        ideal_duty_enabled.append(enabled_row)

    # Validate senior hard rule before building the full model.
    if senior_min_count > 0:
        if len(senior_doctors) < senior_min_count:
            raise RuntimeError(
                f"고년차 hard rule 불가능: grade >= {senior_min_grade} 인원이 {len(senior_doctors)}명인데, "
                f"각 duty마다 최소 {senior_min_count}명이 필요합니다."
            )
        # DutyRequests are minimum staffing values.  If the minimum headcount is
        # smaller than senior_min_count, the solver may simply add staff to that duty.
        # Therefore only the size of the senior pool is a global impossibility here.

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

    # Ideal is optional. Count/sum only cells where the user explicitly entered
    # an Ideal value. Disabled(blank) cells must not appear as Ideal targets.
    ideal_configured_cells = sum(
        1 for d in all_days for s in all_shifts if ideal_duty_enabled[d][s]
    )
    total_ideal_duty = sum(
        ideal_duty_requests[d][s]
        for d in all_days for s in all_shifts
        if ideal_duty_enabled[d][s]
    )
    total_ideal_s = [
        sum(
            ideal_duty_requests[d][s]
            for d in all_days
            if ideal_duty_enabled[d][s]
        )
        for s in all_shifts
    ]
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

    # maximum_total is a separate hard upper bound. -1/absent means unlimited.
    max_total_by_doc = {
        n: int(maximum_total.get(n, -1))
        for n in all_doctors
        if int(maximum_total.get(n, -1)) >= 0
    }
    for n, fixed_total in fixed_total_by_doc.items():
        max_total = max_total_by_doc.get(n, -1)
        if max_total >= 0 and fixed_total > max_total:
            raise RuntimeError(
                f"{names[n]}의 fixed_total({fixed_total})이 maximum_total({max_total})보다 큽니다."
            )

    # minimum_N / maximum_N are separate hard lower/upper bounds on monthly Night count.
    min_n_by_doc = {
        n: int(minimum_n.get(n, -1))
        for n in all_doctors
        if int(minimum_n.get(n, -1)) >= 0
    }
    max_n_by_doc = {
        n: int(maximum_n.get(n, -1))
        for n in all_doctors
        if int(maximum_n.get(n, -1)) >= 0
    }
    for n in all_doctors:
        sc = shift_counts.get(n, {})
        fixed_n = int(sc.get("N", -1))
        fixed_total = int(sc.get("Total", -1))
        min_n = min_n_by_doc.get(n, -1)
        max_n = max_n_by_doc.get(n, -1)
        max_total = max_total_by_doc.get(n, -1)

        if min_n >= 0 and max_n >= 0 and min_n > max_n:
            raise RuntimeError(
                f"{names[n]}의 minimum_N({min_n})이 maximum_N({max_n})보다 큽니다."
            )
        if fixed_n >= 0 and min_n >= 0 and fixed_n < min_n:
            raise RuntimeError(
                f"{names[n]}의 fixed_N({fixed_n})이 minimum_N({min_n})보다 작습니다."
            )
        if fixed_n >= 0 and max_n >= 0 and fixed_n > max_n:
            raise RuntimeError(
                f"{names[n]}의 fixed_N({fixed_n})이 maximum_N({max_n})보다 큽니다."
            )
        required_n = fixed_n if fixed_n >= 0 else (min_n if min_n >= 0 else 0)
        fixed_d = int(sc.get("D", -1))
        fixed_e = int(sc.get("E", -1))
        required_lower_sum = (
            (fixed_d if fixed_d >= 0 else 0)
            + (fixed_e if fixed_e >= 0 else 0)
            + required_n
        )
        if fixed_total >= 0 and required_lower_sum > fixed_total:
            raise RuntimeError(
                f"{names[n]}의 필수 D/E/N 하한 합({required_lower_sum})이 fixed_total({fixed_total})보다 큽니다."
            )
        if max_total >= 0 and required_lower_sum > max_total:
            raise RuntimeError(
                f"{names[n]}의 필수 D/E/N 하한 합({required_lower_sum})이 maximum_total({max_total})보다 큽니다."
            )

    # If every doctor has a finite N upper bound (fixed_N itself is exact), the
    # sum of those bounds must cover the minimum Night staffing.
    n_upper_bounds = []
    all_have_n_upper_bound = True
    for n in all_doctors:
        fixed_n = int(shift_counts.get(n, {}).get("N", -1))
        if fixed_n >= 0:
            n_upper_bounds.append(fixed_n)
        elif n in max_n_by_doc:
            n_upper_bounds.append(max_n_by_doc[n])
        else:
            all_have_n_upper_bound = False
            break
    if all_have_n_upper_bound and sum(n_upper_bounds) < total_s[2]:
        raise RuntimeError(
            f"모든 간호사의 N 상한 합({sum(n_upper_bounds)})이 N Duty 최소합({total_s[2]})보다 작아 "
            f"{total_s[2] - sum(n_upper_bounds)}개의 N 근무를 배정할 수 없습니다."
        )

    # If every doctor has a finite total upper bound (fixed_total itself is also an
    # exact upper bound), the sum of those bounds must cover all required duties.
    finite_upper_bounds = []
    all_have_upper_bound = True
    for n in all_doctors:
        if n in fixed_total_by_doc:
            finite_upper_bounds.append(fixed_total_by_doc[n])
        elif n in max_total_by_doc:
            finite_upper_bounds.append(max_total_by_doc[n])
        else:
            all_have_upper_bound = False
            break
    if all_have_upper_bound and sum(finite_upper_bounds) < total_duty:
        raise RuntimeError(
            f"모든 간호사의 total 상한 합({sum(finite_upper_bounds)})이 Duty 총합({total_duty})보다 작아 "
            f"{total_duty - sum(finite_upper_bounds)}개 근무를 배정할 수 없습니다."
        )

    # DutyRequests are MINIMUM staffing, while fixed_total is an EXACT monthly count.
    # Therefore fixed_total_sum > minimum Duty total is allowed: the solver must
    # overstaff some active D/E/N duties enough to honor those exact totals.
    # The impossible all-fixed case is the opposite direction: exact totals are
    # collectively smaller than the minimum staffing demand.
    if not free_total_doctors and fixed_total_sum < total_duty:
        raise RuntimeError(
            f"모든 간호사의 fixed_total 합({fixed_total_sum})이 Duty 최소합({total_duty})보다 "
            f"{total_duty - fixed_total_sum}개 작아 최소 필요 인원을 채울 수 없습니다."
        )

    for n in all_doctors:
        sc = shift_counts.get(n, {})
        fixed_shift_sum = sum(int(sc.get(sk, -1)) for sk in ("D", "E", "N") if int(sc.get(sk, -1)) >= 0)
        max_total = max_total_by_doc.get(n, -1)
        if max_total >= 0 and fixed_shift_sum > max_total:
            raise RuntimeError(
                f"{names[n]}의 fixed_D/E/N 지정 합({fixed_shift_sum})이 maximum_total({max_total})보다 큽니다."
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

    # ── Workload-based balance targets ─────────────────────────────────────────
    # Nurse scheduling semantics:
    # - x and a choose OFF dates; neither changes workload/D-E-N balance targets.
    # - fixed_Total is the person's exact actual monthly workload and therefore the
    #   primary basis for that person's D/E/N and holiday balance targets.
    # - if fixed_Total is blank, a target total is derived from the remaining staffing
    #   workload after exact fixed totals are accounted for.
    # - shift_adj is retained only as a hidden/legacy SOFT balance offset. The app does
    #   not auto-generate it from fixed_Total or annual leave.

    hidden_shift_adj = {n: int(shift_adj.get(n, 0)) for n in all_doctors}
    target_total_duty = max(total_duty, fixed_total_sum)
    free_adj_sum = sum(hidden_shift_adj.get(n, 0) for n in free_total_doctors)
    avr_total_free = (
        (target_total_duty - fixed_total_sum - free_adj_sum) / len(free_total_doctors)
        if free_total_doctors else 0.0
    )

    # Plan the shift composition of unavoidable extras toward Ideal first.
    extra_for_balance = max(0.0, float(target_total_duty - total_duty))
    ideal_gap_s = [0.0, 0.0, 0.0]
    for d in all_days:
        for s in all_shifts:
            if ideal_duty_enabled[d][s]:
                ideal_gap_s[s] += max(0, int(ideal_duty_requests[d][s]) - int(duty_requests[d][s]))
    ideal_gap_total = sum(ideal_gap_s)

    planned_shift_totals = [float(total_s[s]) for s in all_shifts]
    ideal_fill = min(extra_for_balance, ideal_gap_total)
    if ideal_fill > 0 and ideal_gap_total > 0:
        for s in all_shifts:
            planned_shift_totals[s] += ideal_fill * (ideal_gap_s[s] / ideal_gap_total)

    leftover_extra = max(0.0, extra_for_balance - ideal_fill)
    if leftover_extra > 0:
        base_rate = [
            (total_s[s] / total_duty) if total_duty > 0 else (1.0 / len(all_shifts))
            for s in all_shifts
        ]
        for s in all_shifts:
            planned_shift_totals[s] += leftover_extra * base_rate[s]

    planned_shift_sum = sum(planned_shift_totals)
    s_rate = [
        (planned_shift_totals[s] / planned_shift_sum)
        if planned_shift_sum > 0 else (1.0 / len(all_shifts))
        for s in all_shifts
    ]
    hol_rate = total_holiday_demand / total_duty if total_duty else 0.0

    def _required_total_lower_bound(n: int) -> float:
        sc = shift_counts.get(n, {})
        fixed_d = int(sc.get("D", -1))
        fixed_e = int(sc.get("E", -1))
        fixed_n = int(sc.get("N", -1))
        min_n = int(minimum_n.get(n, -1))
        required_n = fixed_n if fixed_n >= 0 else (min_n if min_n >= 0 else 0)
        return float((fixed_d if fixed_d >= 0 else 0) + (fixed_e if fixed_e >= 0 else 0) + required_n)

    balance_total_target = {}
    for n in all_doctors:
        if n in fixed_total_by_doc:
            raw_target = float(fixed_total_by_doc[n] + hidden_shift_adj.get(n, 0))
        else:
            raw_target = float(avr_total_free + hidden_shift_adj.get(n, 0))
        raw_target = max(raw_target, _required_total_lower_bound(n), 0.0)
        max_total = int(maximum_total.get(n, -1))
        if max_total >= 0:
            raw_target = min(raw_target, float(max_total))
        balance_total_target[n] = raw_target

    def _weighted_split(amount: float, indices: list[int]) -> dict[int, float]:
        if not indices:
            return {}
        amount = max(0.0, float(amount))
        wsum = sum(max(0.0, s_rate[s]) for s in indices)
        if wsum <= 0:
            return {s: amount / len(indices) for s in indices}
        return {s: amount * max(0.0, s_rate[s]) / wsum for s in indices}

    def _person_shift_balance_targets(n: int) -> list[float]:
        sc = shift_counts.get(n, {})
        total_target = float(balance_total_target[n])
        targets = [None, None, None]
        free_shifts = []
        fixed_sum = 0.0
        for s, sk in enumerate(("D", "E", "N")):
            fv = int(sc.get(sk, -1))
            if fv >= 0:
                targets[s] = float(fv)
                fixed_sum += float(fv)
            else:
                free_shifts.append(s)

        residual = max(0.0, total_target - fixed_sum)
        initial = _weighted_split(residual, free_shifts)
        for s in free_shifts:
            targets[s] = initial.get(s, 0.0)

        if 2 in free_shifts:
            n_target = float(targets[2] or 0.0)
            min_n = int(minimum_n.get(n, -1))
            max_n = int(maximum_n.get(n, -1))
            if min_n >= 0:
                n_target = max(n_target, float(min_n))
            if max_n >= 0:
                n_target = min(n_target, float(max_n))
            targets[2] = n_target
            free_de = [s for s in (0, 1) if s in free_shifts]
            if free_de:
                de_amount = max(0.0, total_target - fixed_sum - n_target)
                de_split = _weighted_split(de_amount, free_de)
                for s in free_de:
                    targets[s] = de_split.get(s, 0.0)

        return [float(x or 0.0) for x in targets]

    person_shift_targets = {n: _person_shift_balance_targets(n) for n in all_doctors}
    person_holiday_target = {n: max(0.0, balance_total_target[n] * hol_rate) for n in all_doctors}

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
        r3        = get_rule(n, "rule_no_3eve_consec", 0)
        r4        = get_rule(n, "rule_no_3eve_in_4days", 0)
        r5        = get_rule(n, "rule_max_consec_days", 5)
        r6        = get_rule(n, "rule_max_shifts_per_week", 5)
        r7        = get_rule(n, "rule_no_3day_consec", 0)
        n_max     = get_rule(n, "rule_n_block_max", 2)   # Max N block length (1/2/3)
        n_rest    = get_rule(n, "rule_n_rest", 2)        # Mandatory rest days after N-block
        n_gap     = get_rule(n, "rule_n_gap", 4)         # Min gap before next N after N-block

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

    # ── Minimal / Ideal staffing ─────────────────────────────────────────────
    # Minimal = hard lower bound. Ideal = soft preferred target.
    # Important: Ideal NEVER creates extra work by itself. The objective first minimizes
    # the total number of assignments above Minimal. Only when extra staffing is already
    # necessary do the lower-priority terms steer it toward Ideal and spread it evenly.
    duty_extra_vars = []
    duty_extra_var_map = {}
    duty_count_vars = {}
    ideal_shortfall_vars = []
    over_ideal_vars = []
    for d in all_days:
        for s in all_shifts:
            requested_min = int(duty_requests[d][s])
            requested_ideal = int(ideal_duty_requests[d][s])
            count_var = model.NewIntVar(0, num_doctors, f"duty_count_{d}_{s}")
            model.Add(count_var == sum(shifts[(n,d,s)] for n in all_doctors))
            duty_count_vars[(d, s)] = count_var
            if requested_min <= 0:
                # Preserve legacy semantics: Min=0 closes this duty.
                model.Add(count_var == 0)
                duty_extra_var_map[(d, s)] = 0
            else:
                model.Add(count_var >= requested_min)
                extra = model.NewIntVar(0, max(0, num_doctors - requested_min), f"duty_extra_{d}_{s}")
                model.Add(extra == count_var - requested_min)
                duty_extra_vars.append(extra)
                duty_extra_var_map[(d, s)] = extra

                if ideal_duty_enabled[d][s]:
                    ideal_gap = max(0, requested_ideal - requested_min)
                    shortfall = model.NewIntVar(0, ideal_gap, f"ideal_shortfall_{d}_{s}")
                    # shortfall = max(Ideal - actual, 0)
                    model.AddMaxEquality(shortfall, [requested_ideal - count_var, 0])
                    ideal_shortfall_vars.append(shortfall)

                    over_bound = max(0, num_doctors - requested_ideal)
                    over_ideal = model.NewIntVar(0, over_bound, f"over_ideal_{d}_{s}")
                    # over_ideal = max(actual - Ideal, 0)
                    model.AddMaxEquality(over_ideal, [count_var - requested_ideal, 0])
                    over_ideal_vars.append(over_ideal)

    duty_extra_total = sum(duty_extra_vars) if duty_extra_vars else 0
    ideal_shortfall_total = sum(ideal_shortfall_vars) if ideal_shortfall_vars else 0
    over_ideal_total = sum(over_ideal_vars) if over_ideal_vars else 0

    # Track how extra staffing is distributed across dates and D/E/N cells.
    # The placement phase later balances Ideal preference with even distribution.
    day_extra_vars = []
    for d in all_days:
        day_extra = model.NewIntVar(0, num_doctors * num_shifts, f"day_extra_{d}")
        model.Add(day_extra == sum(duty_extra_var_map.get((d, s), 0) for s in all_shifts))
        day_extra_vars.append(day_extra)

    max_day_extra = model.NewIntVar(0, num_doctors * num_shifts, "max_day_extra")
    if day_extra_vars:
        model.AddMaxEquality(max_day_extra, day_extra_vars)
    else:
        model.Add(max_day_extra == 0)

    max_duty_extra = model.NewIntVar(0, num_doctors, "max_duty_extra")
    if duty_extra_vars:
        model.AddMaxEquality(max_duty_extra, duty_extra_vars)
    else:
        model.Add(max_duty_extra == 0)

    # Indicators used for result metrics (how many dates/cells received extras).
    day_used_extra_vars = []
    day_extra_upper = num_doctors * num_shifts
    for d, day_extra in enumerate(day_extra_vars):
        used = model.NewBoolVar(f"day_has_extra_{d}")
        model.Add(day_extra >= used)
        model.Add(day_extra <= day_extra_upper * used)
        day_used_extra_vars.append(used)
    day_unused_penalty = num_days - sum(day_used_extra_vars) if day_used_extra_vars else 0

    duty_used_extra_vars = []
    for idx, extra in enumerate(duty_extra_vars):
        used = model.NewBoolVar(f"duty_has_extra_{idx}")
        model.Add(extra >= used)
        model.Add(extra <= num_doctors * used)
        duty_used_extra_vars.append(used)
    duty_unused_penalty = len(duty_extra_vars) - sum(duty_used_extra_vars) if duty_used_extra_vars else 0

    # Convex concentration costs model "spread, but not at any cost". The first extra
    # on a date/cell costs 0, the second adds 1, third adds 2, etc. Combined with a
    # modest over-Ideal penalty, this favors Ideal while still allowing distribution
    # to win when one date/duty would otherwise become too concentrated.
    day_concentration_vars = []
    day_concentration_values = [k * (k - 1) // 2 for k in range(day_extra_upper + 1)]
    day_concentration_max = day_concentration_values[-1] if day_concentration_values else 0
    for d, day_extra in enumerate(day_extra_vars):
        conc = model.NewIntVar(0, day_concentration_max, f"day_extra_conc_{d}")
        model.AddElement(day_extra, day_concentration_values, conc)
        day_concentration_vars.append(conc)
    day_concentration_total = sum(day_concentration_vars) if day_concentration_vars else 0

    duty_concentration_vars = []
    duty_concentration_values = [k * (k - 1) // 2 for k in range(num_doctors + 1)]
    duty_concentration_max = duty_concentration_values[-1] if duty_concentration_values else 0
    for idx, extra in enumerate(duty_extra_vars):
        conc = model.NewIntVar(0, duty_concentration_max, f"duty_extra_conc_{idx}")
        model.AddElement(extra, duty_concentration_values, conc)
        duty_concentration_vars.append(conc)
    duty_concentration_total = sum(duty_concentration_vars) if duty_concentration_vars else 0

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
                max_excess = max(0, len(junior_doctors) - junior_soft_max_count)
                if max_excess <= 0:
                    continue
                junior_count = sum(shifts[(n,d,s)] for n in junior_doctors)
                excess = model.NewIntVar(0, max_excess, f"junior_excess_{d}_{s}")
                model.Add(excess >= junior_count - junior_soft_max_count)
                junior_excess_vars.append(excess)

    # ── Grade 구성 편차 (duty별) ─────────────────────────────────────────────
    # Duty headcount is now variable because DutyRequests are minimums.  The old
    # formula divided by the fixed requested headcount, so it would be incorrect
    # after overstaffing.  Instead compare the actual grade sum with
    # (overall average grade × actual assigned headcount), which stays linear.
    max_grade   = max(grades.get(n, 2) for n in all_doctors) if num_doctors > 0 else 3
    total_grade = sum(grades.get(n, 2) for n in all_doctors)
    avr_grade_10 = (total_grade * 10) // num_doctors if num_doctors > 0 else 20
    grade_dev_bound = max(1, num_doctors * max(10, max_grade * 10, avr_grade_10))
    k4 = model.NewIntVar(0, grade_dev_bound, 'k4_grade_dev')

    if weight_grade_dev > 0 and num_doctors > 0:
        for d in all_days:
            for s in all_shifts:
                if duty_requests[d][s] <= 0:
                    continue
                actual_count = duty_count_vars[(d, s)]
                grade_sum_10 = sum(shifts[(n,d,s)] * grades.get(n, 2) * 10 for n in all_doctors)
                dev = model.NewIntVar(0, grade_dev_bound, f"grade_dev_{d}_{s}")
                model.Add(dev >= grade_sum_10 - avr_grade_10 * actual_count)
                model.Add(dev >= avr_grade_10 * actual_count - grade_sum_10)
                model.Add(k4 >= dev)

    # ── Soft balancing (deviation minimization) ───────────────────────────────
    # 각 balance 항목을 아래쪽/위쪽 편차로 분리한다.
    # 예: 목표 19~20일 때 19~21은 상방 1, 18~20은 하방 1, 17~22는 하방 2+상방 2로 계산.
    # A low maximum_total can legitimately put a doctor far below the uncapped
    # average. Keep deviation variables wide enough so that the balancing soft
    # objective never turns a valid maximum_total cap into an accidental hard failure.
    max_balance_dev = max(6, total_duty, num_days * num_shifts)
    k_de_low  = model.NewIntVar(0, max_balance_dev, 'k_DE_low')
    k_de_high = model.NewIntVar(0, max_balance_dev, 'k_DE_high')
    k1_low    = model.NewIntVar(0, max_balance_dev, 'k1_holiday_low')
    k1_high   = model.NewIntVar(0, max_balance_dev, 'k1_holiday_high')
    k2_low    = model.NewIntVar(0, max_balance_dev, 'k2_total_low')
    k2_high   = model.NewIntVar(0, max_balance_dev, 'k2_total_high')
    k3_low    = model.NewIntVar(0, max_balance_dev, 'k3_N_low')
    k3_high   = model.NewIntVar(0, max_balance_dev, 'k3_N_high')

    k  = model.NewIntVar(0, max_balance_dev * 2, 'k_DE_sum')
    k1 = model.NewIntVar(0, max_balance_dev * 2, 'k1_holiday_sum')
    k2 = model.NewIntVar(0, max_balance_dev * 2, 'k2_total_sum')
    k3 = model.NewIntVar(0, max_balance_dev * 2, 'k3_N_sum')
    model.Add(k  == k_de_low + k_de_high)
    model.Add(k1 == k1_low + k1_high)
    model.Add(k2 == k2_low + k2_high)
    model.Add(k3 == k3_low + k3_high)

    # Secondary D/E fairness measure.
    #
    # Existing k_DE is an envelope: once the worst lower/upper D/E deviation is
    # already determined, several other nurses can move around inside that same
    # envelope without making k worse.  That can create 9D/3E vs 3D/11E style
    # outliers even when a more even solution exists with exactly the same k.
    #
    # We therefore keep k as the existing first-level quality measure, and track
    # the SUM of every nurse's D and E deviation from their own workload-scaled
    # target interval as a later lexicographic refinement objective.
    individual_de_dev_terms = []
    individual_de_dev_by_doc = {}

    # Keep expressions so final displayed metrics can be recomputed directly from
    # the selected assignment rather than from soft auxiliary slack variables.
    person_shift_count_exprs = {}
    person_total_exprs = {}
    person_holiday_exprs = {}

    for n in all_doctors:
        sc      = shift_counts.get(n, {})
        fixed_d = sc.get("D", -1)
        fixed_e = sc.get("E", -1)
        fixed_n = sc.get("N", -1)
        fixed_total = sc.get("Total", -1)
        is_total_fixed = fixed_total >= 0
        is_fully_fixed = (fixed_d >= 0 and fixed_e >= 0 and fixed_n >= 0)
        shift_target = person_shift_targets[n]
        total_target = balance_total_target[n]
        holiday_target = person_holiday_target[n]

        num_s = [sum(shifts[(n,d,s)] for d in all_days) for s in all_shifts]
        num_total = sum(num_s)
        hol_worked = sum(shifts[(n,d,s)] for d in holiday for s in all_shifts)

        person_shift_count_exprs[n] = num_s
        person_total_exprs[n] = num_total
        person_holiday_exprs[n] = hol_worked

        # Individual D/E deviation from this nurse's own workload-scaled target.
        # A fractional target such as D=6.4 treats 6~7 as the zero-penalty interval.
        # User-fixed D or E is excluded because it is an explicit exact instruction.
        person_de_terms = []
        for s, fixed_val, shift_label in (
            (0, fixed_d, "D"),
            (1, fixed_e, "E"),
        ):
            if fixed_val >= 0:
                continue
            target_low = int(shift_target[s])
            target_high = _max_avr(shift_target[s])
            below = model.NewIntVar(0, max_balance_dev, f"ind_{shift_label}_below_{n}")
            above = model.NewIntVar(0, max_balance_dev, f"ind_{shift_label}_above_{n}")
            model.Add(below >= target_low - num_s[s])
            model.Add(above >= num_s[s] - target_high)
            person_de_terms.extend([below, above])
            individual_de_dev_terms.extend([below, above])

        if person_de_terms:
            person_de_total = model.NewIntVar(
                0, max_balance_dev * len(person_de_terms), f"ind_DE_total_{n}"
            )
            model.Add(person_de_total == sum(person_de_terms))
            individual_de_dev_by_doc[n] = person_de_total

        # ── 고정 개수 hard constraint ─────────────────────────────────────────
        if fixed_d >= 0: model.Add(num_s[0] == fixed_d)
        if fixed_e >= 0: model.Add(num_s[1] == fixed_e)
        if fixed_n >= 0: model.Add(num_s[2] == fixed_n)
        min_n = int(minimum_n.get(n, -1))
        if min_n >= 0: model.Add(num_s[2] >= min_n)
        max_n = int(maximum_n.get(n, -1))
        if max_n >= 0: model.Add(num_s[2] <= max_n)
        if fixed_total >= 0: model.Add(num_total == fixed_total)
        max_total = int(maximum_total.get(n, -1))
        if max_total >= 0:
            model.Add(num_total <= max_total)

        dev_de  = [model.NewIntVar(0, max_balance_dev, f'dde_{n}_{x}') for x in range(2)]
        dev_hol = [model.NewIntVar(0, max_balance_dev, f'dhol_{n}_{x}') for x in range(2)]
        dev_tot = [model.NewIntVar(0, max_balance_dev, f'dtot_{n}_{x}') for x in range(2)]
        dev_N   = [model.NewIntVar(0, max_balance_dev, f'dN_{n}_{x}') for x in range(2)]

        sum_de  = model.NewIntVar(0, max_balance_dev * 2, f'sde_{n}')
        sum_hol = model.NewIntVar(0, max_balance_dev * 2, f'shol_{n}')
        sum_tot = model.NewIntVar(0, max_balance_dev * 2, f'stot_{n}')
        sum_N   = model.NewIntVar(0, max_balance_dev * 2, f'sN_{n}')

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
            for dv in [dev_de, dev_tot, dev_N]:
                model.Add(dv[0] == 0); model.Add(dv[1] == 0)
            model.Add(int(holiday_target) - dev_hol[0] <= hol_worked)
            model.Add(hol_worked <= _max_avr(holiday_target) + dev_hol[1])
        else:
            if fixed_d < 0:
                model.Add(int(shift_target[0]) - dev_de[0] <= num_s[0])
                model.Add(num_s[0] <= _max_avr(shift_target[0]) + dev_de[1])
            if fixed_e < 0:
                model.Add(int(shift_target[1]) - dev_de[0] <= num_s[1])
                model.Add(num_s[1] <= _max_avr(shift_target[1]) + dev_de[1])
            if fixed_d >= 0 and fixed_e >= 0:
                model.Add(dev_de[0] == 0); model.Add(dev_de[1] == 0)

            if fixed_n >= 0:
                model.Add(dev_N[0] == 0); model.Add(dev_N[1] == 0)
            else:
                model.Add(int(shift_target[2]) - dev_N[0] <= num_s[2])
                model.Add(num_s[2] <= _max_avr(shift_target[2]) + dev_N[1])

            if is_total_fixed:
                model.Add(dev_tot[0] == 0); model.Add(dev_tot[1] == 0)
            else:
                model.Add(int(total_target) - dev_tot[0] <= num_total)
                model.Add(num_total <= _max_avr(total_target) + dev_tot[1])

            model.Add(int(holiday_target) - dev_hol[0] <= hol_worked)
            model.Add(hol_worked <= _max_avr(holiday_target) + dev_hol[1])


    # Total individual D/E deviation is NOT mixed into the existing Quality score.
    # It is optimized only after the existing quality objective is fixed, so it
    # cannot worsen the current k/k1/k2/k3/k4 + junior/grade priority.
    if individual_de_dev_terms:
        individual_de_dev_total = model.NewIntVar(
            0,
            max_balance_dev * len(individual_de_dev_terms),
            "individual_DE_deviation_total",
        )
        model.Add(individual_de_dev_total == sum(individual_de_dev_terms))
    else:
        individual_de_dev_total = 0

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
    # `adv` remains the schedule-quality penalty shown to the user.
    adv = balance_penalty + junior_penalty
    is_multi = "다중" in solver_mode

    # Extra count is a strict first priority. Placement is a separate SOFT tradeoff:
    # Ideal should matter, but not so absolutely that all extras pile into one date.
    # Defaults: Ideal preference 3, date spread 2, duty-cell spread 1.
    ideal_placement_weight = max(0, int(params.get("ideal_placement_weight", 3)))
    date_spread_weight = max(0, int(params.get("date_spread_weight", 2)))
    duty_cell_spread_weight = max(0, int(params.get("duty_cell_spread_weight", 1)))
    placement_penalty = (
        # Prefer placing unavoidable extras into explicitly configured Ideal cells.
        # Without ideal_shortfall_total here, a blank/non-Ideal cell could score the
        # same as an under-filled Ideal cell, which defeats the purpose of Ideal.
        ideal_shortfall_total * ideal_placement_weight
        + over_ideal_total * ideal_placement_weight
        + day_concentration_total * date_spread_weight
        + duty_concentration_total * duty_cell_spread_weight
    )

    # Phase 1 differs by staffing model:
    # - If EVERYONE has fixed_Total, the monthly total assignment count is already
    #   mathematically fixed. There is nothing to optimize about the number of extras.
    #   We hard-fix that known extra count and make phase 1 a pure feasibility search.
    # - Otherwise, keep the original strict first priority: minimize extra staffing.
    all_totals_fixed = (len(free_total_doctors) == 0)
    predetermined_extra_duty = None

    def _clear_objective():
        try:
            model.ClearObjective()
        except AttributeError:
            try:
                model.clear_objective()
            except AttributeError:
                pass

    if all_totals_fixed:
        predetermined_extra_duty = int(fixed_total_sum - total_duty)
        if predetermined_extra_duty < 0:
            raise RuntimeError(
                f"INFEASIBLE: 모든 사람의 fixed_Total 합({fixed_total_sum})이 "
                f"Duty 최소합({total_duty})보다 작습니다."
            )
        if duty_extra_vars:
            model.Add(duty_extra_total == predetermined_extra_duty)
        elif predetermined_extra_duty != 0:
            raise RuntimeError(
                "INFEASIBLE: fixed_Total 합 때문에 추가근무가 필요하지만 "
                "추가배정 가능한 활성 Duty가 없습니다."
            )
        _clear_objective()
    else:
        model.Minimize(duty_extra_total)

    # ── Solve ─────────────────────────────────────────────────────────────────

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
                'Total': tot, 'maximum_total': int(maximum_total.get(n, -1)), 'minimum_N': int(minimum_n.get(n, -1)), 'maximum_N': int(maximum_n.get(n, -1)), '연차': annual_cnt, 'Holiday': hol,
                'Fri_N': fri_n,
                '주간평균hr': round((d_cnt*8 + e_cnt*9 + n_cnt*8) / num_days * 7, 2),
            })
        return sol, pd.DataFrame(rows)

    metrics = []

    # The total time budget is shared dynamically.  Unused time from an earlier
    # phase automatically remains available to later phases.
    total_time_budget = max(3.0, float(time_max))
    solve_started_at = time.monotonic()

    def _remaining_time() -> float:
        return max(0.0, total_time_budget - (time.monotonic() - solve_started_at))

    def _new_solver(limit_seconds: float):
        s = cp_model.CpSolver()
        s.parameters.max_time_in_seconds = max(0.1, float(limit_seconds))
        s.parameters.linearization_level = 0
        return s

    search_progress: list[dict[str, Any]] = []
    plateau_stop_events: list[dict[str, Any]] = []
    stage_timeline: list[dict[str, Any]] = []

    def _solver_stop_async(solver_obj):
        try:
            solver_obj.stop_search()
            return
        except Exception:
            pass
        try:
            solver_obj.StopSearch()
        except Exception:
            pass

    def _solve_monitored(
        solver_obj,
        *,
        stage: str,
        value_exprs: dict[str, Any] | None = None,
        monitor_enabled: bool = False,
    ):
        """Solve one stage and record exact total-time diagnostics.

        When monitor_enabled=True, optional plateau stopping is based on BOTH:
        - incumbent objective improvement, and
        - best-bound improvement (when supported by this OR-Tools version).

        Progress rows include incumbent improvements AND throttled bound-only
        improvements, so the graph does not look falsely flat while CP-SAT is
        still proving a better bound.
        """
        stage_started = time.monotonic()
        stage_start_total = stage_started - solve_started_at

        # Low-overhead path: still record stage duration/status, but no callbacks.
        if not monitor_enabled:
            status_code = solver_obj.Solve(model)
            stage_end = time.monotonic()
            try:
                final_obj = float(solver_obj.ObjectiveValue())
            except Exception:
                final_obj = None
            try:
                final_bound = float(solver_obj.BestObjectiveBound())
            except Exception:
                final_bound = None
            status_name = _status_name(solver_obj, status_code)
            stage_timeline.append({
                "stage": stage,
                "start_seconds": round(stage_start_total, 3),
                "end_seconds": round(stage_end - solve_started_at, 3),
                "duration_seconds": round(stage_end - stage_started, 3),
                "status": status_name,
                "stop_reason": (
                    "optimal_or_complete"
                    if status_code == cp_model.OPTIMAL
                    else "time_or_solver_stop"
                    if status_code == cp_model.FEASIBLE
                    else status_name.lower()
                ),
                "final_objective": final_obj,
                "final_best_bound": final_bound,
                "bound_monitor_available": False,
            })
            return status_code

        lock = threading.Lock()
        done_event = threading.Event()
        bound_monitor_available = hasattr(solver_obj, "best_bound_callback")
        state = {
            "has_solution": False,
            "best_obj": None,
            "best_bound": None,
            "last_incumbent_time": None,
            "last_bound_time": None,
            "last_progress_record_time": stage_started,
            "stopped_for_plateau": False,
        }

        def _append_progress(
            *,
            event: str,
            now: float,
            obj,
            bound,
            callback_obj=None,
            force: bool = False,
        ):
            """Append a compact trace row.

            Bound-only events are throttled to at most ~1 row/sec to avoid
            large logs on long runs.
            """
            with lock:
                last_record = float(state["last_progress_record_time"])
                if not force and event == "bound" and (now - last_record) < 1.0:
                    return
                state["last_progress_record_time"] = now

            point = {
                "stage": stage,
                "event": event,
                "seconds": round(now - solve_started_at, 3),
                "stage_seconds": round(now - stage_started, 3),
                "objective": obj,
                "best_bound": bound,
            }
            if callback_obj is not None and value_exprs:
                for key, expr in value_exprs.items():
                    try:
                        point[key] = int(callback_obj.Value(expr))
                    except Exception:
                        point[key] = None
            search_progress.append(point)

        class _ProgressCallback(cp_model.CpSolverSolutionCallback):
            def on_solution_callback(self):
                now = time.monotonic()
                try:
                    obj = float(self.ObjectiveValue())
                except Exception:
                    obj = None
                try:
                    bound = float(self.BestObjectiveBound())
                except Exception:
                    bound = None

                incumbent_improved = False
                bound_improved = False
                with lock:
                    state["has_solution"] = True

                    if obj is not None and (
                        state["best_obj"] is None or obj < state["best_obj"] - 1e-9
                    ):
                        state["best_obj"] = obj
                        state["last_incumbent_time"] = now
                        incumbent_improved = True

                    if bound is not None and (
                        state["best_bound"] is None or bound > state["best_bound"] + 1e-9
                    ):
                        state["best_bound"] = bound
                        state["last_bound_time"] = now
                        bound_improved = True

                if incumbent_improved:
                    _append_progress(
                        event="incumbent",
                        now=now,
                        obj=obj,
                        bound=bound,
                        callback_obj=self,
                        force=True,
                    )
                elif bound_improved:
                    _append_progress(
                        event="bound",
                        now=now,
                        obj=state["best_obj"],
                        bound=bound,
                        callback_obj=None,
                    )

        callback = _ProgressCallback()

        if bound_monitor_available:
            def _best_bound_callback(bound_value):
                now = time.monotonic()
                try:
                    bound = float(bound_value)
                except Exception:
                    return

                improved = False
                with lock:
                    if (
                        state["best_bound"] is None
                        or bound > state["best_bound"] + 1e-9
                    ):
                        state["best_bound"] = bound
                        state["last_bound_time"] = now
                        improved = True
                    current_obj = state["best_obj"]

                if improved:
                    _append_progress(
                        event="bound",
                        now=now,
                        obj=current_obj,
                        bound=bound,
                        callback_obj=None,
                    )

            try:
                solver_obj.best_bound_callback = _best_bound_callback
            except Exception:
                bound_monitor_available = False

        def _watchdog():
            while not done_event.wait(0.5):
                now = time.monotonic()
                with lock:
                    has_solution = bool(state["has_solution"])
                    last_inc = state["last_incumbent_time"]
                    last_bound = state["last_bound_time"]

                if not has_solution:
                    continue

                stage_elapsed = now - stage_started
                incumbent_stale = (
                    last_inc is not None
                    and (now - float(last_inc)) >= plateau_seconds
                )

                if bound_monitor_available:
                    # If no bound event has been observed yet, do not call it a
                    # two-signal plateau. Be conservative and keep searching.
                    bound_stale = (
                        last_bound is not None
                        and (now - float(last_bound)) >= plateau_seconds
                    )
                else:
                    # Older OR-Tools: degrade gracefully to incumbent-only plateau.
                    bound_stale = True

                if (
                    stage_elapsed >= plateau_min_runtime
                    and incumbent_stale
                    and bound_stale
                ):
                    with lock:
                        state["stopped_for_plateau"] = True
                    _solver_stop_async(solver_obj)
                    return

        watchdog = threading.Thread(
            target=_watchdog,
            name=f"cp_sat_plateau_{stage}",
            daemon=True,
        )
        watchdog.start()
        try:
            status_code = solver_obj.Solve(model, callback)
        finally:
            done_event.set()
            watchdog.join(timeout=1.0)

        stage_end = time.monotonic()

        try:
            final_obj = float(solver_obj.ObjectiveValue())
        except Exception:
            final_obj = state["best_obj"]
        try:
            final_bound = float(solver_obj.BestObjectiveBound())
        except Exception:
            final_bound = state["best_bound"]

        if state["has_solution"]:
            _append_progress(
                event="final",
                now=stage_end,
                obj=final_obj,
                bound=final_bound,
                callback_obj=None,
                force=True,
            )

        status_name = _status_name(solver_obj, status_code)

        if state["stopped_for_plateau"]:
            stop_reason = "plateau"
            plateau_stop_events.append({
                "stage": stage,
                "start_seconds": round(stage_start_total, 2),
                "end_seconds": round(stage_end - solve_started_at, 2),
                "stage_seconds": round(stage_end - stage_started, 2),
                "plateau_seconds": plateau_seconds,
                "best_objective": state["best_obj"],
                "best_bound": state["best_bound"],
                "bound_monitor_available": bound_monitor_available,
            })
        elif status_code == cp_model.OPTIMAL:
            stop_reason = "optimal_or_complete"
        elif status_code == cp_model.FEASIBLE:
            stop_reason = "time_limit"
        else:
            stop_reason = status_name.lower()

        gap_abs = None
        gap_pct = None
        if final_obj is not None and final_bound is not None:
            try:
                gap_abs = max(0.0, float(final_obj) - float(final_bound))
                gap_pct = (
                    0.0
                    if gap_abs == 0
                    else 100.0 * gap_abs / max(1.0, abs(float(final_obj)))
                )
            except Exception:
                gap_abs = None
                gap_pct = None

        stage_timeline.append({
            "stage": stage,
            "start_seconds": round(stage_start_total, 3),
            "end_seconds": round(stage_end - solve_started_at, 3),
            "duration_seconds": round(stage_end - stage_started, 3),
            "status": status_name,
            "stop_reason": stop_reason,
            "final_objective": final_obj,
            "final_best_bound": final_bound,
            "final_gap": gap_abs,
            "final_gap_pct": gap_pct,
            "bound_monitor_available": bound_monitor_available,
        })

        return status_code

    def _is_solution_status(status_code) -> bool:
        return status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def _status_name(solver_obj, status_code) -> str:
        try:
            return solver_obj.StatusName(status_code)
        except Exception:
            return str(status_code)

    def _raise_primary_failure(stage_label: str, solver_obj, status_code):
        name = _status_name(solver_obj, status_code).upper()
        if status_code == cp_model.INFEASIBLE or name == "INFEASIBLE":
            raise RuntimeError(
                f"INFEASIBLE: {stage_label}에서 hard constraint를 만족하는 해가 없다고 증명되었습니다."
            )
        if status_code == cp_model.MODEL_INVALID or name == "MODEL_INVALID":
            raise RuntimeError(
                f"MODEL_INVALID: {stage_label} 모델이 유효하지 않습니다. 코드/입력 검사가 필요합니다."
            )
        # UNKNOWN means the solver did NOT prove infeasibility; it simply did not
        # find a feasible schedule within the allotted search time.
        raise RuntimeError(
            f"UNKNOWN: {stage_label}에서 제한 시간 내 feasible 해를 찾지 못했습니다. "
            "불가능하다고 증명된 것은 아닙니다. 탐색 시간을 늘리거나 hard rule을 확인하세요."
        )

    # Keep a feasible shift assignment as a solver hint for later optimization.
    # ClearHints is version-dependent, so older OR-Tools versions simply retain
    # the first feasible hint instead of replacing it.
    hint_already_added = False

    def _apply_shift_hint(source_solver):
        nonlocal hint_already_added
        cleared = False
        for method_name in ("ClearHints", "clear_hints"):
            method = getattr(model, method_name, None)
            if callable(method):
                try:
                    method()
                    cleared = True
                    hint_already_added = False
                except Exception:
                    pass
                break
        if hint_already_added and not cleared:
            return
        try:
            for var in shifts.values():
                model.AddHint(var, int(source_solver.Value(var)))
            hint_already_added = True
        except Exception:
            # Hints are a performance aid only; never make correctness depend on them.
            pass

    # ── Phase 1 ──────────────────────────────────────────────────────────────
    # All-fixed_Total roster: pure FEASIBILITY search with the known extra count.
    # Otherwise: optimize the minimum number of extras as before.
    phase1_label = "feasibility" if all_totals_fixed else "extra 최소화"
    phase1_fraction = 0.50 if all_totals_fixed else 0.40
    phase1_limit = max(1.0, min(_remaining_time(), total_time_budget * phase1_fraction))
    phase1_solver = _new_solver(phase1_limit)
    phase1_status = _solve_monitored(
        phase1_solver,
        stage=("feasibility" if all_totals_fixed else "extra"),
        monitor_enabled=False,
    )

    if not _is_solution_status(phase1_status):
        _raise_primary_failure(phase1_label, phase1_solver, phase1_status)

    phase1_status_name = _status_name(phase1_solver, phase1_status)
    if all_totals_fixed:
        best_extra_duty = int(predetermined_extra_duty or 0)
        extra_status_name = "SKIPPED_FIXED_TOTAL_ALL"
        feasibility_status_name = phase1_status_name
    else:
        best_extra_duty = phase1_solver.Value(duty_extra_total) if duty_extra_vars else 0
        model.Add(duty_extra_total == best_extra_duty)
        extra_status_name = phase1_status_name
        feasibility_status_name = phase1_status_name

    # For the all-fixed case the equality was already added before phase 1.
    _apply_shift_hint(phase1_solver)

    # The latest successful solver is always preserved.  Later soft optimization
    # is allowed to time out without throwing this feasible schedule away.
    final_solver = phase1_solver
    final_stage = "feasibility" if all_totals_fixed else "extra"
    fallback_used = False

    placement_solver = None
    placement_status = None
    placement_status_name = "SKIPPED_NO_TIME"
    best_placement_penalty = phase1_solver.Value(placement_penalty)
    placement_completed = False

    # ── Phase 2: Ideal + even placement ─────────────────────────────────────
    remaining = _remaining_time()
    if remaining >= 0.75:
        _clear_objective()
        model.Minimize(placement_penalty)

        # Leave meaningful time for phase 3 when possible.
        placement_limit = max(0.5, remaining * 0.60)
        placement_solver = _new_solver(placement_limit)
        placement_status = _solve_monitored(
            placement_solver,
            stage="placement",
            monitor_enabled=early_stop_on_plateau,
        )
        placement_status_name = _status_name(placement_solver, placement_status)

        if _is_solution_status(placement_status):
            best_placement_penalty = placement_solver.Value(placement_penalty)
            model.Add(placement_penalty == best_placement_penalty)
            final_solver = placement_solver
            final_stage = "placement"
            placement_completed = True
            _apply_shift_hint(placement_solver)
        else:
            # IMPORTANT: objective optimization failure is not a schedule failure.
            # We keep the already feasible phase-1 schedule.
            fallback_used = True

    # ── Phase 3: existing individual/grade/junior quality ──────────────────
    # Preserve the existing objective first.  Leave some of the remaining budget
    # for a lexicographic D/E refinement step below.
    quality_solver = None
    quality_status = None
    quality_status_name = "SKIPPED"
    quality_completed = False
    best_quality_adv = None

    if placement_completed and _remaining_time() >= 0.50:
        _clear_objective()
        model.Minimize(adv)

        quality_remaining = _remaining_time()
        quality_limit = (
            max(0.5, quality_remaining * 0.70)
            if individual_de_dev_terms and quality_remaining >= 1.50
            else quality_remaining
        )
        quality_solver = _new_solver(quality_limit)
        quality_status = _solve_monitored(
            quality_solver,
            stage="quality",
            value_exprs={
                "k": k,
                "k1": k1,
                "k2": k2,
                "k3": k3,
                "k4": k4,
            },
            monitor_enabled=early_stop_on_plateau,
        )
        quality_status_name = _status_name(quality_solver, quality_status)

        if _is_solution_status(quality_status):
            best_quality_adv = quality_solver.Value(adv)
            final_solver = quality_solver
            final_stage = "quality"
            quality_completed = True
            _apply_shift_hint(quality_solver)
        else:
            # Keep phase-2 feasible result. UNKNOWN here only means quality
            # optimization did not finish/find a solution in its allotted slice.
            fallback_used = True

    # ── Phase 4: individual D/E deviation SUM refinement ────────────────────
    # IMPORTANT: adv is fixed to the best Phase-3 value first.  Therefore this
    # phase can only choose a more even D/E solution without worsening the existing
    # quality score; it cannot sacrifice k/N/holiday/grade/junior quality.
    de_refine_solver = None
    de_refine_status = None
    de_refine_status_name = "SKIPPED"
    de_refinement_completed = False
    best_individual_de_dev = (
        final_solver.Value(individual_de_dev_total)
        if individual_de_dev_terms else 0
    )

    if (
        quality_completed
        and individual_de_dev_terms
        and _remaining_time() >= 0.50
    ):
        # Do not worsen the incumbent Quality score, but allow the D/E refinement
        # to discover a schedule whose true quality is even better.
        model.Add(adv <= int(best_quality_adv))
        _clear_objective()
        model.Minimize(individual_de_dev_total)

        de_refine_solver = _new_solver(_remaining_time())
        de_refine_status = _solve_monitored(
            de_refine_solver,
            stage="de_refine",
            value_exprs={
                "de_individual": individual_de_dev_total,
                "k": k,
                "k1": k1,
                "k2": k2,
                "k3": k3,
                "k4": k4,
            },
            monitor_enabled=early_stop_on_plateau,
        )
        de_refine_status_name = _status_name(de_refine_solver, de_refine_status)

        if _is_solution_status(de_refine_status):
            best_individual_de_dev = de_refine_solver.Value(individual_de_dev_total)
            final_solver = de_refine_solver
            final_stage = "de_refine"
            de_refinement_completed = True
            _apply_shift_hint(de_refine_solver)
        else:
            # Keep the Phase-3 quality solution.
            fallback_used = True

    # Even if phase 2/3/4 times out, final_solver is guaranteed feasible because
    # phase 1 only reaches this point with FEASIBLE/OPTIMAL.
    best_adv = final_solver.Value(adv)
    allowed_adv = best_adv + adv_limit if is_multi else best_adv

    def _actual_final_quality(value_fn):
        """Recompute final quality components from the actual assignment.

        Soft auxiliary variables (k/dev/excess) are guaranteed to be tight while
        their own objective is being minimized, but a later lexicographic phase can
        leave them with harmless slack.  User-facing final metrics should therefore
        be derived from the schedule itself.
        """
        de_low = de_high = 0
        hol_low = hol_high = 0
        total_low = total_high = 0
        n_low = n_high = 0
        de_sum = 0

        for n in all_doctors:
            sc = shift_counts.get(n, {})
            counts = [
                int(value_fn(person_shift_count_exprs[n][s]))
                for s in all_shifts
            ]

            # D/E: fixed D or E is an explicit instruction and is excluded from
            # fairness deviation, matching the model semantics.
            for s, sk in ((0, "D"), (1, "E")):
                if int(sc.get(sk, -1)) >= 0:
                    continue
                low_target = int(person_shift_targets[n][s])
                high_target = _max_avr(person_shift_targets[n][s])
                low_dev = max(0, low_target - counts[s])
                high_dev = max(0, counts[s] - high_target)
                de_low = max(de_low, low_dev)
                de_high = max(de_high, high_dev)
                de_sum += low_dev + high_dev

            # N
            if int(sc.get("N", -1)) < 0:
                low_target = int(person_shift_targets[n][2])
                high_target = _max_avr(person_shift_targets[n][2])
                n_low = max(n_low, max(0, low_target - counts[2]))
                n_high = max(n_high, max(0, counts[2] - high_target))

            # Total
            if int(sc.get("Total", -1)) < 0:
                actual_total = int(value_fn(person_total_exprs[n]))
                low_target = int(balance_total_target[n])
                high_target = _max_avr(balance_total_target[n])
                total_low = max(total_low, max(0, low_target - actual_total))
                total_high = max(total_high, max(0, actual_total - high_target))

            # Holiday
            actual_holiday = int(value_fn(person_holiday_exprs[n]))
            low_target = int(person_holiday_target[n])
            high_target = _max_avr(person_holiday_target[n])
            hol_low = max(hol_low, max(0, low_target - actual_holiday))
            hol_high = max(hol_high, max(0, actual_holiday - high_target))

        # Grade maximum deviation from actual duty composition.
        actual_k4 = 0
        if weight_grade_dev > 0 and num_doctors > 0:
            for d in all_days:
                for s in all_shifts:
                    if duty_requests[d][s] <= 0:
                        continue
                    actual_count = int(value_fn(duty_count_vars[(d, s)]))
                    grade_sum_10 = sum(
                        int(value_fn(shifts[(n, d, s)])) * grades.get(n, 2) * 10
                        for n in all_doctors
                    )
                    actual_k4 = max(
                        actual_k4,
                        abs(grade_sum_10 - avr_grade_10 * actual_count),
                    )

        # Junior excess from actual duty composition.
        actual_junior_excess = 0
        if junior_penalty_weight > 0 and junior_doctors:
            for d in all_days:
                for s in all_shifts:
                    if duty_requests[d][s] <= 0:
                        continue
                    junior_count = sum(
                        int(value_fn(shifts[(n, d, s)]))
                        for n in junior_doctors
                    )
                    actual_junior_excess += max(
                        0, junior_count - junior_soft_max_count
                    )

        actual_k = de_low + de_high
        actual_k1 = hol_low + hol_high
        actual_k2 = total_low + total_high
        actual_k3 = n_low + n_high

        actual_balance_penalty = (
            actual_k * weight_de_dev
            + actual_k1 * weight_holiday_dev
            + actual_k2 * weight_total_dev
            + actual_k3 * weight_n_dev
            + actual_k4 * weight_grade_dev
        )
        actual_junior_penalty = actual_junior_excess * junior_penalty_weight
        actual_adv = actual_balance_penalty + actual_junior_penalty

        return {
            "actual_k": actual_k,
            "actual_k_low": de_low,
            "actual_k_high": de_high,
            "actual_k1": actual_k1,
            "actual_k1_low": hol_low,
            "actual_k1_high": hol_high,
            "actual_k2": actual_k2,
            "actual_k2_low": total_low,
            "actual_k2_high": total_high,
            "actual_k3": actual_k3,
            "actual_k3_low": n_low,
            "actual_k3_high": n_high,
            "actual_k4": actual_k4,
            "actual_de_deviation_total": de_sum,
            "actual_junior_excess": actual_junior_excess,
            "actual_junior_penalty": actual_junior_penalty,
            "actual_balance_penalty": actual_balance_penalty,
            "actual_adv": actual_adv,
        }

    def _metric_dict(value_fn):
        actual_quality = _actual_final_quality(value_fn)
        return {
            "adv": value_fn(adv),
            "duty_extra": value_fn(duty_extra_total) if duty_extra_vars else 0,
            "duty_minimum_total": total_duty,
            "duty_ideal_total": total_ideal_duty,
            "ideal_configured_cells": ideal_configured_cells,
            "duty_ideal_D": total_ideal_s[0],
            "duty_ideal_E": total_ideal_s[1],
            "duty_ideal_N": total_ideal_s[2],
            "actual_duty_total": total_duty + (value_fn(duty_extra_total) if duty_extra_vars else 0),
            "balance_planned_D": round(planned_shift_totals[0], 2),
            "balance_planned_E": round(planned_shift_totals[1], 2),
            "balance_planned_N": round(planned_shift_totals[2], 2),
            "ideal_shortfall_total": value_fn(ideal_shortfall_total) if ideal_shortfall_vars else 0,
            "over_ideal_total": value_fn(over_ideal_total) if over_ideal_vars else 0,
            "max_day_extra": value_fn(max_day_extra),
            "max_duty_extra": value_fn(max_duty_extra),
            "days_with_extra": (num_days - value_fn(day_unused_penalty)) if day_used_extra_vars else 0,
            "duty_cells_with_extra": (len(duty_extra_vars) - value_fn(duty_unused_penalty)) if duty_used_extra_vars else 0,
            "day_extra_concentration": value_fn(day_concentration_total) if day_concentration_vars else 0,
            "duty_extra_concentration": value_fn(duty_concentration_total) if duty_concentration_vars else 0,
            "placement_penalty": value_fn(placement_penalty),
            "ideal_placement_weight": ideal_placement_weight,
            "date_spread_weight": date_spread_weight,
            "duty_cell_spread_weight": duty_cell_spread_weight,
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
            "individual_de_deviation_total": (
                value_fn(individual_de_dev_total) if individual_de_dev_terms else 0
            ),
            "best_individual_de_deviation": best_individual_de_dev,
            "de_refinement_status": de_refine_status_name,
            "de_refinement_completed": de_refinement_completed,
            "best_adv": best_adv,
            "allowed_adv": allowed_adv,
            "adv_extra_allowed": adv_limit if is_multi else 0,
            "all_totals_fixed": all_totals_fixed,
            "predetermined_extra_duty": predetermined_extra_duty,
            "feasibility_status": feasibility_status_name,
            "extra_optimization_status": extra_status_name,
            "placement_optimization_status": placement_status_name,
            "best_placement_penalty": best_placement_penalty,
            "optimization_status": quality_status_name,
            "final_solution_stage": final_stage,
            "fallback_used": fallback_used,
            "quality_completed": quality_completed,
            "early_stop_on_plateau": early_stop_on_plateau,
            "plateau_seconds": plateau_seconds,
            "plateau_min_runtime": plateau_min_runtime,
            "plateau_stop_events": list(plateau_stop_events),
            "search_progress": list(search_progress),
            "stage_timeline": list(stage_timeline),
            **actual_quality,
        }

    if not is_multi:
        sol, summ = _extract(final_solver.Value)
        solutions.append(sol)
        summaries.append(summ)
        metrics.append(_metric_dict(final_solver.Value))
    else:
        # Preserve the known feasible solution before attempting enumeration.
        fallback_sol, fallback_summ = _extract(final_solver.Value)
        fallback_metric = _metric_dict(final_solver.Value)

        # Multi-solution search is optional refinement. Failure/timeout here must
        # never erase the feasible schedule already found above.
        model.Add(adv <= allowed_adv)
        _clear_objective()
        _apply_shift_hint(final_solver)

        enum_solver = _new_solver(max(1.0, total_time_budget * 0.25))
        enum_solver.parameters.enumerate_all_solutions = True

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
        enum_status = enum_solver.Solve(model, cb)

        if not solutions:
            fallback_metric = dict(fallback_metric)
            fallback_metric["fallback_used"] = True
            fallback_metric["multi_enumeration_status"] = _status_name(enum_solver, enum_status)
            fallback_metric["final_solution_stage"] = final_stage + "+multi_fallback"
            solutions.append(fallback_sol)
            summaries.append(fallback_summ)
            metrics.append(fallback_metric)

    return solutions, summaries, metrics
