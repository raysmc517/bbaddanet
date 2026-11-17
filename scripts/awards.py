"""MLB 수상 기록·명예의 전당 생성: python scripts/awards.py

MLB Stats API에서 상별 역대 수상자를 받아 data/awards.json 하나로 저장한다 (상 하나당 요청 1회).
하나라도 실패하거나 응답이 비면 기존 파일을 그대로 둔다.
선수 페이지 링크 여부는 data/players/에 파일이 있는지로 정하므로 past_players.py 뒤에 실행한다.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from careers import write
from collectors import statsapi

DATA = Path(__file__).resolve().parent.parent / "data"

# (키, 표시 이름, [(원본 상 ID, 리그 표기)]). 화면의 상 선택 순서이기도 하다.
# 리그별로 나뉜 상은 하나로 묶고 리그를 행에 남긴다. 리그 구분이 없는 상은 리그가 빈 문자열이다.
AWARDS = [
    ("hof", "명예의 전당", [("MLBHOF", "")]),
    ("mvp", "MVP", [("ALMVP", "AL"), ("NLMVP", "NL")]),
    ("cy", "사이영상", [("ALCY", "AL"), ("NLCY", "NL"), ("MLBCY", "")]),
    ("roy", "신인왕", [("ALROY", "AL"), ("NLROY", "NL"), ("MLBROY", "")]),
    ("wsmvp", "월드시리즈 MVP", [("WSMVP", "")]),
    ("lcsmvp", "챔피언십시리즈 MVP", [("ALCSMVP", "AL"), ("NLCSMVP", "NL")]),
    ("asmvp", "올스타전 MVP", [("ASMVP", "")]),
    ("allstar", "올스타", [("ALAS", "AL"), ("NLAS", "NL")]),
    ("allmlb1", "All-MLB 퍼스트 팀", [("MLBAFIRST", "")]),
    ("allmlb2", "All-MLB 세컨드 팀", [("MLBSECOND", "")]),
    ("gg", "골드글러브", [("ALGG", "AL"), ("NLGG", "NL"), ("MLGG", "")]),
    ("pg", "플래티넘 글러브", [("ALPG", "AL"), ("NLPG", "NL")]),
    ("ss", "실버슬러거", [("ALSS", "AL"), ("NLSS", "NL")]),
    ("haa", "행크 애런상", [("ALHAA", "AL"), ("NLHAA", "NL")]),
    ("rel", "올해의 구원투수", [("ALREL", "AL"), ("NLREL", "NL")]),
    ("cpoy", "재기상", [("ALCPOY", "AL"), ("NLCPOY", "NL")]),
    ("clemente", "로베르토 클레멘테상", [("MLBRC", "")]),
    ("moy", "올해의 감독", [("ALMOY", "AL"), ("NLMOY", "NL")]),
    ("wschamp", "월드시리즈 우승", [("WSCHAMP", "")]),
]


def assemble(recipients_by_award, has_page):
    """상 ID별 수상자 목록 → (선수 표, 수상 행). 순수 함수라 따로 검증할 수 있다.

    선수 표: {선수 ID: [이름, 포지션, 선수 페이지 여부(1/0)]}
    수상 행: [상 키, 시즌, 리그, 선수 ID, 팀 약칭, 팀 ID]. 같은 상·시즌·리그·선수의 중복은 한 번만 남긴다.
    팀 ID는 구단 페이지가 구단별 우승·수상을 셀 때 쓴다 (연고지를 옮겨도 같은 ID).
    """
    people, rows, seen = {}, [], set()
    for key, _label, sources in AWARDS:
        for award_id, league in sources:
            for item in recipients_by_award.get(award_id, []):
                mark = (key, item["season"], league, item["id"])
                if mark in seen:
                    continue
                seen.add(mark)
                rows.append([key, item["season"], league, item["id"], item["team"], item.get("teamId")])
                people[str(item["id"])] = [item["name"], item["pos"], 1 if has_page(item["id"]) else 0]
    order = {key: index for index, (key, _label, _sources) in enumerate(AWARDS)}
    rows.sort(key=lambda row: (order[row[0]], -row[1], row[2], people[str(row[3])][0]))
    return people, rows


def main():
    recipients_by_award = {}
    try:
        for _key, label, sources in AWARDS:
            for award_id, _league in sources:
                recipients = statsapi.fetch_award_recipients(award_id)
                if not recipients:
                    raise ValueError(f"{award_id} 응답이 비어 있음")
                recipients_by_award[award_id] = recipients
                print(f"{label} ({award_id}): {len(recipients)}건", flush=True)
    except Exception as error:
        print(f"[실패] 수상 기록: {error} (기존 파일 유지)", file=sys.stderr)
        return 1

    players = DATA / "players"
    people, rows = assemble(recipients_by_award, lambda player_id: (players / f"{player_id}.json").exists())
    write(
        DATA / "awards.json",
        {
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "awards": [{"key": key, "name": label} for key, label, _sources in AWARDS],
            "people": people,
            "rows": rows,
        },
    )
    print(f"수상 {len(rows)}건, 수상자 {len(people)}명 저장")
    return 0


if __name__ == "__main__":
    sys.exit(main())
