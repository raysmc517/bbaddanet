"""MLB 투구 위치·핫콜드존 집계. 원본 CSV는 메모리에서만 읽는다.

python scripts/zones.py --season 2026
python scripts/zones.py --from 2008 --to 2026
완료 경기 3일 단위 집계를 캐시하고 최근 7일만 다시 받는다. --refresh는 전부 갱신.
"""
import argparse
import csv
import io
import hashlib
import json
import math
import re
import time
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from careers import write

DATA = Path(__file__).resolve().parent.parent / "data" / "zones"
SOURCE = "https://baseballsavant.mlb.com/statcast_search/csv"
HITS = {"single": 1, "double": 2, "triple": 3, "home_run": 4}
AT_BATS = {*HITS, "field_out", "force_out", "grounded_into_double_play", "double_play", "triple_play",
           "fielders_choice", "fielders_choice_out", "field_error", "strikeout", "strikeout_double_play"}
SWINGS = {"swinging_strike", "swinging_strike_blocked", "missed_bunt", "foul", "foul_tip", "foul_bunt",
          "bunt_foul_tip", "hit_into_play", "hit_into_play_no_out", "hit_into_play_score", "foul_pitchout", "swinging_pitchout"}
WHIFFS = {"swinging_strike", "swinging_strike_blocked", "missed_bunt", "swinging_pitchout"}
FIELDS = {"pitch_type", "game_date", "game_type", "pitcher", "batter", "plate_x", "plate_z", "sz_top", "sz_bot",
          "stand", "p_throws", "description", "events", "game_pk", "at_bat_number", "pitch_number"}
HALF_PLATE = 17 / 24  # feet. 공 중심을 기준으로 하며 공 반지름을 더하지 않는다.
GRID = 20
REQUEST_LOCK = threading.Lock()
LAST_REQUEST = 0.0


