"""MLB 리그 전체 선수 이동 소식 생성: python scripts/moves.py [--season 2026]

rosters.py가 구단별로 받아 둔 이동 기록(data/rosters/{시즌}/{구단 ID}.json의 moves)을 합쳐
data/moves_{시즌}.json 하나로 만든다. 외부 요청은 하지 않는다. rosters.py 뒤에 실행한다.

- 넣는 이동: 트레이드, FA 계약(메이저 계약), 웨이버 클레임, 40인 명단 등록(계약 선택), 양도지명,
  아웃라이트, 방출, FA 선언. 콜업·옵션·부상자 명단처럼 매일 많은 시즌 중 운영 이동은 구단 선수단 페이지에서 본다.
- 같은 트레이드·웨이버 클레임은 양쪽 구단 파일에 모두 있으므로 한 건으로 묶는다.
  트레이드는 날짜와 원문 설명이 같은 기록을 한 건으로 보고, 선수마다 어느 구단에서 어느 구단으로 갔는지 남긴다.
- 공식 처리된 이동만 있다(보도·루머 없음). 원문 설명은 번역하지 않는다.
- 구단 파일이 30개가 아니면 기존 파일을 그대로 둔다.
- 선수 페이지의 "입단 경로"용으로 선수별 마지막 영입(트레이드·FA 계약·웨이버 클레임)을 data/arrivals.json에 모은다.
  {선수 ID: [날짜, 종류, 간 구단 ID, 떠난 구단 ID 또는 None]}. 2009~2023 시즌 이적(past_moves.py)도 함께 본다.
  원본 이동 기록이 2009년 무렵부터라 그 전 이동은 없다.
"""

import argparse
import json
import sys
from pathlib import Path

from careers import write

DATA = Path(__file__).resolve().parent.parent / "data"
SEASONS = [2026, 2025, 2024]  # rosters.py의 SEASONS와 같게 유지한다
MLB_CLUBS = 30

# 한 구단 기록의 이동 종류 → 리그 소식의 종류. 없는 종류는 넣지 않는다.
KINDS = {
    "trade_in": "trade", "trade_out": "trade",
    "claim_in": "claim", "claim_out": "claim",
    "sign": "sign", "select": "select", "dfa": "dfa", "outright": "outright", "release": "release", "fa": "fa",
}


def assemble(files):
    """구단 파일 목록 [(구단 ID, moves)] → 리그 소식 목록 (최신순). 순수 함수라 따로 검증할 수 있다.

    소식 하나: {"date", "type", "desc"(트레이드만), "teams": [구단 ID], "players": [{"id", "name", "page", "from", "to"}]}
    from·to는 그 선수가 떠난·간 구단 ID다(모르면 None). 트레이드에서 구단 소속 마이너리그 선수도 포함된다.
    """
    events = {}
    for club_id, moves in files:
        for move in moves:
            kind = KINDS.get(move.get("type"))
            if not kind:
                continue
            other = (move.get("team") or {}).get("id")
            if move["type"] in ("trade_in", "claim_in"):
                origin, dest = other, club_id
            elif move["type"] in ("trade_out", "claim_out"):
                origin, dest = club_id, other
            elif move["type"] in ("sign", "select"):
                origin, dest = None, club_id  # 계약 선택의 상대는 산하 마이너리그 구단이므로 남기지 않는다
            else:
                origin, dest = club_id, None
            # 트레이드는 원문 설명이 같으면 한 건, 그 밖에는 선수 한 명이 한 건
            key = (move["date"], kind, move.get("desc", "")) if kind == "trade" else (move["date"], kind, move["id"], origin, dest)
            event = events.setdefault(key, {"date": move["date"], "type": kind, "desc": move.get("desc", ""), "teams": set(), "players": {}})
            event["teams"].update(team for team in (origin, dest) if team)
            player = event["players"].setdefault(move["id"], {
                "id": move["id"], "name": move.get("name", ""), "page": move.get("page", 0), "from": None, "to": None,
            })
            player["from"] = player["from"] or origin
            player["to"] = player["to"] or dest
    result = []
    for event in events.values():
        players = sorted(event["players"].values(), key=lambda item: (item["to"] or 0, item["name"]))
        item = {**event, "teams": sorted(event["teams"]), "players": players}
        if event["type"] != "trade":
            del item["desc"]  # 트레이드 외에는 종류·구단·선수로 문장을 만들 수 있으므로 원문을 빼 파일을 줄인다
        result.append(item)
    result.sort(key=lambda item: (item["date"] or "", item["type"], item.get("desc", ""), item["players"][0]["name"]), reverse=True)
    return result


