"""2009~2023 시즌 MLB 이적 기록: python scripts/past_moves.py [--from 2009] [--to 2023] [--refresh]

최근 시즌(rosters.py → moves.py)과 같은 MLB 공식 이동 기록(/transactions)을 구단·시즌별로 한 번 받아
data/moves_{시즌}.json을 만든다. 요청은 시즌마다 구단 목록 1회 + 구단 30회.

- 과거 시즌은 이적만 넣는다: 트레이드, FA 계약(메이저 계약), 웨이버 클레임, 방출, FA 선언(2026-11-19 사용자 결정).
  콜업·옵션·부상자 명단·양도지명·아웃라이트·40인 명단 등록은 넣지 않는다.
- 원본 이동 기록은 2009년 무렵부터 있다(그 전 시즌은 구단당 연 10건 안팎). 그래서 2009년부터 받는다.
- 이미 파일이 있는 시즌은 다시 받지 않는다(--refresh로 다시 받음). 한 구단이라도 실패하면 그 시즌 파일을 만들지 않는다.
- 끝나면 data/arrivals.json(입단 경로)을 저장된 모든 시즌으로 다시 만든다.
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from careers import write
from collectors import statsapi
import moves
import rosters

DATA = Path(__file__).resolve().parent.parent / "data"
FIRST_SEASON = 2009
LAST_SEASON = min(moves.SEASONS) - 1  # 2024년부터는 rosters.py가 모든 이동을 받는다
KEEP = {"trade_in", "trade_out", "claim_in", "claim_out", "sign", "release", "fa"}


def transfers(transactions, team_id, has_page):
    """원본 이동 기록 → 이적 행만 (최신순)."""
    return [row for row in rosters.season_moves(transactions, team_id, has_page) if row["type"] in KEEP]


def collect(season, has_page):
    clubs = statsapi.fetch_team_directory(1, season)
    if len(clubs) != moves.MLB_CLUBS:
        raise ValueError(f"{season} MLB 구단 수가 {moves.MLB_CLUBS}개가 아님: {len(clubs)}")
    files = []
    for club in clubs:
        rows = transfers(statsapi.fetch_transactions(club["id"], f"{season}-01-01", f"{season}-12-31"), club["id"], has_page)
        files.append((club["id"], rows))
    events = moves.assemble(files)
    if not events:
        raise ValueError(f"{season} 이적 기록이 비어 있음")
    return {
        "season": season,
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "transfers",  # 화면 안내용: 이적만 있는 시즌
        "events": events,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="start", type=int, default=FIRST_SEASON)
    parser.add_argument("--to", dest="end", type=int, default=LAST_SEASON)
    parser.add_argument("--refresh", action="store_true", help="이미 받은 시즌도 다시 받는다")
    args = parser.parse_args(argv)
    if args.start < FIRST_SEASON or args.end > LAST_SEASON or args.start > args.end:
        parser.error(f"시즌 범위는 {FIRST_SEASON}~{LAST_SEASON}")

    players = DATA / "players"
    has_page = lambda player_id: (players / f"{player_id}.json").exists()
    failed = 0
    for season in range(args.end, args.start - 1, -1):
        path = DATA / f"moves_{season}.json"
        if path.exists() and not args.refresh:
            print(f"{season}: 이미 있음 (건너뜀)")
            continue
        started = time.time()
        try:
            payload = collect(season, has_page)
        except Exception as error:
            print(f"[실패] {season} 이적 기록: {error} (파일을 만들지 않음)", file=sys.stderr, flush=True)
            failed = 1
            continue
        write(path, payload)
        print(f"{season}: 이적 {len(payload['events'])}건 ({time.time() - started:.0f}초)", flush=True)
    count = moves.save_arrivals()
    print(f"입단 경로 {count}명 저장")
    return failed


if __name__ == "__main__":
    sys.exit(main())
