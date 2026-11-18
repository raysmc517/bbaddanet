"""명예의 전당 투표 자료 검증: python -m unittest discover -s scripts -p test_hof_votes.py"""

import unittest

import hof_votes

MEMBERS = """{|
|-
|align="center"|[[2025 Baseball Hall of Fame balloting|2025]]
!scope="row"|''{{sortname|Ichiro|Suzuki}}''
|[[Right fielder|RF]]|| [[Seattle Mariners]]||2001–2019||BBWAA||99.75%
|<ref>x</ref>
|-
|align="center"|[[1949 Baseball Hall of Fame balloting|1949]]
!scope="row"|{{sortname|Mordecai|Brown}}
|[[Pitcher|P]]||[[Chicago Cubs]]||1903–1916||VC|| data-sort-value="-1"|{{center|—{{Ref|1|1}}}}
|<ref>y</ref>
|-
|align="center"|[[2025 Baseball Hall of Fame balloting|2025]]
!scope="row"|{{sortname|Dick|Allen}}
|[[First baseman|1B]]|| [[Philadelphia Phillies]]||1963–1977||VC <br>(CLB)||81.25%
|}"""

BALLOT_MODERN = """{|class="wikitable sortable plainrowheaders"
!scope="col"|Player
!scope="col" data-sort-type=number|Votes
!scope="col" data-sort-type=number|Percent
!scope="col"|Change
!scope="col" data-sort-type=number|Year
|-
|-bgcolor=ccffcc
|'''''{{sortname|Billy|Wagner}}'''''
|style="text-align:right"|325
|style="text-align:right"|82.5%
|style="text-align:right"|{{Increase}} 8.7%
|style="text-align:right"|{{sort|10|10th}}
|}"""

BALLOT_OLD = """{| class="wikitable"
!Player
!Votes
!Percent
|-bgcolor="#ccffcc"
|'''''[[Ty Cobb]]'''''{{dagger}}
|align=center|'''222'''
|align=center|'''98.2'''
|}"""


class ParseTest(unittest.TestCase):
    def test_members_method_and_percent(self):
        rows = {m["name"]: m for m in hof_votes.parse_members(MEMBERS)}
        self.assertEqual(rows["Ichiro Suzuki"], {"year": 2025, "name": "Ichiro Suzuki", "method": "BBWAA", "pct": 99.75})
        self.assertIsNone(rows["Mordecai Brown"]["pct"])  # "—" 칸의 각주 번호를 득표율로 읽지 않는다
        self.assertEqual((rows["Dick Allen"]["method"], rows["Dick Allen"]["pct"]), ("VC (CLB)", 81.25))

    def test_ballot_tables_modern_and_old(self):
        modern = hof_votes.parse_ballot(BALLOT_MODERN)
        self.assertEqual(modern["billywagner"], {"votes": 325, "pct": 82.5, "ballot": 10})
        old = hof_votes.parse_ballot(BALLOT_OLD)
        self.assertEqual(old["tycobb"], {"votes": 222, "pct": 98.2, "ballot": None})  # 차수 열이 없는 옛 표


class MatchTest(unittest.TestCase):
    PEOPLE = {"1": ["Nolan Ryan Jr.", "P", 1], "2": ["Gil Hodges", "1B", 1], "3": ["Ken Smith", "P", 1], "4": ["Joe Smith", "P", 1]}

    def test_suffix_nearby_year_and_ambiguous_last_name(self):
        rows = [["hof", 1999, "", 1, "", 0], ["hof", 2021, "", 2, "", 0], ["hof", 2000, "", 3, "", 0], ["hof", 2000, "", 4, "", 0]]
        members = [
            {"year": 1999, "name": "Nolan Ryan", "method": "BBWAA", "pct": 98.79},   # Jr. 꼬리 무시
            {"year": 2022, "name": "Gil Hodges", "method": "VC (GD)", "pct": 75.0},  # 12월 선출: 위키백과는 이듬해
            {"year": 2000, "name": "Bob Smith", "method": "BBWAA", "pct": 80.0},     # 같은 성이 둘이면 맞추지 않는다
        ]
        matched, missing = hof_votes.match(members, rows, self.PEOPLE)
        self.assertEqual(set(matched), {"1", "2"})
        self.assertEqual([m["name"] for m in missing], ["Bob Smith"])


if __name__ == "__main__":
    unittest.main()
