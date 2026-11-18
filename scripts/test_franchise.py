"""구단 연도별 성적 검증: python -m unittest discover -s scripts -p test_franchise.py"""

import unittest

import franchise


def team_record(team_id, wins, losses, div_rank=None, lg_rank="1", rs=700, ra=650, ties=0):
    item = {
        "team": {"id": team_id, "name": f"Team {team_id}", "abbreviation": f"T{team_id}"},
        "leagueRank": lg_rank,
        "gamesBack": "-",
        "leagueRecord": {"wins": wins, "losses": losses, "ties": ties},
        "runsScored": rs,
        "runsAllowed": ra,
    }
    if div_rank is not None:
        item["divisionRank"] = div_rank
    return item


def game(away, home, home_wins):
    return {
        "status": {"abstractGameState": "Final"},
        "teams": {"away": {"team": {"id": away}, "isWinner": not home_wins}, "home": {"team": {"id": home}, "isWinner": home_wins}},
    }


def series(kind, games):
    return {"series": {"id": kind + "_1", "gameType": kind}, "games": games}


class StandingsTest(unittest.TestCase):
    def test_division_rank_used_when_divisions_exist(self):
        rows = franchise.parse_standings({"records": [
            {"league": {"id": 103}, "division": {"id": 201}, "teamRecords": [team_record(1, 90, 72, div_rank="2", lg_rank="5")]},
        ]})
        self.assertEqual((rows[0]["lg"], rows[0]["rankType"], rows[0]["rank"]), ("AL", "div", 2))

    def test_league_rank_before_divisions(self):
        rows = franchise.parse_standings({"records": [
            {"league": {"id": 104}, "teamRecords": [team_record(1, 91, 63, lg_rank="1", ties=3)]},
        ]})
        self.assertEqual((rows[0]["lg"], rows[0]["rankType"], rows[0]["rank"], rows[0]["T"]), ("NL", "lg", 1, 3))

    def test_missing_runs_stay_none(self):
        item = team_record(1, 50, 50)
        del item["runsScored"]
        rows = franchise.parse_standings({"records": [{"league": {"id": 103}, "teamRecords": [item]}]})
        self.assertIsNone(rows[0]["RS"])


class PostseasonTest(unittest.TestCase):
    def test_champion_runner_up_and_earlier_exits(self):
        result = franchise.parse_postseason({"series": [
            series("D", [game(3, 1, True), game(3, 1, True), game(1, 3, False)]),  # 1이 3을 이김
            series("L", [game(2, 1, True), game(2, 1, True)]),  # 1이 2를 이김
            series("W", [game(1, 4, False), game(1, 4, False), game(4, 1, True)]),  # 1이 4를 2승 1패로 이김
        ]})
        self.assertEqual(result, {1: "WS", 4: "W", 2: "L", 3: "D"})

    def test_unfinished_series_not_decided(self):
        result = franchise.parse_postseason({"series": [series("W", [game(1, 2, True), game(2, 1, True)])]})
        self.assertEqual(result, {})

    def test_tiebreaker_ignored(self):
        result = franchise.parse_postseason({"series": [{"series": {"id": "R_1_2", "gameType": "R"}, "games": [game(1, 2, True)]}]})
        self.assertEqual(result, {})


class BuildClubTest(unittest.TestCase):
    def test_rows_newest_first_with_expected_record(self):
        cache = {
            "1990": {"teams": [{"id": 1, "name": "Old Name", "abbr": "OLD", "lg": "NL", "W": 80, "L": 82, "T": 0,
                                "rankType": "div", "rank": 3, "GB": "10.0", "RS": None, "RA": 700}], "post": {}},
            "2025": {"teams": [{"id": 1, "name": "New Name", "abbr": "NEW", "lg": "NL", "W": 100, "L": 62, "T": 0,
                                "rankType": "div", "rank": 1, "GB": "-", "RS": 800, "RA": 600}], "post": {"1": "WS"}},
        }
        rows = franchise.build_club(1, cache)
        self.assertEqual([row["season"] for row in rows], [2025, 1990])
        self.assertEqual(rows[0]["post"], "WS")
        self.assertEqual(rows[0]["xW"] + rows[0]["xL"], 162)
        self.assertIsNone(rows[1]["xW"])  # 득점이 없으면 기대 승패를 만들지 않는다
        self.assertEqual(rows[1]["name"], "Old Name")
        self.assertNotIn("id", rows[0])


if __name__ == "__main__":
    unittest.main()
