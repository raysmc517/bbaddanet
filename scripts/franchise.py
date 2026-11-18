"""MLB 구단 연도별 성적 생성: python scripts/franchise.py [--current-season] [--refresh]

구단 페이지의 "연도별 성적" 표에 쓸 시즌별 승패·순위·득실점·기대 승패·포스트시즌 결과를 만든다.
MLB Stats API에서 시즌마다 정규시즌 순위 1회(1876~), 포스트시즌 시리즈 1회(1903~)를 요청한다.

- 끝난 시즌은 바뀌지 않으므로 data/franchise/seasons.json(수집 캐시)에 저장하고 다시 받지 않는다.
  최근 시즌은 매번 다시 받는다. --refresh는 전 시즌을 다시 받는다 (요청 약 280회).
- 화면용 자료는 현재 MLB 30개 구단만 data/franchise/{구단 ID}.json으로 만든다. 팀 ID로 묶으므로
  연고지를 옮기기 전 기록도 같은 구단이며, 그 시즌의 팀 이름을 행에 남긴다. 해체된 옛 구단은 넣지 않는다.
- 한 시즌이라도 실패하면 받은 시즌까지만 캐시에 저장하고 화면용 파일은 바꾸지 않는다.
- 기대 승패는 standings.py와 같은 피타고리안 지수 1.83으로 득점·실점에서 계산한다.
"""

import argparse
import json
import sys
from pathlib import Path

from careers import write
from collectors import statsapi
from standings import MLB_LEAGUES, expected_wins

DATA = Path(__file__).resolve().parent.parent / "data"
FOLDER = DATA / "franchise"
CACHE = FOLDER / "seasons.json"
FIRST_SEASON = 1876
FIRST_POSTSEASON = 1903  # 현대 월드시리즈 시작
SEASON = 2026  # build.py의 최근 시즌과 같게 유지
LEAGUE_ABBR = {103: "AL", 104: "NL"}

# 포스트시즌 라운드 (낮은 단계 → 높은 단계). R(동률 결정전)은 정규시즌 연장이라 넣지 않는다.
ROUNDS = ["F", "D", "L", "W"]


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_standings(data):
    """순위 응답 → 팀별 행 목록. 순수 함수라 따로 검증할 수 있다.

    지구가 있는 시즌(1969~)은 지구 순위, 없는 시즌은 리그 순위를 쓴다(rankType "div"|"lg").
    """
    rows = []
    for record in data.get("records", []):
        league = LEAGUE_ABBR.get(record.get("league", {}).get("id"))
        has_division = bool(record.get("division"))
        for item in record.get("teamRecords", []):
            team = item.get("team", {})
            result = item.get("leagueRecord", {})
            wins, losses = to_int(result.get("wins")), to_int(result.get("losses"))
            if not team.get("id") or wins is None or losses is None:
                continue
            rank = to_int(item.get("divisionRank") if has_division else item.get("leagueRank"))
            rows.append({
                "id": team["id"],
                "name": team.get("name", ""),
                "abbr": team.get("abbreviation", ""),
                "lg": league,
                "W": wins,
                "L": losses,
                "T": to_int(result.get("ties")) or 0,
                "rankType": "div" if has_division else "lg",
                "rank": rank,
                "GB": item.get("gamesBack") if item.get("gamesBack") not in (None, "") else None,
                "RS": to_int(item.get("runsScored")),
                "RA": to_int(item.get("runsAllowed")),
            })
    return rows


def parse_postseason(data):
    """포스트시즌 시리즈 응답 → {팀 ID: 결과}. 순수 함수라 따로 검증할 수 있다.

    결과는 가장 높이 오른 라운드다: "WS"(월드시리즈 우승), 그 밖에는 탈락한 라운드
    "W"(월드시리즈 준우승), "L"(챔피언십시리즈), "D"(디비전시리즈), "F"(와일드카드).
    시리즈 승자는 이긴 경기 수가 많은 팀이다. 아직 승부가 나지 않은 시리즈는 결과를 정하지 않는다.
    """
    best = {}  # 팀 ID → (라운드 순번, 결과)
    for series in data.get("series", []):
        kind = series.get("series", {}).get("gameType") or str(series.get("series", {}).get("id", ""))[:1]
        if kind not in ROUNDS:
            continue
        wins = {}
        for game in series.get("games", []):
            if game.get("status", {}).get("abstractGameState") != "Final":
                continue
            for side in ("away", "home"):
                team = game.get("teams", {}).get(side, {})
                team_id = team.get("team", {}).get("id")
                if team_id is None:
                    continue
                wins.setdefault(team_id, 0)
                if team.get("isWinner"):
                    wins[team_id] += 1
        if len(wins) != 2:
            continue
        (a, a_wins), (b, b_wins) = sorted(wins.items())
        if a_wins == b_wins:
            continue  # 진행 중이거나 판정할 수 없는 시리즈
        winner, loser = (a, b) if a_wins > b_wins else (b, a)
        order = ROUNDS.index(kind)
        results = {loser: kind}
        if kind == "W":
            results[winner] = "WS"
        for team_id, result in results.items():
            rank = order + (1 if result == "WS" else 0)
            if team_id not in best or rank > best[team_id][0]:
                best[team_id] = (rank, result)
    return {team_id: result for team_id, (_rank, result) in best.items()}


