"""MLB Stats API 수집기.

sport_id만 바꾸면 MiLB에도 그대로 쓴다. (1=MLB, 11=AAA, 12=AA)
"""

import time

import requests

BASE = "https://statsapi.mlb.com/api/v1"
PAGE_SIZE = 1000
DELAY_SEC = 0.5  # 요청 사이 간격

_session = requests.Session()


def _get(path, params):
    """GET 요청. 일시적 오류는 세 번까지 다시 시도한다."""
    last_error = None
    for attempt in range(3):
        try:
            res = _session.get(BASE + path, params=params, timeout=30)
            res.raise_for_status()
            time.sleep(DELAY_SEC)
            return res.json()
        except requests.RequestException as error:
            last_error = error
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Stats API 요청 실패: {path} {params}") from last_error


def fetch_teams(sport_id, season):
    """팀 ID → 약칭 표."""
    data = _get("/teams", {"sportId": sport_id, "season": season})
    return {team["id"]: team["abbreviation"] for team in data["teams"]}


def fetch_team_directory(sport_id, season):
    """팀 목록. [{"id", "name", "abbr"}]"""
    data = _get("/teams", {"sportId": sport_id, "season": season})
    return [
        {"id": team["id"], "name": team["name"], "abbr": team["abbreviation"]}
        for team in data["teams"]
    ]


def _fetch_splits(group, sport_id, season, pool):
    """선수별 시즌 성적 전체를 페이지 단위로 받아온다."""
    splits = []
    offset = 0
    while True:
        data = _get(
            "/stats",
            {
                "stats": "season",
                "group": group,
                "season": season,
                "sportId": sport_id,
                "playerPool": pool,
                "limit": PAGE_SIZE,
                "offset": offset,
            },
        )
        block = data["stats"][0] if data["stats"] else {"splits": [], "totalSplits": 0}
        splits.extend(block["splits"])
        offset += PAGE_SIZE
        if not block["splits"] or offset >= block["totalSplits"]:
            return splits


