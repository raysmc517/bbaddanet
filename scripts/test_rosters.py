import unittest

import rosters

DATES = {"springStart": "2026-02-20", "regularStart": "2026-03-25", "regularEnd": "2026-09-27", "postEnd": "2026-10-28"}


def row(player_id, number, name="A"):
    return {"id": player_id, "name": name, "num": number, "status": "A"}


class PhaseTest(unittest.TestCase):
    def test_phases(self):
        self.assertEqual(rosters.season_phase("2026-01-10", DATES), "offseason")
        self.assertEqual(rosters.season_phase("2026-03-01", DATES), "spring")
        self.assertEqual(rosters.season_phase("2026-03-25", DATES), "regular")
        self.assertEqual(rosters.season_phase("2026-09-27", DATES), "regular")
        self.assertEqual(rosters.season_phase("2026-10-01", DATES), "postseason")
        self.assertEqual(rosters.season_phase("2026-11-17", DATES), "offseason")

    def test_missing_dates_is_offseason(self):
        self.assertEqual(rosters.season_phase("2026-06-01", {}), "offseason")


class RowsTest(unittest.TestCase):
    def test_sorted_by_number_then_name_and_page_flag(self):
        rows = [row(1, "", "Zed"), row(2, "99"), row(3, "7", "Bob"), row(4, "7", "Al")]
        result = rosters.clean_rows(rows, lambda player_id: player_id != 2)
        self.assertEqual([item["id"] for item in result], [4, 3, 2, 1])
        self.assertEqual([item["page"] for item in result], [1, 1, 0, 1])

    def test_does_not_modify_input(self):
        rows = [row(1, "5")]
        rosters.clean_rows(rows, lambda player_id: True)
        self.assertNotIn("page", rows[0])

    def test_roster_size_check(self):
        rosters.check_roster("A", [row(i, str(i)) for i in range(26)])
        with self.assertRaises(ValueError):
            rosters.check_roster("A", [])
        with self.assertRaises(ValueError):
            rosters.check_roster("A", [row(i, str(i)) for i in range(60)])


class SeasonRowsTest(unittest.TestCase):
    def roster_row(self, player_id, number, name):
        return {"id": player_id, "name": name, "num": number, "pos": "P", "posType": "Pitcher", "bats": "R",
                "throws": "R", "birthDate": "1995-03-02", "status": "TR", "statusText": "Traded", "note": ""}

    def test_merges_stats_and_drops_status(self):
        roster = [self.roster_row(1, "38", "Andujar"), self.roster_row(2, "50", "Idle")]
        batting = {1: {"G": 34, "PA": 110, "name": "Andujar", "pos": "LF"}}
        result = rosters.season_rows(roster, batting, {}, lambda player_id: True)
        self.assertEqual([row["id"] for row in result], [1, 2])
        self.assertEqual(result[0]["bat"], {"G": 34, "PA": 110})
        self.assertIsNone(result[0]["pit"])
        self.assertIsNone(result[1]["bat"])
        self.assertNotIn("status", result[0])

    def test_fills_player_missing_from_roster(self):
        pitching = {9: {"G": 1, "outs": 3, "name": "Call Up", "pos": "P"}}
        result = rosters.season_rows([], {}, pitching, lambda player_id: False)
        self.assertEqual(result[0]["name"], "Call Up")
        self.assertEqual(result[0]["posType"], "Pitcher")
        self.assertEqual(result[0]["page"], 0)
        self.assertEqual(result[0]["pit"], {"G": 1, "outs": 3})