def fetch_season(season):
    """시즌 하나: {"teams": [행], "post": {팀 ID: 결과}}"""
    data = statsapi._get(
        "/standings",
        {
            "leagueId": ",".join(str(league) for league in MLB_LEAGUES),
            "season": season,
            "standingsTypes": "regularSeason",
            "hydrate": "team",
            "fields": "records,league,id,division,teamRecords,team,name,abbreviation,leagueRecord,wins,losses,ties,"
                      "divisionRank,leagueRank,gamesBack,runsScored,runsAllowed",
        },
    )
    teams = parse_standings(data)
    if not teams:
        return None  # 원본에 순위가 없는 시즌 (예: 1892 전·후반기 시즌). 호출한 쪽이 판단한다
    post = {}
    if season >= FIRST_POSTSEASON:
        series = statsapi._get(
            "/schedule/postseason/series",
            {
                "season": season, "sportId": 1,
                "fields": "series,id,gameType,games,teams,away,home,team,isWinner,status,abstractGameState",
            },
        )
        post = parse_postseason(series)
    return {"teams": teams, "post": {str(key): value for key, value in post.items()}}


def build_club(club_id, cache):
    """현재 구단 하나의 연도별 성적 (최근 시즌부터). 순수 함수라 따로 검증할 수 있다."""
    rows = []
    for season in sorted(cache, key=int, reverse=True):
        entry = cache[season]
        mine = next((row for row in entry["teams"] if row["id"] == club_id), None)
        if mine is None:
            continue
        games = mine["W"] + mine["L"]
        x_wins = expected_wins(mine["RS"], mine["RA"], games)
        row = {key: value for key, value in mine.items() if key != "id"}
        row.update(
            season=int(season),
            xW=x_wins,
            xL=None if x_wins is None else games - x_wins,
            post=entry["post"].get(str(club_id)),
        )
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--current-season", action="store_true", help="최근 시즌만 다시 받는다 (요청 2회)")
    parser.add_argument("--refresh", action="store_true", help="이미 받은 시즌도 다시 받는다")
    args = parser.parse_args()

    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    if args.current_season:
        targets = [SEASON]
    else:
        targets = [s for s in range(FIRST_SEASON, SEASON + 1) if args.refresh or s == SEASON or str(s) not in cache]

    done, failed, missing = 0, None, []
    try:
        for index, season in enumerate(targets, 1):
            entry = fetch_season(season)
            if entry is None:
                # 원본에 순위가 없는 옛 시즌은 건너뛴다. 캐시에 넣지 않아 다음 전체 실행 때 다시 확인한다.
                # 최근 시즌이 비면 일시적 오류일 수 있으므로 실패로 처리해 기존 파일을 지킨다.
                if season == SEASON:
                    raise ValueError(f"{season} 순위 응답이 비어 있음")
                missing.append(season)
                continue
            cache[str(season)] = entry
            done += 1
            if index % 10 == 0 or index == len(targets):
                print(f"구단 연도별 성적 {index}/{len(targets)} ({season})", flush=True)
    except Exception as error:
        failed = error

    # 시즌 단위로 완성된 자료만 들어 있으므로 받은 시즌까지는 캐시에 남긴다. 다시 실행하면 이어서 받는다.
    if missing:
        print(f"[알림] 원본에 순위가 없어 건너뛴 시즌: {', '.join(map(str, missing))}", file=sys.stderr)
    if done:
        write(CACHE, dict(sorted(cache.items(), key=lambda item: int(item[0]))))
    if failed:
        print(f"[실패] 구단 연도별 성적: {failed} (화면용 파일 유지, 다시 실행하면 이어서 받음)", file=sys.stderr)
        return 1

    teams_path = DATA / "teams.json"
    if not teams_path.exists():
        print("[실패] data/teams.json이 없어 현재 구단을 알 수 없음 (teams.py를 먼저 실행)", file=sys.stderr)
        return 1
    clubs = json.loads(teams_path.read_text(encoding="utf-8"))["clubs"]
    # 갱신 시각은 넣지 않는다: 내용이 같으면 파일을 다시 쓰지 않아 매일 30개 파일이 바뀌지 않게 한다
    for club in clubs:
        rows = build_club(club["id"], cache)
        if not rows:
            print(f"[경고] {club['name']} 연도별 성적 없음", file=sys.stderr)
            continue
        write(FOLDER / f"{club['id']}.json", {"id": club["id"], "seasons": rows})
    print(f"구단 {len(clubs)}개 연도별 성적 저장 (캐시 {len(cache)}시즌)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
