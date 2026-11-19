import tempfile
import unittest
from pathlib import Path
from unittest import mock

import daily


class DailyTest(unittest.TestCase):
    def test_offseason_empty_schedule_is_valid_but_bad_response_is_not(self):
        self.assertEqual(daily.games({"dates": [], "totalGames": 0}), [])
        with self.assertRaises(ValueError):
            daily.games({"message": "error"})
        with self.assertRaises(ValueError):
            daily.games({"dates": [], "totalGames": 1})

    def test_news_only_titles_links_times_and_safe_official_urls(self):
        xml = '''<rss><channel>
        <item><title>A &amp; B</title><link>https://www.mlb.com/news/a</link><pubDate>Wed, 18 Nov 2026 12:00:00 GMT</pubDate><description>본문 저장 금지</description></item>
        <item><title>중복</title><link>https://www.mlb.com/news/a</link></item>
        <item><title>잘못된 링크</title><link>javascript:alert(1)</link></item>
        </channel></rss>'''
        rows = daily.news_items(xml)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "A & B")
        self.assertEqual(rows[0]["published"], "2026-11-18T12:00:00+00:00")
        self.assertNotIn("description", rows[0])
        with self.assertRaises(ValueError):
            daily.news_items("<rss><channel/></rss>")

    def test_network_failure_preserves_games_and_news(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "games").mkdir()
            game = root / "games" / "2025-09-28.json"
            news = root / "news.json"
            game.write_text('{"games":[{"id":1}]}', encoding="utf-8")
            news.write_text('{"items":[{"title":"기존 뉴스"}]}', encoding="utf-8")
            before = (game.read_bytes(), news.read_bytes())
            with mock.patch.object(daily, "DATA", root), mock.patch("sys.argv", ["daily.py", "--date", "2025-09-28"]), mock.patch.object(daily.statsapi, "_get", side_effect=RuntimeError("network")), mock.patch.object(daily.requests, "get", side_effect=RuntimeError("network")):
                self.assertEqual(daily.main(), 1)
            self.assertEqual((game.read_bytes(), news.read_bytes()), before)


if __name__ == "__main__":
    unittest.main()
