"""데이터 수집 진입점. 프로젝트 폴더에서 `python scripts/build.py`로 실행한다.

1. 리그·레벨·시즌별 성적을 받아 data/ 아래에 JSON으로 저장한다.
2. 저장된 성적 파일을 모아 선수별 파일(data/players/{id}.json)을 만든다.

한 리그·시즌이 실패해도 나머지는 계속 진행하고, 실패한 파일은 직전 데이터를 유지한다.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import prospects
import search_index
import careers as career_data
from collectors import statsapi
from sabermetrics import calc, parkfactors

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SEASONS = [2026, 2025, 2024]

# 리그 목록. 단계가 진행되면 여기에 KBO, NPB를 추가한다.
# 레벨이 하나뿐인 리그는 level id를 None으로 둔다.
LEAGUES = [
    {
        "id": "mlb",
        "name": "MLB",
        "levels": [{"id": None, "name": "MLB", "sport_id": 1, "official_war": True}],
    },
    {
        "id": "milb",
        "name": "MiLB",
        "levels": [
            {"id": "aaa", "name": "AAA", "sport_id": 11},
            {"id": "aa", "name": "AA", "sport_id": 12},
            {"id": "high_a", "name": "High-A", "sport_id": 13},
            {"id": "single_a", "name": "Single-A", "sport_id": 14},
        ],
    },
]

GROUPS = {"batting": "hitting", "pitching": "pitching"}

# MLB와 산하 마이너리그 (MLB, AAA, AA, High-A, Single-A, Rookie)
AFFILIATED_SPORTS = [1, 11, 12, 13, 14, 16]

# 선수 파일의 시즌 행에는 넣지 않는 항목
ROW_SKIP = {"id", "name", "lg", "pos", "q"}


def write_json(path, payload):
    """JSON 저장. 내용이 그대로면 파일을 건드리지 않는다. 바뀌었으면 True."""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def stats_path(league, level, group, season):
    folder = DATA / league["id"]
    if level["id"]:
        folder = folder / level["id"]
    return folder / f"{group}_{season}.json"


def level_park_factors(level):
    """레벨의 시즌별 파크팩터 {시즌: {팀 ID: 값}}. 실패하면 빈 표(전부 중립)."""
    try:
        games = {season: statsapi.fetch_games(level["sport_id"], season) for season in SEASONS}
        return parkfactors.compute(games)
    except Exception as error:
        print(f"  [경고] {level['name']} 파크팩터를 구하지 못해 중립값을 씀: {error}", file=sys.stderr)
        return {}


def add_official_war(level, season, rows_by_group):
    """MLB가 공식 제공하는 WAR(수비 포함)을 'WAR' 항목으로 붙인다."""
    for group, api_group in GROUPS.items():
        official = statsapi.fetch_official_saber(api_group, level["sport_id"], season)
        for row in rows_by_group[group]:
            war = official.get(row["id"], {}).get("war")
            row["WAR"] = round(war, 1) if war is not None else None


def collect_level(league, level, updated, seasons=SEASONS):
    """리그의 레벨 하나를 수집한다. 모든 시즌이 성공하면 True."""
    label = level["name"]
    ok = True
    park_by_season = level_park_factors(level)
    for season in seasons:
        try:
            teams = statsapi.fetch_teams(level["sport_id"], season)
            rows_by_group = {
                group: statsapi.collect(api_group, level["sport_id"], season, teams)
                for group, api_group in GROUPS.items()
            }
            if not all(rows_by_group.values()):
                raise RuntimeError("선수 데이터가 비어 있음")

            # 세이버 지표 계산 (파크팩터는 팀 약칭 기준으로 바꿔서 넘긴다)
            park = {
                teams[team_id]: value
                for team_id, value in park_by_season.get(season, {}).items()
                if team_id in teams
            }
            constants = calc.apply(rows_by_group["batting"], rows_by_group["pitching"], park)
            if level.get("official_war"):
                add_official_war(level, season, rows_by_group)
            write_json(
                stats_path(league, level, "constants", season),
                {"league": league["id"], "level": level["name"], "season": season, **constants},
            )

            for group, players in rows_by_group.items():
                write_json(
                    stats_path(league, level, group, season),
                    {
                        "league": league["id"],
                        "level": level["name"],
                        "season": season,
                        "group": group,
                        "updated": updated,
                        "players": players,
                    },
                )
                print(f"  {label} {season} {group}: {len(players)}명")
        except Exception as error:  # 한 시즌 실패가 전체를 막지 않게 한다
            ok = False
            print(f"  [실패] {label} {season}: {error}", file=sys.stderr)
    return ok


def existing_seasons(league):
    """모든 레벨의 타자·투수 파일이 저장돼 있는 시즌."""
    return [
        season
        for season in SEASONS
        if all(
            stats_path(league, level, group, season).exists()
            for level in league["levels"]
            for group in GROUPS
        )
    ]


def affiliated_team(player, team_names):
    """비시즌에는 API의 현재 팀이 윈터리그 팀일 수 있다. 이때 쓸 MLB 산하 소속 팀.

    유망주는 Pipeline의 소속 팀을, 그 외에는 가장 최근 시즌 기록의 팀을 쓴다.
    시즌 중 팀을 옮긴 기록이라 팀을 알 수 없거나, 최근 3개 시즌 기록이 없으면 빈 값.
    """
    prospect = player.get("prospect")
    if prospect and prospect.get("club"):
        return prospect["club"]
    rows = player["batting"] + player["pitching"]
    if not rows:
        return ""
    latest = max(rows, key=lambda row: (row["season"], row.get("PA", 0) + row.get("outs", 0)))
    if latest["nt"] > 1:
        return ""
    return team_names.get((latest["level"], latest["team"]), "")


def build_players(prospect_info):
    """저장된 성적 파일을 모아 선수별 파일을 만든다. (성공 여부, 선수별 성적)을 돌려준다.

    수집 레벨의 기록이 없는 유망주도 프로필만 담은 파일을 만든다.
    """
    careers = {}  # 선수 ID → {"batting": [...], "pitching": [...]}
    for player_id in prospect_info:
        careers[player_id] = {"batting": [], "pitching": []}
    for league in LEAGUES:
        for level_order, level in enumerate(league["levels"]):
            for season in SEASONS:
                for group in GROUPS:
                    path = stats_path(league, level, group, season)
                    if not path.exists():
                        continue
                    data = json.loads(path.read_text(encoding="utf-8"))
                    for player in data["players"]:
                        played = player["PA"] if group == "batting" else player["outs"]
                        if not played:
                            continue
                        row = {"season": season, "league": league["id"], "level": level["name"]}
                        row.update({k: v for k, v in player.items() if k not in ROW_SKIP})
                        career = careers.setdefault(player["id"], {"batting": [], "pitching": []})
                        career[group].append(row)

    level_rank = {
        level["name"]: index
        for index, level in enumerate(lv for league in LEAGUES for lv in league["levels"])
    }
    try:
        profiles = statsapi.fetch_people(careers.keys())
        # 레벨별 팀 이름 표 {(레벨 이름, 약칭): 팀 이름}과 MLB 산하 팀 이름 목록
        team_names = {}
        for level in (lv for league in LEAGUES for lv in league["levels"]):
            for team in statsapi.fetch_team_directory(level["sport_id"], SEASONS[0]):
                team_names[(level["name"], team["abbr"])] = team["name"]
        affiliated = {
            team["name"]
            for sport_id in AFFILIATED_SPORTS
            for team in statsapi.fetch_team_directory(sport_id, SEASONS[0])
        }
    except Exception as error:
        print(f"  [실패] 선수 프로필: {error}", file=sys.stderr)
        return False, careers

    changed = 0
    for player_id, career in careers.items():
        profile = profiles.get(player_id)
        if profile is None:
            continue
        for group in GROUPS:
            career[group].sort(key=lambda row: (-row["season"], level_rank[row["level"]]))
        # 별도 수집한 과거 커리어를 매번 재빌드해도 보존한다.
        payload = {**profile, **career}
        career_data.merge_cached(payload, DATA)
        if player_id in prospect_info:
            payload["prospect"] = prospect_info[player_id]
        if payload["team"] not in affiliated:
            payload["team"] = affiliated_team(payload, team_names)
        if write_json(DATA / "players" / f"{player_id}.json", payload):
            changed += 1
    print(f"  선수 파일 {len(careers)}개 (변경 {changed}개)")
    return True, careers


def main():
    parser = argparse.ArgumentParser(description="빠따넷 데이터 수집")
    parser.add_argument("--skip-stats", action="store_true", help="성적은 다시 받지 않고 저장된 파일을 그대로 쓴다")
    parser.add_argument("--pipeline", action="store_true", help="이번 주 랭킹이 있어도 Pipeline 랭킹을 다시 받는다")
    parser.add_argument("--levels", nargs="+", choices=["mlb", "aaa", "aa", "high_a", "single_a"], help="수집할 레벨 ID (mlb, aaa, aa, high_a, single_a)")
    parser.add_argument(
        "--current-season",
        action="store_true",
        help=f"가장 최근 시즌({SEASONS[0]})만 다시 받는다. 끝난 시즌은 저장된 파일을 그대로 쓴다 (일일 자동 갱신용)",
    )
    args = parser.parse_args()
    seasons = SEASONS[:1] if args.current_season else SEASONS

    updated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta = {"updated": updated, "leagues": []}
    ok = True
    for league in LEAGUES:
        if not args.skip_stats:
            print(f"{league['name']} 수집 중...")
            for level in league["levels"]:
                if not args.levels or (level["id"] or league["id"]) in args.levels:
                    ok = collect_level(league, level, updated, seasons) and ok
        seasons = existing_seasons(league)
        if seasons:
            entry = {"id": league["id"], "name": league["name"], "seasons": seasons}
            if len(league["levels"]) > 1:
                entry["levels"] = [{"id": lv["id"], "name": lv["name"]} for lv in league["levels"]]
            meta["leagues"].append(entry)
    print("Pipeline 랭킹 확인 중...")
    latest, history, pipeline_ok = prospects.refresh(
        DATA / "milb" / "pipeline", write_json, SEASONS[0], force=args.pipeline
    )
    ok = pipeline_ok and ok

    print("선수 파일 만드는 중...")
    players_ok, careers = build_players(prospects.index(latest, history))
    ok = players_ok and ok

    if latest:
        write_json(DATA / "milb" / "prospects.json", prospects.build_page(latest, history, careers, SEASONS[0]))
        meta["prospects"] = {"week": latest["week"], "date": latest["date"]}
    write_json(DATA / "meta.json", meta)
    try:
        print(f"검색 색인 {search_index.build(DATA)}명")
    except Exception as error:  # 색인 실패는 기존 색인을 유지한다
        ok = False
        print(f"  [실패] 검색 색인: {error}", file=sys.stderr)
    print("완료" if ok else "일부 실패 (위 메시지 확인)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
