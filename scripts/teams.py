"""MLB 구단·산하 마이너리그 구단·홈구장 정보 생성: python scripts/teams.py

MLB Stats API의 팀·구장 정보를 받아 data/teams.json 하나로 저장한다.
파크팩터는 새로 계산하지 않고 성적 빌드가 저장한 constants_{시즌}.json의 값을 붙인다.
MLB 구단에는 구단 역사(월드시리즈 우승, 주요 수상 횟수, 명예의 전당, 영구결번)와 소개 글을 붙인다.
우승·수상·명예의 전당은 data/awards.json에서 세므로 awards.py 뒤에 실행한다. 영구결번은 구단별로 받는다.
수집이 실패하거나 응답이 비정상이면 기존 파일을 그대로 둔다.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from careers import write
from collectors import statsapi

DATA = Path(__file__).resolve().parent.parent / "data"
SEASON = 2026
MLB_CLUBS = 30
HISTORY_AWARDS = ["mvp", "cy", "roy"]  # 구단별 수상 횟수를 세는 상 (awards.py의 키)

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


def official_site(team_name):
    """MLB 구단 공식 홈페이지 주소. mlb.com/{연고지를 뺀 이름을 소문자로, 공백·하이픈 제거} 규칙을 따른다
    (예: White Sox → whitesox, D-backs → dbacks). 이름이 없으면 None (주소를 지어내지 않는다)."""
    slug = re.sub(r"[^a-z0-9]", "", str(team_name or "").lower())
    return f"https://www.mlb.com/{slug}" if slug else None


def assemble(clubs_by_level, factors_by_level):
    """레벨별 구단 목록 → MLB 구단 목록(산하 구단 포함). 순수 함수라 따로 검증할 수 있다."""
    order = [name for _sport, name, _folder in LEVELS]
    majors = {}
    for club in clubs_by_level.get("MLB", []):
        entry = {key: value for key, value in club.items() if key not in ("parentId", "teamName")}
        entry["level"] = "MLB"
        entry["site"] = official_site(club.get("teamName"))
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
            entry = {key: value for key, value in club.items() if key not in ("parentId", "teamName", "leagueAbbr", "divisionShort")}
            entry["level"] = level
            entry["pf"] = factors_by_level.get(level, {}).get(club["abbr"])
            parent["affiliates"].append(entry)

    for club in majors.values():
        club["affiliates"].sort(key=lambda item: (order.index(item["level"]), item["name"]))
    clubs = sorted(majors.values(), key=lambda item: item["name"])
    return clubs, orphans


def load_awards(data=DATA):
    """awards.py가 만든 수상 기록. 파일이 없으면 None (우승·수상을 0으로 채우지 않기 위해)."""
    path = data / "awards.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_notes(data=DATA):
    """직접 작성해 관리하는 구단 소개 글 {구단 ID: 글}. 파일이 없으면 빈 표."""
    path = data / "team_notes.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def uniform_number(note):
    """영구결번 비고에서 등번호만 뽑는다. 원본 표기가 '42', '#20', '1 - Team Owner', 'No number' 등으로 섞여 있다.
    등번호가 없는 헌정(등번호 도입 이전 선수 등)은 빈 문자열."""
    match = re.search(r"\d+", str(note or ""))
    return match.group() if match else ""


def club_history(club_id, awards, retired, has_page):
    """MLB 구단 하나의 역사. 순수 함수라 따로 검증할 수 있다.

    awards: awards.json 내용 또는 None. None이면 우승·수상·명예의 전당은 0이나 빈 목록이 아닌 None(미제공)이다.
    retired: 영구결번 수상자 목록 (note가 등번호).
    구단은 팀 ID로 찾으므로 연고지를 옮기기 전 기록도 같은 구단으로 센다.
    """
    history = {"titles": None, "awards": None, "hof": None}
    if awards is not None:
        mine = [row for row in awards["rows"] if len(row) > 5 and row[5] == club_id]
        people = awards["people"]
        history["titles"] = sorted({row[1] for row in mine if row[0] == "wschamp"}, reverse=True)
        history["awards"] = {key: sum(1 for row in mine if row[0] == key) for key in HISTORY_AWARDS}
        history["hof"] = [
            {"id": row[3], "name": people[str(row[3])][0], "year": row[1], "page": people[str(row[3])][2]}
            for row in sorted((row for row in mine if row[0] == "hof"), key=lambda row: (row[1], people[str(row[3])][0]))
        ]

    def number_order(item):
        # 숫자 등번호를 번호순으로 먼저, 등번호가 없는 헌정(등번호 도입 이전 선수 등)은 뒤에 연도순으로
        number = item["number"]
        return (0, int(number), item["year"]) if number.isdigit() else (1, 0, item["year"])

    history["retired"] = sorted(
        (
            {
                "number": uniform_number(item["note"]),
                "id": item["id"],
                "name": item["name"],
                "year": item["season"],
                "page": 1 if has_page(item["id"]) else 0,
            }
            for item in retired
        ),
        key=number_order,
    )
    return history


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
        retired_by_club = {}
        for club in clubs_by_level["MLB"]:
            retired_by_club[club["id"]] = statsapi.fetch_award_recipients(f"RETIREDUNI_{club['id']}")
            if not retired_by_club[club["id"]]:
                raise ValueError(f"{club['name']} 영구결번 응답이 비어 있음")
        print(f"영구결번: {sum(len(items) for items in retired_by_club.values())}건", flush=True)
    except Exception as error:
        print(f"[실패] 구단 정보: {error} (기존 파일 유지)", file=sys.stderr)
        return 1

    clubs, orphans = assemble(clubs_by_level, factors_by_level)
    if orphans:
        print(f"[경고] 모구단을 찾지 못한 구단 {orphans}개는 제외함", file=sys.stderr)

    awards = load_awards()
    if awards is None:
        print("[경고] data/awards.json이 없어 우승·수상·명예의 전당은 미제공으로 둠 (awards.py를 먼저 실행)", file=sys.stderr)
    notes = load_notes()
    players = DATA / "players"
    for club in clubs:
        club["history"] = club_history(
            club["id"], awards, retired_by_club[club["id"]], lambda player_id: (players / f"{player_id}.json").exists()
        )
        club["note"] = notes.get(str(club["id"]))
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
