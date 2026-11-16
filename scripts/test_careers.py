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


if __name__ == "__main__":
    unittest.main()
