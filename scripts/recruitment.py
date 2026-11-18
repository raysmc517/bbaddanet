"""MLB 지명·계약금 정보 생성: python scripts/recruitment.py

실제 signingBonus만 사용한다. pickValue(슬롯 배정액)는 계약금이 아니다.
국제 계약 등 수동 확인 정보는 data/recruitment_overrides.json에서 출처와 함께 관리한다.

국제 아마추어 계약(2026-11-18): MLB Pipeline 팀별 Top 30에서 지명 없이 계약한 선수의 계약일·구단과,
소개 글에 적힌 계약금 금액만 가져온다(본문은 저장하지 않음). --pipeline으로 받아
data/drafts/international_pipeline.json에 쌓아 두며, 순위에서 빠진 선수의 기록도 지우지 않는다.
우선순위: 수동 보완(overrides) > Pipeline 국제 계약 > 공식 지명 자료.
"""
import argparse
import json
from pathlib import Path

from careers import write
from collectors import pipeline, statsapi

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="기존 연도 캐시도 다시 수집")
    parser.add_argument("--pipeline", action="store_true", help="Pipeline 팀별 Top 30에서 국제 계약 정보를 다시 받는다 (요청 31회)")
    args = parser.parse_args()
    ids = {int(p.stem) for p in (DATA / "players").glob("*.json")}
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
    for pid, entry in international(args.pipeline).items():
        if int(pid) in ids:
            result[pid] = entry
    overrides = DATA / "recruitment_overrides.json"
    if overrides.exists():
        result.update(json.loads(overrides.read_text(encoding="utf-8")))
    write(DATA / "recruitment.json", result)
    print(f"지명·계약 정보 {len(result)}명", flush=True)


if __name__ == "__main__":
    main()