class MoveTest(unittest.TestCase):
    NYY = {"id": 147, "name": "New York Yankees"}
    SWB = {"id": 531, "name": "Scranton/Wilkes-Barre Highlanders"}

    def tx(self, code, text, tx_id=1, person=10, from_team=None, to_team=None, date="2025-05-01"):
        item = {"id": tx_id, "typeCode": code, "description": text, "date": date, "effectiveDate": date}
        if person:
            item["person"] = {"id": person, "fullName": "Player %d" % person}
        if from_team:
            item["fromTeam"] = from_team
        if to_team:
            item["toTeam"] = to_team
        return item

    def test_call_up_and_option(self):
        up = rosters.classify_move(self.tx("CU", "New York Yankees recalled RHP X from Scranton/Wilkes-Barre RailRiders.", from_team=self.SWB, to_team=self.NYY), 147)
        self.assertEqual((up["type"], up["team"]["id"]), ("up", 531))
        down = rosters.classify_move(self.tx("OPT", "New York Yankees optioned RHP X to Scranton/Wilkes-Barre RailRiders.", from_team=self.NYY, to_team=self.SWB), 147)
        self.assertEqual((down["type"], down["team"]["id"]), ("option", 531))
        select = rosters.classify_move(self.tx("SE", "New York Yankees selected the contract of OF X from Scranton/Wilkes-Barre RailRiders.", from_team=self.SWB, to_team=self.NYY), 147)
        self.assertEqual(select["type"], "select")

    def test_injured_list(self):
        on = rosters.classify_move(self.tx("SC", "New York Yankees placed LHP X on the 15-day injured list retroactive to August 16, 2025. Left forearm contusion.", date="2025-08-18"), 147)
        self.assertEqual((on["type"], on["days"], on["retro"], on["note"]), ("il_on", 15, "2025-08-16", "Left forearm contusion"))
        move = rosters.classify_move(self.tx("SC", "New York Yankees transferred RHP X from the 15-day injured list to the 60-day injured list. Right forearm tightness."), 147)
        self.assertEqual((move["type"], move["days"], move["note"]), ("il_move", 60, "Right forearm tightness"))
        off = rosters.classify_move(self.tx("SC", "New York Yankees activated 3B X from the 60-day injured list."), 147)
        self.assertEqual((off["type"], off["days"]), ("il_off", 60))
        self.assertNotIn("note", off)

    def test_trades_and_claims_by_direction(self):
        cubs = {"id": 112, "name": "Chicago Cubs"}
        incoming = rosters.classify_move(self.tx("TR", "Chicago Cubs traded RHP X to New York Yankees for cash.", from_team=cubs, to_team=self.NYY), 147)
        self.assertEqual((incoming["type"], incoming["team"]["id"]), ("trade_in", 112))
        outgoing = rosters.classify_move(self.tx("TR", "New York Yankees traded OF X to Chicago Cubs.", from_team=self.NYY, to_team=cubs), 147)
        self.assertEqual((outgoing["type"], outgoing["team"]["id"]), ("trade_out", 112))
        claimed = rosters.classify_move(self.tx("CLW", "Chicago Cubs claimed RHP X off waivers from New York Yankees.", from_team=self.NYY, to_team=cubs), 147)
        self.assertEqual(claimed["type"], "claim_out")

    def test_skips_noise(self):
        skipped = [
            self.tx("ASG", "New York Yankees invited non-roster RHP X to spring training."),
            self.tx("NUM", "RHP X changed number to 99."),
            self.tx("SFA", "New York Yankees signed free agent 1B X to a minor league contract."),
            self.tx("SC", "RHP X roster status changed by New York Yankees."),
            self.tx("TR", "Chicago Cubs traded RHP X to New York Yankees for cash.", person=None),
        ]
        for item in skipped:
            self.assertIsNone(rosters.classify_move(item, 147), item["description"])
        signed = rosters.classify_move(self.tx("SFA", "New York Yankees signed free agent SS X."), 147)
        self.assertEqual(signed["type"], "sign")

    def test_season_moves_dedupes_and_sorts_latest_first(self):
        early = self.tx("CU", "recalled", tx_id=1, person=10, date="2025-04-01")
        late = self.tx("OPT", "optioned", tx_id=2, person=11, date="2025-06-01")
        result = rosters.season_moves([early, late, early], 147, lambda player_id: player_id == 10)
        self.assertEqual([row["id"] for row in result], [11, 10])
        self.assertEqual([row["page"] for row in result], [0, 1])


if __name__ == "__main__":
    unittest.main()
