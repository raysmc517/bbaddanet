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
