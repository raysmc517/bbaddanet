import json
import tempfile
import unittest
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