def _rate(value):
    """'.300' 같은 문자열을 숫자로. '.---'처럼 값이 없으면 None."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _div(numerator, denominator, digits=3):
    if not denominator:
        return None
    return round(numerator / denominator, digits)


def _common(split, teams, qualified_ids):
    player = split["player"]
    team_id = split.get("team", {}).get("id")
    return {
        "id": player["id"],
        "name": player["fullName"],
        "team": teams.get(team_id, ""),
        "nt": split.get("numTeams", 1),  # 시즌 중 소속 팀 수
        "lg": split.get("league", {}).get("name", ""),
        "pos": split.get("position", {}).get("abbreviation", ""),
        "age": split["stat"].get("age"),
        "q": player["id"] in qualified_ids,  # 규정타석(이닝) 충족 여부
    }


def _batter(split, teams, qualified_ids):
    s = split["stat"]
    g = s.get
    pa, ab, h, hr = g("plateAppearances", 0), g("atBats", 0), g("hits", 0), g("homeRuns", 0)
    bb, so, sf = g("baseOnBalls", 0), g("strikeOuts", 0), g("sacFlies", 0)
    avg, slg = _rate(g("avg")), _rate(g("slg"))
    row = _common(split, teams, qualified_ids)
    row.update(
        {
            "G": g("gamesPlayed", 0), "PA": pa, "AB": ab, "R": g("runs", 0), "H": h,
            "2B": g("doubles", 0), "3B": g("triples", 0), "HR": hr, "RBI": g("rbi", 0),
            "BB": bb, "IBB": g("intentionalWalks", 0), "SO": so, "HBP": g("hitByPitch", 0),
            "SB": g("stolenBases", 0), "CS": g("caughtStealing", 0),
            "SF": sf, "SH": g("sacBunts", 0), "GDP": g("groundIntoDoublePlay", 0),
            "TB": g("totalBases", 0),
            "AVG": avg, "OBP": _rate(g("obp")), "SLG": slg, "OPS": _rate(g("ops")),
            "ISO": round(slg - avg, 3) if avg is not None and slg is not None else None,
            "BABIP": _div(h - hr, ab - so - hr + sf),
            "BBp": _div(bb, pa, 4), "Kp": _div(so, pa, 4),
        }
    )
    return row


def _pitcher(split, teams, qualified_ids):
    s = split["stat"]
    g = s.get
    outs, bf, h, hr = g("outs", 0), g("battersFaced", 0), g("hits", 0), g("homeRuns", 0)
    bb, so = g("baseOnBalls", 0), g("strikeOuts", 0)
    row = _common(split, teams, qualified_ids)
    row.update(
        {
            "G": g("gamesPitched", 0), "GS": g("gamesStarted", 0),
            "W": g("wins", 0), "L": g("losses", 0), "SV": g("saves", 0), "HLD": g("holds", 0),
            "outs": outs, "H": h, "R": g("runs", 0), "ER": g("earnedRuns", 0), "HR": hr,
            "BB": bb, "IBB": g("intentionalWalks", 0), "SO": so,
            "HBP": g("hitByPitch", 0), "BF": bf,
            "ERA": _rate(g("era")), "WHIP": _rate(g("whip")),
            "K9": _div(so * 27, outs, 2), "BB9": _div(bb * 27, outs, 2),
            "HR9": _div(hr * 27, outs, 2),
            "Kp": _div(so, bf, 4), "BBp": _div(bb, bf, 4), "KBBp": _div(so - bb, bf, 4),
            "BABIP": _div(h - hr, g("atBats", 0) - so - hr + g("sacFlies", 0)),
        }
    )
    return row


def fetch_games(sport_id, season):
    """정규시즌 종료 경기 목록. (홈팀 ID, 원정팀 ID, 홈 득점, 원정 득점, 구장 ID)"""
    data = _get(
        "/schedule",
        {
            "sportId": sport_id,
            "season": season,
            "gameType": "R",
            "startDate": f"{season}-02-01",
            "endDate": f"{season}-11-30",
            "fields": "dates,games,gamePk,status,codedGameState,teams,home,away,score,team,id,venue",
        },
    )
    games = {}
    for date in data.get("dates", []):
        for game in date["games"]:
            home, away = game["teams"]["home"], game["teams"]["away"]
            if game["status"].get("codedGameState") != "F" or "score" not in home or "score" not in away:
                continue
            games[game["gamePk"]] = (
                home["team"]["id"], away["team"]["id"], home["score"], away["score"],
                game.get("venue", {}).get("id"),
            )
    return list(games.values())


def fetch_official_saber(group, sport_id, season):
    """MLB가 제공하는 공식 세이버 지표. 선수 ID → 지표 표. (MLB만 제공된다)"""
    data = _get(
        "/stats",
        {
            "stats": "sabermetrics", "group": group, "season": season,
            "sportId": sport_id, "playerPool": "ALL", "limit": 2000,
        },
    )
    block = data["stats"][0] if data.get("stats") else {"splits": []}
    return {split["player"]["id"]: split["stat"] for split in block["splits"]}


def _height_cm(text):
    """6' 4" 형식의 키를 cm로 바꾼다."""
    try:
        feet, inches = text.replace('"', "").split("'")
        return round((int(feet) * 12 + int(inches)) * 2.54)
    except (AttributeError, ValueError):
        return None


def fetch_people(player_ids, batch_size=300):
    """선수 프로필을 여러 명씩 묶어 받아온다. 선수 ID → 프로필 표를 돌려준다."""
    profiles = {}
    ids = sorted(player_ids)
    for start in range(0, len(ids), batch_size):
        batch = ids[start:start + batch_size]
        data = _get(
            "/people",
            {"personIds": ",".join(str(i) for i in batch), "hydrate": "currentTeam"},
        )
        for person in data.get("people", []):
            weight = person.get("weight")
            profiles[person["id"]] = {
                "id": person["id"],
                "name": person.get("fullName", ""),
                "pos": person.get("primaryPosition", {}).get("abbreviation", ""),
                "team": person.get("currentTeam", {}).get("name", ""),
                "number": person.get("primaryNumber", ""),
                "birthDate": person.get("birthDate"),
                "age": person.get("currentAge"),
                "country": person.get("birthCountry", ""),
                "heightCm": _height_cm(person.get("height")),
                "weightKg": round(weight * 0.4536) if weight else None,
                "bats": person.get("batSide", {}).get("code", ""),
                "throws": person.get("pitchHand", {}).get("code", ""),
                "debut": person.get("mlbDebutDate"),
                "active": person.get("active", False),
            }
    return profiles


def collect(group, sport_id, season, teams=None):
    """한 시즌의 타자('hitting') 또는 투수('pitching') 성적 목록을 돌려준다."""
    if teams is None:
        teams = fetch_teams(sport_id, season)
    qualified = _fetch_splits(group, sport_id, season, "QUALIFIED")
    qualified_ids = {split["player"]["id"] for split in qualified}
    splits = _fetch_splits(group, sport_id, season, "ALL")
    convert = _batter if group == "hitting" else _pitcher
    return [convert(split, teams, qualified_ids) for split in splits]
