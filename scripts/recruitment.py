"""MLB 지명·계약금 정보 생성: python scripts/recruitment.py

실제 signingBonus만 사용한다. pickValue(슬롯 배정액)는 계약금이 아니다.
국제 계약 등 수동 확인 정보는 data/recruitment_overrides.json에서 출처와 함께 관리한다.

국제 아마추어 계약(2026-11-18): MLB Pipeline 팀별 Top 30에서 지명 없이 계약한 선수의 계약일·구단과,
소개 글에 적힌 계약금 금액만 가져온다(본문은 저장하지 않음). --pipeline으로 받아
data/drafts/international_pipeline.json에 쌓아 두며, 순위에서 빠진 선수의 기록도 지우지 않는다.
지명 없는 선수의 첫 계약(2026-11-18, scripts/signings.py):
- --foreign: 위키백과 포스팅 표(NPB·KBO)와 일본·한국·대만 출신 MLB 선수 목록으로 포스팅·해외 리그 이적을 받아
  data/drafts/foreign_signings.json에 둔다 (요청 약 80회, 1.5초 간격).
- --transactions: 미국·캐나다·푸에르토리코 밖에서 태어나 지명 기록이 없고 프로 첫 시즌이 2009년 이후인 선수의
  MLB 이동 기록에서 첫 FA 계약을 받아 data/drafts/first_signings.json에 쌓는다 (선수당 1회, 받은 선수는 건너뜀).
우선순위: 수동 보완(overrides) > 공식 지명 > 해외 프로 이적(포스팅·해외 FA) > Pipeline 국제 계약 > 이동 기록 첫 계약.
"""
import argparse
import json
from pathlib import Path

import signings
from careers import write
from collectors import pipeline, statsapi

# 드래프트 대상 지역 출신은 지명 없이 계약해도 국제 계약이 아니므로 이동 기록을 보지 않는다
DRAFT_COUNTRIES = {"USA", "Canada", "CAN", "Puerto Rico", "PUR", "PRI"}

DATA = Path(__file__).resolve().parent.parent / "data"


def draft_entry(pick, year):
    bonus = str(pick.get("signingBonus", "")).replace(",", "").replace("$", "")
    return {
        "type": "draft", "year": year, "round": pick.get("pickRound"),
        "overall": pick.get("pickNumber"), "team": pick.get("team", {}).get("name"),
        "bonusUSD": int(bonus) if bonus.isdigit() and int(bonus) > 0 else None,
        "source": f"https://statsapi.mlb.com/api/v1/draft/{year}?playerId={pick['person']['id']}",
    }


def international(fetch):
    """Pipeline 국제 계약 캐시 {선수 ID: 표시용 항목}. fetch면 새로 받아 캐시에 더한다."""
    cache_path = DATA / "drafts" / "international_pipeline.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    if fetch:
        signings = pipeline.international_signings()
        if len(signings) < 100:  # 30개 구단 Top 30에서 국제 계약 선수가 이보다 적으면 페이지 구조 변경을 의심한다
            raise ValueError(f"국제 계약 선수가 {len(signings)}명뿐: 기존 캐시 유지")
        teams = json.loads((DATA / "teams.json").read_text(encoding="utf-8"))["clubs"]
        name_by_abbr = {club["abbr"]: club["name"] for club in teams}
        for item in signings:
            old = cache.get(str(item["id"]), {})
            cache[str(item["id"])] = {
                "type": "international",
                "year": int(item["date"][:4]) if item["date"] else old.get("year"),
                "date": item["date"] or old.get("date"),
                "team": name_by_abbr.get(item["abbr"], item["abbr"]) or old.get("team"),
                # 이번 소개 글에서 금액을 못 읽으면 예전에 읽은 금액을 지우지 않는다
                "bonusUSD": item["bonusUSD"] if item["bonusUSD"] is not None else old.get("bonusUSD"),
                "source": item["source"],
            }
        write(cache_path, dict(sorted(cache.items(), key=lambda kv: int(kv[0]))))
        print(f"Pipeline 국제 계약 {len(signings)}명 (금액 확인 {sum(1 for i in signings if i['bonusUSD'])}명)", flush=True)
    return cache


def load_players():
    return {int(p.stem): json.loads(p.read_text(encoding="utf-8")) for p in (DATA / "players").glob("*.json")}


