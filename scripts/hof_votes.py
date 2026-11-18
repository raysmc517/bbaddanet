"""명예의 전당 선출 방식·득표율·투표 차수 생성: python scripts/hof_votes.py

MLB Stats API에는 명예의 전당 득표율이 없으므로 위키백과 공개 문서(CC BY-SA)에서 사실 자료만 가져온다.
- 회원 목록(List of members of the National Baseball Hall of Fame): 헌액 연도, 선출 방식(BBWAA·위원회), 득표율
- 연도별 투표 결과(YYYY Baseball Hall of Fame balloting): 기자단 득표수, 몇 번째 투표인지(표에 있는 연도만)
요청은 위키백과 API로 회원 목록 1회 + 기자단 선출 연도 수만큼(약 60회)이며 1.5초 간격을 둔다.

선수는 data/awards.json의 명예의 전당 행(헌액 연도 + 이름)과 맞춰 MLB 선수 ID로 저장한다.
이름이 맞지 않는 사람은 넣지 않고 목록을 출력한다 (이름만으로 다른 사람을 합치지 않기 위해 같은 연도 안에서만 맞춘다).
회원 목록을 받지 못하거나 맞춘 사람이 너무 적으면 기존 파일을 그대로 둔다.
선출 발표(1월 기자단, 12월 위원회) 뒤에 awards.py → hof_votes.py 순서로 실행한다.
"""

import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests

from careers import write

DATA = Path(__file__).resolve().parent.parent / "data"
API = "https://en.wikipedia.org/w/api.php"
MEMBERS_PAGE = "List_of_members_of_the_National_Baseball_Hall_of_Fame"
BALLOT_PAGE = "{year}_Baseball_Hall_of_Fame_balloting"
WIKI = "https://en.wikipedia.org/wiki/"
HEADERS = {"User-Agent": "bbaddanet-portfolio/1.0 (non-commercial baseball stats project)"}
MIN_MATCHED = 200  # 회원 목록과 맞춘 선수 수가 이보다 적으면 원본 형식이 바뀐 것으로 보고 저장하지 않는다

_session = requests.Session()


def fetch_wikitext(page):
    """위키백과 문서 원문. 없는 문서면 None."""
    for attempt in range(4):
        try:
            res = _session.get(API, params={
                "action": "parse", "page": page, "prop": "wikitext", "format": "json", "formatversion": 2,
            }, headers=HEADERS, timeout=30)
            res.raise_for_status()
            time.sleep(1.5)  # 위키백과 요청 제한을 피하려고 간격을 둔다
            data = res.json()
            if "error" in data:
                return None
            return data["parse"]["wikitext"]
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))  # 요청 제한(429)에 걸리면 간격을 늘려 다시 시도한다
    raise RuntimeError(f"위키백과 요청 실패: {page}")


# ---------- 원문 정리 ----------

