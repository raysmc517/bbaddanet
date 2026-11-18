"""지명 없이 입단한 선수의 첫 계약 경로 (recruitment.py가 사용, 2026-11-18)

1. 해외 프로 리그(NPB·KBO·CPBL) 출신: 위키백과 공개 문서(CC BY-SA)에서 사실 자료만 가져온다.
   - 포스팅: "Posting system"(NPB), "Posting system (KBO)"의 성공한 포스팅 표
     (포스팅 날짜, 전 소속팀, MLB 구단, 포스팅 금액, 계약 합의일, MLB 계약)
   - 포스팅이 아닌 이적(해외 FA 등): 일본·한국·대만 출신 MLB 선수 목록에 있고 포스팅 표에 없는 선수의
     위키백과 문서 정보 상자(teams)에서 MLB 데뷔 전 마지막 해외 프로 구단을 찾는다. 해외 프로 구단이 없으면
     (아마추어로 미국 구단과 계약) 넣지 않는다.
   요청은 목록 문서 5회 + 포스팅 아닌 선수 문서 수만큼이며 1.5초 간격이다.
2. 그 밖의 지명 없는 선수: MLB 공식 이동 기록(/transactions)의 첫 FA 계약(SFA)에서 날짜·구단을 읽는다.
   원본 이동 기록은 2009년 무렵부터 있으므로 프로 첫 시즌이 2009년 이후인 선수만 확인하고,
   계약 연도가 프로 첫 시즌보다 늦거나 2년 넘게 이르면 첫 계약이 아닌 것으로 보고 넣지 않는다.
   23세 미만의 마이너리그 계약은 국제 아마추어 계약, 나머지는 지명 없는 FA 계약으로 표시한다.
   계약금은 원본에 없어 넣지 않는다.

이름만으로 다른 사람을 합치지 않도록 위키백과 선수는 MLB.com 주소의 선수 ID를 먼저 쓰고,
없으면 출신 국가가 같은 선수 중 이름이 하나만 맞을 때만 연결한다.
"""

import re
from datetime import date
from time import sleep

from hof_votes import fetch_wikitext, norm

WIKI = "https://en.wikipedia.org/wiki/"
POSTING_PAGES = {"NPB": "Posting_system", "KBO": "Posting_system_(KBO)"}
LIST_PAGES = {
    "Japan": "List_of_Major_League_Baseball_players_from_Japan",
    "Korea": "List_of_Major_League_Baseball_players_from_South_Korea",
    "Taiwan": "List_of_Major_League_Baseball_players_from_Taiwan",
}
# 선수 파일의 출신 국가 표기 (원본이 전체 이름과 약자를 섞어 준다)
COUNTRIES = {"Japan": {"Japan", "JPN"}, "Korea": {"Republic of Korea", "South Korea", "Korea", "KOR"},
             "Taiwan": {"Taiwan", "TPE", "Chinese Taipei"}}
TRANSACTIONS_FROM = 2009  # 원본 이동 기록이 이 무렵부터 있다
AMATEUR_MAX_AGE = 23  # 이 나이 미만의 마이너리그 계약을 국제 아마추어 계약으로 본다

