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

    def test_non_risp_sums_bases_empty_and_runner_on_first(self):
        r0 = {"plateAppearances": 391, "atBats": 339, "hits": 87, "homeRuns": 20, "rbi": 20, "baseOnBalls": 46, "strikeOuts": 102,
              "hitByPitch": 4, "sacFlies": 0, "totalBases": 165}
        r1 = {"plateAppearances": 90, "atBats": 77, "hits": 27, "homeRuns": 3, "rbi": 11, "baseOnBalls": 11, "strikeOuts": 18,
              "hitByPitch": 2, "sacFlies": 1, "totalBases": 43}
        result = context.non_risp([r0, r1], "hitting")
        self.assertEqual(result["plateAppearances"], 481)
        self.assertEqual(result["atBats"], 416)
        self.assertEqual(result["avg"], ".274")
        self.assertEqual(result["obp"], f"{(114 + 57 + 6) / (416 + 57 + 6 + 1):.3f}"[1:])
        self.assertEqual(result["slg"], ".500")
        self.assertNotIn("battersFaced", result)
        # 1루 상황에 출전하지 않은 선수는 주자 없음 기록만으로 평시를 만든다.
        self.assertEqual(context.non_risp([r0, None], "hitting")["plateAppearances"], 391)
        self.assertIsNone(context.non_risp([None, None], "hitting"))

    def test_non_risp_pitching_uses_outs_and_keeps_missing(self):
        r0 = {"battersFaced": 22, "atBats": 20, "hits": 4, "baseOnBalls": 1, "hitByPitch": 0, "sacFlies": 0, "totalBases": 6,
              "inningsPitched": "5.1", "earnedRuns": 1, "homeRuns": 0, "rbi": 1, "strikeOuts": 5}
        r1 = dict(r0, inningsPitched="0.2", battersFaced=3, atBats=3, hits=0, baseOnBalls=0, totalBases=0, earnedRuns=0)
        result = context.non_risp([r0, r1], "pitching")
        self.assertEqual(result["inningsPitched"], "6.0")
        self.assertEqual(result["battersFaced"], 25)
        self.assertEqual(result["whip"], "0.83")
        # 0분모와 누락 항목은 0이 아닌 빈 값으로 둔다.
        empty = context.non_risp([{"atBats": 0, "hits": 0, "plateAppearances": 1, "baseOnBalls": 1}], "hitting")
        self.assertNotIn("avg", empty)
        self.assertNotIn("obp", empty)

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
