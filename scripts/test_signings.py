"""국제 계약 정보 읽기 검증: python -m unittest discover -s scripts -p test_signings.py"""

import unittest

import signings
from collectors import pipeline


POSTING = """{|class="wikitable sortable plainrowheaders"
|+ Successful postings
|-
!scope="col"|Player
!scope="col"|Posting date
|-
!scope="row"|{{sortname|Yoshinobu|Yamamoto}}{{ref|pitcher|P}}
|{{dts|2023|11|20}}
|[[Orix Buffaloes]]
|[[Los Angeles Dodgers]]
|$50,624,000
|{{dts|2023|12|27}}
|<span style="display:none">$27,083,333</span>12&nbsp;years, $325&nbsp;million
|<ref>note</ref>
|-
!scope="row"|{{sortname|Choi|Hyang-nam}}
|{{dts|2009|1|22}}
|[[Lotte Giants]]
|[[St. Louis Cardinals]]
|$101
|{{dts|||}}
|<span style="display:none">$0</span>Minor league contract
|-
!scope="row"|[[Hyeseong Kim (baseball)|Hyeseong Kim]]
|November 18, 2024
|[[Kiwoom Heroes]]
|[[Los Angeles Dodgers]]
|$2,000,000
|{{dts|2025|01|3}}
|<span style="display:none"></span>3&nbsp;year, $12.5&nbsp;million
|}"""

PLAYER_LIST = """==Current players==
{| class="wikitable"
|-
!scope="row" style="background-color:#ccffff"| {{sortname|Yu|Darvish}}*
| SP
|align="left"| [[Texas Rangers (baseball)|Texas Rangers]] (2012)
| <ref>{{cite web |url=https://www.mlb.com/player/yu-darvish-506433}}</ref>
|-
!scope="row"| {{sortname|Kodai|Senga}}
| SP
|align="left"| [[New York Mets]] (2023&ndash;present)
| <ref>{{cite web |url=https://www.mlb.com/player/kodai-senga-673540}}</ref>
|-
!scope="row" style="background-color:#ccccff"| {{sortname|Mac|Suzuki}}§
| RP
|}
==Awards==
{| class="wikitable"
|-
!scope="row"| {{sortname|Kodai|Senga}}
|}"""

INFOBOX = """{{Infobox baseball biography
| name = Kodai Senga
| teams =
'''As player'''
* [[Fukuoka SoftBank Hawks]] ({{nowrap|2012–2022}})
* [[New York Mets]] ({{nowrap|2023–present}})
'''As coach'''
* [[Yomiuri Giants]] (2030)
| highlights =
}}"""


class ForeignSigningTest(unittest.TestCase):
    def test_posting_table(self):
        rows = signings.parse_postings(POSTING, "NPB")
        self.assertEqual(rows[0]["name"], "Yoshinobu Yamamoto")
        self.assertEqual(rows[0]["postingDate"], "2023-11-20")
        self.assertEqual(rows[0]["date"], "2023-12-27")
        self.assertEqual(rows[0]["foreignTeam"], "Orix Buffaloes")
        self.assertEqual(rows[0]["team"], "Los Angeles Dodgers")
        self.assertEqual(rows[0]["contract"], "12년 $325M")
        # 계약 합의일이 빈 칸이면 날짜를 만들지 않는다
        self.assertIsNone(rows[1]["date"])
        self.assertEqual(rows[1]["contract"], "마이너리그 계약")
        # 정렬 틀 없이 링크만 쓴 행, 틀 없이 글로 쓴 날짜, 단수 'year'
        self.assertEqual(rows[2]["name"], "Hyeseong Kim")
        self.assertEqual(rows[2]["article"], "Hyeseong Kim (baseball)")
        self.assertEqual(rows[2]["postingDate"], "2024-11-18")
        self.assertEqual(rows[2]["date"], "2025-01-03")
        self.assertEqual(rows[2]["contract"], "3년 $12.5M")

    def test_player_list_marks(self):
        listed = {item["name"]: item for item in signings.parse_player_list(PLAYER_LIST)}
        self.assertTrue(listed["Yu Darvish"]["posted"])
        self.assertEqual(listed["Yu Darvish"]["id"], 506433)
        self.assertFalse(listed["Kodai Senga"]["posted"])
        self.assertTrue(listed["Mac Suzuki"]["amateur"])
        self.assertEqual(len(listed), 3)  # 수상 표에 다시 나온 이름은 한 번만

    def test_last_foreign_team_before_mlb(self):
        teams = signings.infobox_teams(INFOBOX)
        self.assertEqual(teams, [("Fukuoka SoftBank Hawks", 2012), ("New York Mets", 2023)])  # 코치 경력은 뺀다
        self.assertEqual(signings.last_foreign_team(teams, 2023), ("NPB", "Fukuoka SoftBank Hawks"))
        self.assertEqual(signings.foreign_league("Lotte Giants"), "KBO")
        self.assertEqual(signings.foreign_league("Chiba Lotte Marines"), "NPB")
        self.assertIsNone(signings.foreign_league("Detroit Tigers"))

    def test_name_order(self):
        players = {1: {"name": "Hyun Jin Ryu", "country": "Republic of Korea"},
                   2: {"name": "Hyeseong Kim", "country": "Republic of Korea"},
                   3: {"name": "Jose Ramirez", "country": "Dominican Republic"},
                   4: {"name": "José Ramírez", "country": "Dominican Republic"}}
        self.assertEqual(signings.match_player({"name": "Ryu Hyun-jin"}, players), 1)
        self.assertEqual(signings.match_player({"name": "Hye-seong Kim"}, players), 2)
        self.assertIsNone(signings.match_player({"name": "José Ramírez"}, players))  # 동명이인은 연결하지 않는다


