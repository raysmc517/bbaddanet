"""MLB 구단 선수단 생성: python scripts/rosters.py [--current-season]

구단(MLB 30개)·시즌마다 data/rosters/{시즌}/{구단 ID}.json을 만든다 (화면이 구단 하나만 읽도록 나눈다). 다음을 담는다.
- players: 그 시즌 중 한 번이라도 구단 명단에 있었던 선수 전원(원본 fullSeason)과 그 구단에서 거둔 정규시즌 성적.
  시즌 중 이적한 선수는 이 구단 기록만 들어간다. 명단에 없지만 기록이 있는 선수도 기록에서 채운다.
- moves: 그해 1~12월의 MLB 선수 이동(콜업, 강등, IL, 트레이드 등). 마이너리그 배정·등번호 변경 등은 뺀다.
- current: 최근 시즌 파일에만 있다. 기준일의 40인 명단(원본 40Man, 상태 포함). 원본 40인 명단은 60일 IL 선수도 포함한다.
  액티브 로스터(26인, 9월부터 28인)는 정규시즌·포스트시즌에만 있으므로 시즌 단계(phase)를 함께 저장한다.

요청: 시즌마다 구단 목록 1회 + 구단별 4회(명단, 타격, 투구, 이동), 최근 시즌은 일정 1회 + 구단별 40인 명단 1회를 더 받는다.
한 구단이라도 실패하거나 명단이 비정상이면 그 시즌의 파일을 하나도 바꾸지 않는다.
"""

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from careers import write
from collectors import statsapi

DATA = Path(__file__).resolve().parent.parent / "data"
SEASONS = [2026, 2025, 2024]  # build.py의 SEASONS와 같게 유지한다
MLB_CLUBS = 30
MIN_ROSTER, MAX_ROSTER = 20, 50  # 40인 명단(60일 IL 포함) 크기의 상식적인 범위
MIN_SEASON, MAX_SEASON = 26, 90  # 시즌 중 명단에 있었던 선수 수의 상식적인 범위


def season_phase(day, dates):
    """날짜(YYYY-MM-DD)의 시즌 단계: spring, regular, postseason, offseason.
    원본에 날짜가 없으면 offseason으로 본다 (액티브 로스터를 만들지 않는 쪽이 안전하다)."""
    spring, start, end, post = (dates.get(key) for key in ("springStart", "regularStart", "regularEnd", "postEnd"))
    if start and end and start <= day <= end:
        return "regular"
    if end and post and end < day <= post:
        return "postseason"
    if spring and start and spring <= day < start:
        return "spring"
    return "offseason"


def number_order(row):
    """등번호순(없으면 뒤), 같은 번호는 이름순."""
    number = row["num"]
    return (0, int(number), row["name"]) if number.isdigit() else (1, 0, row["name"])


def clean_rows(rows, has_page):
    """원본 명단 → 저장할 행 (등번호순, 선수 페이지 여부). 순수 함수라 따로 검증할 수 있다."""
    return [dict(row, page=1 if has_page(row["id"]) else 0) for row in sorted(rows, key=number_order)]


def season_rows(roster, batting, pitching, has_page):
    """시즌 명단 + 구단 성적 → 시즌 선수단 행. 순수 함수라 따로 검증할 수 있다.

    상태(status)는 시즌 이후 값이라 시즌 선수단에서는 쓰지 않는다. 기록이 없는 항목은 None이다.
    명단에 없는데 기록이 있는 선수(원본 누락)는 기록의 이름·포지션으로 채운다.
    """
    keep = ("id", "name", "num", "pos", "posType", "bats", "throws", "birthDate")
    rows = {row["id"]: {key: row[key] for key in keep} for row in roster}
    for stats in (batting, pitching):
        for player_id, stat in stats.items():
            if player_id not in rows:
                rows[player_id] = {
                    "id": player_id, "name": stat["name"], "num": "", "pos": stat["pos"],
                    "posType": "Pitcher" if stat["pos"] == "P" else "", "bats": "", "throws": "", "birthDate": None,
                }
    result = []
    for row in sorted(rows.values(), key=number_order):
        bat = batting.get(row["id"])
        pit = pitching.get(row["id"])
        row["bat"] = {key: value for key, value in bat.items() if key not in ("name", "pos")} if bat else None
        row["pit"] = {key: value for key, value in pit.items() if key not in ("name", "pos")} if pit else None
        row["page"] = 1 if has_page(row["id"]) else 0
        result.append(row)
    return result


