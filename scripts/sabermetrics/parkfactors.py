"""파크팩터 계산.

팀의 홈 경기와 원정 경기에서 나온 득점(양 팀 합계)을 비교한다.
1.000이 중립이고, 값이 클수록 타자에게 유리한 구장이다.

계산 순서
1. 원시값 = (홈 경기당 득점) / (원정 경기당 득점)
2. 원정 구장에 자기 구장이 빠져 있는 것을 보정
3. 표본이 작으므로 1.000 쪽으로 당김 (같은 구장을 쓴 시즌이 많을수록 덜 당김)
4. 선수는 경기의 절반만 홈에서 뛰므로 절반만 적용
"""

from collections import Counter

# 같은 구장을 쓴 시즌 수 → 원시값을 얼마나 믿을지
TRUST = {1: 0.6, 2: 0.8, 3: 0.9}


def _tally(games):
    """한 시즌 경기 목록 → 팀별 주 구장과 홈/원정 (경기 수, 득점 합)."""
    venues = {}
    for home, _away, _hs, _as, venue in games:
        venues.setdefault(home, Counter())[venue] += 1
    primary = {team: counter.most_common(1)[0][0] for team, counter in venues.items()}

    teams = {team: {"venue": venue, "home": [0, 0], "road": [0, 0]} for team, venue in primary.items()}
    for home, away, home_score, away_score, venue in games:
        if venue != primary.get(home):
            continue  # 해외 개최 등 주 구장이 아닌 경기는 뺀다
        runs = home_score + away_score
        teams[home]["home"][0] += 1
        teams[home]["home"][1] += runs
        if away in teams:
            teams[away]["road"][0] += 1
            teams[away]["road"][1] += runs
    return teams


def compute(games_by_season):
    """{시즌: 경기 목록} → {시즌: {팀 ID: 파크팩터}}"""
    tallies = {season: _tally(games) for season, games in games_by_season.items()}
    result = {}
    for season, teams in tallies.items():
        factors = {}
        for team, info in teams.items():
            # 같은 팀이 같은 구장을 쓴 시즌을 모두 합친다
            pool = [
                other[team]
                for other in tallies.values()
                if team in other and other[team]["venue"] == info["venue"]
            ]
            home_games = sum(p["home"][0] for p in pool)
            home_runs = sum(p["home"][1] for p in pool)
            road_games = sum(p["road"][0] for p in pool)
            road_runs = sum(p["road"][1] for p in pool)
            if not home_games or not road_games or not road_runs:
                factors[team] = 1.0
                continue
            raw = (home_runs / home_games) / (road_runs / road_games)
            count = len(teams)
            corrected = raw * count / (count - 1 + raw)
            trusted = 1 + (corrected - 1) * TRUST[min(len(pool), 3)]
            factors[team] = round((1 + trusted) / 2, 3)
        result[season] = factors
    return result
