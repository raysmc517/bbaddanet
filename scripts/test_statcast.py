import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import statcast


def batting_csv(**changes):
    row = {"player_id": "1", "attempts": "10", "avg_hit_speed": "95", "max_hit_speed": "110",
           "avg_hit_angle": "-2", "ev95percent": "0", "brl_percent": "0", "anglesweetspotpercent": "30"}
    row.update(changes)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=row.keys())
    writer.writeheader()
    writer.writerow(row)
    return "\ufeff" + stream.getvalue()


def pitch_row(**changes):
    row = {"pitcher": "1", "sport_id": 1, "year": "2025", "n": "100", "pitch_hand": "R"}
    for code in statcast.PITCH_TYPES:
        row["n_" + code] = None
        row["n_" + code + "_formatted"] = None
    row.update({"n_ff": "75.0", "n_ff_formatted": "75.0", "ff_avg_speed": "95", "ff_avg_spin": None, "ff_avg_break_x": "-10", "ff_avg_break_z_induced": "15",
                "n_fastball": 0.75, "fastball_avg_speed": "95"})
    row.update(changes)
    return row


def page(rows):
    return "<script>var data = " + json.dumps(rows) + "; var other = 1;</script>"


class StatcastTest(unittest.TestCase):
    def test_average_weights_samples_excludes_missing_and_separates_hand_and_pitch(self):
        batting = {"1": {"bbe": 10, "exitVelocity": 100, "launchAngle": None, "hardHitPct": 0},
                   "2": {"bbe": 30, "exitVelocity": 80, "launchAngle": 20, "hardHitPct": 40}}
        pitching = {"1": {"pitches": 100, "hand": "R", "arsenal": [{"type": "FF", "usagePct": 50, "velocity": 100, "spin": None, "horizontal": -10, "ivb": 10}]},
                    "2": {"pitches": 300, "hand": "R", "arsenal": [{"type": "FF", "usagePct": 50, "velocity": 80, "spin": 2000, "horizontal": 0, "ivb": 20}]},
                    "3": {"pitches": 1000, "hand": "L", "arsenal": [{"type": "FF", "usagePct": 100, "velocity": 90, "spin": 0, "horizontal": 10, "ivb": 15}]}}
        a = statcast.averages(batting, pitching)
        self.assertEqual(a["batters"]["exitVelocity"], 85)
        self.assertEqual(a["batters"]["launchAngle"], 20)
        self.assertEqual(a["batters"]["hardHitPct"], 30)
        self.assertNotIn("maxExitVelocity", a["batters"])
        self.assertIsNone(a["batters"]["barrelPct"])
        self.assertEqual(a["pitchers"]["R:FF"]["velocity"], 85)
        self.assertEqual(a["pitchers"]["R:FF"]["spin"], 2000)
        self.assertEqual(a["pitchers"]["R:FF"]["horizontal"], -2.5)
        self.assertEqual(a["pitchers"]["L:FF"]["spin"], 0)

    def test_batting_preserves_zero_missing_and_negative_launch_angle(self):
        result = statcast.batters(batting_csv())["1"]
        self.assertEqual(result["hardHitPct"], 0)
        self.assertEqual(result["barrelPct"], 0)
        self.assertEqual(result["launchAngle"], -2)
        text = batting_csv(max_hit_speed="null")
        self.assertIsNone(statcast.batters(text)["1"]["maxExitVelocity"])

    def test_one_unmeasured_batter_does_not_erase_measured_players(self):
        first = batting_csv()
        second = batting_csv(player_id="2", avg_hit_speed="", avg_hit_angle="")
        combined = first + second.split("\n", 1)[1]
        data = statcast.batters(combined)
        self.assertIsNone(data["2"]["exitVelocity"])
        self.assertIsNone(data["2"]["launchAngle"])
        self.assertEqual(data["1"]["exitVelocity"], 95)

    def test_empty_error_pages_and_duplicate_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            statcast.batters("<html>error</html>")
        with self.assertRaises(ValueError):
            statcast.batters(batting_csv(avg_hit_speed="", avg_hit_angle=""))
        with self.assertRaises(ValueError):
            statcast.pitchers(page([]), 2025)
        with self.assertRaises(ValueError):
            statcast.pitchers(page([pitch_row(), pitch_row()]), 2025)

    def test_usage_is_percent_not_count_and_aggregate_groups_are_excluded(self):
        row = statcast.pitchers(page([pitch_row()]), 2025)["1"]
        self.assertEqual(row["pitches"], 100)
        self.assertEqual(len(row["arsenal"]), 1)
        pitch = row["arsenal"][0]
        self.assertEqual(pitch["usagePct"], 75)
        self.assertNotIn("count", pitch)
        self.assertIsNone(pitch["spin"])
        self.assertEqual(pitch["horizontal"], -10)
        self.assertEqual(pitch["ivb"], 15)

    def test_wrong_season_league_truncation_and_missing_fields_are_rejected(self):
        for changes in ({"year": "2024"}, {"sport_id": 11}):
            with self.assertRaises(ValueError):
                statcast.pitchers(page([pitch_row(**changes)]), 2025)
        with self.assertRaises(ValueError):
            statcast.pitchers("var data = [{", 2025)
        row = pitch_row()
        del row["ff_avg_speed"]
        with self.assertRaises(ValueError):
            statcast.pitchers(page([row]), 2025)

    def test_forkball_internal_fraction_and_fastball_percent_use_display_percent(self):
        row = pitch_row(n_ff="0.4", n_ff_formatted="0.4", n_fo=0.25, n_fo_formatted="25.0",
                        fo_avg_speed="85", fo_avg_spin="1000", fo_avg_break_x="-5", fo_avg_break_z_induced="1")
        pitches = statcast.pitchers(page([row]), 2025)["1"]["arsenal"]
        self.assertEqual([(p["type"], p["usagePct"]) for p in pitches], [("FO", 25), ("FF", 0.4)])

    def test_nonfinite_numbers_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaises(ValueError):
                statcast.number(value)

    def test_failed_collection_keeps_last_good_file_and_index(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "statcast").mkdir()
            path = root / "statcast" / "2025.json"
            path.write_text('{"batters":{"1":{}},"pitchers":{"2":{}}}', encoding="utf-8")
            before = path.read_bytes()
            with mock.patch.object(statcast, "DATA", root), mock.patch.object(statcast, "get", side_effect=RuntimeError("network")):
                self.assertEqual(statcast.main(["--season", "2025", "--refresh"]), 1)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(json.loads((root / "statcast" / "index.json").read_text(encoding="utf-8")), {"seasons": [2025]})

    def test_sharp_coverage_drop_is_rejected_before_replacing_season(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "statcast").mkdir()
            (root / "statcast" / "2025.json").write_text(json.dumps({"batters": {str(i): {} for i in range(10)}}), encoding="utf-8")
            with mock.patch.object(statcast, "DATA", root), mock.patch.object(statcast, "get", side_effect=[batting_csv(), page([pitch_row()])]):
                with self.assertRaisesRegex(ValueError, "급감"):
                    statcast.collect(2025)

    def test_switch_pitcher_hands_are_kept_separate_without_averaging(self):
        rows = [pitch_row(pitch_hand="L", n="341"), pitch_row(pitch_hand="R", n="148", ff_avg_speed="90")]
        player = statcast.pitchers(page(rows), 2025)["1"]
        self.assertEqual(player["pitches"], 489)
        self.assertEqual(player["arsenal"], [])
        self.assertEqual([(h["hand"], h["pitches"], h["arsenal"][0]["velocity"]) for h in player["handSplits"]],
                         [("L", 341, 95), ("R", 148, 90)])

    def test_backfill_range_skips_cached_seasons_and_keeps_current_refresh(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "statcast").mkdir()
            (root / "statcast" / "2015.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(statcast, "DATA", root), mock.patch.object(statcast, "collect", return_value={"batters": {}, "pitchers": {}}) as collect:
                self.assertEqual(statcast.main(["--from", "2015", "--to", "2016"]), 0)
                collect.assert_called_once_with(2016)
                collect.reset_mock()
                self.assertEqual(statcast.main(["--current-season"]), 0)
                collect.assert_called_once_with(2026)


if __name__ == "__main__":
    unittest.main()
