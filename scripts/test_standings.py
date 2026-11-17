import unittest

import standings


def team(team_id, wins, losses, rs, ra):
    return {"id": team_id, "W": wins, "L": losses, "RS": rs, "RA": ra}


class ExpectedWinsTest(unittest.TestCase):
    def test_matches_mlb_expected_record(self):
        # 2026 탬파베이: 736득점 650실점 162경기 → MLB 공식 기대 승패 90-72
        self.assertEqual(standings.expected_wins(736, 650, 162), 90)

    def test_even_runs_is_half(self):
        self.assertEqual(standings.expected_wins(500, 500, 100), 50)

    def test_missing_or_zero(self):
        self.assertIsNone(standings.expected_wins(None, 10, 10))
        self.assertIsNone(standings.expected_wins(0, 0, 0))
        self.assertIsNone(standings.expected_wins(0, 0, 5))
        self.assertIsNone(standings.expected_wins(10, 5, 0))

    def test_finish_team_adds_losses(self):
        row = standings.finish_team(team(1, 98, 64, 736, 650))
        self.assertEqual((row["xW"], row["xL"]), (90, 72))
        row = standings.finish_team(team(2, 0, 0, None, None))
        self.assertEqual((row["xW"], row["xL"]), (None, None))


class GroupTest(unittest.TestCase):
    leagues = [
        {"id": 117, "name": "International League", "abbr": "INT", "wildCards": 0, "split": True, "games": 150},
        {"id": 126, "name": "Northwest League", "abbr": "NWL", "wildCards": 0, "split": True, "games": 132},
    ]

    def test_groups_by_league_and_names_division_less_league(self):
        groups = [
            {"leagueId": 117, "division": "International League East", "divisionShort": "INT East", "teams": [team(1, 1, 0, 5, 3)]},
            {"leagueId": 126, "division": None, "divisionShort": None, "teams": [team(2, 0, 1, 3, 5)]},
        ]
        result = standings.group_by_league(self.leagues, groups)
        self.assertEqual([league["id"] for league in result], [117, 126])
        self.assertEqual(result[0]["divisions"][0]["short"], "INT East")
        self.assertEqual(result[1]["divisions"][0]["name"], "Northwest League")
        self.assertEqual(result[1]["divisions"][0]["short"], "NWL")

    def test_empty_league_fails_check(self):
        result = standings.group_by_league(self.leagues, [])
        with self.assertRaises(ValueError):
            standings.check_level("aaa", result)

    def test_mlb_requires_thirty_clubs(self):
        league = {"id": 103, "name": "American League", "abbr": "AL", "wildCards": 3, "split": False, "games": 162}
        groups = [{"leagueId": 103, "division": "AL East", "divisionShort": "AL East", "teams": [team(i, 1, 1, 1, 1) for i in range(29)]}]
        with self.assertRaises(ValueError):
            standings.check_level("mlb", standings.group_by_league([league], groups))
        groups[0]["teams"].append(team(99, 1, 1, 1, 1))
        standings.check_level("mlb", standings.group_by_league([league], groups))


if __name__ == "__main__":
    unittest.main()
