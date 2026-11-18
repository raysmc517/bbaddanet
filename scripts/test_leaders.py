"""리그 1위 추출 검증: python -m unittest discover -s scripts -p test_leaders.py"""

import unittest

import leaders


def item(rank, player_id, value="10"):
    return {"rank": rank, "value": value, "person": {"id": player_id}}


class FirstPlaceTest(unittest.TestCase):
    def test_single_leader(self):
        self.assertEqual(leaders.first_place([item(1, 5), item(2, 6)]), [5])

    def test_ties_all_kept(self):
        self.assertEqual(leaders.first_place([item(1, 9), item(1, 3), item(3, 4)]), [3, 9])

    def test_zero_value_is_not_a_leader(self):
        # 홀드 도입 이전처럼 기록이 없어 0으로 나오는 경우
        self.assertEqual(leaders.first_place([item(1, 5, "0"), item(1, 6, "0")]), [])

    def test_rate_value_zero_string(self):
        self.assertEqual(leaders.first_place([item(1, 5, ".000")]), [])

    def test_too_many_ties_left_empty(self):
        # 목록 전체가 1위면 목록 밖에 동률 선수가 더 있을 수 있다
        self.assertEqual(leaders.first_place([item(1, n) for n in range(1, leaders.LIMIT + 1)]), [])

    def test_empty(self):
        self.assertEqual(leaders.first_place([]), [])


if __name__ == "__main__":
    unittest.main()
