"""수동 관리 계약 자료 검사: python scripts/contracts.py

외부 요청·데이터 생성 없이 contracts.json의 ID·출처·연봉 범위·보장 총액을 검사한다.
salaryComplete는 모든 보장 시즌의 기본 연봉과 계약금·바이아웃을 확인했을 때만 켠다.
옵션 행사/징계/이적에 따른 실제 지급액을 재계산하지 않는다.
"""
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

DATA = Path(__file__).resolve().parent.parent / "data"


def valid_url(value):
    parsed = urlparse(value or "")
    return parsed.scheme == "https" and bool(parsed.hostname)


def money(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate(payload, data_dir=DATA):
    errors = []
    date.fromisoformat(payload["checked"])
    clubs = {row["abbr"] for row in json.loads((data_dir / "teams.json").read_text(encoding="utf-8"))["clubs"]}
    if not payload.get("players"):
        return ["계약 자료가 비어 있음"]
    for pid, records in payload["players"].items():
        path = data_dir / "players" / f"{pid}.json"
        if not pid.isdigit() or not path.is_file():
            errors.append(f"{pid}: 선수 ID/파일 없음")
            continue
        player = json.loads(path.read_text(encoding="utf-8"))
        for record in records:
            prefix = f"{pid} {player['name']}"
            def fail(message):
                errors.append(f"{prefix}: {message}")
            if record.get("name") != player["name"]:
                fail("선수 이름과 ID 불일치")
            if record.get("team") not in clubs:
                fail("계약 당시 구단 약자 오류")
            start, end = record.get("from"), record.get("to")
            if not isinstance(start, int) or not isinstance(end, int) or not 1876 <= start <= end <= 2100:
                fail("계약 기간 오류")
                continue
            try:
                date.fromisoformat(record.get("checked", payload["checked"]))
            except (ValueError, TypeError):
                fail("확인일 오류")
            for key in ("source", "salarySource", "termsSource"):
                if (key == "source" or key in record) and not valid_url(record.get(key)):
                    fail(f"{key} 출처 오류")
            for key in ("totalUSD", "signingBonusUSD", "buyoutUSD"):
                if key == "totalUSD" and record.get("amountUnknown") is True and record.get("listedTeam") is True and record.get(key) is None:
                    continue
                if (key == "totalUSD" or key in record) and not money(record.get(key)):
                    fail(f"{key} 금액 오류")
            years = {}
            for salary in record.get("salaries", []):
                first, last = salary.get("from"), salary.get("to")
                if not isinstance(first, int) or not isinstance(last, int) or not start <= first <= last <= end:
                    fail("연봉 시즌이 보장 계약 기간 밖임")
                    continue
                if not money(salary.get("baseUSD")):
                    fail("기본 연봉 금액 오류")
                    continue
                if "deferredUSD" in salary and (not money(salary["deferredUSD"]) or salary["deferredUSD"] > salary["baseUSD"]):
                    fail("이연액이 음수이거나 기본 연봉 초과")
                for season in range(first, last + 1):
                    if season in years:
                        fail(f"{season} 연봉 중복")
                    years[season] = salary["baseUSD"]
            if record.get("salaryComplete"):
                if set(years) != set(range(start, end + 1)):
                    fail("전체 연봉으로 표시했으나 미확인 시즌 있음")
                extras = [record.get("signingBonusUSD", 0), record.get("buyoutUSD", 0)]
                if all(money(value) for value in extras):
                    total = sum(years.values()) + sum(extras)
                    if total != record.get("totalUSD"):
                        fail(f"기본 연봉+계약금+바이아웃 {total:,} != 보장 총액 {record.get('totalUSD')}")
    return errors


def main():
    payload = json.loads((DATA / "contracts.json").read_text(encoding="utf-8"))
    errors = validate(payload)
    for error in errors:
        print(error, file=sys.stderr)
    players = payload["players"]
    salary_count = sum(any(r.get("salaries") for r in rows) for rows in players.values())
    print(f"계약 {len(players)}명 · 연도별 연봉 {salary_count}명 · 오류 {len(errors)}건")
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
