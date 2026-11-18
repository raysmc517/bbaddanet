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

    def test_hof_december_election_is_next_year_induction(self):
        # 12월 위원회 선출은 다음 해 헌액, 1월 기자단 선출과 11-01로 채운 옛 행은 그대로
        hof = [
            dict(item(2021, 1, "Gil Hodges"), date="2021-12-05"),
            dict(item(2018, 2, "Vladimir Guerrero"), date="2018-01-24"),
            dict(item(1936, 3, "Babe Ruth"), date="1936-11-01"),
        ]
        _people, rows = awards.assemble({"MLBHOF": hof, "WSMVP": [dict(item(2021, 4, "D Four"), date="2021-12-05")]}, lambda pid: True)
        years = {(row[0], row[3]): row[1] for row in rows}
        self.assertEqual(years, {("hof", 1): 2022, ("hof", 2): 2018, ("hof", 3): 1936, ("wsmvp", 4): 2021})

    def test_later_blank_position_does_not_overwrite(self):
        # 월드시리즈 우승 응답의 알 수 없는 포지션(빈 값)이 앞서 받은 포지션을 지우지 않는다
        people, _rows = awards.assemble(
            {"WSCHAMP": [item(1995, 1, "Chipper Jones", pos="")],
             "MLBHOF": [item(2018, 1, "Chipper Jones", pos="3B"), item(2000, 2, "B Two", pos="")], "ALMVP": [item(1991, 2, "B Two", pos="C")]},
            lambda pid: True,
        )
        self.assertEqual(people["1"][1], "3B")
        self.assertEqual(people["2"][1], "C")  # 앞이 빈 값이면 뒤의 값으로 채운다

    def test_profile_position_preferred(self):
        # 선수 프로필의 주 포지션이 있으면 그것을, 없으면 수상 응답의 포지션을 쓴다
        people, _rows = awards.assemble(
            {"MLBHOF": [item(2018, 1, "Andruw Jones", pos="OF"), item(2000, 2, "B Two", pos="C")]},
            lambda pid: True,
            lambda pid: {1: "CF"}.get(pid, ""),
        )
        self.assertEqual((people["1"][1], people["2"][1]), ("CF", "C"))

    def test_unfiltered_rows_kept_with_non_mlb_team_cleared(self):
        # sportId=1에 없던 행(대표팀·옛 구단 ID·팀 없음)도 남기고, 그 팀은 MLB 구단이 아니므로 비운다
        mlb = [item(2023, 1, "A One", team="MIL", team_id=158)]
        everything = mlb + [item(2023, 2, "Devin Williams", team="USA", team_id=940), item(2018, 3, "Vladimir Guerrero", team="", team_id=3823)]
        merged = awards.merge_unfiltered(mlb, everything)
        self.assertEqual([(m["id"], m["team"], m["teamId"]) for m in merged], [(1, "MIL", 158), (2, "", None), (3, "", None)])
        self.assertEqual(everything[1]["team"], "USA")  # 원본 목록은 바꾸지 않는다

    def test_award_keys_unique(self):
        keys = [key for key, _label, _sources in awards.AWARDS]
        ids = [award_id for _key, _label, sources in awards.AWARDS for award_id, _league in sources]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
