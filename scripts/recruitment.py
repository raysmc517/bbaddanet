"""MLB 지명·계약금 정보 생성: python scripts/recruitment.py

실제 signingBonus만 사용한다. pickValue(슬롯 배정액)는 계약금이 아니다.
국제 계약 등 수동 확인 정보는 data/recruitment_overrides.json에서 출처와 함께 관리한다.
"""
import argparse
import json
from pathlib import Path

from careers import write
from collectors import statsapi

DATA = Path(__file__).resolve().parent.parent / "data"


def draft_entry(pick, year):
    bonus = str(pick.get("signingBonus", "")).replace(",", "").replace("$", "")
    return {
        "type": "draft", "year": year, "round": pick.get("pickRound"),
        "overall": pick.get("pickNumber"), "team": pick.get("team", {}).get("name"),
        "bonusUSD": int(bonus) if bonus.isdigit() and int(bonus) > 0 else None,
        "source": f"https://statsapi.mlb.com/api/v1/draft/{year}?playerId={pick['person']['id']}",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="기존 연도 캐시도 다시 수집")
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
    overrides = DATA / "recruitment_overrides.json"
    if overrides.exists():
        result.update(json.loads(overrides.read_text(encoding="utf-8")))
    write(DATA / "recruitment.json", result)
    print(f"지명·계약 정보 {len(result)}명", flush=True)


if __name__ == "__main__":
    main()
