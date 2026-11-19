import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import player_context as context


class AverageTest(unittest.TestCase):
    def test_outs_and_weighted_rates(self):
        self.assertEqual(context.outs("5.1"), 16)
        self.assertEqual(context.outs("0.2"), 2)
        with self.assertRaises(ValueError):
            context.outs("5.3")
        rows = [{"inningsPitched": "5.1", "earnedRuns": 2, "hits": 4, "baseOnBalls": 1, "strikeOuts": 5, "battersFaced": 22},
                {"inningsPitched": "0.2", "earnedRuns": 0, "hits": 0, "baseOnBalls": 0, "strikeOuts": 1, "battersFaced": 2}]
        result = context.rates(rows, "pitching")
        self.assertEqual(result["ERA"], 3)
        self.assertEqual(result["WHIP"], 0.83333)
        self.assertEqual(result["Kp"], 0.25)

    def test_batting_uses_totals_not_mean_of_rates(self):
        rows = [{"atBats": 10, "hits": 5, "baseOnBalls": 0, "hitByPitch": 0, "sacFlies": 0, "totalBases": 8, "plateAppearances": 10, "strikeOuts": 0},
                {"atBats": 90, "hits": 15, "baseOnBalls": 10, "hitByPitch": 0, "sacFlies": 0, "totalBases": 22, "plateAppearances": 100, "strikeOuts": 20}]
        result = context.rates(rows, "hitting")
        self.assertEqual(result["AVG"], 0.2)
        self.assertEqual(result["SLG"], 0.3)
        self.assertAlmostEqual(result["OBP"], 30 / 110, places=5)

    def test_missing_is_not_zero_and_zero_denominators(self):
        self.assertIsNone(context.rates([], "hitting")["AVG"])
        self.assertIsNone(context.rates([{"atBats": 0, "hits": 0}], "hitting")["AVG"])
        self.assertIsNone(context.rates([{"atBats": 5, "hits": 1}], "hitting")["OPS"])
        self.assertIsNone(context.rates([{"inningsPitched": "0.0", "earnedRuns": 2}], "pitching")["ERA"])

    def test_truncated_or_empty_response_rejected(self):
        with mock.patch.object(context.statsapi, "_get", return_value={"stats": []}):
            with self.assertRaises(ValueError):
                context.average(2025)
            with self.assertRaises(ValueError):
                context.splits(2025)
        payload = {"stats": [{"splits": [{"player": {"id": 1}}], "totalSplits": 2}]}
        with mock.patch.object(context.statsapi, "_get", return_value=payload):
            with self.assertRaisesRegex(ValueError, "잘림"):
                context.splits(2025)

    def test_failed_splits_keep_last_good_season_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "situations" / "2025.json"
            path.parent.mkdir()
            path.write_text('{"players":{"9":{}}}', encoding="utf-8")
            (root / "mlb_averages.json").write_text(json.dumps({"2025": {"hitting": {"AVG": 0.25}}}), encoding="utf-8")
            before = path.read_bytes()
            with mock.patch.object(context, "DATA", root), mock.patch("sys.argv", ["player_context.py", "--from", "2025", "--to", "2025"]), mock.patch.object(context, "splits", side_effect=ValueError("빈 응답")):
                self.assertEqual(context.main(), 1)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
