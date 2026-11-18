"""리그 이동 소식 검증: python -m unittest discover -s scripts -p test_moves.py"""

import unittest

import moves

TRADE = "St. Louis Cardinals traded RHP A to Milwaukee Brewers for OF B."


def move(kind, player_id, name, other=None, date="2026-08-03", desc=TRADE):
    row = {"date": date, "type": kind, "id": player_id, "name": name, "desc": desc, "page": 1}
    if other:
        row["team"] = {"id": other, "name": "Other"}
    return row


class AssembleTest(unittest.TestCase):
    def test_trade_from_both_clubs_becomes_one_event_with_directions(self):
        events = moves.assemble([
            (158, [move("trade_in", 1, "A", 138), move("trade_out", 2, "B", 138)]),
            (138, [move("trade_out", 1, "A", 158), move("trade_in", 2, "B", 158)]),
        ])
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual((event["type"], event["teams"]), ("trade", [138, 158]))
        directions = {p["name"]: (p["from"], p["to"]) for p in event["players"]}
        self.assertEqual(directions, {"A": (138, 158), "B": (158, 138)})
        self.assertIn("desc", event)

    def test_claim_deduplicated_and_operational_moves_skipped(self):
        events = moves.assemble([
            (134, [move("claim_in", 5, "C", 158, desc="x"), move("up", 6, "D"), move("il_on", 7, "E")]),
            (158, [move("claim_out", 5, "C", 134, desc="y")]),
        ])
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0]["type"], events[0]["players"][0]["from"], events[0]["players"][0]["to"]), ("claim", 158, 134))
        self.assertNotIn("desc", events[0])  # 트레이드 외에는 원문을 빼 파일을 줄인다

    def test_newest_first(self):
        events = moves.assemble([(1, [move("sign", 1, "A", date="2026-01-01"), move("release", 2, "B", date="2026-05-01")])])
        self.assertEqual([e["date"] for e in events], ["2026-05-01", "2026-01-01"])
        self.assertEqual(events[1]["players"][0]["to"], 1)
        self.assertEqual(events[0]["players"][0]["from"], 1)


class ArrivalsTest(unittest.TestCase):
    def test_latest_arrival_kept_and_departures_ignored(self):
        older = [{"date": "2025-07-30", "type": "trade", "players": [{"id": 1, "from": 10, "to": 20}]}]
        newer = [
            {"date": "2026-01-10", "type": "sign", "players": [{"id": 1, "from": None, "to": 30}]},
            {"date": "2026-02-01", "type": "release", "players": [{"id": 1, "from": 30, "to": None}]},
            {"date": "2026-03-01", "type": "trade", "players": [{"id": 2, "from": 30, "to": None}]},
        ]
        result = moves.latest_arrivals([newer, older])
        self.assertEqual(result, {"1": ["2026-01-10", "sign", 30, None]})


if __name__ == "__main__":
    unittest.main()
