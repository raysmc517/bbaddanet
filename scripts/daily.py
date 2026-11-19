"""경기 결과·MLB 뉴스 제목 갱신. python scripts/daily.py [--date 2026-10-31]

기본은 UTC 오늘과 앞의 이틀을 받는다. 날짜는 MLB 공식 경기일(미국 현지 기준).
빈 경기 일정은 비시즌의 정상 응답이다. 요청 실패·비정상 응답은 기존 파일을 유지한다.
뉴스는 공식 RSS의 순서대로 제목·시각·링크만 저장하며 본문·사진은 저장하지 않는다.
"""
import argparse
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import requests

from careers import DATA, write
from collectors import statsapi

FEED = "https://www.mlb.com/feeds/news/rss.xml"


def news_items(xml):
    result, seen = [], set()
    for item in ET.fromstring(xml).findall("./channel/item"):
        title, link, published = [item.findtext(key, "").strip() for key in ("title", "link", "pubDate")]
        if not title or urlparse(link).scheme != "https" or urlparse(link).hostname != "www.mlb.com" or link in seen:
            continue
        when = parsedate_to_datetime(published).astimezone(timezone.utc).isoformat(timespec="seconds") if published else None
        result.append({"title": title, "url": link, "published": when, "source": "MLB.com"})
        seen.add(link)
    if not result:
        raise ValueError("뉴스 RSS가 비어 있음")
    return result[:30]


def games(payload):
    if "dates" not in payload or "totalGames" not in payload:
        raise ValueError("경기 응답 형식 오류")
    result = []
    for day in payload["dates"]:
        for game in day["games"]:
            result.append({
                "id": game["gamePk"], "date": game["officialDate"], "start": game["gameDate"],
                "state": game["status"]["abstractGameState"], "status": game["status"]["detailedState"],
                "teams": {side: {"id": game["teams"][side]["team"]["id"], "name": game["teams"][side]["team"]["name"],
                                  "score": game["teams"][side].get("score")} for side in ("away", "home")},
                "innings": [{"n": i["num"], "away": i["away"].get("runs"), "home": i["home"].get("runs")} for i in game.get("linescore", {}).get("innings", [])],
                "decisions": {k: {"id": v["id"], "name": v["fullName"]} for k, v in game.get("decisions", {}).items()},
            })
    if len(result) != payload["totalGames"]:
        raise ValueError("경기 수 불일치")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat)
    args = parser.parse_args()
    today = datetime.now(timezone.utc).date()
    dates = [args.date] if args.date else [today - timedelta(days=i) for i in range(3)]
    failed = 0
    for day in dates:
        try:
            rows = games(statsapi._get("/schedule", {"sportId": 1, "date": day.isoformat(), "hydrate": "linescore,decisions"}))
            write(DATA / "games" / f"{day}.json", {"date": str(day), "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "games": rows})
            print(f"{day}: 경기 {len(rows)}건", flush=True)
        except Exception as error:
            print(f"[실패] {day} 경기: {error} (기존 파일 유지)", file=sys.stderr)
            failed = 1
    write(DATA / "games" / "index.json", sorted([p.stem for p in (DATA / "games").glob("????-??-??.json")], reverse=True))
    try:
        response = requests.get(FEED, timeout=30)
        response.raise_for_status()
        items = news_items(response.content)
        write(DATA / "news.json", {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": FEED, "items": items})
        print(f"뉴스 {len(items)}건", flush=True)
    except Exception as error:
        print(f"[실패] 뉴스: {error} (기존 파일 유지)", file=sys.stderr)
        failed = 1
    return failed


if __name__ == "__main__":
    sys.exit(main())
