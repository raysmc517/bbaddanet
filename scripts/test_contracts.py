import copy
import json
import tempfile
import unittest
from pathlib import Path

import contracts


class ContractsTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.data = Path(self.folder.name)
        (self.data / "players").mkdir()
        (self.data / "players" / "1.json").write_text('{"name":"A"}', encoding="utf-8")
        (self.data / "teams.json").write_text('{"clubs":[{"abbr":"SF"}]}', encoding="utf-8")
        self.payload = {"checked": "2026-11-19", "players": {"1": [{
            "name": "A", "team": "SF", "from": 2024, "to": 2025, "totalUSD": 120,
            "source": "https://www.mlb.com/news/a", "signingBonusUSD": 10, "buyoutUSD": 5,
            "salaryComplete": True, "salaries": [{"from": 2024, "to": 2024, "baseUSD": 50, "deferredUSD": 20},
                                                  {"from": 2025, "to": 2025, "baseUSD": 55}],
        }]}}

    def check_bad(self, change, message):
        data = copy.deepcopy(self.payload)
        change(data["players"]["1"][0])
        self.assertTrue(any(message in error for error in contracts.validate(data, self.data)))

    def test_bonus_and_buyout_in_total_deferral_not_subtracted(self):
        self.assertEqual(contracts.validate(self.payload, self.data), [])

    def test_missing_season_cannot_be_called_complete(self):
        self.check_bad(lambda r: r["salaries"].pop(), "미확인 시즌")

    def test_option_salary_outside_guaranteed_period_rejected(self):
        self.check_bad(lambda r: r["salaries"][0].update({"from": 2026, "to": 2026}), "기간 밖")

    def test_duplicate_season_and_over_deferral_rejected(self):
        self.check_bad(lambda r: r["salaries"].append(r["salaries"][0]), "중복")
        self.check_bad(lambda r: r["salaries"][0].update({"deferredUSD": 51}), "초과")

    def test_player_and_source_must_match(self):
        self.check_bad(lambda r: r.update({"name": "Other"}), "불일치")
        self.check_bad(lambda r: r.update({"salarySource": "javascript:alert(1)"}), "출처 오류")

    def test_partial_schedule_and_actual_zero_allowed(self):
        data = copy.deepcopy(self.payload)
        record = data["players"]["1"][0]
        record["salaryComplete"] = False
        record["salaries"] = [{"from": 2024, "to": 2024, "baseUSD": 0}]
        self.assertEqual(contracts.validate(data, self.data), [])

    def test_unknown_imported_header_amount_is_explicit_and_not_complete(self):
        data = copy.deepcopy(self.payload)
        row = data["players"]["1"][0]
        row.update({"totalUSD": None, "amountUnknown": True, "listedTeam": True, "salaryComplete": False, "salaries": []})
        self.assertEqual(contracts.validate(data, self.data), [])
        row["amountUnknown"] = False
        self.assertTrue(any("totalUSD" in error for error in contracts.validate(data, self.data)))

    def test_curated_contracts(self):
        data = json.loads((contracts.DATA / "contracts.json").read_text(encoding="utf-8"))
        self.assertEqual(contracts.validate(data), [])


if __name__ == "__main__":
    unittest.main()
