"""MLB 타구·구종 시즌 집계: python scripts/statcast.py [--season 2025 | --current-season]

Baseball Savant 공개 리더보드 2회/시즌, 요청 사이 0.5초.
타구 CSV와 구종 페이지의 공개 JSON 집계만 읽고 HTML·본문·투구별 원본은 저장하지 않는다.
시즌 전체를 검증한 뒤에만 교체한다. 실패·빈 응답·다른 시즌·중복 ID는 기존 파일 유지.
"""
import argparse
import csv
import io
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from careers import write

DATA = Path(__file__).resolve().parent.parent / "data"
SEASONS = list(range(2026, 2014, -1))
BASE = "https://baseballsavant.mlb.com/leaderboard/"
# 넓은 fastball/breaking/offspeed 묶음은 포함하지 않는다(구종 사용률 중복 방지).
PITCH_TYPES = ("ff", "si", "fc", "sl", "st", "cu", "sv", "ch", "fs", "fo", "kn", "sc")
BAT_FIELDS = {"bbe": "attempts", "exitVelocity": "avg_hit_speed", "maxExitVelocity": "max_hit_speed",
              "launchAngle": "avg_hit_angle", "hardHitPct": "ev95percent", "barrelPct": "brl_percent",
              "sweetSpotPct": "anglesweetspotpercent"}
_session = requests.Session()


def number(value):
    if value is None or str(value).strip() in ("", "null", "-", "--", "N/A"):
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"유한하지 않은 숫자: {value}")
    return result


def integer(value):
    result = number(value)
    if result is None or result < 1 or not result.is_integer():
        raise ValueError(f"양의 정수 형식 오류: {value}")
    return int(result)


def batters(text):
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    required = {"player_id", *BAT_FIELDS.values()}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("타구 CSV 열 누락 또는 HTML 오류 응답")
    result = {}
    for row in reader:
        pid = str(integer(row["player_id"]))
        if pid in result:
            raise ValueError(f"타구 선수 중복: {pid}")
        item = {key: number(row[field]) for key, field in BAT_FIELDS.items()}
        item["bbe"] = integer(row["attempts"])
        for key in ("hardHitPct", "barrelPct", "sweetSpotPct"):
            if item[key] is not None and not 0 <= item[key] <= 100:
                raise ValueError(f"타구 비율 범위 오류: {pid} {key}")
        result[pid] = item
    if not result:
        raise ValueError("타구 기록 빈 응답")
    if not any(r["exitVelocity"] is not None and r["launchAngle"] is not None for r in result.values()):
        raise ValueError("타구 주요 지표가 모두 누락됨")
    return result


def pitchers(html, season):
    match = re.search(r"\bvar\s+data\s*=\s*", html)
    if not match:
        raise ValueError("공개 구종 JSON 집계 없음")
    rows, _ = json.JSONDecoder().raw_decode(html[match.end():])
    if not isinstance(rows, list) or not rows:
        raise ValueError("구종 기록 빈 응답")
    result = {}
    for row in rows:
        if int(row.get("sport_id", -1)) != 1 or int(row.get("year", -1)) != season:
            raise ValueError("요청과 다른 시즌/리그 구종 응답")
        pid = str(integer(row["pitcher"]))
        if any("n_" + code not in row or "n_" + code + "_formatted" not in row for code in PITCH_TYPES):
            raise ValueError("구종 사용률 열 누락")
        pitches = []
        for code in PITCH_TYPES:
            # FF 등의 내부 값은 %, 새 FO/SC는 0~1 비율이다. 화면용 formatted는 모두 %다.
            raw_usage = number(row["n_" + code])
            usage = number(row["n_" + code + "_formatted"])
            if usage is None:
                if raw_usage not in (None, 0):
                    raise ValueError("구종 표시용 백분율 누락")
                continue
            if usage == 0 and raw_usage in (None, 0):
                continue
            if not 0 <= usage <= 100:
                raise ValueError(f"구종 사용률 범위 오류: {pid}/{code}")
            fields = {"velocity": "avg_speed", "spin": "avg_spin", "horizontal": "avg_break_x", "ivb": "avg_break_z_induced"}
            if any(code + "_" + suffix not in row for suffix in fields.values()):
                raise ValueError("구종 지표 열 누락")
            item = {key: number(row[code + "_" + suffix]) for key, suffix in fields.items()}
            pitches.append({"type": code.upper(), "usagePct": usage, **item})
        # 반올림된 사용률 합이 100보다 작을 수 있다. 미분류 공을 추정해 채우지 않는다.
        if sum(p["usagePct"] for p in pitches) > 101:
            raise ValueError(f"구종 사용률 중복 또는 합계 오류: {pid}")
        if not pitches:
            continue  # 소수의 미분류/이퍼스 등 지원되지 않는 공만 던진 선수는 제외
        pitches.sort(key=lambda p: (-p["usagePct"], p["type"]))
        item = {"pitches": integer(row["n"]), "hand": row.get("pitch_hand"), "arsenal": pitches}
        if pid in result:
            previous = result[pid]
            hands = previous.get("handSplits", [previous])
            # Pat Venditte 등 양손 투수의 좌/우 행은 별개 표본이다. 반올림 비율로 합산하지 않는다.
            if item["hand"] not in ("L", "R") or any(h["hand"] not in ("L", "R") or h["hand"] == item["hand"] for h in hands):
                raise ValueError(f"구종 선수/투구 손 중복: {pid}")
            hands = sorted(hands + [item], key=lambda h: h["hand"])
            result[pid] = {"pitches": sum(h["pitches"] for h in hands), "hand": "S", "arsenal": [], "handSplits": hands}
        else:
            result[pid] = item
    if not result:
        raise ValueError("지원되는 구종 기록 없음")
    return result


