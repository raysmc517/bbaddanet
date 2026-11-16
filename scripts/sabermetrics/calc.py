"""세이버매트릭스 지표 계산.

한 리그(레벨)·한 시즌의 타자·투수 목록을 받아 리그 상수를 구하고,
선수별 지표를 각 행에 직접 채워 넣는다. 리그가 달라도 같은 방식으로 계산한다.

타자: wOBA, wRCp(wRC+), sWAR(간이 WAR)
투수: FIP, ERAm(ERA-), FIPm(FIP-), LOBp(LOB%), sWAR(간이 WAR)

간이 WAR은 수비 기여를 0으로 두고, 구원 투수의 등판 상황 가중치도 반영하지 않는다.
"""

# 포지션 보정 (162경기 기준 득점)
POSITION_RUNS = {
    "C": 12.5, "1B": -12.5, "2B": 2.5, "3B": 2.5, "SS": 7.5,
    "LF": -7.5, "CF": 2.5, "RF": -7.5, "OF": -4.0, "DH": -17.5, "TWP": -17.5,
}
REPLACEMENT_RUNS_PER_600PA = 20

BAT_KEYS = ["PA", "AB", "H", "2B", "3B", "HR", "BB", "IBB", "HBP", "SF", "SB", "CS", "R"]
PIT_KEYS = ["outs", "H", "R", "ER", "HR", "BB", "HBP", "SO"]


def _sum(rows, keys):
    return {key: sum(row[key] for row in rows) for key in keys}


def _by_sub(rows):
    """하위 리그(AL/NL 등)별로 나눈다."""
    groups = {}
    for row in rows:
        groups.setdefault(row["lg"], []).append(row)
    return groups


def _woba(row, w):
    """가중 출루율."""
    denominator = row["AB"] + row["BB"] - row["IBB"] + row["SF"] + row["HBP"]
    if not denominator:
        return None
    singles = row["H"] - row["2B"] - row["3B"] - row["HR"]
    numerator = (
        w["BB"] * (row["BB"] - row["IBB"]) + w["HBP"] * row["HBP"] + w["1B"] * singles
        + w["2B"] * row["2B"] + w["3B"] * row["3B"] + w["HR"] * row["HR"]
    )
    return numerator / denominator


def _fip_core(row):
    """FIP에서 리그 상수를 뺀 부분."""
    return (13 * row["HR"] + 3 * (row["BB"] + row["HBP"]) - 2 * row["SO"]) / (row["outs"] / 3)


def league_constants(batting, pitching):
    """리그 전체 기록에서 득점 환경과 wOBA 가중치를 구한다 (톰 탱고의 간이 산출법)."""
    bat = _sum(batting, BAT_KEYS)
    pit = _sum(pitching, PIT_KEYS)
    runs_per_out = pit["R"] / pit["outs"]

    # 사건별 득점 가치
    run = {"BB": runs_per_out + 0.14}
    run["HBP"] = run["BB"] + 0.025
    run["1B"] = run["BB"] + 0.155
    run["2B"] = run["1B"] + 0.3
    run["3B"] = run["2B"] + 0.27
    run["HR"] = 1.4
    run_sb = 0.2
    run_cs = 2 * runs_per_out + 0.075

    singles = bat["H"] - bat["2B"] - bat["3B"] - bat["HR"]
    walks = bat["BB"] - bat["IBB"]
    value = (
        run["BB"] * walks + run["HBP"] * bat["HBP"] + run["1B"] * singles
        + run["2B"] * bat["2B"] + run["3B"] * bat["3B"] + run["HR"] * bat["HR"]
    )
    on_base = walks + bat["HBP"] + bat["H"]
    run_minus = value / (bat["AB"] - bat["H"] + bat["SF"])  # 아웃 하나의 손실
    run_plus = value / on_base
    scale = 1 / (run_plus + run_minus)
    weights = {event: (run[event] + run_minus) * scale for event in run}

    league_era = pit["ER"] * 27 / pit["outs"]
    return {
        "weights": weights,
        "scale": scale,
        "wOBA": on_base / (bat["AB"] + walks + bat["HBP"] + bat["SF"]),
        "runsPerPA": bat["R"] / bat["PA"],
        "runsPerWin": 9 * (pit["R"] / (pit["outs"] / 3)) * 1.5 + 3,
        "runSB": run_sb,
        "runCS": run_cs,
        "lgSB": (bat["SB"] * run_sb - bat["CS"] * run_cs) / (singles + walks + bat["HBP"]),
        "ERA": league_era,
        "RA9": pit["R"] * 27 / pit["outs"],
        "cFIP": league_era - _fip_core(pit),
    }