# ---------- 선수 이동 ----------
IL_DAYS = re.compile(r"(\d+)-day injured list")
RETRO = re.compile(r"retroactive to ([A-Z][a-z]+ \d{1,2}, \d{4})")
MONTHS = {name: index for index, name in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], 1)}


def _iso(text):
    """'March 24, 2025' → '2025-03-24'. 형식이 다르면 None."""
    try:
        month, day, year = text.replace(",", "").split()
        return f"{int(year):04d}-{MONTHS[month]:02d}-{int(day):02d}"
    except (KeyError, ValueError):
        return None


def classify_move(tx, team_id):
    """원본 이동 기록 하나 → 화면에 보일 행 또는 None. 순수 함수라 따로 검증할 수 있다.

    type: up(콜업: 리콜), select(콜업: 계약 선택), option(옵션 강등), outright(아웃라이트), dfa(양도지명),
          il_on(IL 등록), il_off(IL 복귀), il_move(IL 이동), leave_on/leave_off(출산휴가·경조사 명단),
          trade_in/trade_out(트레이드), claim_in/claim_out(웨이버 클레임), sign(메이저 계약 FA 영입),
          release(방출), fa(FA 선언)
    마이너리그 배정, 등번호 변경, 마이너 계약, 내용이 모호한 상태 변경은 넣지 않는다.
    """
    person = tx.get("person") or {}
    if not person.get("id"):
        return None  # 트레이드 요약 행 등 선수가 없는 기록
    code = tx.get("typeCode")
    text = tx.get("description") or ""
    lower = text.lower()
    from_team = tx.get("fromTeam") or {}
    to_team = tx.get("toTeam") or {}
    other = None
    kind = None
    extra = {}

    if code == "CU":
        kind, other = "up", from_team
    elif code == "SE":
        kind, other = "select", from_team
    elif code == "OPT":
        kind, other = "option", to_team
    elif code == "OUT":
        kind, other = "outright", to_team
    elif code == "DES":
        kind = "dfa"
    elif code == "SC" and "injured list" in lower:
        if " placed " in f" {lower}":
            kind = "il_on"
        elif "transferred" in lower:
            kind = "il_move"
        elif "activated" in lower:
            kind = "il_off"
        days = IL_DAYS.findall(text)
        if days:
            extra["days"] = int(days[-1])  # 이동은 마지막(옮겨 간) 명단
        retro = RETRO.search(text)
        if retro and _iso(retro.group(1)):
            extra["retro"] = _iso(retro.group(1))
        if kind in ("il_on", "il_move"):
            # 부상 내용은 문장 끝의 원문 ("... injured list. Left hamstring strain.")
            tail = text.split("injured list", 1)[1]
            note = tail.split(".", 1)[1].strip() if "." in tail else ""
            if note:
                extra["note"] = note.rstrip(".")
    elif code == "SC" and ("paternity list" in lower or "bereavement list" in lower):
        kind = "leave_on" if "placed" in lower else "leave_off" if "activated" in lower else None
        extra["list"] = "paternity" if "paternity" in lower else "bereavement"
    elif code == "TR":
        kind = "trade_in" if to_team.get("id") == team_id else "trade_out"
        other = from_team if kind == "trade_in" else to_team
    elif code == "CLW":
        kind = "claim_in" if to_team.get("id") == team_id else "claim_out"
        other = from_team if kind == "claim_in" else to_team
    elif code == "SFA" and "minor league contract" not in lower:
        kind = "sign"
    elif code == "REL":
        kind = "release"
    elif code == "DFA":
        kind = "fa"
    if not kind:
        return None

    row = {
        "date": tx.get("effectiveDate") or tx.get("date"),
        "type": kind,
        "id": person["id"],
        "name": person.get("fullName", ""),
        "desc": text,
    }
    if other and other.get("id") and other.get("id") != team_id:
        row["team"] = {"id": other["id"], "name": other.get("name", "")}
    row.update(extra)
    return row


