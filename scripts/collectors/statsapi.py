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


def _venue(venue):
    """구장 정보. 원본에 없는 항목은 None으로 둔다."""
    location = venue.get("location", {})
    coords = location.get("defaultCoordinates", {})
    field = venue.get("fieldInfo", {})
    return {
        "id": venue.get("id"),
        "name": venue.get("name", ""),
        "address": location.get("address1"),
        "city": location.get("city"),
        "state": location.get("stateAbbrev") or location.get("state"),
        "country": location.get("country"),
        "lat": coords.get("latitude"),
        "lon": coords.get("longitude"),
        "elevationFt": location.get("elevation"),
        "capacity": field.get("capacity"),
        "turf": field.get("turfType"),
        "roof": field.get("roofType"),
        # 홈플레이트에서 펜스까지 거리(피트): 좌, 좌중, 중, 우중, 우
        "fence": [field.get(key) for key in ("leftLine", "leftCenter", "center", "rightCenter", "rightLine")],
    }


def fetch_clubs(sport_id, season):
    """구단과 홈구장 정보 목록. 마이너리그 구단은 parentId가 MLB 모구단 ID다."""
    data = _get(
        "/teams",
        {"sportId": sport_id, "season": season, "hydrate": "venue(location,fieldInfo),division,league"},
    )
    clubs = []
    for team in data["teams"]:
        if not team.get("active", True):
            continue
        first_year = team.get("firstYearOfPlay")
        clubs.append(
            {
                "id": team["id"],
                "name": team["name"],
                "teamName": team.get("teamName", ""),  # 연고지를 뺀 이름 (예: White Sox). 공식 홈페이지 주소용
                "abbr": team.get("abbreviation", ""),
                "parentId": team.get("parentOrgId"),
                "league": team.get("league", {}).get("name", ""),
                "leagueAbbr": team.get("league", {}).get("abbreviation", ""),
                "division": team.get("division", {}).get("name", ""),
                "divisionShort": team.get("division", {}).get("nameShort", ""),
                "firstYear": int(first_year) if str(first_year).isdigit() else None,
                "venue": _venue(team.get("venue", {})),
            }
        )
    return clubs


def fetch_award_recipients(award_id, sport_id=1):
    """상 하나의 역대 수상자 목록 (요청 1회). 팀은 수상 시즌 기준 약칭이다.

    선수 정보가 없는 항목은 건너뛴다. 원본에 없는 팀·포지션·비고는 빈 문자열, 팀 ID는 None으로 둔다.
    팀 ID는 연고지를 옮겨도 같은 구단이면 그대로다. 비고(note)는 영구결번의 등번호 등이다.
    날짜(date)는 원본의 수상·선출일이다 (옛 명예의 전당 행은 11-01로 채워져 있다).
    sport_id=None이면 레벨 필터를 넣지 않는다. sportId=1은 팀이 없거나 MLB 일반 구단 ID가 아닌 행
    (명예의 전당 임원·니그로리그 인물, 옛 구단 ID로 남은 Vladimir Guerrero 등)을 빼므로 수상 기록에는 None을 쓴다.
    """
    params = {
        "hydrate": "team",
        "fields": "awards,season,date,notes,team,abbreviation,player,id,nameFirstLast,primaryPosition",
    }
    if sport_id is not None:
        params["sportId"] = sport_id
    data = _get(f"/awards/{award_id}/recipients", params)
    recipients = []
    for item in data.get("awards", []):
        player = item.get("player") or {}
        season = str(item.get("season", ""))
        if not player.get("id") or not season.isdigit():
            continue
        position = player.get("primaryPosition", {}).get("abbreviation", "")
        recipients.append(
            {
                "season": int(season),
                "id": player["id"],
                "name": player.get("nameFirstLast", ""),
                "pos": "" if position == "X" else position,  # X는 원본의 '알 수 없음'
                "team": (item.get("team") or {}).get("abbreviation", ""),
                "teamId": (item.get("team") or {}).get("id"),
                "note": item.get("notes", ""),
                "date": item.get("date", ""),
            }
        )
    return recipients


