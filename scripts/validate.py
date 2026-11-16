"""자체 계산한 세이버 지표를 MLB 공식 값과 대조한다.

`python scripts/build.py`로 데이터를 만든 뒤 `python scripts/validate.py`로 실행한다.
규정타석·규정이닝을 채운 선수만 비교한다.
"""

import json
import sys
from pathlib import Path

from collectors import statsapi

DATA = Path(__file__).resolve().parent.parent / "data"

# (우리 항목, 공식 항목, 표시 이름)
CHECKS = {
    "batting": [("wOBA", "woba", "wOBA"), ("wRCp", "wRcPlus", "wRC+"), ("sWAR", "war", "간이 WAR vs 공식 WAR")],
    "pitching": [("FIP", "fip", "FIP"), ("ERAm", "eraMinus", "ERA-"), ("FIPm", "fipMinus", "FIP-"), ("sWAR", "war", "간이 WAR vs 공식 WAR")],
}
API_GROUP = {"batting": "hitting", "pitching": "pitching"}


def correlation(xs, ys):
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    return cov / (var_x * var_y) ** 0.5


def main():
    season = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    print(f"MLB {season} 자체 계산값 vs 공식 값 (규정 충족 선수)")
    for group, checks in CHECKS.items():
        rows = json.loads((DATA / "mlb" / f"{group}_{season}.json").read_text(encoding="utf-8"))["players"]
        official = statsapi.fetch_official_saber(API_GROUP[group], 1, season)
        print(f"\n[{group}]")
        for ours_key, official_key, label in checks:
            pairs = [
                (row[ours_key], official[row["id"]][official_key])
                for row in rows
                if row["q"] and row.get(ours_key) is not None and official.get(row["id"], {}).get(official_key) is not None
            ]
            ours, theirs = zip(*pairs)
            mean_gap = sum(abs(a - b) for a, b in pairs) / len(pairs)
            bias = sum(a - b for a, b in pairs) / len(pairs)
            print(f"  {label:<22} {len(pairs):>3}명  평균 오차 {mean_gap:.3f}  치우침 {bias:+.3f}  상관계수 {correlation(ours, theirs):.3f}")


if __name__ == "__main__":
    main()