def plain_name(text):
    """표 칸의 위키 문법 → 이름. {{sortname|First|Last}}, [[문서|표시]], 굵게·기울임, 각주를 정리한다."""
    text = re.sub(r"<ref[^>]*?/>|<ref.*?</ref>", "", text, flags=re.S)
    sort = re.search(r"\{\{sortname\|([^|}]*)\|([^|}]*)", text)
    if sort:
        return (sort.group(1) + " " + sort.group(2)).strip()
    link = re.search(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", text)
    if link:
        text = link.group(1)
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    return re.sub(r"'{2,}", "", text).strip(" |")


SUFFIX = re.compile(r"\s+(jr\.?|sr\.?|ii|iii|iv)$", re.I)


def norm(name):
    """이름 비교용: 악센트·기호와 Jr./Sr. 같은 꼬리를 빼고 소문자로. 'Nolan Ryan Jr.' → 'nolanryan'"""
    text = unicodedata.normalize("NFD", name or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", SUFFIX.sub("", text.strip()).lower())


def last_name(name):
    words = SUFFIX.sub("", (name or "").strip()).split()
    return norm(words[-1]) if words else ""


def to_float(text):
    match = re.search(r"(\d+(?:\.\d+)?)\s*%?", text or "")
    return float(match.group(1)) if match else None


def ballot_number(text):
    """'{{sort|10|10th}}', '1st' → 10, 1. 없으면 None."""
    match = re.search(r"(\d+)(?:st|nd|rd|th)", text or "")
    return int(match.group(1)) if match else None


# ---------- 회원 목록 ----------

def parse_members(wikitext):
    """회원 목록 원문 → [{"year", "name", "method", "pct"}]. 순수 함수라 따로 검증할 수 있다.

    표 한 행: |[[YYYY Baseball Hall of Fame balloting|YYYY]] / !scope="row"|이름 / |포지션||구단||경력||방식||득표율
    """
    members = []
    for row in re.split(r"\n\|-", wikitext):
        year = re.search(r"\[\[(\d{4}) Baseball Hall of Fame balloting\|", row)
        name = re.search(r'!\s*scope="row"\s*\|(.+)', row)
        if not year or not name:
            continue
        lines = [line for line in row.split("\n") if line.startswith("|") and "||" in line]
        if not lines:
            continue
        cells = [cell.strip() for cell in lines[0].lstrip("|").split("||")]
        if len(cells) < 5:
            continue
        method = re.sub(r"<br\s*/?>", " ", cells[3]).strip()
        pct_cell = cells[4].split("|")[-1]
        committee_dash = "—" in cells[4]  # 위원회 선출 등 득표율이 없는 칸 (각주 번호를 득표율로 읽지 않게)
        members.append({
            "year": int(year.group(1)),
            "name": plain_name(name.group(1)),
            "method": re.sub(r"\s+", " ", re.sub(r"[\[\]]", "", method)),
            "pct": None if committee_dash else to_float(pct_cell),
        })
    return members


# ---------- 연도별 기자단 투표 ----------

def parse_ballot(wikitext):
    """연도별 투표 결과 원문 → {정규화 이름: {"votes", "pct", "ballot"}}. 순수 함수라 따로 검증할 수 있다.

    Votes·Percent 열이 있는 표를 모두 읽는다. 투표 차수(Year) 열은 있는 표에서만 채운다.
    같은 사람이 여러 표(본 투표·결선 투표)에 있으면 처음 나온 값을 쓴다.
    """
    result = {}
    for table in re.findall(r"\{\|.*?\n\|\}", wikitext, flags=re.S):
        header_cells = []
        for line in table.split("\n"):
            if line.startswith("!"):
                header_cells += [cell.split("|")[-1].strip() for cell in line.lstrip("!").split("!!")]
        headers = [re.sub(r"[^a-z ]", "", cell.lower()).strip() for cell in header_cells]
        # 머리글은 연도마다 조금씩 다르다 ("Player", "Player name", "Votes", "Votes received", "Percent", "Year"...)
        index = {}
        for name in ("player", "votes", "percent", "year"):
            found = [i for i, header in enumerate(headers) if header.startswith(name)]
            if found:
                index[name] = found[0]
        if "player" not in index or "votes" not in index:
            continue
        for row in re.split(r"\n\|-", table)[1:]:
            cells = []
            for line in row.split("\n"):
                if line.startswith("|") and not line.startswith("|}") and not line.startswith("|+"):
                    cells += [cell for cell in line[1:].split("||")]
            # 칸 서식(align=..., style=...)을 떼어낸다
            cells = [cell.split("|", 1)[1] if re.match(r"\s*(align|style|data-sort|bgcolor)", cell) and "|" in cell else cell
                     for cell in cells]
            if len(cells) <= index.get("votes", 0):
                continue
            name = norm(plain_name(cells[index["player"]]))
            if not name or name in result:
                continue
            result[name] = {
                "votes": int(v) if (v := re.sub(r"\D", "", cells[index["votes"]])) else None,
                "pct": to_float(cells[index["percent"]]) if "percent" in index and len(cells) > index["percent"] else None,
                "ballot": ballot_number(cells[index["year"]]) if "year" in index and len(cells) > index["year"] else None,
            }
    return result


def match(members, hof_rows, people):
    """회원 목록 + awards.json의 명예의 전당 행 → ({선수 ID: 회원}, 맞추지 못한 회원). 순수 함수라 따로 검증할 수 있다.

    같은 헌액 연도 안에서 전체 이름이 같으면 맞추고, 아니면 성(마지막 단어)이 그 연도에 한 명뿐일 때만 맞춘다.
    그래도 없으면 앞뒤 1년에서 전체 이름이 같은 사람만 맞춘다 (12월 위원회 선출자는 MLB가 선출 연도,
    위키백과가 이듬해 헌액 연도로 적는다. 예: 2021년 12월 선출 Gil Hodges → 위키백과 2022).
    """
    by_year = {}
    for row in hof_rows:
        by_year.setdefault(row[1], []).append((row[3], people.get(str(row[3]), [""])[0]))
    matched, missing = {}, []
    for member in members:
        candidates = by_year.get(member["year"], [])
        key = norm(member["name"])
        found = [pid for pid, name in candidates if norm(name) == key]
        if not found:
            last = last_name(member["name"])
            same_last = [pid for pid, name in candidates if name and last_name(name) == last]
            found = same_last if len(same_last) == 1 else []
        if not found:
            nearby = by_year.get(member["year"] - 1, []) + by_year.get(member["year"] + 1, [])
            found = [pid for pid, name in nearby if norm(name) == key]
        if len(found) == 1 and str(found[0]) not in matched:
            matched[str(found[0])] = member
        else:
            missing.append(member)
    return matched, missing


def main():
    awards_path = DATA / "awards.json"
    if not awards_path.exists():
        print("[실패] data/awards.json이 없음 (awards.py를 먼저 실행)", file=sys.stderr)
        return 1
    awards = json.loads(awards_path.read_text(encoding="utf-8"))
    hof_rows = [row for row in awards["rows"] if row[0] == "hof"]
    try:
        members = parse_members(fetch_wikitext(MEMBERS_PAGE) or "")
        matched, missing = match(members, hof_rows, awards["people"])
        if len(matched) < MIN_MATCHED:
            raise ValueError(f"맞춘 회원이 {len(matched)}명뿐 (원본 형식 변경 의심)")
        years = sorted({m["year"] for m in matched.values() if m["method"] == "BBWAA"})
    except Exception as error:
        print(f"[실패] 명예의 전당 투표: {error} (기존 파일 유지)", file=sys.stderr)
        return 1

    # 연도별 문서가 실패하면 그 연도만 득표수·투표 차수를 비워 둔다 (득표율은 회원 목록에 있다)
    ballots, failed_years = {}, []
    for year in years:
        try:
            ballots[year] = parse_ballot(fetch_wikitext(BALLOT_PAGE.format(year=year)) or "")
        except Exception:
            failed_years.append(year)
    if failed_years:
        print(f"[알림] 연도별 투표 문서를 받지 못해 득표수·투표 차수를 비운 연도: {failed_years}", file=sys.stderr)

    # 받지 못한 연도는 이전 파일의 득표수·투표 차수를 그대로 쓴다 (요청 제한으로 매번 다른 연도가 빠질 수 있다)
    old_path = DATA / "hof_votes.json"
    previous = json.loads(old_path.read_text(encoding="utf-8")).get("players", {}) if old_path.exists() else {}

    result = {}
    for pid, member in matched.items():
        entry = {"year": member["year"], "method": member["method"], "pct": member["pct"], "votes": None, "ballot": None}
        if member["method"] == "BBWAA":
            detail = ballots.get(member["year"], {}).get(norm(member["name"]))
            if detail is None and member["year"] in failed_years and pid in previous:
                detail = previous[pid]
            if detail:
                entry["votes"] = detail["votes"]
                entry["ballot"] = detail["ballot"]
                if entry["pct"] is None:
                    entry["pct"] = detail["pct"]
        result[pid] = entry
    write(DATA / "hof_votes.json", {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {"members": WIKI + MEMBERS_PAGE, "ballot": WIKI + BALLOT_PAGE},
        "players": dict(sorted(result.items(), key=lambda item: int(item[0]))),
    })
    bbwaa = [e for e in result.values() if e["method"] == "BBWAA"]
    print(f"명예의 전당 {len(result)}명 저장 (기자단 {len(bbwaa)}명, 투표 차수 확인 {sum(1 for e in bbwaa if e['ballot'])}명)")
    if missing:
        print(f"[알림] 선수 ID와 맞추지 못한 회원 {len(missing)}명 (감독·임원 등 포함): " +
              ", ".join(f"{m['year']} {m['name']}" for m in missing[:40]) + (" ..." if len(missing) > 40 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
