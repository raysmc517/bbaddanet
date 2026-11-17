"""리그·지구별 순위 생성: python scripts/standings.py [--current-season]

MLB Stats API의 순위를 받아 시즌마다 data/standings_{시즌}.json 하나로 저장한다.
레벨은 리더보드와 같은 MLB, AAA, AA, High-A, Single-A다.
전·후반기로 나누는 마이너리그는 시즌 전체 순위와 함께 전반기·후반기 순위도 받는다.
요청은 시즌당 레벨마다 리그 목록 1회 + 순위 1~3회로 약 17회다.

한 레벨이라도 실패하거나 응답이 비정상(MLB 구단이 30개가 아님, 빈 순위)이면 그 시즌 파일을 그대로 둔다.
피타고리안 기대 승패는 MLB 표기와 같은 지수 1.83으로 득점·실점에서 직접 계산한다.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from careers import write
from collectors import statsapi

DATA = Path(__file__).resolve().parent.parent / "data"
SEASONS = [2026, 2025, 2024]  # build.py의 SEASONS와 같게 유지한다
MLB_CLUBS = 30
MLB_LEAGUES = (103, 104)  # 아메리칸리그, 내셔널리그
PYTHAGOREAN_EXPONENT = 1.83

# (화면 ID, 표시 이름, sportId)
LEVELS = [
    ("mlb", "MLB", 1),
    ("aaa", "AAA", 11),
    ("aa", "AA", 12),
    ("high_a", "High-A", 13),
    ("single_a", "Single-A", 14),
]
HALVES = ["firstHalf", "secondHalf"]


def expected_wins(runs_scored, runs_allowed, games):
    """피타고리안 기대 승수 (정수 반올림). 득점·실점이 없거나 0경기면 None."""
    if runs_scored is None or runs_allowed is None or not games:
        return None
    if runs_scored + runs_allowed == 0:
        return None
    rs = runs_scored ** PYTHAGOREAN_EXPONENT
    ra = runs_allowed ** PYTHAGOREAN_EXPONENT
    return round(games * rs / (rs + ra))


def finish_team(team):
    """화면에 필요 없는 항목을 빼고 기대 승패를 붙인다."""
    games = team["W"] + team["L"]
    x_wins = expected_wins(team["RS"], team["RA"], games)
    team["xW"] = x_wins
    team["xL"] = None if x_wins is None else games - x_wins
    return team


def group_by_league(leagues, groups):
    """리그 목록 + 지구별 묶음 → [{리그 정보, "divisions": [...]}]. 원본에 없는 리그는 빈 지구 목록."""
    result = []
    for league in leagues:
        divisions = [
            {
                "name": group["division"] or league["name"],
                "short": group["divisionShort"] or league["abbr"] or league["name"],
                "teams": [finish_team(team) for team in group["teams"]],
            }
            for group in groups
            if group["leagueId"] == league["id"]
        ]
        result.append(dict(league, divisions=divisions))
    return result


def check_level(level_id, leagues):
    """정규시즌 순위가 비정상이면 ValueError."""
    if not leagues:
        raise ValueError(f"{level_id} 리그 목록이 비어 있음")
    for league in leagues:
        if not league["divisions"] or not any(division["teams"] for division in league["divisions"]):
            raise ValueError(f"{level_id} {league['name']} 순위가 비어 있음")
    if level_id == "mlb":
        count = sum(len(division["teams"]) for league in leagues for division in league["divisions"])
        if count != MLB_CLUBS:
            raise ValueError(f"MLB 구단 수가 {MLB_CLUBS}개가 아님: {count}")


def collect_level(level_id, sport_id, season):
    leagues = statsapi.fetch_leagues(sport_id, season)
    if level_id == "mlb":
        # MLB 리그 목록에는 시범경기 리그(Cactus, Grapefruit)도 있으므로 AL·NL만 쓴다
        leagues = [league for league in leagues if league["id"] in MLB_LEAGUES]
    ids = [league["id"] for league in leagues]
    regular = group_by_league(leagues, statsapi.fetch_standings(ids, season)) if ids else []
    check_level(level_id, regular)
    split_ids = [league["id"] for league in leagues if league["split"]]
    halves = {}
    for half in HALVES:
        # 전·후반기 순위는 시즌 중에 아직 없을 수 있으므로 비어 있어도 실패로 보지 않는다
        groups = statsapi.fetch_standings(split_ids, season, half) if split_ids else []
        halves[half] = {league["id"]: league["divisions"] for league in group_by_league(leagues, groups)}
    for league in regular:
        league["halves"] = {
            half: halves[half].get(league["id"], []) for half in HALVES if league["split"] and halves[half].get(league["id"])
        }
    return regular


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-season", action="store_true", help=f"{SEASONS[0]} 시즌만 받는다 (일일 갱신)")
    parser.add_argument("--season", type=int, action="append", help="받을 시즌 (여러 번 지정 가능)")
    args = parser.parse_args()
    seasons = args.season or (SEASONS[:1] if args.current_season else SEASONS)

    failed = 0
    for season in seasons:
        levels = []
        try:
            for level_id, name, sport_id in LEVELS:
                leagues = collect_level(level_id, sport_id, season)
                teams = sum(len(division["teams"]) for league in leagues for division in league["divisions"])
                print(f"{season} {name}: 리그 {len(leagues)}개, 구단 {teams}개", flush=True)
                levels.append({"id": level_id, "name": name, "leagues": leagues})
        except Exception as error:
            print(f"[실패] {season} 순위: {error} (기존 파일 유지)", file=sys.stderr)
            failed += 1
            continue
        write(
            DATA / f"standings_{season}.json",
            {
                "season": season,
                "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "levels": levels,
            },
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