def season_moves(transactions, team_id, has_page):
    """원본 이동 기록 → 최신순 행 목록. 같은 기록(같은 ID·선수)은 한 번만."""
    seen = set()
    rows = []
    for tx in transactions:
        row = classify_move(tx, team_id)
        if not row:
            continue
        key = (tx.get("id"), row["id"], row["type"])
        if key in seen:
            continue
        seen.add(key)
        row["page"] = 1 if has_page(row["id"]) else 0
        rows.append(row)
    rows.sort(key=lambda row: (row["date"] or "", row["name"]), reverse=True)
    return rows


def check_size(name, rows, low, high):
    if not low <= len(rows) <= high:
        raise ValueError(f"{name} 명단 인원이 비정상: {len(rows)}명")


def check_roster(name, rows):
    check_size(name, rows, MIN_ROSTER, MAX_ROSTER)


def collect_season(season, snapshot_day, has_page):
    """시즌 하나의 파일 내용. snapshot_day가 있으면 그날의 40인 명단도 담는다."""
    directory = statsapi.fetch_team_directory(1, season)
    if len(directory) != MLB_CLUBS:
        raise ValueError(f"{season} MLB 구단 수가 {MLB_CLUBS}개가 아님: {len(directory)}")
    payload = {"season": season}
    if snapshot_day:
        dates = statsapi.fetch_season_dates(int(snapshot_day[:4]))
        payload.update({"date": snapshot_day, "phase": season_phase(snapshot_day, dates)})
    clubs = {}
    for club in directory:
        roster = statsapi.fetch_roster(club["id"], season=season, roster_type="fullSeason")
        batting = statsapi.fetch_team_season_stats(club["id"], season, "hitting")
        pitching = statsapi.fetch_team_season_stats(club["id"], season, "pitching")
        rows = season_rows(roster, batting, pitching, has_page)
        check_size(f"{season} {club['name']} 시즌", rows, MIN_SEASON, MAX_SEASON)
        moves = season_moves(statsapi.fetch_transactions(club["id"], f"{season}-01-01", f"{season}-12-31"), club["id"], has_page)
        entry = {"players": rows, "moves": moves}
        if snapshot_day:
            current = statsapi.fetch_roster(club["id"], date=snapshot_day)
            check_roster(f"{club['name']} 40인", current)
            entry["current"] = clean_rows(current, has_page)
        clubs[str(club["id"])] = entry
        print(f"  {club['abbr']}: 시즌 {len(rows)}명, 이동 {len(moves)}건" + (f", 40인 명단 {len(entry['current'])}명" if snapshot_day else ""), flush=True)
    payload["clubs"] = clubs
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-season", action="store_true", help=f"{SEASONS[0]} 시즌만 받는다 (일일 갱신)")
    parser.add_argument("--season", type=int, action="append", help="받을 시즌 (여러 번 지정 가능)")
    parser.add_argument("--date", help="40인 명단 기준 날짜 YYYY-MM-DD (기본: 오늘, UTC)")
    args = parser.parse_args()
    seasons = args.season or (SEASONS[:1] if args.current_season else SEASONS)
    today = args.date or datetime.now(timezone.utc).date().isoformat()

    players = DATA / "players"
    has_page = lambda player_id: (players / f"{player_id}.json").exists()
    failed = 0
    for season in seasons:
        print(f"{season} 선수단", flush=True)
        try:
            # 기준일의 40인 명단은 최근 시즌 파일에만 담는다
            payload = collect_season(season, today if season == SEASONS[0] else None, has_page)
        except Exception as error:
            print(f"[실패] {season} 선수단: {error} (기존 파일 유지)", file=sys.stderr)
            failed += 1
            continue
        updated = datetime.now(timezone.utc).isoformat(timespec="seconds")
        meta = {key: value for key, value in payload.items() if key != "clubs"}
        for club_id, entry in payload["clubs"].items():
            write(DATA / "rosters" / str(season) / f"{club_id}.json", dict(meta, team=int(club_id), updated=updated, **entry))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
