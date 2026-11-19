import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import moves
import past_moves


def tx(tid, code, desc, person=1, from_team=None, to_team=None):
    row = {"id": tid, "typeCode": code, "description": desc, "date": "2020-02-10", "person": {"id": person, "fullName": "A"}}
    if from_team:
        row["fromTeam"] = {"id": from_team, "name": str(from_team)}
    if to_team:
        row["toTeam"] = {"id": to_team, "name": str(to_team)}
    return row


class TransfersTest(unittest.TestCase):
    def test_keeps_only_transfers(self):
        rows = past_moves.transfers([
            tx(1, "TR", "X traded A to Y.", from_team=111, to_team=119),
            tx(2, "CU", "Recalled A.", from_team=1),
            tx(3, "SC", "placed A on the 10-day injured list.", person=2),
            tx(4, "SFA", "signed free agent A to a minor league contract.", person=3),
            tx(5, "SFA", "signed free agent A.", person=4, to_team=111),
            tx(6, "DES", "designated A for assignment.", person=5),
            tx(7, "REL", "released A.", person=6),
        ], 111, lambda pid: True)
        self.assertEqual(sorted(row["type"] for row in rows), ["release", "sign", "trade_out"])


class ArrivalsTest(unittest.TestCase):
    def test_arrivals_use_all_saved_seasons(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            old = {"events": [{"date": "2020-02-10", "type": "trade", "players": [{"id": 9, "to": 119, "from": 111}]}]}
            new = {"events": [{"date": "2025-07-01", "type": "trade", "players": [{"id": 8, "to": 143, "from": 137}]}]}
            (data / "moves_2020.json").write_text(json.dumps(old), encoding="utf-8")
            (data / "moves_2025.json").write_text(json.dumps(new), encoding="utf-8")
            with mock.patch.object(moves, "DATA", data):
                self.assertEqual(moves.save_arrivals(), 2)
            arrivals = json.loads((data / "arrivals.json").read_text(encoding="utf-8"))
            self.assertEqual(arrivals["9"], ["2020-02-10", "trade", 119, 111])


if __name__ == "__main__":
    unittest.main()