def foreign(fetch, players, clubs):
    """해외 프로 리그 출신 캐시. fetch면 위키백과에서 다시 받는다 (실패하면 기존 캐시 유지)."""
    path = DATA / "drafts" / "foreign_signings.json"
    if fetch:
        found = signings.foreign_signings(players, {club["name"] for club in clubs})
        if len(found) < 30:  # 포스팅만 해도 수십 명이므로 이보다 적으면 문서 형식이 바뀐 것으로 본다
            raise ValueError(f"해외 프로 출신 {len(found)}명뿐: 기존 캐시 유지")
        write(path, {str(k): v for k, v in sorted(found.items())})
        print(f"해외 프로 출신 {len(found)}명 (포스팅 {sum(1 for v in found.values() if v['type'] == 'posting')}명)", flush=True)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def first_signings(fetch, candidates, club_ids, refresh=False):
    """이동 기록 첫 계약 캐시 {선수 ID: {date, team, minor} 또는 {}}. 받은 선수는 다시 받지 않는다."""
    path = DATA / "drafts" / "first_signings.json"
    cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if fetch:
        todo = [pid for pid in sorted(candidates) if refresh or str(pid) not in cache]
        print(f"이동 기록 확인 {len(todo)}명 (요청 {len(todo)}회)", flush=True)
        for index, pid in enumerate(todo, 1):
            response = statsapi._get("/transactions", {"playerId": pid})
            cache[str(pid)] = signings.first_signing(response.get("transactions", []), club_ids)
            if index % 200 == 0 or index == len(todo):
                write(path, cache)  # 중간에 끊겨도 받은 선수까지 남긴다
                print(f"  {index}/{len(todo)}", flush=True)
    return cache


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="기존 연도 캐시도 다시 수집")
    parser.add_argument("--pipeline", action="store_true", help="Pipeline 팀별 Top 30에서 국제 계약 정보를 다시 받는다 (요청 31회)")
    parser.add_argument("--foreign", action="store_true", help="위키백과에서 포스팅·해외 리그 이적을 다시 받는다 (요청 약 80회)")
    parser.add_argument("--transactions", action="store_true", help="지명 없는 해외 출신 선수의 이동 기록에서 첫 계약을 받는다")
    args = parser.parse_args()
    players = load_players()
    ids = set(players)
    clubs = json.loads((DATA / "teams.json").read_text(encoding="utf-8"))["clubs"]
    result = {}
    # 현재 데이터의 최초 시즌보다 이른 지명도 포함한다.
    for year in range(1995, 2027):
        path = DATA / "drafts" / f"{year}.json"
        if path.exists() and not args.refresh:
            picks = json.loads(path.read_text(encoding="utf-8"))
        else:
            response = statsapi._get(f"/draft/{year}", {})
            rounds = response["drafts"]["rounds"]
            picks = [{"id": p["person"]["id"], **draft_entry(p, year)}
                     for rnd in rounds for p in rnd["picks"]
                     if p.get("person", {}).get("id") and not p.get("isPass")]
            if not picks:
                raise ValueError(f"{year} 지명 응답 없음: 기존 결과 유지")
            write(path, picks)
        for pick in picks:
            if pick["id"] in ids:
                # 재지명 선수는 가장 최근 지명을 표시한다.
                result[str(pick["id"])] = pick
        print(f"지명 {year}: {len(picks)}명", flush=True)
    drafted = set(result)
    abroad = foreign(args.foreign, players, clubs)
    pipeline_cache = international(args.pipeline)
    overrides_path = DATA / "recruitment_overrides.json"
    overrides = json.loads(overrides_path.read_text(encoding="utf-8")) if overrides_path.exists() else {}

    # 이동 기록: 지명·Pipeline·해외 포스팅·수동 보완 어디에도 없는 해외 출신 선수만 (해외 FA는 계약일을 채우려고 본다)
    known = drafted | set(pipeline_cache) | set(overrides) | {k for k, v in abroad.items() if v["type"] == "posting"}
    candidates = {pid for pid, p in players.items()
                  if str(pid) not in known and p.get("country") not in DRAFT_COUNTRIES
                  and (signings.first_season(p) or 0) >= signings.TRANSACTIONS_FROM}
    first = first_signings(args.transactions, candidates, {club["id"] for club in clubs}, args.refresh)
    for pid, signing in first.items():
        if pid in result or int(pid) not in ids:
            continue
        entry = signings.signing_entry(int(pid), signing, players[int(pid)])
        if entry:
            result[pid] = entry
    for pid, entry in pipeline_cache.items():
        if int(pid) in ids and pid not in drafted:
            result[pid] = entry
    for pid, entry in abroad.items():
        if int(pid) in ids and pid not in drafted:
            result[pid] = signings.fill_foreign_from_signing(entry, first.get(pid))
    result.update(overrides)
    counts = {}
    for entry in result.values():
        counts[entry["type"]] = counts.get(entry["type"], 0) + 1
    print("입단 경로별:", counts, flush=True)
    write(DATA / "recruitment.json", result)
    print(f"지명·계약 정보 {len(result)}명", flush=True)


if __name__ == "__main__":
    main()
