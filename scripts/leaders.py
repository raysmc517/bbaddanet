"""MLB 시즌별 리그 1위 생성: python scripts/leaders.py

선수 페이지의 연도별 성적 표에서 리그(AL·NL) 1위 기록을 굵게 표시하기 위한 자료다.
MLB Stats API의 /stats/leaders를 시즌·리그·기록 묶음(타격·투구)마다 한 번씩 요청한다.
끝난 시즌은 바뀌지 않으므로 이미 받은 시즌은 다시 받지 않고, 최근 시즌만 매번 다시 받는다.

    python scripts/leaders.py                    # 1876~최근 시즌 중 없는 시즌 + 최근 시즌
    python scripts/leaders.py --current-season   # 최근 시즌만 (자동 갱신용, 요청 4회)
    python scripts/leaders.py --refresh          # 전 시즌 다시 받기 (요청 약 550회)

리그 1위는 원본의 리그별 1위(규정 타석·이닝은 원본 기준)이며 동률이면 모두 1위다.
시즌 중 리그를 옮긴 선수는 원본이 리그별 기록만으로 순위를 매기므로, 화면의 시즌 합계와 기준이 다를 수 있다.
한 시즌·리그라도 실패하면 기존 파일을 그대로 둔다.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from careers import write
from collectors import statsapi

DATA = Path(__file__).resolve().parent.parent / "data"
PATH = DATA / "leaders.json"
FIRST_SEASON = 1876
SEASON = 2026  # build.py의 최근 시즌과 같게 유지

# 리그 ID, 표기, 첫 시즌 (그 이전 리그는 수집하지 않는다)
LEAGUES = [(103, "AL", 1901), (104, "NL", 1876)]
LIMIT = 10  # 1위 동률이 이 수를 넘으면 누가 1위인지 다 알 수 없으므로 그 기록은 비운다

# 원본 기록 이름 → 선수 페이지 행의 키 (js/common.js의 열 키)
CATEGORIES = {
    "hitting": {
        "runs": "R", "hits": "H", "doubles": "2B", "triples": "3B", "homeRuns": "HR", "runsBattedIn": "RBI",
        "stolenBases": "SB", "walks": "BB", "battingAverage": "AVG", "onBasePercentage": "OBP",
        "sluggingPercentage": "SLG", "onBasePlusSlugging": "OPS",
    },
    "pitching": {
        "wins": "W", "saves": "SV", "holds": "HLD", "inningsPitched": "outs", "strikeouts": "SO",
        "earnedRunAverage": "ERA", "walksAndHitsPerInningPitched": "WHIP",
    },
}
GROUP_KEY = {"hitting": "b", "pitching": "p"}  # 화면의 batting·pitching


def first_place(leaders):
    """원본 순위 목록 → 1위 선수 ID 목록. 순수 함수라 따로 검증할 수 있다.

    값이 0이면(홀드 도입 이전 시즌 등 기록이 없는 경우) 1위로 보지 않는다.
    목록이 모두 1위라 동률이 더 있을 수 있으면 빈 목록을 돌려준다 (일부만 굵게 하지 않기 위해).
    """
    top = [item for item in leaders if item.get("rank") == 1 and item.get("person", {}).get("id")]
    if not top or len(top) >= LIMIT:
        return []
    try:
        if float(top[0].get("value", "0")) == 0:
            return []
    except ValueError:
        pass
    return sorted({item["person"]["id"] for item in top})


def fetch_season(season):
    """시즌 하나의 리그별 1위 {리그: {b|p: {열 키: [선수 ID]}}}. 그 시즌에 없는 리그는 뺀다."""
    result = {}
    for league_id, league, since in LEAGUES:
        if season < since:
            continue
        groups = {}
        for group, names in CATEGORIES.items():
            data = statsapi._get(
                "/stats/leaders",
                {
                    "season": season, "leagueId": league_id, "statGroup": group, "limit": LIMIT,
                    "leaderCategories": ",".join(names),
                    "fields": "leagueLeaders,leaderCategory,leaders,rank,value,person,id",
                },
            )
            mine = {}
            for item in data.get("leagueLeaders", []):
                key = names.get(item.get("leaderCategory"))
                ids = first_place(item.get("leaders", [])) if key else []
                if ids:
                    mine[key] = ids
            groups[GROUP_KEY[group]] = mine
        if not any(groups.values()):
            raise ValueError(f"{season} {league} 1위 응답이 비어 있음")
        result[league] = groups
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--current-season", action="store_true", help="최근 시즌만 다시 받는다")
    parser.add_argument("--refresh", action="store_true", help="이미 받은 시즌도 다시 받는다")
    args = parser.parse_args()

    old = json.loads(PATH.read_text(encoding="utf-8")) if PATH.exists() else {"seasons": {}}
    seasons = dict(old.get("seasons", {}))
    if args.current_season:
        targets = [SEASON]
    else:
        targets = [s for s in range(FIRST_SEASON, SEASON + 1) if args.refresh or s == SEASON or str(s) not in seasons]

    done, failed = 0, None
    try:
        for index, season in enumerate(targets, 1):
            seasons[str(season)] = fetch_season(season)
            done += 1
            if index % 10 == 0 or index == len(targets):
                print(f"리그 1위 {index}/{len(targets)} ({season})", flush=True)
    except Exception as error:
        failed = error

    # 시즌 단위로 완성된 자료만 들어 있으므로, 중간에 실패해도 받은 시즌까지는 저장한다.
    # 실패한 시즌은 기존 값을 그대로 두고, 다시 실행하면 이어서 받는다.
    if done:
        write(
            PATH,
            {
                "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "seasons": dict(sorted(seasons.items(), key=lambda item: int(item[0]))),
            },
        )
        print(f"리그 1위 {done}시즌 갱신, 전체 {len(seasons)}시즌 저장")
    if failed:
        print(f"[실패] 리그 1위: {failed} (실패한 시즌은 기존 값 유지, 다시 실행하면 이어서 받음)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