def get(path, params):
    response = _session.get(BASE + path, params=params, timeout=60)
    response.raise_for_status()
    time.sleep(0.5)
    return response.text


def averages(batting, pitching):
    """반올림된 선수 집계의 표본 가중 근사. 실측 공별 평균/정확한 구종 수로 설명하지 않는다."""
    def weighted(rows, key):
        valid = [(row[key], weight) for row, weight in rows if row.get(key) is not None and weight > 0]
        denominator = sum(weight for _, weight in valid)
        return round(sum(value * weight for value, weight in valid) / denominator, 4) if denominator else None

    bat_rows = [(row, row["bbe"]) for row in batting.values()]
    bats = {key: weighted(bat_rows, key) for key in BAT_FIELDS if key not in ("bbe", "maxExitVelocity")}
    groups = {}
    for player in pitching.values():
        for part in player.get("handSplits", [player]):
            if part.get("hand") not in ("L", "R"):
                continue
            for pitch in part["arsenal"]:
                # 비율은 반올림 값: 가중치에만 쓰며 정확한 구종별 투구 수를 만들지 않는다.
                groups.setdefault(part["hand"] + ":" + pitch["type"], []).append((pitch, part["pitches"] * pitch["usagePct"] / 100))
    return {"method": "weighted-rounded-aggregates", "batters": bats,
            "pitchers": {group: {key: weighted(rows, key) for key in ("velocity", "spin", "horizontal", "ivb")} for group, rows in groups.items()}}


def collect(season):
    batting = batters(get("statcast", {"type": "batter", "year": season, "position": "", "team": "", "min": 1, "csv": "true"}))
    pitching = pitchers(get("pitch-arsenals", {"year": season, "type": "avg_speed", "min": 1}), season)
    # 일부만 잘린 응답이 정상 시즌 파일을 덮지 않도록 기존 선수 수와도 비교한다.
    path = DATA / "statcast" / f"{season}.json"
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        for key, new in (("batters", batting), ("pitchers", pitching)):
            if len(new) < len(old.get(key, {})) * 0.9:
                raise ValueError(f"{key} 선수 수 급감: 기존 파일 유지")
    return {"season": season, "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "gameType": "R", "batters": batting, "pitchers": pitching, "averages": averages(batting, pitching)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--season", type=int, choices=SEASONS)
    group.add_argument("--current-season", action="store_true")
    parser.add_argument("--from", dest="start", type=int, choices=SEASONS, help="수집 시작 시즌 (기본: 2015)")
    parser.add_argument("--to", dest="end", type=int, choices=SEASONS, help="수집 끝 시즌 (기본: 2026)")
    parser.add_argument("--refresh", action="store_true", help="이미 받은 완료 시즌도 다시 받는다")
    parser.add_argument("--averages-only", action="store_true", help="외부 요청 없이 저장된 시즌 집계로 비교 평균 재계산")
    args = parser.parse_args(argv)
    if (args.season or args.current_season) and (args.start is not None or args.end is not None):
        parser.error("--from/--to는 --season/--current-season과 함께 쓸 수 없습니다")
    if args.start is not None and args.end is not None and args.start > args.end:
        parser.error("시작 시즌은 끝 시즌보다 늦을 수 없습니다")
    seasons = [args.season] if args.season else [SEASONS[0]] if args.current_season else [
        s for s in SEASONS if (args.start is None or s >= args.start) and (args.end is None or s <= args.end)]
    failed = 0
    for season in seasons:
        if args.averages_only:
            path = DATA / "statcast" / f"{season}.json"
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["averages"] = averages(payload["batters"], payload["pitchers"])
                write(path, payload)  # 원본 갱신 시각은 유지
                print(f"{season}: 비교 평균 재계산", flush=True)
            continue
        if season != SEASONS[0] and not args.refresh and (DATA / "statcast" / f"{season}.json").exists():
            print(f"{season}: 이미 있음 (건너뜀)", flush=True)
            continue
        try:
            payload = collect(season)
            write(DATA / "statcast" / f"{season}.json", payload)
            print(f"{season}: 타구 {len(payload['batters'])}명, 구종 {len(payload['pitchers'])}명 저장", flush=True)
        except Exception as error:
            failed = 1
            print(f"[실패] {season} Statcast: {error} (기존 파일 유지)", file=sys.stderr, flush=True)
    folder = DATA / "statcast"
    saved = sorted([int(p.stem) for p in folder.glob("[0-9][0-9][0-9][0-9].json")], reverse=True)
    if saved:
        write(folder / "index.json", {"seasons": saved})
    return failed


if __name__ == "__main__":
    sys.exit(main())