def fetch_player_ids(sport_id, season):
    """해당 시즌에 그 레벨 로스터에 있었던 선수 ID 목록."""
    data = _get(f"/sports/{sport_id}/players", {"season": season, "fields": "people,id"})
    return [person["id"] for person in data.get("people", [])]


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
            # MLB.com 표의 GO/AO용 땅볼·뜬공 아웃. 원본에 없으면(옛 시즌) None
            "GO": g("groundOuts"), "AO": g("airOuts"),
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
            # MLB.com 표 항목: 완투, 완봉, 세이브 기회, 투구 수, 상대 타수(피안타율용), 땅볼·뜬공 아웃.
            # 원본에 없으면(옛 시즌) 0이 아닌 None
            "CG": g("completeGames"), "SHO": g("shutouts"), "SVO": g("saveOpportunities"),
            "NP": g("numberOfPitches"), "AB": g("atBats"), "GO": g("groundOuts"), "AO": g("airOuts"),
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
            # 은퇴 선수에게만 있는 값. 현역 선수 파일은 바뀌지 않게 있을 때만 넣는다.
            if person.get("lastPlayedDate"):
                profiles[person["id"]]["lastPlayed"] = person["lastPlayedDate"]
            if person.get("deathDate"):
                profiles[person["id"]]["deathDate"] = person["deathDate"]
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


def fetch_leagues(sport_id, season):
    """레벨의 리그 목록. [{"id", "name", "abbr", "wildCards", "split", "games", "endDate"}]
    wildCards: 와일드카드 진출 팀 수(없으면 0), split: 전·후반기로 나누는 리그인지,
    games: 팀당 정규시즌 경기 수, endDate: 정규시즌 마지막 날(YYYY-MM-DD, 없으면 None)."""
    data = _get("/league", {"sportId": sport_id, "season": season})
    leagues = []
    for league in data.get("leagues", []):
        if not league.get("active", True):
            continue
        leagues.append(
            {
                "id": league["id"],
                "name": league.get("name", ""),
                "abbr": league.get("abbreviation", ""),
                "wildCards": league.get("numWildcardTeams", 0) if league.get("hasWildCard") else 0,
                "split": bool(league.get("hasSplitSeason")),
                "games": league.get("numGames"),
                "endDate": league.get("seasonDateInfo", {}).get("regularSeasonEndDate"),
            }
        )
    return leagues


def _split_record(team, kind):
    """splitRecords에서 [승, 패]. 없으면 None."""
    for item in team.get("records", {}).get("splitRecords", []):
        if item.get("type") == kind:
            return [item.get("wins", 0), item.get("losses", 0)]
    return None


def _number(value):
    """'5', '+1.0', '-' 같은 원본 표기를 숫자로. 값이 없거나 '-'이면 None."""
    try:
        return float(str(value).replace("+", ""))
    except (TypeError, ValueError):
        return None


def fetch_standings(league_ids, season, kind="regularSeason"):
    """리그들의 순위 (요청 1회). kind: regularSeason, firstHalf, secondHalf.

    지구별 묶음 목록 [{"leagueId", "division", "divisionShort", "teams": [...]}]을 원본 순서대로 돌려준다.
    지구가 없는 리그는 division이 None이다. 승차는 원본 표기를 숫자로 바꾸고 1위(원본 '-')는 0이다.
    와일드카드 승차는 원본처럼 진출권 안쪽 팀이 양수('+3.0' → 3.0)라 부호를 뒤집어 뒤처진 만큼 양수로 둔다.
    """
    data = _get(
        "/standings",
        {
            "leagueId": ",".join(str(i) for i in league_ids),
            "season": season,
            "standingsTypes": kind,
            "hydrate": "team,division",
        },
    )
    groups = []
    for record in data.get("records", []):
        division = record.get("division") or {}
        teams = []
        for team in record.get("teamRecords", []):
            info = team.get("team", {})
            wc_gb = team.get("wildCardGamesBack")
            wc_back = None
            if team.get("wildCardRank"):
                wc_back = 0.0 if wc_gb in (None, "-") else -_number(wc_gb) if str(wc_gb).startswith("+") else _number(wc_gb)
            streak = team.get("streak", {}).get("streakCode")
            magic = team.get("magicNumber")
            teams.append(
                {
                    "id": info.get("id"),
                    "name": info.get("name", ""),
                    "abbr": info.get("abbreviation", ""),
                    "parentId": info.get("parentOrgId"),
                    "W": team.get("wins", 0),
                    "L": team.get("losses", 0),
                    "GB": 0.0 if team.get("gamesBack") == "-" else _number(team.get("gamesBack")),
                    "wcRank": int(team["wildCardRank"]) if str(team.get("wildCardRank", "")).isdigit() else None,
                    "wcGB": wc_back,
                    "clinch": team.get("clinchIndicator") or "",
                    "home": _split_record(team, "home"),
                    "away": _split_record(team, "away"),
                    "last10": _split_record(team, "lastTen"),
                    "streak": streak or "",
                    "RS": team.get("runsScored"),
                    "RA": team.get("runsAllowed"),
                    "magic": int(magic) if str(magic).isdigit() else None,
                }
            )
        groups.append(
            {
                "leagueId": record.get("league", {}).get("id"),
                "division": division.get("name"),
                "divisionShort": division.get("nameShort"),
                "teams": teams,
            }
        )
    return groups