def numeric(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def zone(x, height):
    """위→아래·포수 왼쪽→오른쪽 5×5. 외곽 한 칸은 그 방향 전체다."""
    col = sum(x >= edge for edge in (-HALF_PLATE, -HALF_PLATE / 3, HALF_PLATE / 3, HALF_PLATE))
    row = 4 - sum(height >= edge for edge in (0, 1 / 3, 2 / 3, 1))
    return row * 5 + col


def blank(pitch, hand):
    return {"pitch": pitch, "hand": hand, "seen": 0, "missing": 0, "outside": 0,
            "zones": [[0] * 6 for _ in range(25)], "density": Counter()}


def aggregate(text, start, end, expected, allowed=None, allow_sparse=False):
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not FIELDS.issubset(reader.fieldnames or []):
        raise ValueError("위치 CSV 열 누락 또는 오류 응답")
    result, games, seen = {}, set(), {}
    located_count = 0
    raw_count = 0
    for row in reader:
        raw_count += 1
        day = date.fromisoformat(row["game_date"][:10])
        if not start <= day <= end or row["game_type"] != "R":
            raise ValueError("요청 기간·정규시즌과 다른 응답")
        game = int(row["game_pk"])
        if game not in expected:
            if allowed is not None and game in allowed:
                continue  # 일정에 있는 진행 중 경기는 완료 경기 표본에 섞지 않는다.
            raise ValueError(f"요청 경기 밖 응답: {game}")
        key = (game, int(row["at_bat_number"]), int(row["pitch_number"]))
        signature = tuple(row[field] for field in sorted(FIELDS))
        if key in seen:
            if seen[key] != signature:
                raise ValueError("동일 투구의 상충 행")
            continue
        seen[key] = signature
        games.add(game)
        x, z, top, bot = (numeric(row[k]) for k in ("plate_x", "plate_z", "sz_top", "sz_bot"))
        located = None not in (x, z, top, bot) and top > bot > 0
        located_count += int(located)
        height = (z - bot) / (top - bot) if located else None
        for role, opponent in (("pitching", "stand"), ("batting", "p_throws")):
            pid = str(int(row["pitcher" if role == "pitching" else "batter"]))
            if int(pid) < 1:
                raise ValueError("선수 ID 오류")
            pitch, hand = row["pitch_type"] or "UN", row[opponent] or "U"
            splits = result.setdefault(pid, {}).setdefault(role, {})
            item = splits.setdefault((pitch, hand), blank(pitch, hand))
            item["seen"] += 1
            if not located:
                item["missing"] += 1
                continue
            cell = item["zones"][zone(x, height)]
            event, description = row["events"], row["description"]
            for i, value in enumerate((1, int(description in SWINGS), int(description in WHIFFS),
                                       int(event in AT_BATS), int(event in HITS), HITS.get(event, 0))):
                cell[i] += value
            # 위치 분포는 공별 좌표 대신 20×20 빈도만 저장한다.
            if -2 <= x < 2 and -0.5 <= height < 1.5:
                col = min(GRID - 1, int((x + 2) / 4 * GRID))
                r = min(GRID - 1, int((1.5 - height) / 2 * GRID))
                item["density"][r * GRID + col] += 1
            else:
                item["outside"] += 1
    if games != set(expected):
        missing = sorted(set(expected) - games)
        raise ValueError(f"{start}~{end}: 경기 누락 {len(missing)}개 {missing[:10]} (CSV 잘림·원본 미제공 가능)")
    if not result or raw_count >= 25000:
        raise ValueError("빈 응답 또는 CSV 응답 한도 도달")
    if located_count < len(seen) * .5 and not allow_sparse:
        raise ValueError("위치·존 높이 유효 측정값이 50% 미만")
    return {"games": sorted(games), "pitches": len(seen), "players": encode(result)}


def encode(players):
    return {pid: {role: [{**item, "zones": {str(i): cell for i, cell in enumerate(item["zones"]) if any(cell)},
                           "density": sorted(item["density"].items())}
                          for _, item in sorted(splits.items())] for role, splits in roles.items()}
            for pid, roles in players.items()}


def merge(chunks):
    result = {}
    games = set()
    for chunk in chunks:
        if games.intersection(chunk["games"]):
            raise ValueError("수집 구간의 경기 중복")
        games.update(chunk["games"])
        for pid, roles in chunk["players"].items():
            for role, rows in roles.items():
                splits = result.setdefault(pid, {}).setdefault(role, {})
                for row in rows:
                    item = splits.setdefault((row["pitch"], row["hand"]), blank(row["pitch"], row["hand"]))
                    for field in ("seen", "missing", "outside"):
                        item[field] += row[field]
                    cells = row["zones"].items() if isinstance(row["zones"], dict) else enumerate(row["zones"])
                    for i, cell in cells:
                        i = int(i)
                        for j, n in enumerate(cell):
                            item["zones"][i][j] += n
                    item["density"].update(dict(row["density"]))
    return encode(result)


def fetch(url, params):
    global LAST_REQUEST
    for attempt in range(3):
        if attempt:
            time.sleep(3 * attempt)
        # 여러 구간을 동시에 받을 때도 요청 시작 간격은 최소 1초다.
        with REQUEST_LOCK:
            time.sleep(max(0, 1 - (time.monotonic() - LAST_REQUEST)))
            LAST_REQUEST = time.monotonic()
        try:
            response = requests.get(url, params=params, timeout=120)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == 2:
                raise


def publish(payload):
    season = payload["season"]
    index_path = DATA / str(season) / "index.json"
    old = None
    if index_path.exists():
        old = json.loads(index_path.read_text(encoding="utf-8"))
        if payload["pitches"] < old["pitches"] * .9 or len(payload["players"]) < old["playerCount"] * .9:
            raise ValueError("시즌 표본 10% 초과 감소")
    buckets = {}
    for pid, player in payload["players"].items():
        for rows in player.values():
            for row in rows:
                if isinstance(row["zones"], list):
                    row["zones"] = {str(i): cell for i, cell in enumerate(row["zones"]) if any(cell)}
        buckets.setdefault(f"{int(pid) % 100:02}", {})[pid] = player
    names = {}
    for key, players in buckets.items():
        data = {"season": season, "players": players}
        digest = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]
        names[key] = f"{key}.{digest}.json"
        write(DATA / str(season) / names[key], data)
    previous = set()
    if old:
        previous = set(old["buckets"].values()) if isinstance(old["buckets"], dict) else {f"{k}.json" for k in old["buckets"]}
    # 변경하지 않는 파일을 모두 쓴 뒤 색인 하나만 원자적으로 바꾼다.
    write(index_path, {**{k: v for k, v in payload.items() if k != "players"},
                       "playerCount": len(payload["players"]), "buckets": names, "previousBuckets": sorted(previous)})
    write(DATA / "index.json", {"seasons": sorted((int(p.parent.name) for p in DATA.glob("*/index.json") if p.parent.name.isdigit()), reverse=True)})
    # 이전 색인을 가진 브라우저를 위해 직전 버전도 한 세대 보존한다.
    keep = set(names.values()) | previous
    for path in index_path.parent.glob("*.json"):
        if re.fullmatch(r"\d{2}(\.[a-f0-9]{12})?\.json", path.name) and path.name not in keep:
            path.unlink()


