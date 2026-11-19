import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import arrivals
import moves


def tx(pid=571970, club=119, code="SFA", when="2017-04-28", desc="signed free agent Max Muncy to a minor league contract."):
    return {"id": 308070, "person": {"id": pid}, "toTeam": {"id": club}, "typeCode": code, "date": when, "description": desc}


class ArrivalTest(unittest.TestCase):
    def test_minor_signing_and_other_club_or_internal_move(self):
        row = arrivals.latest_for_club([tx(), tx(club=133, when="2020-01-01"), tx(code="SE", when="2018-04-17")],571970,119)
        self.assertEqual(row[:4],["2017-04-28","minor_sign",119,None])
        self.assertIn("571970",row[4])
        self.assertIsNone(arrivals.latest_for_club([tx(club=133)],571970,119))
        self.assertIsNone(arrivals.latest_for_club([tx(pid=1)],571970,119))

    def test_latest_verified_acquisition_and_effective_date(self):
        newest = tx(code="TR",when="2024-01-01")
        newest["fromTeam"] = {"id": 111}
        newest["effectiveDate"] = "2024-01-02"
        self.assertEqual(arrivals.latest_for_club([newest,tx()],571970,119)[:4],["2024-01-02","trade",119,111])

    def test_empty_and_unrelated_batch_are_rejected(self):
        for payload in ({"transactions":[]},{"transactions":[tx(pid=2)]},{}):
            with mock.patch.object(arrivals.statsapi,"_get",return_value=payload),self.assertRaises(ValueError):
                arrivals.fetch_batch(["571970"])

    def test_supplement_survives_daily_rebuild_but_does_not_replace_newer_move(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            old = {"events":[{"date":"2015-01-01","type":"sign","players":[{"id":571970,"to":133,"from":None}]}]}
            (data/"moves_2015.json").write_text(json.dumps(old),encoding="utf-8")
            detail = {"players":{"571970":{"arrival":["2017-04-28","minor_sign",119,None,"https://example.com"]}}}
            (data/"arrival_details.json").write_text(json.dumps(detail),encoding="utf-8")
            with mock.patch.object(moves,"DATA",data):
                moves.save_arrivals()
                self.assertEqual(json.loads((data/"arrivals.json").read_text(encoding="utf-8"))["571970"][1],"minor_sign")
                old["events"][0]["date"] = "2026-01-01"
                (data/"moves_2026.json").write_text(json.dumps(old),encoding="utf-8")
                moves.save_arrivals()
                self.assertEqual(json.loads((data/"arrivals.json").read_text(encoding="utf-8"))["571970"][2],133)

    def test_failed_fetch_preserves_previous_positive_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            path = data/"arrival_details.json"
            before = {"players":{"571970":{"name":"Max Muncy","team":119,"checked":"2026-11-20","arrival":["2017-04-28","minor_sign",119,None]}}}
            path.write_text(json.dumps(before),encoding="utf-8")
            (data/"arrivals.json").write_text('{"571970":["2017-04-28","minor_sign",119,null]}',encoding="utf-8")
            with mock.patch.object(arrivals,"DATA",data), mock.patch.object(arrivals,"audit",return_value=(1,{"571970":{"name":"Max Muncy","team":119}})), mock.patch.object(arrivals,"fetch_batch",side_effect=RuntimeError("network")), mock.patch.object(arrivals.moves,"save_arrivals"):
                self.assertEqual(arrivals.main(["--refresh"]),1)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["players"],before["players"])


if __name__ == "__main__":
    unittest.main()
