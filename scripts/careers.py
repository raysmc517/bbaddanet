"""프로 커리어 수집. python scripts/careers.py [--ids 694973 ...] [--refresh]

레벨별 yearByYear 정규시즌 기록을 캐시한다. 기본 실행은 미수집 선수만 받는다.
해외 리그 기록과 정확한 최초 경기 날짜는 이 API 응답으로 확정하지 않는다.
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from collectors import statsapi

DATA = Path(__file__).resolve().parent.parent / "data"
SPORTS = {1: "MLB", 11: "AAA", 12: "AA", 13: "High-A", 14: "Single-A", 15: "Short-Season A", 16: "Rookie"}
SPORT_IDS = {name: sport for sport, name in SPORTS.items()}
TEAM_ABBR_FILE = "team_abbr.json"  # {"레벨ID-시즌": {"팀ID": "약자"}}
# 은퇴 선수는 이 시즌 이후 MLB 출전 기록이 있을 때만 마이너리그 기록을 받는다(2026-11-17 사용자 결정).
# 원본은 1990년대 초 이전 마이너리그 기록을 거의 제공하지 않는다. js/player.js의 같은 상수와 맞춘다.
PAST_MINOR_FROM = 2000

# 화면 항목 → 원본 필드. 옛 시즌은 원본에 없는 항목이 있다(예: 1914년 도루 실패, 희생플라이).
# 없는 항목을 0으로 저장하면 실제 0과 구분할 수 없으므로 None으로 남긴다.
SOURCE_FIELDS = {
    "batting": {
        "PA": "plateAppearances", "R": "runs", "2B": "doubles", "3B": "triples", "RBI": "rbi",
        "BB": "baseOnBalls", "IBB": "intentionalWalks", "SO": "strikeOuts", "HBP": "hitByPitch",
        "SB": "stolenBases", "CS": "caughtStealing", "SF": "sacFlies", "SH": "sacBunts",
        "GDP": "groundIntoDoublePlay", "TB": "totalBases", "GO": "groundOuts", "AO": "airOuts",
    },
    "pitching": {
        "GS": "gamesStarted", "W": "wins", "L": "losses", "SV": "saves", "HLD": "holds",
        "R": "runs", "ER": "earnedRuns", "HR": "homeRuns", "BB": "baseOnBalls",
        "IBB": "intentionalWalks", "SO": "strikeOuts", "HBP": "hitByPitch", "BF": "battersFaced",
        "CG": "completeGames", "SHO": "shutouts", "SVO": "saveOpportunities", "NP": "numberOfPitches",
        "AB": "atBats", "GO": "groundOuts", "AO": "airOuts",
    },
}
# 2026-11-18 추가 항목. 최근 시즌 행(리더보드 자료)에 없으면 같은 시즌·레벨 커리어 행의 합으로 채운다.
ADDED_FIELDS = {"batting": ["GO", "AO"], "pitching": ["CG", "SHO", "SVO", "NP", "AB", "GO", "AO"]}


def fill_added(recent, cached_rows, group):
    """최근 시즌 행에 없는 추가 항목을 커리어 캐시의 같은 시즌·레벨 팀별 행 합으로 채운다.
    한 팀이라도 값이 없으면 None으로 둔다. 커리어 행이 없으면 건드리지 않는다."""
    for row in recent:
        same = [r for r in cached_rows if r["season"] == row["season"] and r["level"] == row["level"]]
        if not same:
            continue
        for key in ADDED_FIELDS[group]:
            if row.get(key) is not None:
                continue
            values = [r.get(key) for r in same]
            row[key] = sum(values) if all(v is not None for v in values) else None


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    temporary = path.with_suffix(".tmp")
    temporary.write_text(text, encoding="utf-8")
    # OneDrive 등 동기화 프로그램이 파일을 잠깐 잡고 있으면 바꾸기가 거부될 수 있으므로 몇 번 다시 시도한다
    for attempt in range(6):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.5 * (attempt + 1))


def convert(person, sport):
    result = {"batting": [], "pitching": []}
    for block in person.get("stats", []):
        group = {"hitting": "batting", "pitching": "pitching"}.get(block["group"]["displayName"])
        if not group:
            continue
        splits = block.get("splits", [])
        seen = set()
        for split in splits:
            if split.get("gameType", "R") != "R" or split.get("sport", {}).get("id", sport) != sport:
                continue
            # API 합계 행과 팀별 행을 동시에 표시하지 않는다.
            if not split.get("team"):
                continue
            key = (split["season"], split["team"]["id"])
            if key in seen:
                continue
            seen.add(key)
            split = {**split, "player": person}
            team = split["team"]
            converter = statsapi._batter if group == "batting" else statsapi._pitcher
            row = converter(split, {team["id"]: team["name"]}, set())
            row.update(season=int(str(split["season"]).split(".")[0]), league="mlb" if sport == 1 else "milb",
                       level=SPORTS[sport], teamId=team["id"], careerSource=True,
                       seasonLabel=str(split["season"]))
            for field in ("id", "name", "q", "pos", "lg"):
                row.pop(field, None)
            for key, source in SOURCE_FIELDS[group].items():
                if source not in split["stat"]:
                    row[key] = None
            if row["G"]:
                result[group].append(row)
    return result


def load_team_abbr(data=DATA):
    path = data / TEAM_ABBR_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def fill_team_abbr(table, careers, fetch=None):
    """커리어에 나오는 레벨·시즌 중 표에 없는 팀 목록만 받아 약자 표를 채운다.

    과거 시즌 팀 약자는 바뀌지 않으므로 한 번 받은 레벨·시즌은 다시 요청하지 않는다.
    받지 못한 레벨·시즌은 건너뛰고 False 를 돌려준다(기존 표기 유지).
    """
    fetch = fetch or statsapi.fetch_teams
    needed = {(SPORT_IDS[r["level"]], r["season"])
              for career in careers for g in ("batting", "pitching") for r in career.get(g, [])
              if r.get("teamId") and r.get("level") in SPORT_IDS}
    ok = True
    for sport, season in sorted(needed):
        key = f"{sport}-{season}"
        if key in table:
            continue
        try:
            teams = fetch(sport, season)
        except Exception as error:
            ok = False
            print(f"팀 약자 수집 실패 {key}: {error}", flush=True)
            continue
        if teams:
            table[key] = {str(tid): abbr for tid, abbr in teams.items() if abbr}
    return ok


def apply_team_abbr(career, table):
    """과거 기록의 팀 표기를 최근 시즌 리더보드와 같은 약자로 바꾼다. 바뀌면 True."""
    changed = False
    for group in ("batting", "pitching"):
        for row in career.get(group, []):
            sport = SPORT_IDS.get(row.get("level"))
            abbr = table.get(f"{sport}-{row['season']}", {}).get(str(row.get("teamId")))
            if not abbr or row.get("team") == abbr:
                continue
            row.setdefault("teamName", row.get("team"))
            row["team"] = abbr
            changed = True
    return changed


def merge_cached(player, data=DATA):
    path = data / "careers" / f"{player['id']}.json"
    if not path.exists():
        return
    cached = json.loads(path.read_text(encoding="utf-8"))
    for group in ("batting", "pitching"):
        recent = [r for r in player[group] if not r.get("careerSource") and "teamId" not in r]
        keys = {(r["season"], r["level"]) for r in recent}
        fill_added(recent, cached[group], group)
        # 현재 시즌의 자체 계산 지표를 보존하고, 과거 및 Rookie 기록을 추가한다.
        history = [r for r in cached[group] if (r["season"], r["level"]) not in keys]
        player[group] = sorted(recent + history, key=lambda r: (-r["season"], r["level"], r["team"]))
    seasons = [r["season"] for g in ("batting", "pitching") for r in player[g]]
    player["careerStart"] = min(seasons) if seasons else None
    player["careerUpdated"] = cached["updated"]
    player["careerStatus"] = cached.get("status", "available")


def chunks(ids, size=300):
    return [ids[start:start + size] for start in range(0, len(ids), size)]


def is_past(player_id, data=DATA):
    """past_players.py가 추가한 은퇴 선수인지. 선수 파일의 past 표시로 판단한다."""
    path = data / "players" / f"{player_id}.json"
    return path.exists() and bool(json.loads(path.read_text(encoding="utf-8")).get("past"))


def past_minor_eligible(rows):
    """은퇴 선수의 MLB 기록(행 목록)에 PAST_MINOR_FROM 이후 시즌이 있는지."""
    return any(r.get("level") == "MLB" and r["season"] >= PAST_MINOR_FROM for r in rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", nargs="+", type=int)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)
    ids = args.ids or sorted(int(p.stem) for p in (DATA / "players").glob("*.json"))
    pending = [i for i in ids if args.refresh or not (DATA / "careers" / f"{i}.json").exists()]
    failed = False
    # 은퇴 선수(past)는 MLB 기록을 먼저 받고, PAST_MINOR_FROM 이후 MLB 출전 선수만 마이너리그 기록을 받는다.
    past = {i for i in pending if is_past(i)}
    queue = [(batch, False) for batch in chunks(sorted(set(pending) - past))]
    queue += [(batch, True) for batch in chunks(sorted(past))]
    done = 0
    for batch, is_past_batch in queue:
        rows = {i: {"batting": [], "pitching": []} for i in batch}
        try:
            for sport in SPORTS:  # MLB(1)가 먼저
                targets = batch
                if is_past_batch and sport != 1:
                    targets = [i for i in batch if past_minor_eligible(rows[i]["batting"] + rows[i]["pitching"])]
                    if not targets:
                        continue
                response = statsapi._get("/people", {
                    "personIds": ",".join(map(str, targets)),
                    "hydrate": f"stats(group=[hitting,pitching],type=[yearByYear],sportId={sport},gameType=R)",
                })
                people = response["people"]
                if {p["id"] for p in people} != set(targets):
                    raise ValueError("선수 응답 누락: 기존 커리어 유지")
                for person in people:
                    converted = convert(person, sport)
                    for group in ("batting", "pitching"):
                        rows[person["id"]][group].extend(converted[group])
            for pid, career in rows.items():
                if not career["batting"] and not career["pitching"]:
                    print(f"기록 없음: {pid}", flush=True)
                    career["status"] = "no_records"
                career["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                write(DATA / "careers" / f"{pid}.json", career)
            done += len(batch)
            print(f"커리어 수집 {done}/{len(pending)}", flush=True)
        except Exception as error:
            failed = True
            print(f"커리어 수집 실패: {error}", flush=True)
    # 팀 약자: 캐시된 커리어 전체에 적용한다(선수 성적은 다시 받지 않는다).
    cached = {}
    for pid in ids:
        path = DATA / "careers" / f"{pid}.json"
        if path.exists():
            cached[pid] = json.loads(path.read_text(encoding="utf-8"))
    table = load_team_abbr()
    if not fill_team_abbr(table, cached.values()):
        failed = True
    write(DATA / TEAM_ABBR_FILE, table)
    fixed = 0
    for pid, career in cached.items():
        if apply_team_abbr(career, table):
            write(DATA / "careers" / f"{pid}.json", career)
            fixed += 1
    print(f"팀 약자 적용: 커리어 {fixed}개 수정", flush=True)
    for pid in ids:
        path = DATA / "players" / f"{pid}.json"
        if path.exists():
            player = json.loads(path.read_text(encoding="utf-8"))
            merge_cached(player)
            write(path, player)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