# 해외 프로 구단 이름 조각. KBO의 Lotte Giants와 NPB의 Lotte Marines처럼 겹치는 이름이 있어 KBO를 먼저 본다.
FOREIGN_TEAMS = [
    ("KBO", ["Lotte Giants", "Hanwha", "Binggrae", "Samsung Lions", "LG Twins", "MBC Blue Dragons", "Doosan", "OB Bears",
             "Kia Tigers", "KIA Tigers", "Haitai", "SK Wyverns", "SSG Landers", "Kiwoom", "Nexen", "Woori Heroes",
             "Hyundai Unicorns", "Pacific Dolphins", "Sammi", "Chungbo", "Ssangbangwool", "NC Dinos", "KT Wiz", "kt wiz"]),
    ("NPB", ["Yomiuri", "Hanshin", "Chunichi", "Yakult", "Kokutetsu", "Yokohama", "Taiyo", "Hiroshima", "Orix",
             "Hankyu", "Kintetsu", "Fukuoka", "Daiei", "Nankai", "SoftBank", "Nippon-Ham", "Nippon Ham", "Fighters",
             "Lotte Orions", "Chiba Lotte", "Lotte Marines", "Seibu", "Rakuten", "Pacific League", "Central League"]),
    ("CPBL", ["Brother Elephants", "CTBC Brothers", "Uni-President", "Uni-Lions", "Lamigo", "Rakuten Monkeys",
              "Fubon Guardians", "EDA Rhinos", "Sinon", "La New", "Wei Chuan", "TSG Hawks", "First Financial",
              "Chinatrust", "Mercuries Tigers", "China Times Eagles", "Koos Group", "Macoto", "Wei Chuan Dragons"]),
]


# ---------- 위키 문법 정리 ----------

def clean(text):
    """표 칸 → 글자. 각주, 숨긴 정렬 값, 링크, 틀, 줄바꿈 표시를 정리한다."""
    text = re.sub(r"<ref[^>]*?/>|<ref.*?</ref>", "", text or "", flags=re.S)
    text = re.sub(r'<span style="display:none">.*?</span>', "", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\{\{(?:ref|efn|sup|refn)[^}]*\}\}", "", text)
    text = text.replace("&nbsp;", " ").replace("&ndash;", "–")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip(" |")


def link_target(text):
    """[[문서|표시]] → 문서 이름"""
    match = re.search(r"\[\[([^|\]]+)", text or "")
    return match.group(1).strip() if match else None


