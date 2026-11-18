"""MLB Pipeline 유망주 랭킹 수집기.

mlb.com/prospects 페이지에 들어 있는 초기 데이터에서 순위만 읽는다.
공식 API가 아니라 페이지 구조가 바뀌면 깨질 수 있으므로, 결과가 이상하면 오류를 낸다.
스카우팅 리포트 본문과 사진은 가져오지 않는다.
"""

import html
import json
import re
import time

import requests

BASE = "https://www.mlb.com/prospects"
HEADERS = {"User-Agent": "Mozilla/5.0"}
DELAY_SEC = 1.0
MLB_SPORT = "Sport:1"


def _fetch_state(slug):
    """랭킹 페이지 하나의 초기 데이터."""
    res = requests.get(f"{BASE}/{slug}/", headers=HEADERS, timeout=60)
    res.raise_for_status()
    time.sleep(DELAY_SEC)
    match = re.search(r'data-init-state="([^"]*)"', res.text)
    if not match:
        raise RuntimeError(f"Pipeline 페이지에서 데이터를 찾지 못함: {slug}")
    return json.loads(html.unescape(match.group(1)))


def _rankings(state):
    """페이지 데이터 → 유망주 목록."""
    payload = state["payload"]
    root = payload["ROOT_QUERY"]
    key = next((k for k in root if k.startswith("getPlayerRankingsFromSelection")), None)
    if key is None:
        raise RuntimeError("Pipeline 페이지에 랭킹 목록이 없음")

    prospects = []
    for entry in root[key]:
        entity = entry["playerEntity"]
        person = payload[entity["player"]["__ref"]]
        team_ref = (person.get("activeRosterMLB") or person.get("activeRoster") or {}).get("__ref")
        team = payload.get(team_ref, {}) if team_ref else {}
        sport_ref = (team.get("sport") or {}).get("__ref")
        level = payload.get(sport_ref, {}).get("abbreviation", "") if sport_ref else ""
        org_id = team.get("id") if sport_ref == MLB_SPORT else team.get("parentOrgId")
        prospects.append(
            {
                "rank": entry["rank"],
                "id": person["id"],
                "name": f"{person.get('useName', '')} {person.get('useLastName', '')}".strip(),
                "pos": entity.get("position") or "",
                "age": person.get("currentAge"),
                "eta": entity.get("eta") or "",
                "level": level,  # 현재 소속 레벨 (MLB, AAA, AA, A+, A, ROK 등)
                "club": team.get("name", ""),  # 현재 소속 팀
                "orgId": org_id,  # 소속 MLB 구단 ID
            }
        )
    return prospects


def _team_pages(state):
    """Top 100 페이지의 메뉴에서 팀별 Top 30 페이지 목록을 읽는다. [(주소 조각, 구단 이름)]"""
    root = state["payload"]["ROOT_QUERY"]
    key = next((k for k in root if k.startswith("getForgeNavigation")), None)
    pages = []
    for item in (root.get(key) or {}).get("menuItems", []):
        if "by team" not in (item.get("text") or "").lower():
            continue  # 드래프트, 국제 유망주 등 다른 메뉴는 건너뛴다
        for child in item.get("menuItems") or []:
            if child.get("link"):
                pages.append((child["link"], child["text"]))
    return pages


def collect():
    """Top 100과 팀별 Top 30을 받아온다."""
    state = _fetch_state("top100")
    top100 = _rankings(state)
    if len(top100) < 90:
        raise RuntimeError(f"Top 100 인원이 이상함: {len(top100)}명")
    pages = _team_pages(state)
    if len(pages) != 30:
        raise RuntimeError(f"팀별 페이지 수가 이상함: {len(pages)}개")

    teams = []
    for slug, name in pages:
        players = _rankings(_fetch_state(slug))
        if len(players) < 20:
            raise RuntimeError(f"{name} Top 30 인원이 이상함: {len(players)}명")
        teams.append({"name": name, "players": players})
    return {"top100": top100, "teams": teams}


# ---------- 국제 아마추어 계약 (2026-11-18) ----------
# 팀별 Top 30 항목의 signed("Jan. 15, 2022 - LAD")에서 계약일·구단을 읽고, 계약금은 소개 글에서
# "Signed for $297,500 ..."처럼 계약을 말하는 문장의 금액 숫자만 뽑는다. 소개 글 본문은 저장하지 않는다.
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
SIGNED = re.compile(r"([A-Za-z]+)\.?\s+(\d{1,2}),\s*(\d{4})\s*-\s*([A-Z]{2,3})")
# 'signed (him) ... for $X'처럼 계약 문장에서 for 바로 뒤의 금액만 인정한다. 구단 전체 한도(bonus pool) 같은
# 다른 금액을 계약금으로 잘못 읽지 않기 위해서다 (예: '...bonus pool of over $5.3 million')
BONUS = re.compile(r"\b[Ss]ign(?:ed|s|ing)\b[^.$]{0,160}?\bfor\s+(?:an?\s+)?\$\s?(\d[\d,]*(?:\.\d+)?)\s*(million)?")


def signing_date(text):
    """'Jan. 15, 2022 - LAD' → ('2022-01-15', 'LAD'). 읽지 못하면 (None, None)."""
    match = SIGNED.search(text or "")
    if not match or match.group(1)[:3].lower() not in MONTHS:
        return None, None
    month = MONTHS[match.group(1)[:3].lower()]
    return f"{match.group(3)}-{month:02d}-{int(match.group(2)):02d}", match.group(4)


def bonus_usd(text):
    """소개 글에서 계약 문장의 금액 → 달러 정수. 없으면 None. ('$1.2 million' → 1200000)"""
    plain = re.sub(r"<[^>]+>", " ", text or "")
    match = BONUS.search(plain)
    if not match:
        return None
    amount = float(match.group(1).replace(",", ""))
    if match.group(2):
        amount *= 1_000_000
    return int(round(amount)) if amount >= 1000 else None  # $10,000 미만 등 비정상 값은 버린다


def _signings(state, slug):
    payload = state["payload"]
    root = payload["ROOT_QUERY"]
    key = next((k for k in root if k.startswith("getPlayerRankingsFromSelection")), None)
    result = []
    for entry in root.get(key) or []:
        entity = entry["playerEntity"]
        person = payload[entity["player"]["__ref"]]
        if person.get("drafts") or not entity.get("signed"):
            continue  # 드래프트 지명 선수는 recruitment.py가 공식 지명 자료로 처리한다
        date, abbr = signing_date(entity["signed"])
        bio = " ".join(item.get("contentText", "") for item in entity.get("prospectBio") or [])
        result.append({
            "id": person["id"],
            "date": date,
            "abbr": abbr,
            "bonusUSD": bonus_usd(bio),
            "source": f"{BASE}/{slug}/",
        })
    return result


def international_signings():
    """팀별 Top 30 페이지에서 지명 없이 계약한 선수의 계약일·구단·계약금 (요청 31회)."""
    pages = _team_pages(_fetch_state("top100"))
    if len(pages) != 30:
        raise RuntimeError(f"팀별 페이지 수가 이상함: {len(pages)}개")
    result = []
    for slug, _name in pages:
        result.extend(_signings(_fetch_state(slug), slug))
    return result