def compact_cache(chunk):
    """초기 배열 캐시도 읽되 빈 구역을 생략해 저장 공간을 줄인다."""
    changed = False
    for roles in chunk["players"].values():
        for rows in roles.values():
            for row in rows:
                if isinstance(row["zones"], list):
                    row["zones"] = {str(i): cell for i, cell in enumerate(row["zones"]) if any(cell)}
                    changed = True
    return changed


def located_pitches(chunk):
    return sum(row["seen"] - row["missing"] for player in chunk["players"].values()
               for row in player.get("pitching", []))


def completed(game):
    status = game.get("status", {})
    # 취소·연기·중단의 옛 일정 행도 abstractGameState=Final일 수 있다.
    # 취소된 경기의 과거 연기 행을 완료 경기로 다시 포함하지 않는다.
    return (status.get("abstractGameState") == "Final" and status.get("codedGameState") not in {"C", "D", "U"}
            and not status.get("detailedState", "").startswith(("Cancelled", "Postponed", "Suspended")))


def collect(season, refresh=False, workers=1):
    today = datetime.now(timezone(timedelta(hours=9))).date()
    schedule = fetch("https://statsapi.mlb.com/api/v1/schedule", {"sportId": 1, "season": season, "gameType": "R"}).json()
    if not isinstance(schedule.get("dates"), list) or not schedule["dates"]:
        raise ValueError("정규시즌 일정 빈 응답")
    days, scheduled = {}, {}
    for block in schedule["dates"]:
        for g in block["games"]:
            day = date.fromisoformat(g.get("officialDate", block["date"]))
            if g.get("gameType") == "R":
                scheduled.setdefault(day, set()).add(g["gamePk"])
            if g.get("gameType") == "R" and completed(g) and day <= today:
                days.setdefault(day, set()).add(g["gamePk"])
    if not days:
        raise ValueError("완료된 경기 없음")
    start, last = min(days), max(days)
    intervals = []
    while start <= last:
        end = min(start + timedelta(days=2), last)
        expected = set().union(*(ids for day, ids in days.items() if start <= day <= end))
        if expected:
            intervals.append((start, end, expected))
        start = end + timedelta(days=1)

    def load_interval(interval):
        start, end, expected = interval
        path = DATA / "cache" / str(season) / f"{start}.json"
        old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        if old:
            changed = False
            if "updated" not in old:
                old["updated"] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
                changed = True
            if compact_cache(old) or changed:
                write(path, old)
        reusable = old and set(old["games"]) == expected and not refresh and end < today - timedelta(days=7)
        if reusable:
            return old
        print(f"{start}~{end}: {len(expected)}경기 조회", flush=True)
        text = fetch(SOURCE, {"all": "true", "type": "details", "player_type": "pitcher",
                             "game_date_gt": str(start), "game_date_lt": str(end),
                             "hfSea": f"{season}|", "hfGT": "R|"}).text
        allowed = set().union(*(ids for day, ids in scheduled.items() if start <= day <= end))
        # 과거 해외 개막전 등 경기 전체의 위치가 미측정일 수 있다.
        # 경기·투구·기간 검증은 유지하고 누락 수를 보존하며 시즌 전체 유효 비율도 검사한다.
        chunk = aggregate(text, start, end, expected, allowed, allow_sparse=season < today.year)
        chunk["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if old and chunk["pitches"] < old["pitches"] * .9:
            raise ValueError("구간 투구 수 10% 초과 감소")
        if old and located_pitches(chunk) < located_pitches(old) * .9:
            raise ValueError("구간 위치 유효 표본 10% 초과 감소 — 기존 캐시 유지")
        write(path, chunk)
        print(f"{start}~{end}: {chunk['pitches']}구 캐시 저장", flush=True)
        return chunk

    if workers == 1:
        chunks = [load_interval(interval) for interval in intervals]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            chunks = list(pool.map(load_interval, intervals))
    pitches = sum(c["pitches"] for c in chunks)
    missing = pitches - sum(located_pitches(c) for c in chunks)
    if pitches - missing < pitches * .5:
        raise ValueError("시즌 위치·존 높이 유효 측정값이 50% 미만")
    players = merge(chunks)
    games_count = len(set().union(*(set(c["games"]) for c in chunks)))
    if len(players) < min(100, games_count * 10):
        raise ValueError("시즌 선수 수 비정상")
    updated = max(c["updated"] for c in chunks)
    # 모든 구간을 검증한 뒤 화면용 버킷을 교체한다. 수집 실패 중에는 공개 파일을 건드리지 않는다.
    payload = {"season": season, "updated": updated, "through": str(last), "gameType": "R", "games": games_count,
               "checked": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "pitches": pitches, "missing": missing, "players": players}
    publish(payload)
    print(f"{season}: {len(players)}명, {payload['games']}경기, {payload['pitches']}구 저장", flush=True)


def published(season):
    """정상 공개본이 있으면 완료 시즌을 불필요하게 다시 받지 않는다."""
    path = DATA / str(season) / "index.json"
    try:
        index = json.loads(path.read_text(encoding="utf-8"))
        # 시즌 도중 만든 파일이 해가 바뀐 뒤 영구히 고정되지 않도록 한다.
        checked = datetime.fromisoformat(index.get("checked", "").replace("Z", "+00:00")).date()
        if checked < date(season + 1, 1, 1):
            return False
        buckets = index["buckets"]
        names = list(buckets.values()) if isinstance(buckets, dict) else [f"{key}.json" for key in buckets]
        return (index["season"] == season and index["gameType"] == "R" and index["pitches"] > 0 and bool(names)
                and all(re.fullmatch(r"\d{2}(\.[a-f0-9]{12})?\.json", name)
                        and (path.parent / name).is_file() and (path.parent / name).stat().st_size > 0 for name in names))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--season", type=int)
    selection.add_argument("--current-season", action="store_true")
    selection.add_argument("--from", dest="start", type=int)
    parser.add_argument("--to", dest="end", type=int)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--workers", type=int, default=1, help="동시 조회 구간 수(1~16). 요청 시작 간격은 최소 1초 유지")
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error("--workers는 1~16입니다")
    current = datetime.now(timezone(timedelta(hours=9))).year
    if args.end is not None and args.start is None:
        parser.error("--to는 --from과 함께 사용합니다")
    if args.start is not None:
        end = args.end if args.end is not None else current
        if not 2008 <= args.start <= end <= current:
            parser.error("수집 범위는 2008년부터 현재 연도까지 오름차순으로 지정합니다")
        seasons = range(end, args.start - 1, -1)
    else:
        seasons = [current if args.current_season else args.season or 2026]
    failed = []
    for season in seasons:
        try:
            if season < current and not args.refresh and published(season):
                print(f"{season}: 검증된 공개본 있음 (건너뜀, 재수집은 --refresh)", flush=True)
                continue
            collect(season, args.refresh, args.workers)
        except (ValueError, requests.RequestException, KeyError, OSError) as error:
            print(f"{season} 위치 집계 실패 — 화면용 기존 파일 유지: {error}", flush=True)
            failed.append(season)
    if failed:
        print(f"실패 시즌: {', '.join(map(str, failed))} — 정상 구간 캐시부터 재실행 가능", flush=True)
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
