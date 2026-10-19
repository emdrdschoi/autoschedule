import unittest
from unittest.mock import patch

import scheduler


@unittest.skipUnless(scheduler.ORTOOLS_AVAILABLE, "ortools required")
class LinkedConflictTests(unittest.TestCase):
    def params(self):
        return {
            "doctors": ["A", "B"], "num_days": 3, "start_date": "2026-11-01",
            "day_types": {}, "duty_requests": {d: [1, 0, 1] for d in range(3)},
            "rules": {}, "shift_counts": {}, "shift_requests": {},
            "previous_schedule_days": 5, "previous_schedule": {},
        }

    def test_night_chain_missed_by_independent_capacity(self):
        params = self.params()
        self.assertFalse(scheduler.diagnose_window_capacity(params)["windows"])
        result = scheduler.diagnose_linked_conflicts(params)
        self.assertEqual(result["status"], "PROVEN_SHORTAGE")
        self.assertEqual(result["date"], "11/03")
        self.assertEqual(result["required"], 2)
        self.assertEqual(result["capacity"], 1)
        work = {(r["이름"], r["날짜"]) for r in result["facts"]
                if r["피할 수 없는 배치"].startswith("반드시 근무")}
        self.assertEqual(work, {(n, d) for n in ("A", "B") for d in ("11/01", "11/02")})
        # Either person may be the night worker; do not label one as forced OFF.
        self.assertFalse(any(r["날짜"] == "11/03" for r in result["facts"]))
        self.assertTrue(any(r["구분"] == "예시 배치의 연결" for r in result["explanations"]))

    def test_relaxation_resolves_chain(self):
        params = self.params()
        params["rules"] = {0: {"rule_n_block_max": 3}}
        result = scheduler.diagnose_linked_conflicts(params)
        self.assertEqual(result["status"], "NO_CONFLICT_FOUND")
        self.assertFalse(result["facts"])

    def test_unknown_and_timeout_are_not_conflicts(self):
        result = scheduler.diagnose_linked_conflicts(self.params(), time_limit=0)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertTrue(result["incomplete"])
        with patch.object(scheduler.cp_model.CpSolver, "Solve", return_value=scheduler.cp_model.UNKNOWN):
            result = scheduler.diagnose_linked_conflicts(self.params())
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertFalse(result["facts"])

    def test_personal_conflict_is_not_a_staffing_chain(self):
        params = self.params()
        params["shift_counts"] = {0: {"Total": 4}}
        result = scheduler.diagnose_linked_conflicts(params)
        self.assertEqual(result["status"], "PERSONAL_INFEASIBLE")


if __name__ == "__main__":
    unittest.main()
