"""과거 MLB 선수(은퇴 선수 등) 추가: python scripts/past_players.py [--from 1999 --to 1999] [--ids 118377]

최근 시즌 리더보드에 없는 MLB 출전 경험 선수의 프로필과 커리어를 만든다.
1. 시즌별 MLB 선수 명단에서 선수 ID를 모은다. (--ids를 주면 명단을 받지 않는다)
2. 선수 파일이 없는 선수만 프로필을 받아 data/players/{id}.json을 만든다.
3. careers.py와 같은 방식으로 MLB·마이너리그 연도별 기록을 받아 합친다.
4. 검색 색인(data/search.json)을 다시 만든다.

이미 있는 선수 파일은 덮어쓰지 않는다. 과거 시즌의 세이버 지표는 계산하지 않는다.
"""

import argparse
import sys
from pathlib import Path

import careers
import search_index
from collectors import statsapi

DATA = Path(__file__).resolve().parent.parent / "data"
FIRST_SEASON = 1876  # 원본이 선수 명단을 제공하는 첫 시즌
LAST_SEASON = 2026


def discover(first, last):
    """시즌별 MLB 명단의 선수 ID. (ID 집합, 실패한 시즌 목록)"""
    ids, failed = set(), []
    for season in range(first, last + 1):
        try:
            found = statsapi.fetch_player_ids(1, season)
            if not found:
                raise ValueError("명단이 비어 있음")
            ids.update(found)
            print(f"명단 {season}: {len(found)}명 (누적 {len(ids)}명)", flush=True)
        except Exception as error:
            failed.append(season)
            print(f"[실패] 명단 {season}: {error}", file=sys.stderr, flush=True)
    return ids, failed


def create_profiles(ids):
    """선수 파일이 없는 선수의 프로필 파일을 만든다. 만든 선수 ID 목록을 돌려준다."""
    profiles = statsapi.fetch_people(ids)
    created = []
    for player_id in sorted(ids):
        profile = profiles.get(player_id)
        path = DATA / "players" / f"{player_id}.json"
        if profile is None or path.exists():
            continue
        if not profile["active"]:
            # 은퇴 선수의 '현재 팀'은 윈터리그 팀이나 마지막 소속 팀이라 현재 소속으로 표시하지 않는다.
            profile["team"] = ""
            # 은퇴 선수 표시. careers.py는 이 선수들의 MLB 기록만 받는다.
            profile["past"] = True
        careers.write(path, {**profile, "batting": [], "pitching": []})
        created.append(player_id)
    return created


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="first", type=int, default=FIRST_SEASON, help="명단을 받을 첫 시즌")
    parser.add_argument("--to", dest="last", type=int, default=LAST_SEASON, help="명단을 받을 마지막 시즌")
    parser.add_argument("--ids", nargs="+", type=int, help="명단 대신 지정한 선수만 추가")
    args = parser.parse_args()

    ok = True
    if args.ids:
        ids = set(args.ids)
    else:
        ids, failed = discover(args.first, args.last)
        ok = not failed
    existing = {int(path.stem) for path in (DATA / "players").glob("*.json")}
    missing = ids - existing
    print(f"대상 {len(ids)}명 중 새 선수 {len(missing)}명", flush=True)

    if missing:
        try:
            created = create_profiles(missing)
        except Exception as error:
            print(f"[실패] 프로필: {error}", file=sys.stderr)
            return 1
        print(f"프로필 {len(created)}명 생성", flush=True)
        if len(created) < len(missing):
            ok = False
            print(f"[경고] 프로필 응답이 없는 선수 {len(missing) - len(created)}명", file=sys.stderr)

    # careers.py는 커리어가 아직 없는 선수만 받고, 받은 기록을 선수 파일에 합친다.
    # 이전 실행이 중간에 끊겼어도 대상 선수 전체를 넘기면 남은 선수부터 이어진다.
    targets = sorted(player_id for player_id in ids if (DATA / "players" / f"{player_id}.json").exists())
    if targets and careers.main(["--ids", *map(str, targets)]):
        ok = False

    print(f"검색 색인 {search_index.build()}명", flush=True)
    print("완료" if ok else "일부 실패 (위 메시지 확인)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
