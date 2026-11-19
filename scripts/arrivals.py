"""입단 경로 누락 점검: python scripts/arrivals.py [--ids 571970] [--refresh]

기존 이동·지명으로 설명되지 않는 경로만 공식 이동에서 50명씩 조회한다. 마이너 FA 포함.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path
from careers import write
from collectors import statsapi
import moves

DATA = Path(__file__).resolve().parent.parent / "data"


def latest_for_club(rows, pid, club):
    candidates = []
    for tx in rows:
        if (tx.get("person") or {}).get("id") != pid or (tx.get("toTeam") or {}).get("id") != club:
            continue
        kind = {"SFA": "sign", "TR": "trade", "CLW": "claim"}.get(tx.get("typeCode"))
        if not kind:
            continue
        when = (tx.get("effectiveDate") or tx.get("date") or "")[:10]
        date.fromisoformat(when)
        if when < "2009-01-01":
            continue
        if kind == "sign" and "minor league contract" in tx.get("description", "").lower():
            kind = "minor_sign"
        candidates.append((when, tx.get("id", 0), kind, (tx.get("fromTeam") or {}).get("id")))
    if not candidates:
        return None
    when, _, kind, origin = max(candidates)
    return [when, kind, club, origin, f"https://statsapi.mlb.com/api/v1/transactions?playerId={pid}"]


def audit():
    clubs = json.loads((DATA / "teams.json").read_text(encoding="utf-8"))["clubs"]
    organizations = {team["name"]: club for club in clubs for team in [club] + club.get("affiliates", [])}
    existing = json.loads((DATA / "arrivals.json").read_text(encoding="utf-8"))
    recruitment = json.loads((DATA / "recruitment.json").read_text(encoding="utf-8"))
    index = json.loads((DATA / "search.json").read_text(encoding="utf-8"))["players"]
    candidates, inspected = {}, 0
    # 화면에서 입단 경로를 표시하는 모든 프로필을 점검한다. MLB 출전 여부로 거르지 않는다.
    for row in index:
        player = json.loads((DATA / "players" / f"{row[0]}.json").read_text(encoding="utf-8"))
        club = organizations.get(player.get("team"))
        if player.get("past") or not club:
            continue
        inspected += 1
        pid = str(player["id"])
        arrival, entry = existing.get(pid), recruitment.get(pid) or {}
        if arrival and arrival[2] == club["id"] or entry.get("team") == club["name"]:
            continue
        candidates[pid] = {"name": player["name"], "team": club["id"]}
    return inspected, candidates


def fetch_batch(ids):
    payload = statsapi._get("/transactions", {"playerId": ",".join(ids), "startDate": "2009-01-01", "endDate": date.today().isoformat()})
    rows = payload.get("transactions")
    if not isinstance(rows, list) or not rows:
        raise ValueError("이동 기록 빈 응답/형식 오류: 기존 캐시 유지")
    allowed = set(map(int, ids))
    if any((tx.get("person") or {}).get("id") not in allowed for tx in rows):
        raise ValueError("요청하지 않은 선수 이동 응답")
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", nargs="+", type=int)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)
    inspected, candidates = audit()
    path = DATA / "arrival_details.json"
    cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"players": {}}
    if args.refresh or args.ids:
        for pid, record in cache["players"].items():
            if args.refresh or int(pid) in args.ids:
                candidates.setdefault(pid, {"name": record["name"], "team": record["team"]})
    if args.ids:
        candidates = {pid: row for pid, row in candidates.items() if int(pid) in args.ids}
    todo = [pid for pid, item in candidates.items() if args.refresh or pid not in cache["players"] or cache["players"][pid]["team"] != item["team"]
            or (not cache["players"][pid].get("arrival") and (date.today() - date.fromisoformat(cache["players"][pid]["checked"])).days >= 7)]
    print(f"구단 연결 선수 {inspected}명 점검 · 누락 {len(candidates)}명 · 요청 대상 {len(todo)}명", flush=True)
    failed = 0
    for offset in range(0, len(todo), 50):
        batch = todo[offset:offset + 50]
        try:
            rows = fetch_batch(batch)
            updates = {}
            for pid in batch:
                item = candidates[pid]
                arrival = latest_for_club(rows, int(pid), item["team"])
                previous = cache["players"].get(pid)
                if arrival is None and previous and previous["team"] == item["team"] and previous.get("arrival"):
                    raise ValueError(f"{pid}: 이전 정상 입단 기록이 빈 결과로 바뀜")
                updates[pid] = {**item, "checked": date.today().isoformat(), "arrival": arrival}
            cache["players"].update(updates)
            write(path, cache)
            print(f"  {offset + len(batch)}/{len(todo)}명 확인", flush=True)
        except Exception as error:
            failed = 1
            print(f"[실패] 입단 경로 {batch[0]} 등: {error}", file=sys.stderr, flush=True)
    moves.save_arrivals()
    updated = json.loads((DATA / "arrivals.json").read_text(encoding="utf-8"))
    resolved = sum(bool(updated.get(pid) and updated[pid][2] == item["team"]) for pid, item in candidates.items())
    cache["audit"] = {"checked": date.today().isoformat(), "inspected": inspected, "candidates": len(candidates), "resolved": resolved, "unresolved": len(candidates) - resolved}
    write(path, cache)
    print(f"누락 중 {resolved}명 보완 · {len(candidates) - resolved}명 미확인", flush=True)
    return failed


if __name__ == "__main__":
    sys.exit(main())
