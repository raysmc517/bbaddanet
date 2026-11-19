"""Cot's 30개 구단의 공개 계약 사실 수집. 본문을 저장하지 않는다.

python scripts/contract_sources.py [--team PHI | --cached]
수동 자료는 contracts_manual.json, 구단별 사실 캐시는 contracts_sources/. 실패 시 이전 캐시 유지.
"""
import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests

from careers import write
from contracts import validate

DATA = Path(__file__).resolve().parent.parent / "data"
BASE = "https://legacy.baseballprospectus.com/compensation/cots/"


class Node:
    def __init__(self, tag="", attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        return "".join(c if isinstance(c, str) else "|" if c.tag == "br" else c.text() for c in self.children)

    def descendants(self, tag):
        for child in self.children:
            if isinstance(child, Node):
                if child.tag == tag:
                    yield child
                yield from child.descendants(tag)


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        node.parent = self.stack[-1]
        self.stack[-1].children.append(node)
        if tag not in ("br", "img", "meta", "link", "hr", "input", "wbr", "source"):
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def normalize(name):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower())


def dollars(amount, suffix=""):
    return int(Decimal(amount.replace(",", "")) * {"M": 1000000, "K": 1000, "": 1}[suffix.upper()])


def parse(html):
    root = Page(html).root
    result = []
    for p in root.descendants("p"):
        text = " ".join(p.text().split())
        match = re.fullmatch(r"(.+?)\s+(rhp|lhp|[a-z0-9/-]+)\s*\|\s*(\d+) years?(?:/\$([\d.,]+)([MK]?))?\s*\((\d{4})(?:[-–](\d{2,4}))?\)(.*?)(?:\|)?", text)
        if not match or match[2] not in ("rhp", "lhp", "c", "1b", "2b", "3b", "ss", "lf", "cf", "rf", "of", "dh", "inf", "of-ss", "1b-of", "inf-of"):
            continue
        name, pos, years, amount, suffix, first, last, tail = match.groups()
        first = int(first)
        last = int(last) if last and len(last) == 4 else first // 100 * 100 + int(last) if last else first
        if last - first + 1 != int(years):
            continue
        result.append({"name": name.strip(), "position": pos, "from": first, "to": last,
                       "totalUSD": dollars(amount, suffix) if amount else None,
                       "hasOptions": bool(re.search(r"option", tail, re.I))})
        siblings = p.parent.children
        following = [s for s in siblings[siblings.index(p) + 1:] if isinstance(s, Node)]
        if following and following[0].tag == "ul":
            entries = [s for s in following[0].children if isinstance(s, Node) and s.tag == "li"]
            if entries:
                entry = entries[0]
                heading = "".join(s if isinstance(s, str) else s.text() for s in entry.children if not isinstance(s, Node) or s.tag != "ul")
                # 같은 기간의 첫 계약만 읽어 과거 계약과 혼동하지 않는다.
                if re.search(r"\(" + str(first) + r"(?:[-–]" + str(last)[-2:] + r"|[-–]" + str(last) + r")?\)", heading):
                    salaries = []
                    for li in entry.descendants("li"):
                        line = " ".join(li.text().split())
                        # 조건·옵션·상향 조정 등이 포함된 행은 추정하지 않는다.
                        token = r"(\d{2})(?:[-–](\d{2}))?\s*:\s*\$([\d.,]+)([MK]?)"
                        matches = list(re.finditer(token, line))
                        rest = re.sub(token, "", line).strip(" ,;")
                        if matches and not rest:
                            for m in matches:
                                a, b = 2000 + int(m[1]), 2000 + int(m[2] or m[1])
                                if first <= a <= b <= last:
                                    salaries.append({"from": a, "to": b, "baseUSD": dollars(m[3], m[4])})
                    if salaries and len({y for s in salaries for y in range(s["from"], s["to"] + 1)}) == sum(s["to"] - s["from"] + 1 for s in salaries):
                        result[-1]["salaries"] = salaries
    if len(result) < 15:
        raise ValueError("선수 계약 표제 부족/잘못된 응답")
    return result


def team_links(html, clubs):
    names = {normalize(c["name"]): c for c in clubs}
    links = {}
    for a in Page(html).root.descendants("a"):
        key = normalize(a.text())
        if key in names:
            url = urljoin(BASE, a.attrs.get("href", ""))
            if url.startswith(BASE):
                links[names[key]["abbr"]] = url
    if len(links) != 30:
        raise ValueError(f"구단 링크 {len(links)}개, 30개 필요")
    return links


def identities():
    index = json.loads((DATA / "search.json").read_text(encoding="utf-8"))["players"]
    names = {}
    for row in index:
        names.setdefault(normalize(row[1]), []).append((str(row[0]), row[1], row[2]))
    membership = {}
    for path in (DATA / "rosters").glob("*/*.json"):
        roster = json.loads(path.read_text(encoding="utf-8"))
        for player in roster.get("players", []) + roster.get("current", []):
            membership.setdefault(str(player["id"]), set()).add(roster["team"])
    moves_path = DATA / "player_moves.json"
    if moves_path.exists():
        moves = json.loads(moves_path.read_text(encoding="utf-8"))
        for pid, rows in moves.items():
            for row in rows:
                for key in ("from", "to"):
                    if isinstance(row.get(key), int):
                        membership.setdefault(pid, set()).add(row[key])
    return names, membership


