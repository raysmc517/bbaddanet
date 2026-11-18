"""MLB 구장 사진 주소·저작자·라이선스 생성: python scripts/venue_photos.py

구장 사진 파일은 저장하지 않는다(2026-11-18 사용자 결정). 위키백과 구장 문서의 대표 사진(위키미디어 공용)
주소와 저작자·라이선스만 data/venue_photos.json에 두고 화면은 그 주소로 걸어 표시하며 출처를 적는다.
자유 라이선스(CC BY·CC BY-SA·CC0·퍼블릭 도메인)인 사진만 넣는다. 요청은 구장마다 2회(약 60회), 1초 간격.

data/teams.json의 MLB 구단 홈구장 이름으로 위키백과 문서를 찾는다(리디렉션 따름). 이름으로 찾기 어려운
구장은 WIKI_TITLE에 문서 제목을 적는다. 사진을 찾지 못한 구장은 넣지 않고 출력한다(화면은 사진 없이 그린다).
teams.py 뒤에 실행한다. 구장이 바뀌거나 사진을 바꿀 때만 다시 실행하면 된다.
"""

import json
import re
import sys
import time
from pathlib import Path

import requests

from careers import write

DATA = Path(__file__).resolve().parent.parent / "data"
API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "bbaddanet-portfolio/1.0 (non-commercial baseball stats project)"}
WIDTH = 1280
FREE = re.compile(r"^(CC BY(-SA)?( \d\.\d)?|CC0|Public domain|PD\b)", re.I)

# 구장 ID → 위키백과 문서 제목 (원본 구장 이름으로 문서를 찾지 못할 때만)
WIKI_TITLE = {
    22: "Dodger Stadium",        # UNIQLO Field at Dodger Stadium
    4: "Rate Field",
    2529: "Sutter Health Park",
    2889: "Busch Stadium",       # 현재 부시 스타디움(3세대) 문서
    3313: "Yankee Stadium",      # 2009년 개장 구장 문서
}

_session = requests.Session()


def query(params):
    for attempt in range(4):
        try:
            res = _session.get(API, params={**params, "format": "json", "formatversion": 2}, headers=HEADERS, timeout=30)
            res.raise_for_status()
            time.sleep(1)
            return res.json()
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"위키백과 요청 실패: {params.get('titles')}")


def plain(text):
    """extmetadata의 HTML 조각 → 글자만."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip()


def photo_entry(page, info):
    """위키백과 문서 정보 + 파일 정보 → 저장할 항목 또는 None(자유 라이선스가 아님). 순수 함수라 따로 검증할 수 있다."""
    meta = info.get("extmetadata") or {}
    license_name = plain((meta.get("LicenseShortName") or {}).get("value"))
    if not FREE.match(license_name):
        return None
    return {
        "page": "https://en.wikipedia.org/wiki/" + page["title"].replace(" ", "_"),
        "file": info.get("descriptionurl") or "",
        "url": info.get("thumburl") or info.get("url"),
        "width": info.get("thumbwidth") or info.get("width"),
        "height": info.get("thumbheight") or info.get("height"),
        "author": plain((meta.get("Artist") or {}).get("value")) or "작자 미상",
        "license": license_name,
        "licenseUrl": plain((meta.get("LicenseUrl") or {}).get("value")) or None,
    }


def fetch_photo(title):
    data = query({"action": "query", "titles": title, "redirects": 1, "prop": "pageimages", "piprop": "name"})
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing") or not pages[0].get("pageimage"):
        return None
    page = pages[0]
    info = query({
        "action": "query", "titles": "File:" + page["pageimage"], "prop": "imageinfo",
        "iiprop": "url|extmetadata|size", "iiurlwidth": WIDTH,
    })
    files = info.get("query", {}).get("pages", [])
    if not files or not files[0].get("imageinfo"):
        return None
    return photo_entry(page, files[0]["imageinfo"][0])


def main():
    clubs = json.loads((DATA / "teams.json").read_text(encoding="utf-8"))["clubs"]
    # 요청이 실패한 구장은 이전 파일의 사진을 그대로 쓴다 (위키백과 요청 제한으로 일부만 실패할 수 있다)
    old_path = DATA / "venue_photos.json"
    previous = json.loads(old_path.read_text(encoding="utf-8")) if old_path.exists() else {}
    result, missing, failed = {}, [], []
    for club in clubs:
        venue = club["venue"]
        try:
            entry = fetch_photo(WIKI_TITLE.get(venue["id"], venue["name"]))
        except Exception:
            failed.append(venue["name"])
            entry = previous.get(str(venue["id"]))
        if entry:
            result[str(venue["id"])] = entry
        else:
            missing.append(venue["name"])
    if failed:
        print(f"[알림] 요청 실패로 이전 사진을 쓴 구장: {', '.join(failed)}", file=sys.stderr)
    if len(result) < 20:
        print(f"[실패] 사진을 찾은 구장이 {len(result)}곳뿐 (기존 파일 유지)", file=sys.stderr)
        return 1
    write(DATA / "venue_photos.json", dict(sorted(result.items(), key=lambda item: int(item[0]))))
    print(f"구장 사진 {len(result)}곳 저장")
    if missing:
        print(f"[알림] 자유 라이선스 사진을 찾지 못한 구장: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