ARRIVALS = ("trade", "sign", "claim")


def latest_arrivals(events_by_season):
    """시즌별 소식 목록 → {선수 ID: [날짜, 종류, 간 구단, 떠난 구단]} (가장 최근 영입). 순수 함수라 따로 검증할 수 있다."""
    result = {}
    for events in events_by_season:
        for event in events:
            if event["type"] not in ARRIVALS:
                continue
            for player in event["players"]:
                if not player.get("to"):
                    continue
                key = str(player["id"])
                if key not in result or event["date"] > result[key][0]:
                    result[key] = [event["date"], event["type"], player["to"], player.get("from")]
    return dict(sorted(result.items(), key=lambda item: int(item[0])))


def save_arrivals():
    """저장된 모든 시즌 파일(최근 시즌 + past_moves.py의 2009~2023)로 입단 경로 색인을 만든다. 저장한 선수 수."""
    saved = [json.loads(path.read_text(encoding="utf-8"))["events"] for path in sorted(DATA.glob("moves_*.json"))]
    arrivals = latest_arrivals(saved)
    write(DATA / "arrivals.json", arrivals)
    # 선수 페이지에서는 연도 선택 없이 커리어 전체의 이적만 읽는다.
    histories = {}
    for events in saved:
        for event in events:
            if event["type"] not in ("trade", "sign", "claim", "release", "fa"):
                continue
            for player in event["players"]:
                histories.setdefault(str(player["id"]), []).append({
                    "date": event["date"], "type": event["type"],
                    "from": player.get("from"), "to": player.get("to"),
                })
    for rows in histories.values():
        rows.sort(key=lambda row: (row["date"], row["type"]), reverse=True)
    write(DATA / "player_moves.json", histories)
    return len(arrivals)


def build(season):
    folder = DATA / "rosters" / str(season)
    paths = sorted(folder.glob("*.json"))
    if len(paths) != MLB_CLUBS:
        raise ValueError(f"{season} 구단 선수단 파일이 {MLB_CLUBS}개가 아님: {len(paths)}")
    files, updated = [], []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        team = data.get("team")
        club_id = team.get("id") if isinstance(team, dict) else int(path.stem)
        files.append((club_id, data.get("moves", [])))
        if data.get("updated"):
            updated.append(data["updated"])
    events = assemble(files)
    return {"season": season, "updated": min(updated) if updated else None, "events": events}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--season", type=int, help="이 시즌만 만든다 (기본: 전 시즌)")
    args = parser.parse_args()
    failed = 0
    for season in [args.season] if args.season else SEASONS:
        try:
            payload = build(season)
        except Exception as error:
            print(f"[실패] {season} 이동 소식: {error} (기존 파일 유지)", file=sys.stderr)
            failed = 1
            continue
        write(DATA / f"moves_{season}.json", payload)
        print(f"{season} 이동 소식 {len(payload['events'])}건 저장")
    # 입단 경로 색인은 저장된 시즌 파일 전체로 만든다 (이번에 실패한 시즌은 직전 파일을 쓴다)
    print(f"입단 경로 {save_arrivals()}명 저장")
    return failed


if __name__ == "__main__":
    sys.exit(main())
