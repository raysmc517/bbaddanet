"""구단 조직 구성 검증: python -m unittest discover -s scripts -p test_teams.py"""

import unittest

import teams


def club(club_id, name, abbr, parent=None, country="USA", city="City"):
    return {
        "id": club_id, "name": name, "abbr": abbr, "parentId": parent,
        "league": "L", "leagueAbbr": "L", "division": "D", "divisionShort": "D", "firstYear": 1900,
        "venue": {"id": club_id, "name": "Park", "city": city, "state": "ST", "country": country},
    }


class AssembleTest(unittest.TestCase):
    def test_affiliates_grouped_by_parent_in_level_order(self):
        clubs, orphans = teams.assemble(
            {
                "MLB": [club(2, "B Club", "BBB"), club(1, "A Club", "AAA")],
                "AA": [club(12, "Double", "DBL", parent=1)],
                "AAA": [club(11, "Triple", "TRP", parent=1)],
                "Rookie": [club(16, "Rook", "RK", parent=1)],
            },
            {"MLB": {"AAA": 1.05}, "AAA": {"TRP": 0.98}},
        )
        self.assertEqual(orphans, 0)
        self.assertEqual([c["name"] for c in clubs], ["A Club", "B Club"])
        self.assertEqual([a["level"] for a in clubs[0]["affiliates"]], ["AAA", "AA", "Rookie"])
        self.assertEqual(clubs[1]["affiliates"], [])

    def test_missing_park_factor_stays_none(self):
        clubs, _ = teams.assemble(
            {"MLB": [club(1, "A Club", "AAA")], "AAA": [club(11, "Triple", "TRP", parent=1)]},
            {"MLB": {}, "AAA": {"TRP": 0.98}},
        )
        self.assertIsNone(clubs[0]["pf"])  # 중립값 1.0으로 채우지 않는다
        self.assertEqual(clubs[0]["affiliates"][0]["pf"], 0.98)

    def test_unknown_parent_is_not_attached(self):
        clubs, orphans = teams.assemble(
            {"MLB": [club(1, "A Club", "AAA")], "AAA": [club(11, "Lost", "LST", parent=999)]}, {}
        )
        self.assertEqual(orphans, 1)
        self.assertEqual(clubs[0]["affiliates"], [])

    def test_official_site_only_for_major_clubs(self):
        major = dict(club(1, "Chicago White Sox", "CWS"), teamName="White Sox")
        minor = dict(club(11, "Charlotte Knights", "CLT", parent=1), teamName="Knights")
        clubs, _ = teams.assemble({"MLB": [major], "AAA": [minor]}, {})
        self.assertEqual(clubs[0]["site"], "https://www.mlb.com/whitesox")
        self.assertNotIn("teamName", clubs[0])
        self.assertNotIn("site", clubs[0]["affiliates"][0])
        self.assertNotIn("teamName", clubs[0]["affiliates"][0])
        self.assertEqual(teams.official_site("D-backs"), "https://www.mlb.com/dbacks")
        self.assertIsNone(teams.official_site(""))

    def test_placeholder_dominican_city_removed(self):
        fixed = teams.fix_placeholder_location(club(5, "DSL X", "DX", country="DOM", city="New York"))
        self.assertIsNone(fixed["venue"]["city"])
        self.assertEqual(fixed["venue"]["country"], "Dominican Republic")
        kept = teams.fix_placeholder_location(club(6, "DSL Y", "DY", country="Dominican Republic", city="Boca Chica"))
        self.assertEqual(kept["venue"]["city"], "Boca Chica")


class ClubHistoryTest(unittest.TestCase):
    AWARDS = {
        "people": {"1": ["A One", "OF", 1], "2": ["B Two", "P", 0]},
        "rows": [
            ["wschamp", 1990, "", 1, "OLD", 7],  # 연고지 이전 전 약칭이어도 팀 ID가 같으면 같은 구단
            ["wschamp", 1990, "", 2, "OLD", 7],
            ["wschamp", 2020, "", 1, "NEW", 7],
            ["wschamp", 2021, "", 1, "XXX", 8],
            ["mvp", 2020, "AL", 1, "NEW", 7],
            ["mvp", 2021, "AL", 1, "NEW", 7],
            ["hof", 2030, "", 2, "NEW", 7],
            ["hof", 2025, "", 1, "", None],  # 명판 팀이 없는 헌액자는 어느 구단에도 넣지 않는다
        ],
    }

    def test_titles_awards_hof_counted_by_team_id(self):
        history = teams.club_history(7, self.AWARDS, [], lambda player_id: True)
        self.assertEqual(history["titles"], [2020, 1990])  # 선수 여러 명이어도 시즌당 한 번
        self.assertEqual(history["awards"], {"mvp": 2, "cy": 0, "roy": 0})
        self.assertEqual(history["hof"], [{"id": 2, "name": "B Two", "year": 2030, "page": 0}])

    def test_missing_awards_file_stays_none(self):
        history = teams.club_history(7, None, [], lambda player_id: True)
        self.assertIsNone(history["titles"])  # 우승 0회로 표시하지 않는다
        self.assertIsNone(history["awards"])
        self.assertIsNone(history["hof"])
        self.assertEqual(history["retired"], [])

    def test_retired_numbers_sorted_numerically(self):
        def retired(number, player_id, year):
            return {"season": year, "id": player_id, "name": f"P{player_id}", "pos": "", "team": "", "teamId": 7, "note": number}

        history = teams.club_history(
            7, None, [retired("#42", 1, 1997), retired("No number", 2, 1950), retired("4 - Owner", 3, 1939)], lambda player_id: player_id == 3
        )
        self.assertEqual([item["number"] for item in history["retired"]], ["4", "42", ""])
        self.assertEqual([item["page"] for item in history["retired"]], [1, 0, 0])


if __name__ == "__main__":
    unittest.main()
