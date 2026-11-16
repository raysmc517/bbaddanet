"""MLB Pipeline 유망주 랭킹의 주차별 스냅샷과 유망주 페이지용 데이터.

data/milb/pipeline/latest.json   가장 최근에 받아온 랭킹 (주 1회 갱신)
data/milb/pipeline/history.json  주차별 순위 기록 (순위 변동 계산용)
data/milb/prospects.json         유망주 페이지가 읽는 파일 (랭킹 + 올 시즌 성적, 매일 갱신)
"""

import json
import sys
from datetime import date

from collectors import pipeline, statsapi

# 유망주 목록에 함께 보여줄 올 시즌 성적 항목
BATTING_KEYS = ["level", "team", "G", "PA", "AVG", "OBP", "SLG", "OPS", "HR", "SB", "BBp", "Kp", "wRCp"]
PITCHING_KEYS = ["level", "team", "G", "GS", "outs", "ERA", "FIP", "WHIP", "Kp", "BBp", "ERAm"]


def current_week():
    year, week, _ = date.today().isocalendar()
    return f"{year}-W{week:02d}"


def _read(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _collect(season):
    """랭킹을 받아와 소속 구단을 약칭으로 정리한다."""
    data = pipeline.collect()
    directory = statsapi.fetch_team_directory(1, season)
    abbr_by_name = {team["name"]: team["abbr"] for team in directory}
    abbr_by_id = {team["id"]: team["abbr"] for team in directory}

    org_of = {}  # 선수 ID → 구단 약칭 (팀별 목록 기준)
    for team in data["teams"]:
        if team["name"] not in abbr_by_name:
            raise RuntimeError(f"구단 이름을 찾지 못함: {team['name']}")
        team["abbr"] = abbr_by_name[team["name"]]
        for player in team["players"]:
            player["org"] = team["abbr"]
            player.pop("orgId", None)
            org_of[player["id"]] = team["abbr"]
    for player in data["top100"]:
        player["org"] = org_of.get(player["id"]) or abbr_by_id.get(player.pop("orgId", None), "")
        player.pop("orgId", None)
    data["teams"].sort(key=lambda team: team["abbr"])
    return data


def refresh(folder, write_json, season, force=False):
    """이번 주 랭킹이 없으면 받아온다. (latest, history, 성공 여부)를 돌려준다."""
    latest_path = folder / "latest.json"
    history_path = folder / "history.json"
    latest = _read(latest_path, None)
    history = _read(history_path, [])
    week = current_week()
    ok = True

    if latest and latest["week"] == week and not force:
        print(f"  이번 주({week}) 랭킹이 이미 있어 다시 받지 않음")
    else:
        try:
            latest = {"week": week, "date": date.today().isoformat(), **_collect(season)}
            write_json(latest_path, latest)
            count = sum(len(team["players"]) for team in latest["teams"])
            print(f"  {week} 랭킹: Top 100 {len(latest['top100'])}명, 팀별 {count}명")
        except Exception as error:  # 실패하면 지난 랭킹을 그대로 쓴다
            ok = False
            print(f"  [실패] Pipeline 랭킹: {error}", file=sys.stderr)

    if latest:
        snapshot = {
            "week": latest["week"],
            "date": latest["date"],
            "top100": {str(p["id"]): p["rank"] for p in latest["top100"]},
            "org": {str(p["id"]): [team["abbr"], p["rank"]] for team in latest["teams"] for p in team["players"]},
        }
        history = [item for item in history if item["week"] != snapshot["week"]] + [snapshot]
        history.sort(key=lambda item: item["week"])
        write_json(history_path, history)
    return latest, history, ok


def index(latest, history):
    """선수 ID → 유망주 정보 (선수 페이지용)."""
    if not latest:
        return {}
    info = {}
    for team in latest["teams"]:
        for player in team["players"]:
            info[player["id"]] = {
                "top100": None, "org": team["abbr"], "orgRank": player["rank"],
                "eta": player["eta"], "pos": player["pos"], "level": player["level"], "club": player["club"],
            }
    for player in latest["top100"]:
        entry = info.setdefault(
            player["id"],
            {"org": player["org"], "orgRank": None, "eta": player["eta"], "pos": player["pos"],
             "level": player["level"], "club": player["club"]},
        )
        entry["top100"] = player["rank"]
    for player_id, entry in info.items():
        key = str(player_id)
        entry["history"] = [
            {"week": item["week"], "top100": item["top100"].get(key), "orgRank": (item["org"].get(key) or [None, None])[1]}
            for item in history
            if key in item["top100"] or key in item["org"]
        ]
    return info


def is_pitcher(position):
    return "HP" in position or position in ("P", "SP", "RP")


def _season_line(career, position, season):
    """올 시즌 가장 많이 뛴 레벨의 성적 한 줄. AA 이상 기록이 없으면 None."""
    order = ["pitching", "batting"] if is_pitcher(position) else ["batting", "pitching"]
    for group in order:
        rows = [row for row in career.get(group, []) if row["season"] == season]
        if rows:
            amount = "outs" if group == "pitching" else "PA"
            best = max(rows, key=lambda row: row[amount])
            keys = PITCHING_KEYS if group == "pitching" else BATTING_KEYS
            return {"group": group, **{key: best.get(key) for key in keys}}
    return None


def build_page(latest, history, careers, season):
    """유망주 페이지가 읽을 데이터."""
    previous = history[-2] if len(history) >= 2 else None

    def rows(players, previous_rank):
        result = []
        for player in players:
            row = dict(player)
            if previous:
                row["prev"] = previous_rank(player)  # 지난주 순위, 없으면 None(신규)
            row["stat"] = _season_line(careers.get(player["id"], {}), player["pos"], season)
            result.append(row)
        return result

    def previous_org_rank(abbr):
        def lookup(player):
            entry = previous["org"].get(str(player["id"]))
            return entry[1] if entry and entry[0] == abbr else None
        return lookup

    return {
        "week": latest["week"],
        "date": latest["date"],
        "season": season,
        "previousWeek": previous["week"] if previous else None,
        "top100": rows(latest["top100"], lambda player: previous["top100"].get(str(player["id"]))),
        "teams": [
            {"abbr": team["abbr"], "name": team["name"], "players": rows(team["players"], previous_org_rank(team["abbr"]))}
            for team in latest["teams"]
        ],
    }