def assemble(clubs):
    names, membership = identities()
    manual = json.loads((DATA / "contracts_manual.json").read_text(encoding="utf-8"))
    players = manual["players"]
    manual_ids = set(players)
    unmatched, imported, covered = [], 0, []
    for club in clubs:
        path = DATA / "contracts_sources" / f"{club['abbr']}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        covered.append(club["abbr"])
        for item in payload["players"]:
            candidates = names.get(normalize(item["name"]), [])
            pitching = item["position"] in ("rhp", "lhp")
            candidates = [c for c in candidates if (c[2] == "P") == pitching]
            # 이름만으로 연결하지 않는다. 같은 구단 선수단 ID 또는 선수 파일의 MLB 구단 경력을 함께 확인.
            verified = []
            for candidate in candidates:
                pid = candidate[0]
                if club["id"] in membership.get(pid, set()):
                    verified.append(candidate)
                    continue
                profile_path = DATA / "players" / f"{pid}.json"
                if profile_path.exists():
                    profile = json.loads(profile_path.read_text(encoding="utf-8"))
                    history = profile.get("batting", []) + profile.get("pitching", [])
                    if profile.get("team") == club["name"] or any(r.get("league") == "mlb" and r.get("team") == club["abbr"] for r in history):
                        verified.append(candidate)
            if len(verified) != 1:
                unmatched.append({"team": club["abbr"], "name": item["name"], "reason": "MLB ID·구단·포지션 연결 미확인"})
                continue
            pid, name, _ = verified[0]
            if pid in manual_ids:
                continue  # 수동으로 확인한 세부·정정 자료를 우선한다.
            record = {"name": name, "team": club["abbr"], "listedTeam": True, "from": item["from"], "to": item["to"],
                      "totalUSD": item["totalUSD"], "amountUnknown": item["totalUSD"] is None,
                      "source": payload["source"], "sourceLabel": "Cot's Baseball Contracts / Baseball Prospectus",
                      "checked": payload["checked"], "note": "구단별 공개 계약 표제 기준. 분류 구단은 최초 계약 구단과 다를 수 있습니다. 연봉·이연·옵트아웃·성과급·행사된 옵션과 변경 조건은 원문을 확인하세요."}
            if item["hasOptions"]:
                record["note"] += " 별도 옵션이 있으며 표제 기간·금액에 임의로 더하지 않았습니다."
            if item.get("salaries"):
                record["salaries"] = item["salaries"]
                record["salaryNote"] = "원문의 조건 없는 연봉표 행에서 확인한 시즌만 표시합니다. 옵션·이연·상향 조정 등 조건이 붙은 행은 추정하지 않습니다."
            # 같은 계약이 전 소속 팀에도 남아 있을 때 중복하지 않는다.
            rows = players.setdefault(pid, [])
            if not any((r["from"], r["to"], r["totalUSD"]) == (record["from"], record["to"], record["totalUSD"]) for r in rows):
                rows.append(record)
                imported += 1
    for rows in players.values():
        rows.sort(key=lambda r: (-r["from"], -r["to"]))
    manual.update({"checked": date.today().isoformat(), "coverage": {"teams": covered, "importedContracts": imported, "unmatched": unmatched}, "scope": "출처를 확인한 수동 자료 우선 + Cot's MLB 구단별 공개 계약 표제. 미확인 금액·기본 연봉은 추정하지 않음."})
    errors = validate(manual, DATA)
    if errors:
        raise ValueError("; ".join(errors[:10]))
    return manual


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team")
    parser.add_argument("--cached", action="store_true", help="외부 요청 없이 사실 캐시로 합성")
    args = parser.parse_args(argv)
    clubs = json.loads((DATA / "teams.json").read_text(encoding="utf-8"))["clubs"]
    if args.team and args.team not in {c["abbr"] for c in clubs}:
        parser.error("알 수 없는 구단 약자")
    failed = 0
    if not args.cached:
        session = requests.Session()
        def get(url):
            response = session.get(url, timeout=60)
            response.raise_for_status()
            time.sleep(2)
            return response.text
        links = team_links(get(BASE), clubs)
        for club in clubs:
            if args.team and club["abbr"] != args.team:
                continue
            try:
                url = links[club["abbr"]]
                rows = parse(get(url))
                path = DATA / "contracts_sources" / f"{club['abbr']}.json"
                if path.exists() and len(rows) < len(json.loads(path.read_text(encoding="utf-8"))["players"]) * 0.8:
                    raise ValueError("계약 수 급감")
                write(path, {"source": url, "checked": date.today().isoformat(), "players": rows})
                print(f"{club['abbr']}: {len(rows)}명 저장", flush=True)
            except Exception as error:
                failed = 1
                print(f"[실패] {club['abbr']}: {error} (기존 캐시 유지)", file=sys.stderr, flush=True)
    payload = assemble(clubs)
    write(DATA / "contracts.json", payload)
    print(f"{len(payload['coverage']['teams'])}구단 · {len(payload['players'])}명 · 연결 미확인 {len(payload['coverage']['unmatched'])}건", flush=True)
    return failed


if __name__ == "__main__":
    sys.exit(main())
