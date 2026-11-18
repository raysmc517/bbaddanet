"""국제 계약 정보 읽기 검증: python -m unittest discover -s scripts -p test_signings.py"""

import unittest

from collectors import pipeline


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