def _park(row, park_factors):
    """선수에게 적용할 파크팩터. 시즌 중 팀을 옮긴 선수는 중립(1.0)으로 둔다."""
    if row["nt"] > 1:
        return 1.0
    return park_factors.get(row["team"], 1.0)


def _apply_batting(batting, c, park_factors):
    # 하위 리그별 타석당 wRC (wRC+의 분모)
    sub_wrc = {}
    for sub, rows in _by_sub(batting).items():
        woba = _woba(_sum(rows, BAT_KEYS), c["weights"])
        sub_wrc[sub] = (woba - c["wOBA"]) / c["scale"] + c["runsPerPA"] if woba is not None else c["runsPerPA"]

    rpa = c["runsPerPA"]
    for row in batting:
        woba = _woba(row, c["weights"])
        pa = row["PA"]
        if woba is None or not pa:
            row.update({"wOBA": None, "wRCp": None, "sWAR": None})
            continue
        pf = _park(row, park_factors)
        base = sub_wrc.get(row["lg"], rpa)
        wraa = (woba - c["wOBA"]) / c["scale"] * pa
        park_runs = (rpa - pf * rpa) * pa
        row["wOBA"] = round(woba, 3)
        row["wRCp"] = round(100 * ((wraa + park_runs) / pa + rpa) / base)

        singles = row["H"] - row["2B"] - row["3B"] - row["HR"]
        chances = singles + row["BB"] - row["IBB"] + row["HBP"]
        steal_runs = row["SB"] * c["runSB"] - row["CS"] * c["runCS"] - c["lgSB"] * chances
        batting_runs = wraa + park_runs + (rpa - base) * pa
        position_runs = POSITION_RUNS.get(row["pos"], 0) * row["G"] / 162
        replacement_runs = REPLACEMENT_RUNS_PER_600PA / 600 * pa
        total = batting_runs + steal_runs + position_runs + replacement_runs
        row["sWAR"] = round(total / c["runsPerWin"], 1)


def _apply_pitching(pitching, c, park_factors):
    # 하위 리그별 평균자책점과 FIP (ERA-, FIP-의 분모)
    sub_era, sub_fip = {}, {}
    for sub, rows in _by_sub(pitching).items():
        total = _sum(rows, PIT_KEYS)
        if total["outs"]:
            sub_era[sub] = total["ER"] * 27 / total["outs"]
            sub_fip[sub] = _fip_core(total) + c["cFIP"]

    unearned = c["RA9"] - c["ERA"]  # 자책점 기준을 실점 기준으로 옮길 때 더하는 값
    for row in pitching:
        if not row["outs"]:
            row.update({"FIP": None, "ERAm": None, "FIPm": None, "LOBp": None, "sWAR": None})
            continue
        pf = _park(row, park_factors)
        league_era = sub_era.get(row["lg"], c["ERA"])
        league_fip = sub_fip.get(row["lg"], c["ERA"])
        fip = _fip_core(row) + c["cFIP"]
        era = row["ER"] * 27 / row["outs"]
        row["FIP"] = round(fip, 2)
        row["ERAm"] = round(100 * (era + (era - era * pf)) / league_era)
        row["FIPm"] = round(100 * (fip + (fip - fip * pf)) / league_fip)

        runners = row["H"] + row["BB"] + row["HBP"]
        stranded_base = runners - 1.4 * row["HR"]
        row["LOBp"] = round((runners - row["R"]) / stranded_base, 4) if stranded_base > 0 else None

        # FIP 기반 간이 WAR
        innings_per_game = row["outs"] / 3 / row["G"]
        start_share = row["GS"] / row["G"]
        player_ra9 = (fip + unearned) / pf
        league_ra9 = league_fip + unearned
        runs_per_win = (((18 - innings_per_game) * league_ra9 + innings_per_game * player_ra9) / 18 + 2) * 1.5
        replacement = 0.03 * (1 - start_share) + 0.12 * start_share
        wins_per_game = (league_ra9 - player_ra9) / runs_per_win + replacement
        row["sWAR"] = round(wins_per_game * row["outs"] / 27, 1)


def apply(batting, pitching, park_factors):
    """선수 행에 지표를 채우고, 화면과 용어 설명에 쓸 리그 상수를 돌려준다."""
    c = league_constants(batting, pitching)
    _apply_batting(batting, c, park_factors)
    _apply_pitching(pitching, c, park_factors)
    return {
        "wOBA": round(c["wOBA"], 3),
        "wOBAScale": round(c["scale"], 3),
        "weights": {event: round(value, 3) for event, value in c["weights"].items()},
        "runsPerPA": round(c["runsPerPA"], 4),
        "runsPerWin": round(c["runsPerWin"], 2),
        "ERA": round(c["ERA"], 2),
        "cFIP": round(c["cFIP"], 3),
        "parkFactors": dict(sorted(park_factors.items())),
    }