def dts(text):
    """{{dts|2023|12|27}}, {{dts|December 27, 2023}} → '2023-12-27'. 날짜가 비면 None."""
    months = ["january", "february", "march", "april", "may", "june", "july", "august",
              "september", "october", "november", "december"]
    match = re.search(r"\{\{dts\|([^}]*)\}\}", text or "", re.I)
    if not match:
        # 틀 없이 'November 18, 2019'로 적은 칸 (최근 포스팅 행)
        plain = re.search(r"\b([A-Z][a-z]+)\s+(\d{1,2}),\s*(\d{4})\b", clean(text or ""))
        if plain and plain.group(1).lower() in months:
            return f"{plain.group(3)}-{months.index(plain.group(1).lower()) + 1:02d}-{int(plain.group(2)):02d}"
        return None
    parts = [p.strip() for p in match.group(1).split("|") if p.strip() and "=" not in p]
    if len(parts) == 1:  # 'December 27, 2023'
        found = re.match(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", parts[0])
        if not found or found.group(1).lower() not in months:
            return None
        return f"{found.group(3)}-{months.index(found.group(1).lower()) + 1:02d}-{int(found.group(2)):02d}"
    if len(parts) < 3 or not parts[0].isdigit():
        return None
    month = parts[1]
    month = months.index(month.lower()) + 1 if month.lower() in months else int(month) if month.isdigit() else None
    return f"{parts[0]}-{month:02d}-{int(parts[2]):02d}" if month and parts[2].isdigit() else None


def sortname(text):
    """{{sortname|First|Last|문서}} → (이름, 문서 이름). 없으면 (None, None)"""
    match = re.search(r"\{\{sortname\|([^|}]*)\|([^|}]*)(?:\|([^|}]*))?", text or "")
    if not match:
        return None, None
    name = (match.group(1) + " " + match.group(2)).strip()
    article = (match.group(3) or "").strip() or name
    return name, article


def contract_text(text):
    """'12 years, $325 million' → '12년 $325M', 'Minor league contract' → '마이너리그 계약'. 모르는 형식은 원문."""
    text = clean(text)
    if re.search(r"minor league", text, re.I):
        return "마이너리그 계약"
    found = re.match(r"(\d+)\s*years?,\s*\$([\d.,]+)\s*million", text, re.I)
    if found:
        return f"{found.group(1)}년 ${found.group(2)}M"
    return text or None


def split_cells(line):
    """'a || b !! c' → 칸들. 틀({{ }})과 링크([[ ]]) 안은 나누지 않는다."""
    parts, depth, start, i = [], 0, 0, 0
    while i < len(line):
        two = line[i:i + 2]
        if two in ("{{", "[["):
            depth += 1
            i += 2
        elif two in ("}}", "]]"):
            depth = max(0, depth - 1)
            i += 2
        elif depth == 0 and two in ("||", "!!"):
            parts.append(line[start:i])
            i += 2
            start = i
        else:
            i += 1
    parts.append(line[start:])
    return parts


def rows(table):
    """위키 표 → 행별 칸 목록. 행 머리(!scope=row)도 칸으로 넣는다."""
    result = []
    for chunk in table.split("\n|-")[1:]:
        cells = []
        for line in chunk.strip("\n").split("\n"):
            if line.startswith("!scope=\"col\"") or line.startswith("|+") or line.startswith("|}"):
                continue
            if line.startswith("!") or line.startswith("|"):
                # 한 줄에 '||'로 여러 칸을 쓰는 표(대만 목록)도 나눈다. {{dts|||}}처럼 틀 안의 '||'는 나누지 않는다.
                cells.extend(split_cells(line[1:]))
            elif cells:
                cells[-1] += "\n" + line
        if cells:
            result.append(cells)
    return result


def tables(wikitext):
    return re.findall(r"\{\|.*?\n\|\}", wikitext or "", flags=re.S)


# ---------- 포스팅 표 ----------

def parse_postings(wikitext, league):
    """성공한 포스팅 표 → [{name, article, league, postingDate, foreignTeam, team, fee, date, contract}]"""
    found = []
    for table in tables(wikitext):
        if "Successful postings" not in table:
            continue
        for cells in rows(table):
            name, article = sortname(cells[0])
            link = re.search(r"\[\[([^|\]]+)(?:\|([^\]]+))?\]\]", cells[0])
            if not name and link and "scope=\"row\"" in cells[0]:  # 정렬 틀 없이 링크만 쓴 행 (예: 김혜성)
                name, article = (link.group(2) or link.group(1)).strip(), link.group(1).strip()
            if not name or len(cells) < 7:
                continue
            found.append({
                "name": name, "article": article, "league": league,
                "postingDate": dts(cells[1]), "foreignTeam": clean(cells[2]), "team": clean(cells[3]),
                "fee": clean(cells[4]) or None, "date": dts(cells[5]), "contract": contract_text(cells[6]),
            })
    return found


# ---------- 출신 국가별 MLB 선수 목록 ----------

def parse_player_list(wikitext):
    """국가별 MLB 선수 목록 → [{name, article, id, posted, amateur}]. 같은 선수가 여러 표에 나오면 한 번만."""
    result, seen = [], set()
    head = re.split(r"\n==\s*Awards", wikitext or "")[0]  # 수상 표 등에 다시 나오는 이름은 빼고 선수 표만 본다
    for table in tables(head):
        for cells in rows(table):
            name, article = None, None
            for cell in cells[:3]:
                name, article = sortname(cell)
                if name:
                    break
            if not name or name in seen:
                continue
            seen.add(name)
            row = "\n".join(cells)
            mlb_id = re.search(r"mlb\.com/player/[a-z0-9-]*?-(\d{6})\b", row)
            first = cells[0]
            result.append({
                "name": name, "article": article, "id": int(mlb_id.group(1)) if mlb_id else None,
                "teams": [link for link in re.findall(r"\[\[([^|\]]+)", row)],
                # 일본 목록 표시: 하늘색·* 포스팅, 보라색·§ NPB를 거치지 않고 MLB 구단과 계약
                "posted": "#ccffff" in first or "}}*" in first,
                "amateur": "#ccccff" in first or "§" in first,
            })
    return result


# ---------- 선수 문서 정보 상자 ----------

def infobox_teams(wikitext):
    """정보 상자의 teams 칸 → [(구단 이름, 시작 연도)]. 감독·코치 경력은 뺀다."""
    match = re.search(r"\|\s*teams\s*=(.*?)(?=\n\s*\|\s*[a-z_ ]+\s*=)", wikitext or "", flags=re.S)
    if not match:
        return []
    result = []
    for line in match.group(1).split("\n"):
        if re.search(r"as (coach|manager)|as executive", line, re.I):
            break
        target = re.search(r"\[\[(?:([^|\]]+)\|)?([^\]]+)\]\]", line)
        if not target or not line.strip().startswith("*"):
            continue
        year = re.search(r"(1[89]\d\d|20\d\d)", line[target.end():])
        result.append(((target.group(1) or target.group(2)).strip(), int(year.group(1)) if year else None))
    return result


def foreign_league(team):
    for league, names in FOREIGN_TEAMS:
        if any(name.lower() in team.lower() for name in names):
            return league
    return None


def last_foreign_team(teams, before_year):
    """MLB 이적 전 마지막 해외 프로 구단 (리그, 구단). before_year 이후에 시작한 구단(복귀 등)은 보지 않는다."""
    found = None
    for team, start in teams:
        league = foreign_league(team)
        if league and (start is None or before_year is None or start <= before_year):
            found = (league, re.sub(r"\s*\(.*?\)$", "", team))
    return found


# ---------- 선수 연결 ----------

def name_keys(name):
    """'Ryu Hyun-jin'·'Hyun Jin Ryu'처럼 순서와 띄어쓰기가 다른 이름을 같은 키로 본다."""
    words = re.split(r"\s+", (name or "").strip())
    if len(words) < 2:
        return {norm(name)}
    return {norm(" ".join(words)), norm(" ".join(words[1:] + words[:1])), norm(" ".join(words[-1:] + words[:-1]))}


def match_player(entry, players, countries=None):
    """위키 항목 → 선수 ID. MLB.com 주소의 ID를 먼저 쓰고, 없으면 이름이 하나만 맞을 때 연결한다."""
    if entry.get("id") and entry["id"] in players:
        return entry["id"]
    keys = name_keys(entry["name"]) | name_keys(entry.get("article", "").split(" (")[0])
    found = [pid for pid, p in players.items()
             if norm(p.get("name")) in keys and (not countries or p.get("country") in countries)]
    return found[0] if len(found) == 1 else None


def first_season(player):
    seasons = [row["season"] for group in ("batting", "pitching") for row in player.get(group) or []]
    return min(seasons) if seasons else None


def debut_year(player):
    return int(player["debut"][:4]) if player.get("debut") else first_season(player)


def foreign_signings(players, club_names, fetch=fetch_wikitext, log=print):
    """해외 프로 출신 {선수 ID: 항목}. players는 {선수 ID: 선수 파일}, club_names는 MLB 구단 이름들."""
    result = {}
    for league, page in POSTING_PAGES.items():
        text = fetch(page)
        postings = parse_postings(text, league)
        if not postings:
            raise ValueError(f"{page} 포스팅 표를 읽지 못함")
        for item in postings:
            pid = match_player(item, players)
            if not pid:
                continue
            old = result.get(pid)
            if old and (old.get("date") or "") > (item["date"] or ""):
                continue  # 여러 번 포스팅된 선수는 마지막 계약
            result[pid] = {
                "type": "posting", "league": league, "foreignTeam": item["foreignTeam"],
                "postingDate": item["postingDate"], "date": item["date"],
                "year": int((item["date"] or item["postingDate"] or "0")[:4]) or None,
                "team": item["team"], "fee": item["fee"], "contract": item["contract"], "bonusUSD": None,
                "source": WIKI + page,
            }
        log(f"{page}: 포스팅 {len(postings)}건")
    todo = []
    for country, page in LIST_PAGES.items():
        listed = parse_player_list(fetch(page))
        if not listed:
            raise ValueError(f"{page} 선수 표를 읽지 못함")
        for item in listed:
            if item["posted"] or item["amateur"]:
                continue
            pid = match_player(item, players, COUNTRIES[country])
            if pid and pid not in result:
                todo.append((pid, item))
        log(f"{page}: 선수 {len(listed)}명")
    failed = []
    for attempt in range(2):
        for pid, item in todo:
            try:
                article = fetch(item["article"].replace(" ", "_"))
                redirect = re.match(r"#REDIRECT\s*\[\[([^\]]+)\]\]", article or "", re.I)
                if redirect:
                    article = fetch(redirect.group(1).replace(" ", "_"))
            except RuntimeError as error:  # 선수 문서 하나가 실패해도 나머지는 받는다
                failed.append((pid, item))
                log(f"  건너뜀: {error}")
                continue
            team = last_foreign_team(infobox_teams(article), debut_year(players[pid]))
            if not team:
                continue
            # 계약일은 이동 기록에서 채운다. 그 전에는 목록의 첫 MLB 구단만 둔다.
            mlb_team = next((link for link in item["teams"] if link.replace(" (baseball)", "") in club_names), None)
            result[pid] = {
                "type": "foreign", "league": team[0], "foreignTeam": team[1],
                "date": None, "year": debut_year(players[pid]),
                "team": mlb_team.replace(" (baseball)", "") if mlb_team else None, "bonusUSD": None,
                "source": WIKI + item["article"].replace(" ", "_"),
            }
        if not failed or attempt:
            break
        log(f"문서 {len(failed)}건 실패: 잠시 뒤 다시 받는다")
        sleep(60)
        todo, failed = failed, []
    log(f"선수 문서 확인 {len(todo)}명")
    if failed:
        log(f"문서를 받지 못한 선수 {len(failed)}명 (다음 실행에서 다시 확인): {', '.join(i['name'] for _, i in failed)}")
    return result


# ---------- MLB 이동 기록의 첫 계약 ----------

def first_signing(transactions, club_ids):
    """이동 기록 → MLB 구단과의 첫 FA 계약 {date, team, minor}. 없으면 {}"""
    signed = sorted((t for t in transactions
                     if t.get("typeCode") == "SFA" and (t.get("toTeam") or {}).get("id") in club_ids and t.get("date")),
                    key=lambda t: t["date"])
    if not signed:
        return {}
    first = signed[0]
    return {"date": first["date"], "team": first["toTeam"]["name"],
            "minor": "minor league contract" in (first.get("description") or "").lower()}


def age_on(birth, day):
    if not birth or not day:
        return None
    b, d = date.fromisoformat(birth), date.fromisoformat(day)
    return d.year - b.year - ((d.month, d.day) < (b.month, b.day))


def signing_entry(pid, signing, player):
    """첫 계약 → 표시용 항목. 첫 계약으로 보기 어려우면 None."""
    if not signing:
        return None
    season = first_season(player)
    year = int(signing["date"][:4])
    if season is None or year > season or season - year > 2:
        return None  # 원본 이동 기록이 생기기 전의 계약이면 나중 계약을 첫 계약으로 잘못 읽게 된다
    age = age_on(player.get("birthDate"), signing["date"])
    amateur = signing["minor"] and age is not None and age < AMATEUR_MAX_AGE
    return {
        "type": "international" if amateur else "free_agent", "year": year, "date": signing["date"],
        "team": signing["team"], "minor": signing["minor"], "bonusUSD": None,
        "source": f"https://statsapi.mlb.com/api/v1/transactions?playerId={pid}",
    }


def fill_foreign_from_signing(entry, signing):
    """해외 FA 항목에 이동 기록의 계약일·구단을 채운다 (이동 기록이 있는 2009년 이후 이적만)."""
    if entry["type"] == "foreign" and signing and not entry.get("date") and int(signing["date"][:4]) <= (entry.get("year") or 9999):
        entry = dict(entry, date=signing["date"], year=int(signing["date"][:4]), team=signing["team"])
    return entry
