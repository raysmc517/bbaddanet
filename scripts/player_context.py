"""MLB 시즌 평균과 상황별 성적. python scripts/player_context.py [--from 1876 --to 2026] [--averages-only]

평균은 구단 누적 기록의 합으로 계산하며 구장·리그 보정 지표가 아니다.
완료 시즌 평균은 캐시를 쓰고 현재 시즌만 다시 받는다. 상황별 성적은 지정 시즌마다 갱신한다.
실패·빈 응답·잘린 응답은 해당 시즌 기존 파일을 유지한다.
"""
import argparse
import json
import sys
from datetime import datetime, timezone

from careers import DATA, write
from collectors import statsapi

SITUATIONS = {"risp": "득점권", "vr": "우투수/우타자 상대", "vl": "좌투수/좌타자 상대", "h": "홈", "a": "원정"}


def number(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def outs(value):
    if value is None:
        return None
    whole, _, fraction = str(value).partition(".")
    if not whole.isdigit() or fraction not in ("", "0", "1", "2"):
        raise ValueError(f"이닝 형식 오류: {value}")
    return int(whole) * 3 + int(fraction or 0)


def rates(rows, group):
    def total(key):
        values = [number(row.get(key)) for row in rows]
        return sum(values) if values and all(v is not None for v in values) else None

    def ratio(a, b, scale=1):
        return round(a / b * scale, 5) if a is not None and b else None

    if group == "hitting":
        ab, hits, bb, hbp, sf = [total(k) for k in ("atBats", "hits", "baseOnBalls", "hitByPitch", "sacFlies")]
        obp = ratio(hits + bb + hbp, ab + bb + hbp + sf) if all(v is not None for v in (ab, hits, bb, hbp, sf)) else None
        slg = ratio(total("totalBases"), ab)
        return {"AVG": ratio(hits, ab), "OBP": obp, "SLG": slg,
                "OPS": round(obp + slg, 5) if obp is not None and slg is not None else None,
                "BBp": ratio(bb, total("plateAppearances")), "Kp": ratio(total("strikeOuts"), total("plateAppearances")),
                "ISO": round(slg - hits / ab, 5) if slg is not None and ab else None}
    innings = [outs(row.get("inningsPitched")) for row in rows]
    out_count = sum(innings) if innings and all(v is not None for v in innings) else None
    hits, bb = total("hits"), total("baseOnBalls")
    return {"ERA": ratio(total("earnedRuns"), out_count, 27),
            "WHIP": ratio(hits + bb, out_count, 3) if hits is not None and bb is not None else None,
            "Kp": ratio(total("strikeOuts"), total("battersFaced")), "BBp": ratio(bb, total("battersFaced"))}


def average(season):
    data = statsapi._get("/teams/stats", {"stats": "season", "group": "hitting,pitching", "season": season,
                                         "sportIds": 1, "gameType": "R", "limit": 100})
    result = {}
    for group in ("hitting", "pitching"):
        blocks = [b for b in data.get("stats", []) if b.get("group", {}).get("displayName") == group]
        if len(blocks) != 1:
            raise ValueError(f"{group} 평균 응답 없음")
        block = blocks[0]
        rows = block.get("splits", [])
        if not rows or len(rows) != block.get("totalSplits") or (season >= 1998 and len(rows) != 30):
            raise ValueError(f"{group} 구단 합계 누락")
        result[group] = rates([row["stat"] for row in rows], group)
        if result[group].get("AVG" if group == "hitting" else "ERA") is None:
            raise ValueError(f"{group} 평균 계산 불가")
    result["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return result


def splits(season):
    players = {}
    for group in ("hitting", "pitching"):
        for code in SITUATIONS:
            data = statsapi._get("/stats", {"stats": "statSplits", "group": group, "season": season,
                                          "sportIds": 1, "gameType": "R", "sitCodes": code, "playerPool": "ALL", "limit": 10000})
            blocks = data.get("stats", [])
            if len(blocks) != 1 or not blocks[0].get("splits"):
                raise ValueError(f"{group}/{code} 상황별 기록 없음")
            block = blocks[0]
            if len(block["splits"]) != block.get("totalSplits"):
                raise ValueError(f"{group}/{code} 상황별 응답 잘림")
            for row in block["splits"]:
                if row.get("split", {}).get("code") != code:
                    raise ValueError("요청과 다른 상황 코드")
                target = players.setdefault(str(row["player"]["id"]), {}).setdefault(group, {})
                if code in target:
                    raise ValueError("선수 합계 중복: 팀별 기록과 혼합하지 않음")
                stat = row["stat"]
                keys = ("plateAppearances", "atBats", "hits", "homeRuns", "rbi", "baseOnBalls", "strikeOuts", "avg", "obp", "slg", "ops", "battersFaced", "inningsPitched", "era", "whip")
                target[code] = {key: stat[key] for key in keys if key in stat}
    return {"season": season, "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "players": players}


def main():
    now = datetime.now(timezone.utc).year
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="start", type=int, default=now)
    parser.add_argument("--to", dest="end", type=int, default=now)
    parser.add_argument("--averages-only", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="완료 시즌 평균도 다시 받는다")
    args = parser.parse_args()
    if not 1876 <= args.start <= args.end <= now:
        parser.error("시즌 범위 오류")
    path = DATA / "mlb_averages.json"
    averages = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    failed = 0
    for season in range(args.end, args.start - 1, -1):
        try:
            if str(season) not in averages or season == now or args.refresh:
                averages[str(season)] = average(season)
                write(path, averages)
            if not args.averages_only:
                write(DATA / "situations" / f"{season}.json", splits(season))
            print(f"{season} 저장", flush=True)
        except Exception as error:
            print(f"[실패] {season}: {error} (기존 자료 유지)", file=sys.stderr, flush=True)
            failed = 1
    return failed


if __name__ == "__main__":
    sys.exit(main())
