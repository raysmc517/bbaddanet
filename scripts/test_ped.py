"""금지약물 징계 목록 읽기·선수 연결 검증: python -m unittest discover -s scripts -p test_ped.py"""

import unittest

import ped

PAGE = """==Suspended players==
===Players who were on major league rosters===
{| class="wikitable sortable plainrowheaders"
|-
!scope="col"|Player
!scope="col"|Team
!scope="col"|Date announced
!scope="col"|Drug
!scope="col"|Penalty
!scope="col"|Position
|-
!scope="row"|{{sortname|Nelson|Cruz}}
|[[Texas Rangers (baseball)|Texas Rangers]]
| rowspan="2" |{{dts|August 5, 2013}}
| rowspan="2" |
|{{sort|050|50 games}}
|[[Outfielder|OF]]
|-
! scope="row" style="background:#fbb;"|{{sortname|Alex|Rodriguez}} <small>MVP</small>
|[[New York Yankees]]
| style="background:#fbb;"|2014 season {{small|({{sort|162|162 games}})}}^{{#tag:ref|initially {{nowrap|211}} games|group=upper-alpha}}
|[[Third baseman|3B]]
|}
===Players with major league experience in a non-affiliated professional league===
{| class="wikitable"
|-
!scope="col"|Player
!scope="col"|Date announced
|-
!scope="row"|{{sortname|Indie|Player}}
|{{dts|May 1, 2015}}
|}
==See also==
"""


class PedTest(unittest.TestCase):
    def test_rowspan_and_cleanup(self):
        rows = ped.parse(PAGE)
        self.assertEqual([r["name"] for r in rows], ["Nelson Cruz", "Alex Rodriguez"])  # 독립리그 표는 넣지 않는다
        self.assertEqual(rows[1]["date"], "2013-08-05")  # 위 행에서 합친 날짜 칸
        self.assertEqual(rows[1]["team"], "New York Yankees")
        self.assertEqual(rows[1]["penalty"], "2014 season (162 games)")  # 서식·각주·표시 기호를 지운다
        self.assertEqual(rows[1]["position"], "3B")
        self.assertIsNone(rows[0]["drug"])

    def test_match_requires_unique_player_in_career(self):
        players = {
            1: {"name": "Nelson Cruz", "pos": "RF", "batting": [{"season": 2012}, {"season": 2014}]},
            2: {"name": "Javy Guerra", "pos": "P", "pitching": [{"season": 2015}]},
            3: {"name": "Javy Guerra", "pos": "P", "pitching": [{"season": 2015}]},
            4: {"name": "Old Name", "pos": "P", "pitching": [{"season": 1990}]},
        }
        rows = [
            {"name": "Nelson Cruz", "date": "2013-08-05", "team": "", "penalty": "", "drug": None, "position": "OF"},
            {"name": "Javy Guerra", "date": "2015-07-08", "team": "", "penalty": "", "drug": None, "position": "P"},
            {"name": "Old Name", "date": "2013-04-17", "team": "", "penalty": "", "drug": None, "position": "P"},
        ]
        found, missed = ped.match(rows, players, search=lambda name: set())
        self.assertEqual(list(found), [1])  # 2013년에 출전 기록이 없어도 경력 기간 안이면 연결
        self.assertEqual(len(missed), 2)  # 동명이인, 경력 기간 밖의 같은 이름은 연결하지 않는다


if __name__ == "__main__":
    unittest.main()
