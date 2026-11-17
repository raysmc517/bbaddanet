"""MLB 구단·산하 마이너리그 구단·홈구장 정보 생성: python scripts/teams.py

MLB Stats API의 팀·구장 정보를 받아 data/teams.json 하나로 저장한다.
파크팩터는 새로 계산하지 않고 성적 빌드가 저장한 constants_{시즌}.json의 값을 붙인다.
수집이 실패하거나 응답이 비정상이면 기존 파일을 그대로 둔다.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from careers import write
from collectors import statsapi

DATA = Path(__file__).resolve().parent.parent / "data"
SEASON = 2026
MLB_CLUBS = 30

# (sportId, 표시 이름, 파크팩터가 저장된 폴더)
LEVELS = [
    (1, "MLB", "mlb"),
    (11, "AAA", "milb/aaa"),
    (12, "AA", "milb/aa"),
    (13, "High-A", "milb/high_a"),
    (14, "Single-A", "milb/single_a"),
    (16, "Rookie", None),  # 독립 리더보드가 없어 파크팩터도 없다
]


def park_factors(folder, season):
    """성적 빌드가 저장한 팀 약칭 → 파크팩터. 파일이 없으면 빈 표."""
    if folder is None:
        return {}
    path = DATA / folder / f"constants_{season}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("parkFactors", {})


def fix_placeholder_location(club):
    """도미니카 서머리그 일부 구장은 원본의 도시가 모구단 연고지(예: New York)로 채워져 있고
    국가만 'DOM'이다. 틀린 도시는 지우고 국가 표기는 다른 구장과 맞춘다."""
    venue = club["venue"]
    if venue.get("country") == "DOM":
        venue["city"] = None
        venue["state"] = None
        venue["country"] = "Dominican Republic"
    return club


def assemble(clubs_by_level, factors_by_level):
    """레벨별 구단 목록 → MLB 구단 목록(산하 구단 포함). 순수 함수라 따로 검증할 수 있다."""
    order = [name for _sport, name, _folder in LEVELS]
    majors = {}
    for club in clubs_by_level.get("MLB", []):
        entry = {key: value for key, value in club.items() if key != "parentId"}
        entry["level"] = "MLB"
        entry["pf"] = factors_by_level.get("MLB", {}).get(club["abbr"])
        entry["affiliates"] = []
        majors[club["id"]] = entry

    orphans = 0
    for level in order[1:]:
        for club in clubs_by_level.get(level, []):
            parent = majors.get(club["parentId"])
            if parent is None:
                orphans += 1  # 모구단을 알 수 없는 구단은 임의로 붙이지 않는다
                continue
            entry = {key: value for key, value in club.items() if key not in ("parentId", "leagueAbbr", "divisionShort")}
            entry["level"] = level
            entry["pf"] = factors_by_level.get(level, {}).get(club["abbr"])
            parent["affiliates"].append(entry)

    for club in majors.values():
        club["affiliates"].sort(key=lambda item: (order.index(item["level"]), item["name"]))
    clubs = sorted(majors.values(), key=lambda item: item["name"])
    return clubs, orphans


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=SEASON, help="구단·구장 기준 시즌")
    args = parser.parse_args()

    clubs_by_level, factors_by_level = {}, {}
    try:
        for sport_id, level, folder in LEVELS:
            clubs = statsapi.fetch_clubs(sport_id, args.season)
            if not clubs:
                raise ValueError(f"{level} 구단 응답이 비어 있음")
            clubs_by_level[level] = [fix_placeholder_location(club) for club in clubs]
            factors_by_level[level] = park_factors(folder, args.season)
            print(f"{level}: {len(clubs)}개 구단", flush=True)
        if len(clubs_by_level["MLB"]) != MLB_CLUBS:
            raise ValueError(f"MLB 구단 수가 {MLB_CLUBS}개가 아님: {len(clubs_by_level['MLB'])}")
    except Exception as error:
        print(f"[실패] 구단 정보: {error} (기존 파일 유지)", file=sys.stderr)
        return 1

    clubs, orphans = assemble(clubs_by_level, factors_by_level)
    if orphans:
        print(f"[경고] 모구단을 찾지 못한 구단 {orphans}개는 제외함", file=sys.stderr)
    write(
        DATA / "teams.json",
        {
            "season": args.season,
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "clubs": clubs,
        },
    )
    affiliates = sum(len(club["affiliates"]) for club in clubs)
    print(f"구단 {len(clubs)}개, 산하 구단 {affiliates}개 저장")
    return 0


if __name__ == "__main__":
    sys.exit(main())
