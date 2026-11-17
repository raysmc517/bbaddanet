"""수상 기록 구성 검증: python -m unittest discover -s scripts -p test_awards.py"""

import unittest

import awards


def item(season, player_id, name, pos="OF", team="AAA", team_id=10):
    return {"season": season, "id": player_id, "name": name, "pos": pos, "team": team, "teamId": team_id, "note": ""}


class AssembleTest(unittest.TestCase):
    def test_league_awards_merged_with_league_kept(self):
        people, rows = awards.assemble(
            {"ALMVP": [item(2024, 1, "A One")], "NLMVP": [item(2024, 2, "B Two", team="BBB")]},
            lambda player_id: player_id == 1,
        )
        self.assertEqual(rows, [["mvp", 2024, "AL", 1, "AAA", 10], ["mvp", 2024, "NL", 2, "BBB", 10]])
        self.assertEqual(people, {"1": ["A One", "OF", 1], "2": ["B Two", "OF", 0]})

    def test_duplicates_removed_but_shared_award_kept(self):
        # 같은 선수의 중복 행은 하나로, 같은 시즌 공동 수상은 둘 다 남긴다
        _people, rows = awards.assemble(
            {"WSMVP": [item(1981, 1, "A One"), item(1981, 1, "A One"), item(1981, 2, "B Two")]},
            lambda player_id: False,
        )
        self.assertEqual([row[3] for row in rows], [1, 2])

    def test_rows_ordered_by_award_then_latest_season(self):
        _people, rows = awards.assemble(
            {
                "ALMVP": [item(1999, 1, "A One"), item(2001, 1, "A One")],
                "MLBHOF": [item(2010, 1, "A One", team="", team_id=None)],
            },
            lambda player_id: True,
        )
        self.assertEqual([(row[0], row[1]) for row in rows], [("hof", 2010), ("mvp", 2001), ("mvp", 1999)])
        self.assertEqual(rows[0][4:], ["", None])  # 원본에 없는 팀은 빈 문자열, ID는 None

    def test_award_keys_unique(self):
        keys = [key for key, _label, _sources in awards.AWARDS]
        ids = [award_id for _key, _label, sources in awards.AWARDS for award_id, _league in sources]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
