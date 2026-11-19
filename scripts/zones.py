"""MLB 투구 위치·핫콜드존 집계. 원본 CSV는 메모리에서만 읽는다.

python scripts/zones.py --season 2026
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
from collections import Counter
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


def aggregate(text, start, end, expected, allowed=None):
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
        raise ValueError(f"경기 누락: {len(set(expected) - games)}개 (CSV 잘림·원본 미제공 가능)")
    if not result or raw_count >= 25000:
        raise ValueError("빈 응답 또는 CSV 응답 한도 도달")
    if located_count < len(seen) * .5:
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
    for attempt in range(3):
        time.sleep(1 + 3 * attempt)
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


def completed(game):
    status = game.get("status", {})
    # 우천 취소도 abstractGameState=Final이다. 투구 없는 취소를 완료 경기로 요구하지 않는다.
    return status.get("abstractGameState") == "Final" and status.get("codedGameState") != "C" and not status.get("detailedState", "").startswith("Cancelled")


def collect(season, refresh=False):
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
    chunks = []
    while start <= last:
        end = min(start + timedelta(days=2), last)
        expected = set().union(*(ids for day, ids in days.items() if start <= day <= end))
        if expected:
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
                chunk = old
            else:
                print(f"{start}~{end}: {len(expected)}경기 조회", flush=True)
                text = fetch(SOURCE, {"all": "true", "type": "details", "player_type": "pitcher",
                                     "game_date_gt": str(start), "game_date_lt": str(end), "hfGT": "R|"}).text
                allowed = set().union(*(ids for day, ids in scheduled.items() if start <= day <= end))
                chunk = aggregate(text, start, end, expected, allowed)
                chunk["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                if old and chunk["pitches"] < old["pitches"] * .9:
                    raise ValueError("구간 투구 수 10% 초과 감소")
                write(path, chunk)
            chunks.append(chunk)
        start = end + timedelta(days=1)
    players = merge(chunks)
    games_count = len(set().union(*(set(c["games"]) for c in chunks)))
    if len(players) < min(100, games_count * 10):
        raise ValueError("시즌 선수 수 비정상")
    updated = max(c["updated"] for c in chunks)
    # 모든 구간을 검증한 뒤 화면용 버킷을 교체한다. 수집 실패 중에는 공개 파일을 건드리지 않는다.
    payload = {"season": season, "updated": updated, "through": str(last), "gameType": "R", "games": games_count,
               "checked": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "pitches": sum(c["pitches"] for c in chunks), "players": players}
    publish(payload)
    print(f"{season}: {len(players)}명, {payload['games']}경기, {payload['pitches']}구 저장", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--current-season", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    try:
        collect(datetime.now(timezone(timedelta(hours=9))).year if args.current_season else args.season, args.refresh)
    except (ValueError, requests.RequestException, KeyError, OSError) as error:
        print(f"위치 집계 실패 — 화면용 기존 파일 유지: {error}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
