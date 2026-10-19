import unittest
from unittest.mock import patch

import scheduler


@unittest.skipUnless(scheduler.ORTOOLS_AVAILABLE, "ortools required")
class WindowCapacityTests(unittest.TestCase):
    def params(self):
        return {
            "doctors": ["A"], "num_days": 2, "start_date": "2026-11-01",
            "day_types": {}, "duty_requests": {0: [1, 0, 0], 1: [1, 0, 0]},
            "shift_requests": {}, "rules": {}, "shift_counts": {},
            "previous_schedule_days": 5,
            "previous_schedule": {f"0,{h}": "D" for h in range(4)},
        }

    def test_history_creates_two_day_shortage(self):
        result = scheduler.diagnose_window_capacity(self.params())
        row = result["windows"][0]
        self.assertEqual(row["구간"], "11/01~11/02")
        self.assertEqual(row["필요 근무수"], 2)
        self.assertEqual(row["개인 최대 합계(상한)"], 1)
        self.assertEqual(result["people"][0]["개인 최대 근무수"], 1)

    def test_feasible_and_multiple_shifts_are_not_false_shortages(self):
        params = self.params()
        params["previous_schedule"] = {}
        self.assertFalse(scheduler.diagnose_window_capacity(params)["windows"])
        params["num_days"] = 1
        params["duty_requests"] = {0: [1, 1, 0]}
        params["rules"] = {0: {"rule_max_shifts_per_day": 3}}
        params["shift_counts"] = {0: {"Total": 2}}
        self.assertFalse(scheduler.diagnose_window_capacity(params)["windows"])

    def test_timeout_and_unknown_are_not_proofs(self):
        result = scheduler.diagnose_window_capacity(self.params(), time_limit=0)
        self.assertTrue(result["incomplete"])
        self.assertFalse(result["windows"])
        with patch.object(scheduler.cp_model.CpSolver, "Solve", return_value=scheduler.cp_model.UNKNOWN):
            result = scheduler.diagnose_window_capacity(self.params())
        self.assertTrue(result["incomplete"])
        self.assertFalse(result["windows"])

    def test_personal_infeasibility_is_reported_separately(self):
        params = self.params()
        params["shift_counts"] = {0: {"Total": 2}}
        result = scheduler.diagnose_window_capacity(params)
        self.assertEqual(result["personal_infeasible"], ["A"])
        self.assertFalse(result["windows"])


if __name__ == "__main__":
    unittest.main()