def fetch_season_dates(season, sport_id=1):
    """시즌 일정의 주요 날짜 {"regularStart", "regularEnd", "postEnd", "springStart"}. 원본에 없으면 빈 표."""
    data = _get(f"/seasons/{season}", {"sportId": sport_id})
    seasons = data.get("seasons") or [{}]
    info = seasons[0]
    return {
        "springStart": info.get("springStartDate"),
        "regularStart": info.get("regularSeasonStartDate"),
        "regularEnd": info.get("regularSeasonEndDate"),
        "postEnd": info.get("postSeasonEndDate"),
    }


def fetch_roster(team_id, date=None, season=None, roster_type="40Man"):
    """MLB 구단 명단 (요청 1회). 원본의 40Man 명단은 60일 IL 선수도 포함한다.
    roster_type "fullSeason" + season은 그 시즌 중 한 번이라도 명단에 있었던 선수 전원이다 (상태는 시즌 이후 값일 수 있다).

    [{"id", "name", "num", "pos", "posType", "bats", "throws", "birthDate", "status", "statusText", "note"}]
    status는 원본 코드(A 액티브, RM 마이너 강등, D10/D15/D60 부상자 명단 등)다.
    """
    params = {"rosterType": roster_type, "hydrate": "person"}
    if date:
        params["date"] = date
    if season:
        params["season"] = season
    data = _get(f"/teams/{team_id}/roster", params)
    rows = []
    for item in data.get("roster", []):
        person = item.get("person") or {}
        if not person.get("id"):
            continue
        position = item.get("position") or person.get("primaryPosition") or {}
        status = item.get("status") or {}
        rows.append(
            {
                "id": person["id"],
                "name": person.get("fullName", ""),
                "num": item.get("jerseyNumber") or "",
                "pos": position.get("abbreviation", ""),
                "posType": position.get("type", ""),
                "bats": (person.get("batSide") or {}).get("code", ""),
                "throws": (person.get("pitchHand") or {}).get("code", ""),
                "birthDate": person.get("birthDate"),
                "status": status.get("code", ""),
                "statusText": status.get("description", ""),
                "note": item.get("note") or "",
            }
        )
    return rows


BAT_KEYS = {
    "G": "gamesPlayed", "PA": "plateAppearances", "H": "hits", "HR": "homeRuns", "RBI": "rbi",
    "SB": "stolenBases", "BB": "baseOnBalls", "SO": "strikeOuts",
}
PIT_KEYS = {
    "G": "gamesPitched", "GS": "gamesStarted", "W": "wins", "L": "losses", "SV": "saves", "HLD": "holds",
    "outs": "outs", "SO": "strikeOuts", "BB": "baseOnBalls",
}


def fetch_team_season_stats(team_id, season, group):
    """한 구단에서 거둔 선수별 정규시즌 성적 (요청 1회). 시즌 중 이적한 선수는 이 구단 기록만 들어 있다.
    {선수 ID: {"name", "pos", 기록...}}. group은 'hitting' 또는 'pitching'."""
    data = _get(
        "/stats",
        {
            "stats": "season", "group": group, "season": season, "sportId": 1,
            "teamId": team_id, "playerPool": "ALL", "limit": 500,
        },
    )
    block = data["stats"][0] if data.get("stats") else {"splits": []}
    keys = BAT_KEYS if group == "hitting" else PIT_KEYS
    result = {}
    for split in block["splits"]:
        stat = split.get("stat", {})
        row = {key: stat.get(source, 0) for key, source in keys.items()}
        if group == "hitting":
            row.update({key: _rate(stat.get(key.lower())) for key in ("AVG", "OBP", "SLG", "OPS")})
        else:
            row.update({"ERA": _rate(stat.get("era")), "WHIP": _rate(stat.get("whip"))})
        player = split.get("player", {})
        result[player["id"]] = dict(row, name=player.get("fullName", ""), pos=split.get("position", {}).get("abbreviation", ""))
    return result


def fetch_transactions(team_id, start_date, end_date):
    """구단의 선수 이동 기록 원본 목록 (요청 1회). 산하 마이너리그 배정 등도 섞여 있으므로 쓰는 쪽에서 거른다."""
    data = _get("/transactions", {"teamId": team_id, "startDate": start_date, "endDate": end_date})
    return data.get("transactions", [])
