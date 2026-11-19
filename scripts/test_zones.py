import csv
import io
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

import zones


def row(**changes):
    result = dict.fromkeys(zones.FIELDS, "")
    result.update(pitch_type="FF", game_date="2026-04-01", game_type="R", pitcher="1", batter="2",
                  plate_x="0", plate_z="2.5", sz_top="3.5", sz_bot="1.5", stand="L", p_throws="R",
                  description="hit_into_play", events="single", game_pk="10", at_bat_number="1", pitch_number="1")
    result.update(changes)
    return result


def csv_text(rows):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=sorted(zones.FIELDS))
    writer.writeheader()
    writer.writerows(rows)
    return "\ufeff" + stream.getvalue()


def aggregate(rows, games=(10,)):
    return zones.aggregate(csv_text(rows), date(2026, 4, 1), date(2026, 4, 3), games)


class ZoneTest(unittest.TestCase):
    def test_cancelled_rain_game_is_not_a_completed_game_even_when_abstract_final(self):
        self.assertFalse(zones.completed({"status": {"abstractGameState": "Final", "codedGameState": "C", "detailedState": "Cancelled: Rain"}}))
        self.assertTrue(zones.completed({"status": {"abstractGameState": "Final", "codedGameState": "F", "detailedState": "Final"}}))

    def test_coordinate_boundaries_catcher_view_and_zone_height(self):
        self.assertEqual(zones.zone(0, .5), 12)
        self.assertEqual(zones.zone(-2, 1.1), 0)
        self.assertEqual(zones.zone(2, -.1), 24)
        self.assertEqual(zones.zone(-zones.HALF_PLATE, 0), 16)
        self.assertEqual(zones.zone(zones.HALF_PLATE, 1), 4)

    def test_denominators_terminal_pitch_and_fouls(self):
        data = aggregate([row(), row(pitch_number="2", events="", description="foul_tip"),
                          row(pitch_number="3", events="walk", description="ball"),
                          row(pitch_number="4", events="strikeout", description="swinging_strike")])
        pitcher = data["players"]["1"]["pitching"][0]
        self.assertEqual(pitcher["zones"]["12"], [4, 3, 1, 2, 1, 1])
        self.assertEqual(data["players"]["2"]["batting"][0]["hand"], "R")
        self.assertEqual(pitcher["hand"], "L")

    def test_missing_coordinate_is_not_zero_and_outside_plot_is_still_in_zone_counts(self):
        data = aggregate([row(plate_x=""), row(pitch_number="2", plate_x="0", plate_z="0"),
                          row(pitch_number="3", plate_x="3")])
        item = data["players"]["1"]["pitching"][0]
        self.assertEqual((item["seen"], item["missing"], item["outside"]), (3, 1, 2))
        self.assertEqual(sum(c[0] for c in item["zones"].values()), 2)
        self.assertEqual(item["density"], [])

    def test_exact_duplicates_removed_conflicts_and_incomplete_games_rejected(self):
        self.assertEqual(aggregate([row(), row()])["pitches"], 1)
        with self.assertRaises(ValueError):
            aggregate([row(), row(events="double")])
        with self.assertRaises(ValueError):
            aggregate([row()], (10, 11))
        with self.assertRaises(ValueError):
            aggregate([row(game_type="S")])
        with self.assertRaises(ValueError):
            aggregate([row(game_date="2025-04-01")])
        with self.assertRaises(ValueError):
            aggregate([row(plate_z="")])

    def test_runner_out_sacrifices_and_walks_do_not_become_at_bats(self):
        data = aggregate([row(pitch_number=str(i + 1), events=event) for i, event in enumerate(
            ["other_out", "sac_fly", "sac_bunt", "sac_fly_double_play", "walk", "hit_by_pitch", "catcher_interf"])])
        cell = data["players"]["2"]["batting"][0]["zones"]["12"]
        self.assertEqual(cell[3:], [0, 0, 0])

    def test_only_known_nonfinal_games_can_be_excluded(self):
        text = csv_text([row(), row(game_pk="11")])
        data = zones.aggregate(text, date(2026, 4, 1), date(2026, 4, 3), {10}, {10, 11})
        self.assertEqual(data["games"], [10])
        self.assertEqual(data["pitches"], 1)

    def test_merge_separates_pitch_and_hand_and_preserves_counts(self):
        first = aggregate([row(), row(pitch_number="2", pitch_type="SL", stand="R")])
        second = aggregate([row(game_pk="11", events="home_run")], (11,))
        merged = zones.merge([first, second])
        ff = next(r for r in merged["1"]["pitching"] if r["pitch"] == "FF")
        self.assertEqual(ff["zones"]["12"], [2, 2, 0, 2, 2, 5])
        self.assertEqual(sum(n for _, n in ff["density"]), 2)
        with self.assertRaises(ValueError):
            zones.merge([first, first])

    def test_fetch_failure_preserves_published_data(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(zones, "DATA", Path(directory)):
            target = Path(directory) / "2026" / "index.json"
            target.parent.mkdir()
            target.write_text('{"sentinel":1}', encoding="utf-8")
            with mock.patch.object(zones, "fetch", side_effect=zones.requests.ConnectionError("offline")):
                with self.assertRaises(zones.requests.ConnectionError):
                    zones.collect(2026)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"sentinel": 1})

    def test_publish_rejects_sample_collapse_before_writing_buckets(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(zones, "DATA", Path(directory)):
            payload = {"season": 2026, "pitches": 100, "players": {"1": {"pitching": []}}}
            zones.publish(payload)
            before = (Path(directory) / "2026" / "index.json").read_bytes()
            with self.assertRaises(ValueError):
                zones.publish({**payload, "pitches": 1})
            self.assertEqual((Path(directory) / "2026" / "index.json").read_bytes(), before)

    def test_bucket_write_failure_leaves_previous_manifest_and_data_readable(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(zones, "DATA", Path(directory)):
            payload = {"season": 2026, "pitches": 100, "players": {"1": {"pitching": []}}}
            zones.publish(payload)
            index = Path(directory) / "2026" / "index.json"
            before = index.read_bytes()
            old = json.loads(before)
            real_write = zones.write
            def fail_bucket(path, data):
                if re_bucket(path.name):
                    raise OSError("disk failure")
                real_write(path, data)
            with mock.patch.object(zones, "write", side_effect=fail_bucket):
                with self.assertRaises(OSError):
                    zones.publish({**payload, "players": {"1": {"batting": []}}})
            self.assertEqual(index.read_bytes(), before)
            self.assertTrue((index.parent / old["buckets"]["01"]).exists())

    def test_cached_season_keeps_original_data_timestamp(self):
        chunk = aggregate([row(pitcher=str(i + 1), batter=str(i + 11), at_bat_number=str(i + 1)) for i in range(10)])
        chunk["updated"] = "2026-04-02T00:00:00+00:00"
        schedule = {"dates": [{"date": "2026-04-01", "games": [{"gamePk": 10, "gameType": "R",
                    "officialDate": "2026-04-01", "status": {"abstractGameState": "Final"}}]}]}
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(zones, "DATA", Path(directory)), \
             mock.patch.object(zones, "datetime") as clock, mock.patch.object(zones, "fetch") as fetch:
            clock.now.return_value = datetime(2026, 11, 20, tzinfo=timezone.utc)
            fetch.return_value.json.return_value = schedule
            zones.write(Path(directory) / "cache" / "2026" / "2026-04-01.json", chunk)
            with mock.patch("builtins.print"):
                zones.collect(2026)
                clock.now.return_value = datetime(2026, 11, 21, tzinfo=timezone.utc)
                zones.collect(2026)
            index = json.loads((Path(directory) / "2026" / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["updated"], chunk["updated"])
            self.assertTrue(index["checked"].startswith("2026-11-21"))
            self.assertEqual(fetch.call_count, 2)  # 매번 일정만 확인하고 CSV를 다시 받지 않는다.


def re_bucket(name):
    return name.startswith("01.") and name.endswith(".json")


if __name__ == "__main__":
    unittest.main()
