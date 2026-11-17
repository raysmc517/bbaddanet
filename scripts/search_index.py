"""선수 검색 색인 생성: python scripts/search_index.py

data/players/*.json을 읽어 data/search.json 하나로 만든다. 외부 요청은 없다.
선수 파일이 추가·변경되는 빌드(build.py, past_players.py) 끝에서도 호출한다.
"""

import json
import sys
from pathlib import Path

from careers import write

DATA = Path(__file__).resolve().parent.parent / "data"


def entry(player):
    """[ID, 이름, 포지션, 첫 시즌, 마지막 시즌, MLB 출전 여부(1/0)]. 기록이 없으면 시즌은 None."""
    rows = player.get("batting", []) + player.get("pitching", [])
    seasons = [row["season"] for row in rows]
    return [
        player["id"],
        player.get("name", ""),
        player.get("pos", ""),
        min(seasons) if seasons else None,
        max(seasons) if seasons else None,
        1 if any(row.get("level") == "MLB" for row in rows) else 0,
    ]


def build(data=DATA):
    """색인을 저장하고 선수 수를 돌려준다. 선수 파일이 하나도 없으면 기존 색인을 유지한다."""
    players = []
    for path in sorted((data / "players").glob("*.json"), key=lambda p: int(p.stem)):
        players.append(entry(json.loads(path.read_text(encoding="utf-8"))))
    if not players:
        raise ValueError("선수 파일이 없음: 기존 색인 유지")
    write(data / "search.json", {"players": players})
    return len(players)


if __name__ == "__main__":
    try:
        print(f"검색 색인 {build()}명")
    except Exception as error:
        print(f"[실패] 검색 색인: {error}", file=sys.stderr)
        sys.exit(1)
