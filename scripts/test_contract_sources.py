import unittest
import json
import tempfile
from pathlib import Path
from unittest import mock

import contract_sources as source


def page(header, details=""):
    return "<div>" + "".join(f'<p>Player {i} rhp<br>{header}</p><ul><li>{header}<ul>{details}</ul></li></ul>' for i in range(15)) + "</div>"


class ContractSourceTest(unittest.TestCase):
    def test_facts_only_and_explicit_salary_schedule(self):
        rows = source.parse(page("2 years/$10.5M (2026-27)", "<li><b>26</b>:$5M, <b>27</b>:$5.5M</li><li>arbitrary prose</li>"))
        self.assertEqual(rows[0]["totalUSD"], 10500000)
        self.assertEqual(rows[0]["to"], 2027)
        self.assertEqual(rows[0]["salaries"], [{"from": 2026, "to": 2026, "baseUSD": 5000000}, {"from": 2027, "to": 2027, "baseUSD": 5500000}])
        self.assertNotIn("arbitrary", str(rows))

    def test_unknown_money_and_conditional_salary_are_not_zero_or_guessed(self):
        rows = source.parse(page("1 year (2026)", "<li>26:$1M if in majors, $200,000 in minors</li>"))
        self.assertIsNone(rows[0]["totalUSD"])
        self.assertNotIn("salaries", rows[0])
        rows = source.parse(page("1 year/$5M (2026), plus 2027 option", "<li>26:$4M, 27:$8M club option ($1M buyout)</li>"))
        self.assertTrue(rows[0]["hasOptions"])
        self.assertNotIn("salaries", rows[0])

    def test_invalid_and_truncated_pages_fail_before_cache_write(self):
        for html in ("<h1>Access denied</h1>", page("3 years/$10M (2026-27)")):
            with self.assertRaises(ValueError):
                source.parse(html)

    def test_name_normalization_handles_accents_and_initials(self):
        self.assertEqual(source.normalize("J.T. Realmuto"), source.normalize("JT Realmuto"))
        self.assertEqual(source.normalize("Jesus Lúzardo"), source.normalize("Jesús Luzardo"))

    def test_identity_requires_team_evidence_and_preserves_manual_override(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "players").mkdir()
            (root / "contracts_sources").mkdir()
            clubs = [{"name": "Test Club", "abbr": "SF", "id": 137}]
            (root / "teams.json").write_text(json.dumps({"clubs": clubs}), encoding="utf-8")
            for pid, name in (("1", "Manual"), ("2", "Matched"), ("3", "Unverified")):
                (root / "players" / f"{pid}.json").write_text(json.dumps({"name": name}), encoding="utf-8")
            manual = {"checked": "2026-11-19", "players": {"1": [{"name": "Manual", "team": "SF", "from": 2026, "to": 2026, "totalUSD": 99, "source": "https://www.mlb.com/a"}]}}
            (root / "contracts_manual.json").write_text(json.dumps(manual), encoding="utf-8")
            rows = [{"name": name, "position": "rhp", "from": 2026, "to": 2026, "totalUSD": None, "hasOptions": False} for name in ("Manual", "Matched", "Unverified")]
            cache = {"checked": "2026-11-19", "source": "https://example.com/a", "players": rows}
            (root / "contracts_sources" / "SF.json").write_text(json.dumps(cache), encoding="utf-8")
            names = {source.normalize(name): [(pid, name, "P")] for pid, name in (("1", "Manual"), ("2", "Matched"), ("3", "Unverified"))}
            with mock.patch.object(source, "DATA", root), mock.patch.object(source, "identities", return_value=(names, {"1": {137}, "2": {137}})):
                result = source.assemble(clubs)
            self.assertEqual(result["players"]["1"][0]["totalUSD"], 99)
            self.assertIsNone(result["players"]["2"][0]["totalUSD"])
            self.assertNotIn("3", result["players"])
            self.assertEqual(result["coverage"]["unmatched"][0]["name"], "Unverified")

    def test_bad_team_response_keeps_previous_fact_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "contracts_sources").mkdir()
            clubs = [{"name": "Test Club", "abbr": "SF", "id": 137}]
            (root / "teams.json").write_text(json.dumps({"clubs": clubs}), encoding="utf-8")
            cache = root / "contracts_sources" / "SF.json"
            cache.write_text('{"players":[{"name":"last good"}]}', encoding="utf-8")
            before = cache.read_bytes()
            response = mock.Mock(text="<h1>temporary failure</h1>")
            payload = {"coverage": {"teams": ["SF"], "unmatched": []}, "players": {"1": []}}
            with mock.patch.object(source, "DATA", root), mock.patch.object(source.requests, "Session") as session, mock.patch.object(source.time, "sleep"), mock.patch.object(source, "team_links", return_value={"SF": "https://example.com/team"}), mock.patch.object(source, "assemble", return_value=payload):
                session.return_value.get.return_value = response
                self.assertEqual(source.main(["--team", "SF"]), 1)
            self.assertEqual(cache.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