class TransactionSigningTest(unittest.TestCase):
    TRANSACTIONS = [
        {"date": "2016-05-31", "typeCode": "ASG", "toTeam": {"id": 615, "name": "DSL Nationals"}},
        {"date": "2021-12-01", "typeCode": "SFA", "toTeam": {"id": 120, "name": "Washington Nationals"},
         "description": "Washington Nationals signed free agent OF Juan Soto."},
        {"date": "2015-07-02", "typeCode": "SFA", "toTeam": {"id": 120, "name": "Washington Nationals"},
         "description": "Washington Nationals signed free agent OF Juan Soto to a minor league contract."},
        {"date": "2014-10-04", "typeCode": "SFA", "toTeam": {"id": 699, "name": "Tigres de Aragua"}},
    ]

    def test_first_signing_with_mlb_club(self):
        self.assertEqual(signings.first_signing(self.TRANSACTIONS, {120}),
                         {"date": "2015-07-02", "team": "Washington Nationals", "minor": True})
        self.assertEqual(signings.first_signing([], {120}), {})

    def test_entry_type_and_range(self):
        signing = {"date": "2015-07-02", "team": "Washington Nationals", "minor": True}
        young = {"birthDate": "1998-10-25", "batting": [{"season": 2016}]}
        self.assertEqual(signings.signing_entry(665742, signing, young)["type"], "international")
        adult = {"birthDate": "1987-01-29", "batting": [{"season": 2016}]}
        self.assertEqual(signings.signing_entry(1, signing, adult)["type"], "free_agent")
        # 프로 첫 시즌보다 한참 뒤의 계약은 첫 계약이 아니다 (이동 기록이 생기기 전 입단)
        veteran = {"birthDate": "1983-04-18", "batting": [{"season": 2003}]}
        self.assertIsNone(signings.signing_entry(1, signing, veteran))
        self.assertIsNone(signings.signing_entry(1, {}, young))


class SigningTest(unittest.TestCase):
    def test_signing_date_formats(self):
        self.assertEqual(pipeline.signing_date("Jan. 15, 2022 - LAD"), ("2022-01-15", "LAD"))
        self.assertEqual(pipeline.signing_date("June 4, 2024 - LAD"), ("2024-06-04", "LAD"))
        self.assertEqual(pipeline.signing_date("unknown"), (None, None))

    def test_bonus_only_from_signing_sentence(self):
        self.assertEqual(pipeline.bonus_usd("<p>Signed for $297,500 out of Venezuela</p>"), 297500)
        self.assertEqual(pipeline.bonus_usd("signed out of the Dominican Republic in January 2022 for $397,500."), 397500)
        self.assertEqual(pipeline.bonus_usd("signed for a $1.2 million bonus"), 1200000)
        # 구단 전체 한도나 다른 선수 금액은 계약금으로 읽지 않는다
        self.assertIsNone(pipeline.bonus_usd("the Mariners made sure to use nearly all of their bonus pool of over $5.3 million."))
        self.assertIsNone(pipeline.bonus_usd("no amount here"))


if __name__ == "__main__":
    unittest.main()
