"""프로 커리어 수집. python scripts/careers.py [--ids 694973 ...] [--refresh]

레벨별 yearByYear 정규시즌 기록을 캐시한다. 기본 실행은 미수집 선수만 받는다.
해외 리그 기록과 정확한 최초 경기 날짜는 이 API 응답으로 확정하지 않는다.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from collectors import statsapi

DATA = Path(__file__).resolve().parent.parent / "data"
SPORTS = {1: "MLB", 11: "AAA", 12: "AA", 13: "High-A", 14: "Single-A", 15: "Short-Season A", 16: "Rookie"}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    temporary = path.with_suffix(".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


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
            if row["G"]:
                result[group].append(row)
    return result


def merge_cached(player, data=DATA):
    path = data / "careers" / f"{player['id']}.json"
    if not path.exists():
        return
    cached = json.loads(path.read_text(encoding="utf-8"))
    for group in ("batting", "pitching"):
        recent = [r for r in player[group] if not r.get("careerSource") and "teamId" not in r]
        keys = {(r["season"], r["level"]) for r in recent}
        # 현재 시즌의 자체 계산 지표를 보존하고, 과거 및 Rookie 기록을 추가한다.
        history = [r for r in cached[group] if (r["season"], r["level"]) not in keys]
        player[group] = sorted(recent + history, key=lambda r: (-r["season"], r["level"], r["team"]))
    seasons = [r["season"] for g in ("batting", "pitching") for r in player[g]]
    player["careerStart"] = min(seasons) if seasons else None
    player["careerUpdated"] = cached["updated"]
    player["careerStatus"] = cached.get("status", "available")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", nargs="+", type=int)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    ids = args.ids or sorted(int(p.stem) for p in (DATA / "players").glob("*.json"))
    pending = [i for i in ids if args.refresh or not (DATA / "careers" / f"{i}.json").exists()]
    failed = False
    for start in range(0, len(pending), 300):
        batch = pending[start:start + 300]
        rows = {i: {"batting": [], "pitching": []} for i in batch}
        try:
            for sport in SPORTS:
                response = statsapi._get("/people", {
                    "personIds": ",".join(map(str, batch)),
                    "hydrate": f"stats(group=[hitting,pitching],type=[yearByYear],sportId={sport},gameType=R)",
                })
                people = response["people"]
                if {p["id"] for p in people} != set(batch):
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
            print(f"커리어 수집 {min(start + 300, len(pending))}/{len(pending)}", flush=True)
        except Exception as error:
            failed = True
            print(f"커리어 수집 실패: {error}", flush=True)
    for pid in ids:
        path = DATA / "players" / f"{pid}.json"
        if path.exists():
            player = json.loads(path.read_text(encoding="utf-8"))
            merge_cached(player)
            write(path, player)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
