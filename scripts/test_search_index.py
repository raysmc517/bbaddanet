"""검색 색인 검증: python -m unittest discover -s scripts -p test_search_index.py"""

import json
import tempfile
import unittest
from pathlib import Path

import search_index


class SearchIndexTest(unittest.TestCase):
    def test_entry_seasons_and_mlb_flag(self):
        player = {"id": 1, "name": "Pedro Martínez", "pos": "P", "batting": [],
                  "pitching": [{"season": 1990, "level": "Rookie"}, {"season": 2009, "level": "MLB"}]}
        self.assertEqual(search_index.entry(player), [1, "Pedro Martínez", "P", 1990, 2009, 1])

    def test_entry_without_records(self):
        player = {"id": 2, "name": "No Games", "pos": "C", "batting": [], "pitching": []}
        self.assertEqual(search_index.entry(player), [2, "No Games", "C", None, None, 0])

    def test_build_keeps_existing_index_when_no_players(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "players").mkdir()
            (root / "search.json").write_text('{"players":[[9,"Old","P",2000,2001,1]]}', encoding="utf-8")
            with self.assertRaises(ValueError):
                search_index.build(root)
            self.assertEqual(json.loads((root / "search.json").read_text(encoding="utf-8"))["players"][0][0], 9)

    def test_build_sorts_by_id(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "players").mkdir()
            for player_id in (10, 9):
                (root / "players" / f"{player_id}.json").write_text(
                    json.dumps({"id": player_id, "name": "N", "pos": "P", "batting": [], "pitching": []}), encoding="utf-8")
            self.assertEqual(search_index.build(root), 2)
            saved = json.loads((root / "search.json").read_text(encoding="utf-8"))
            self.assertEqual([row[0] for row in saved["players"]], [9, 10])


if __name__ == "__main__":
    unittest.main()
