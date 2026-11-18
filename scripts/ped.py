"""금지약물 징계 기록 생성: python scripts/ped.py (2026-11-18 사용자 요구)

MLB Stats API의 이동 기록은 징계 선수를 "restricted list"로만 적고 사유를 주지 않는다(개인 사정·비자 문제도 같은 명단).
그래서 위키백과 "List of Major League Baseball players suspended for performance-enhancing drugs"(CC BY-SA)에서
MLB·마이너리그 공식 징계(약물 방지 프로그램에 따른 징계 발표)만 사실 자료로 가져온다. 요청 1회.
- 넣는 표: MLB 로스터 선수, MLB 경력이 있는 마이너리그·FA 선수, 마이너리그 경력만 있는 선수
- 넣지 않는 것: 독립리그·국제대회 징계, 미첼 보고서 등 징계 없이 이름만 거론된 선수(공식 징계가 아니므로)
선수 연결은 이름이 한 명에게만 맞고, 징계 연도가 그 선수의 프로 경력 기간 안에 있을 때만 한다(동명이인은 투수·야수로 한 번 더 거른다).
동명이인을 잘못 표시하지 않기 위해서이며, 맞추지 못한 이름은 출력만 한다.
결과: data/ped.json {선수 ID: [{date, team, penalty, drug}]}와 출처. 표를 읽지 못하면 기존 파일을 유지한다.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from careers import write
from hof_votes import fetch_wikitext, norm
from signings import clean, dts, first_season, name_keys, tables

DATA = Path(__file__).resolve().parent.parent / "data"
PAGE = "List_of_Major_League_Baseball_players_suspended_for_performance-enhancing_drugs"
SOURCE = "https://en.wikipedia.org/wiki/" + PAGE
SECTIONS = ["Players who were on major league rosters",
            "Players with major league experience on minor league rosters or free agents",
            "Players with only minor league experience"]
MIN_FOUND = 100  # 이보다 적게 맞추면 문서 형식이 바뀐 것으로 보고 저장하지 않는다


def section(wikitext, title):
    match = re.search(r"===\s*" + re.escape(title) + r"\s*===(.*?)(?=\n==)", wikitext, flags=re.S)
    return match.group(1) if match else ""


def parse_table(table):
    """rowspan을 펼친 행 목록 [{열 이름: 칸 원문}]"""
    header = [clean(h).lower() for h in re.findall(r'^!scope="col"[^|]*\|(.*)$', table, flags=re.M)]
    if not header:
        return []
    result, carry = [], {}  # carry: 열 번호 → [남은 행 수, 칸 원문]
    for chunk in table.split("\n|-")[1:]:
        raw = []
        for line in chunk.strip("\n").split("\n"):
            if line.startswith("!scope=\"col\"") or line.startswith("|}") or line.startswith("|+"):
                continue
            if line.startswith("!") or line.startswith("|"):
                raw.append(line[1:])
            elif raw:
                raw[-1] += "\n" + line
        if not raw:
            continue
        row, col = {}, 0
        for cell in raw:
            while col in carry:
                row[col] = carry[col][1]
                carry[col][0] -= 1
                if not carry[col][0]:
                    del carry[col]
                col += 1
            span = re.match(r'\s*(?:scope="row"\s*)?(?:style="[^"]*"\s*)?rowspan="?(\d+)"?[^|]*\|(.*)', cell, flags=re.S)
            if span:
                cell = span.group(2)
                if int(span.group(1)) > 1:
                    carry[col] = [int(span.group(1)) - 1, cell]
            row[col] = cell
            col += 1
        while col in carry:  # 줄 끝에 남은 합친 칸
            row[col] = carry[col][1]
            carry[col][0] -= 1
            if not carry[col][0]:
                del carry[col]
            col += 1
        result.append({header[i]: row.get(i, "") for i in range(len(header))})
    return result


def player_name(cell):
    match = re.search(r"\{\{[Ss]ortname\|([^|}]*)\|([^|}]*)", cell)
    if match:
        return (match.group(1) + " " + match.group(2)).strip()
    link = re.search(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", cell)
    return link.group(1).strip() if link else None


def tidy(cell):
    """칸 앞의 서식(style="..."|), {{#tag:ref|...}} 각주(중첩 괄호 포함), 정렬 틀, 표시 기호(^)를 지운 글자"""
    cell = re.sub(r'^\s*(?:[a-z]+="[^"]*"\s*)+\|', "", cell or "")
    while "{{#tag:ref" in cell:
        start = cell.index("{{#tag:ref")
        depth, i = 0, start
        while i < len(cell):
            if cell.startswith("{{", i):
                depth, i = depth + 1, i + 2
            elif cell.startswith("}}", i):
                depth, i = depth - 1, i + 2
                if not depth:
                    break
            else:
                i += 1
        cell = cell[:start] + cell[i:]
    cell = re.sub(r"\{\{sort\|[^|}]*\|([^}]*)\}\}", r"\1", cell)
    cell = re.sub(r"\{\{small\|(.*?)\}\}", r"\1", cell)
    return clean(cell).replace("^", "").strip() or None


def parse(wikitext):
    """징계 행 [{name, date, team, penalty, drug}]"""
    found = []
    for title in SECTIONS:
        for table in tables(section(wikitext, title)):
            for row in parse_table(table):
                name = player_name(row.get("player", ""))
                when = dts(row.get("date announced", ""))
                if not name or not when:
                    continue
                found.append({
                    "name": name, "date": when,
                    "team": tidy(row.get("team") or row.get("organization")),
                    "penalty": tidy(row.get("penalty")),
                    "drug": tidy(row.get("drug")),
                    "position": tidy(row.get("position")),
                })
    return found


def seasons(player):
    return {row["season"] for group in ("batting", "pitching") for row in player.get(group) or []}


def search_ids(name):
    """선수 파일의 이름과 다르게 적힌 경우(예: Mike Morse ↔ Michael Morse) MLB 선수 검색으로 후보 ID를 찾는다."""
    from collectors import statsapi
    try:
        return {p["id"] for p in statsapi._get("/people/search", {"names": name}).get("people", [])}
    except RuntimeError:
        return set()


def match(rows, players, search=search_ids):
    """징계 행 → {선수 ID: [징계]}, 맞추지 못한 이름"""
    by_name = {}
    for pid, p in players.items():
        by_name.setdefault(norm(p.get("name")), []).append(pid)
    result, missed = {}, []

    def active(pid, year):
        # 징계 연도가 그 선수의 프로 경력 기간(첫 시즌 ~ 마지막 시즌 다음 해) 안에 있어야 한다.
        # 부상·징계로 그해 기록이 없을 수 있어 그해 출전까지는 요구하지 않는다.
        played = seasons(players[pid])
        return bool(played) and min(played) <= year <= max(played) + 1

    def narrow(ids, row, year):
        ids = {pid for pid in ids if pid in players and active(pid, year)}
        if len(ids) > 1 and row.get("position"):  # 동명이인이면 투수·야수로 한 번 더 거른다
            pitcher = row["position"] == "P"
            ids = {pid for pid in ids if (players[pid].get("pos") in ("P", "TWP")) == pitcher}
        return ids

    for row in rows:
        year = int(row["date"][:4])
        # 'Ramón A. Castro'의 가운데 머리글자, 'Mike'·'Michael' 같은 흔한 줄임 이름도 같은 이름으로 본다
        name = re.sub(r"\s[A-Z]\.\s", " ", row["name"])
        keys = name_keys(name) | name_keys(re.sub(r"^Mike\b", "Michael", name))
        ids = narrow({pid for key in keys for pid in by_name.get(key, [])}, row, year)
        if not ids:
            ids = narrow(search(row["name"]), row, year)
        if len(ids) != 1:
            missed.append(f"{row['name']} ({row['date']}, 후보 {len(ids)}명)")
            continue
        pid = ids.pop()
        result.setdefault(pid, []).append({k: row[k] for k in ("date", "team", "penalty", "drug")})
    for items in result.values():
        items.sort(key=lambda item: item["date"])
    return result, missed


def main():
    players = {int(p.stem): json.loads(p.read_text(encoding="utf-8")) for p in (DATA / "players").glob("*.json")}
    rows = parse(fetch_wikitext(PAGE) or "")
    found, missed = match(rows, players)
    print(f"징계 행 {len(rows)}건, 선수 {len(found)}명 연결, 못 맞춘 행 {len(missed)}건")
    for line in missed:
        print("  못 맞춤:", line)
    if len(found) < MIN_FOUND:
        print("연결한 선수가 너무 적어 기존 파일을 유지한다", file=sys.stderr)
        sys.exit(1)
    write(DATA / "ped.json", {
        "source": SOURCE,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "players": {str(pid): items for pid, items in sorted(found.items())},
    })


if __name__ == "__main__":
    main()
