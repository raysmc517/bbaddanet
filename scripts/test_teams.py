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

    def test_placeholder_dominican_city_removed(self):
        fixed = teams.fix_placeholder_location(club(5, "DSL X", "DX", country="DOM", city="New York"))
        self.assertIsNone(fixed["venue"]["city"])
        self.assertEqual(fixed["venue"]["country"], "Dominican Republic")
        kept = teams.fix_placeholder_location(club(6, "DSL Y", "DY", country="Dominican Republic", city="Boca Chica"))
        self.assertEqual(kept["venue"]["city"], "Boca Chica")


if __name__ == "__main__":
    unittest.main()
