import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import careers


class CareerTests(unittest.TestCase):
    def test_team_rows_without_total_or_postseason_duplicates(self):
        split = {"season": "2020", "team": {"id": 1, "name": "Team"},
                 "sport": {"id": 14}, "gameType": "R", "stat": {
                     "gamesPitched": 1, "outs": 16, "earnedRuns": 2}}
        total = {**split, "team": None}
        playoff = {**split, "gameType": "P"}
        person = {"id": 123, "fullName": "Test", "stats": [{
            "group": {"displayName": "pitching"},
            "splits": [split, split, total, playoff]}]}
        rows = careers.convert(person, 14)["pitching"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outs"], 16)
        self.assertNotIn("FIP", rows[0])

    def test_fields_missing_in_old_seasons_stay_none(self):
        # 1914년 기록처럼 원본에 도루 실패·희생플라이가 없으면 0이 아니라 None이어야 한다.
        split = {"season": "1914", "team": {"id": 111, "name": "Boston Red Sox"},
                 "sport": {"id": 1}, "gameType": "R", "stat": {
                     "gamesPlayed": 5, "plateAppearances": 10, "atBats": 10, "hits": 2,
                     "stolenBases": 0, "homeRuns": 0, "avg": ".200", "slg": ".300"}}
        person = {"id": 121578, "fullName": "Test", "stats": [{
            "group": {"displayName": "hitting"}, "splits": [split]}]}
        row = careers.convert(person, 1)["batting"][0]
        self.assertIsNone(row["CS"])
        self.assertIsNone(row["SF"])
        self.assertEqual(row["SB"], 0)  # 원본에 있는 0은 그대로 0
        self.assertEqual(row["PA"], 10)

    def test_past_flag_marks_retired_players(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            careers.write(root / "players/1.json", {"id": 1, "past": True})
            careers.write(root / "players/2.json", {"id": 2, "active": False})
            self.assertTrue(careers.is_past(1, root))
            self.assertFalse(careers.is_past(2, root))  # 최근 리더보드에 있던 비활동 선수는 기존대로
            self.assertFalse(careers.is_past(3, root))  # 선수 파일이 없으면 전체 레벨

    def test_past_minor_eligible_from_2000_mlb_season(self):
        self.assertTrue(careers.past_minor_eligible([{"level": "MLB", "season": 2000}]))
        self.assertTrue(careers.past_minor_eligible([{"level": "MLB", "season": 1995}, {"level": "MLB", "season": 2003}]))
        self.assertFalse(careers.past_minor_eligible([{"level": "MLB", "season": 1999}]))
        self.assertFalse(careers.past_minor_eligible([{"level": "AAA", "season": 2005}]))  # 마이너 기록은 기준이 아님
        self.assertFalse(careers.past_minor_eligible([]))

    def test_past_players_get_minor_records_only_if_mlb_after_2000(self):
        def season_split(season):
            return {"season": str(season), "gameType": "R", "team": {"id": 10, "name": "T"},
                    "stat": {"gamesPlayed": 3, "plateAppearances": 5}}

        mlb_seasons = {1: 1990, 2: 2004}  # 1번은 1999년까지, 2번은 2000년 이후 MLB 출전
        calls = []

        def fake_get(path, params):
            ids = [int(i) for i in params["personIds"].split(",")]
            sport = int(params["hydrate"].split("sportId=")[1].split(",")[0])
            calls.append((sport, ids))
            season = mlb_seasons if sport == 1 else {i: 2001 for i in ids}
            return {"people": [{"id": i, "fullName": f"P{i}", "stats": [
                {"group": {"displayName": "hitting"}, "splits": [season_split(season[i])]}]} for i in ids]}

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for pid in (1, 2):
                careers.write(root / f"players/{pid}.json", {"id": pid, "past": True, "batting": [], "pitching": []})
            with mock.patch.object(careers, "DATA", root),                     mock.patch.object(careers, "is_past", lambda pid: True),                     mock.patch.object(careers.statsapi, "_get", fake_get),                     mock.patch.object(careers, "fill_team_abbr", lambda table, cached: True),                     mock.patch.object(careers, "load_team_abbr", lambda: {}),                     mock.patch.object(careers, "merge_cached", lambda player: None):
                self.assertEqual(careers.main(["--ids", "1", "2"]), 0)
            self.assertEqual(calls[0], (1, [1, 2]))
            self.assertTrue(all(ids == [2] for sport, ids in calls[1:]))
            self.assertEqual(len(calls), len(careers.SPORTS))
            levels = lambda pid: {r["level"] for r in json.loads((root / f"careers/{pid}.json").read_text(encoding="utf-8"))["batting"]}
            self.assertEqual(levels(1), {"MLB"})
            self.assertEqual(levels(2), set(careers.SPORTS.values()))

    def test_chunks(self):
        self.assertEqual(careers.chunks([1, 2, 3], 2), [[1, 2], [3]])
        self.assertEqual(careers.chunks([]), [])

    def test_refresh_replaces_history_preserves_current_saber(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            past = {"season": 2020, "level": "Rookie", "team": "Test", "G": 4, "careerSource": True}
            recent = {"season": 2026, "level": "MLB", "team": "Test", "wRCp": 125}
            player = {"id": 1, "batting": [recent, {**past, "G": 1}], "pitching": []}
            careers.write(root / "careers/1.json", {"batting": [past], "pitching": [], "updated": "now"})
            careers.merge_cached(player, root)
            careers.merge_cached(player, root)
            self.assertEqual(len(player["batting"]), 2)
            self.assertEqual(player["batting"][1]["G"], 4)
            self.assertEqual(player["batting"][0]["wRCp"], 125)
            self.assertEqual(player["careerStart"], 2020)

    def test_team_abbr_by_level_and_season(self):
        career = {"batting": [
            {"season": 2018, "level": "MLB", "team": "Los Angeles Angels", "teamId": 108},
            {"season": 2024, "level": "Rookie", "team": "DSL Brewers 1", "teamId": 607},
            {"season": 2023, "level": "MLB", "team": "Unknown Club", "teamId": 999},
        ], "pitching": []}
        calls = []

        def fetch(sport, season):
            calls.append((sport, season))
            if sport == 1 and season == 2023:
                raise RuntimeError("네트워크 오류")
            return {108: "LAA", 607: "D-BW1"}

        table = {"16-2024": {"607": "D-BW1"}}
        self.assertFalse(careers.fill_team_abbr(table, [career], fetch))
        # 이미 받은 레벨·시즌은 다시 요청하지 않는다.
        self.assertEqual(sorted(calls), [(1, 2018), (1, 2023)])
        self.assertTrue(careers.apply_team_abbr(career, table))
        rows = career["batting"]
        self.assertEqual((rows[0]["team"], rows[0]["teamName"]), ("LAA", "Los Angeles Angels"))
        self.assertEqual(rows[1]["team"], "D-BW1")
        # 약자를 못 찾으면 기존 이름을 그대로 둔다.
        self.assertEqual(rows[2]["team"], "Unknown Club")
        self.assertFalse(careers.apply_team_abbr(career, table))


if __name__ == "__main__":
    unittest.main()
