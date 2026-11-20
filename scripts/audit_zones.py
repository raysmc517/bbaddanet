"""저장된 위치 집계의 해시·표본·선수 연결 검사. 외부 요청 없음.

python scripts/audit_zones.py --report docs/zones-audit-2026-11-20.md
"""
import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "zones"
PITCHES = set("FA FF FT FC FS FO SI ST SL CU KC SC GY SV CS CH KN EP UN IN PO AB AS NP".split())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit():
    seasons = json.loads((DATA / "index.json").read_text(encoding="utf-8"))["seasons"]
    require(bool(seasons) and seasons == sorted(set(seasons), reverse=True), "제공 시즌 순서·중복 오류")
    records, people, absent, unknown = [], set(), set(), set()
    for season in seasons:
        folder = DATA / str(season)
        index = json.loads((folder / "index.json").read_text(encoding="utf-8"))
        require(index["season"] == season and index["gameType"] == "R", f"{season}: 시즌·경기 종류 오류")
        require(date.fromisoformat(index["through"]).year == season, f"{season}: 경기일 오류")
        seen = dict.fromkeys(("batting", "pitching"), 0)
        missing = dict(seen)
        players, size = set(), 0
        for key, filename in index["buckets"].items():
            path = folder / filename
            require(path.parent == folder and path.suffix == ".json", f"{season}: 버킷 경로 오류")
            size += path.stat().st_size
            data = json.loads(path.read_text(encoding="utf-8"))
            digest = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]
            require(filename == f"{key}.{digest}.json" and data["season"] == season, f"{path}: 해시·시즌 오류")
            for pid, roles in data["players"].items():
                label = f"{season}/{pid}"
                require(pid not in players and int(pid) > 0 and f"{int(pid) % 100:02}" == key, f"{label}: 선수 버킷 오류")
                players.add(pid)
                people.add(pid)
                if not (ROOT / "data" / "players" / f"{pid}.json").is_file():
                    absent.add(pid)
                for role, rows in roles.items():
                    require(role in seen, f"{label}: 역할 오류")
                    for row in rows:
                        unknown.update({row["pitch"]} - PITCHES)
                        seen[role] += row["seen"]
                        missing[role] += row["missing"]
                        require(0 <= row["missing"] <= row["seen"], f"{label}: 누락 수 오류")
                        cells = row["zones"].items() if isinstance(row["zones"], dict) else enumerate(row["zones"])
                        count = 0
                        for i, cell in cells:
                            require(0 <= int(i) < 25 and len(cell) == 6 and all(type(n) is int and n >= 0 for n in cell),
                                    f"{label}: 구역 형식 오류")
                            require(cell[2] <= cell[1] <= cell[0] and cell[4] <= cell[3] <= cell[0]
                                    and cell[4] <= cell[5] <= 4 * cell[4], f"{label}: 구역 분모·루타 오류")
                            count += cell[0]
                        require(count + row["missing"] == row["seen"], f"{label}: 구역 합계 오류")
                        ids = [i for i, n in row["density"]]
                        require(len(ids) == len(set(ids)) and all(0 <= i < 400 and type(n) is int and n > 0
                                                                for i, n in row["density"]), f"{label}: 격자 오류")
                        require(row["outside"] >= 0 and sum(n for i, n in row["density"]) + row["outside"] == count,
                                f"{label}: 분포 합계 오류")
        require(len(players) == index["playerCount"], f"{season}: 선수 수 오류")
        require(seen["batting"] == seen["pitching"] == index["pitches"], f"{season}: 역할·시즌 합계 오류")
        # 초기 정상 공개본에는 시즌 missing 필드가 없다. 선수별 값은 항상 검사한다.
        require(missing["batting"] == missing["pitching"] == index.get("missing", missing["batting"]),
                f"{season}: 누락 합계 오류")
        records.append((season, index["games"], index["pitches"], len(players), missing["batting"], index["through"], size))
        print(f"{season}: 검수 통과 · {index['games']:,}경기 · {index['pitches']:,}건", flush=True)
    require(not absent, f"선수 프로필 누락: {sorted(absent)}")
    require(not unknown, f"원본 구종 코드 확인 필요: {sorted(unknown)}")
    return records, len(people)


def report(records, people):
    games, pitches, missing, size = (sum(row[i] for row in records) for i in (1, 2, 4, 6))
    lines = ["# 투구 위치·핫콜드존 집계 검수", "",
             f"{records[-1][0]}~{records[0][0]} MLB 정규시즌 {len(records)}개 시즌 · {games:,}경기 · 원본 투구 기록 {pitches:,}건 · 선수 ID {people:,}명.",
             f"위치·존 높이 누락 {missing:,}건은 구역 계산에서 제외한다. 활성 화면용 버킷 합계 {size / 1024**2:.2f} MiB.", "",
             "## 검사 결과", "",
             "- 모든 활성 버킷의 내용 해시·시즌·선수 ID와 버킷 번호 일치.",
             "- 투수·타자 양쪽의 기록 합계와 시즌 색인의 합계 일치.",
             "- 구역 합계 + 위치 누락 = 전체 기록, 격자 합계 + 그림 밖 = 위치 확인 기록.",
             "- 모든 셀에서 헛스윙 ≤ 스윙 ≤ 투구, 안타 ≤ 타수 ≤ 투구, 안타 ≤ 루타 ≤ 4×안타.",
             "- 누락 선수 프로필 0명, 미등록 원본 구종 코드 0개.",
             "- 저장 파일·집계 정합성 검사이며, 모든 선수의 MLB 공식 성적과 전수 일치한다는 뜻은 아니다.", "",
             "## 시즌별 범위", "",
             "| 시즌 | 경기 | 투구 기록 | 선수 | 위치·존 높이 누락 | 마지막 경기일 | 활성 버킷 MiB |",
             "|---|---:|---:|---:|---:|---|---:|"]
    for year, games, pitches, players, missing, through, size in records:
        lines.append(f"| {year} | {games:,} | {pitches:,} | {players:,} | {missing:,} | {through} | {size / 1024**2:.2f} |")
    lines += ["", "원본: [Baseball Savant CSV 정의](https://baseballsavant.mlb.com/csv-docs), MLB 공식 정규시즌 일정. 정의·한계는 [PRD 20절](../PRD.md)을 따른다.",
              "2008~2014는 Statcast 도입 전 PITCHf/x 자료다. 2026의 플레이트 중앙·ABS 기준과 이전의 앞면·원본 존 높이 기준을 합치지 않는다.",
              "과거 수집 캐시는 로컬에 유지하고 Git 추적·배포에서 제외한다. 크기는 활성 버킷만 센 값이다.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="검수 통과 시 Markdown 보고서 저장")
    args = parser.parse_args()
    try:
        records, people = audit()
        if args.report:
            args.report.write_text(report(records, people), encoding="utf-8")
        print(f"전체 {len(records)}시즌 · {sum(r[1] for r in records):,}경기 · {sum(r[2] for r in records):,}건 · {people:,}명 검수 통과")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"위치 집계 검수 실패: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
