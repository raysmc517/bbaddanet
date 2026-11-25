// 빠따넷 구단 선수단
// roster.html?id={MLB 구단 ID}&season={시즌}&view={명단 종류}
// data/rosters/{시즌}/{구단 ID}.json을 읽는다.
// - 시즌 선수단(players): 그 시즌 구단 명단에 있었던 선수 전원과 이 구단에서 거둔 성적
// - 최근 시즌에만: 기준일의 액티브 로스터(정규시즌·포스트시즌만), 40인 로스터, 부상자 명단(current)

(function () {
  "use strict";

  const { escapeHtml, loadJson, fmt, has } = window.BB;
  const $ = (id) => document.getElementById(id);

  const FALLBACK_SEASONS = [2026, 2025, 2024];
  const LOGO_BASE = "https://www.mlbstatic.com/team-logos/";
  const IN_SEASON = ["regular", "postseason"];
  const POSITION_GROUPS = [
    ["Pitcher", "투수"],
    ["Two-Way Player", "투타겸업"],
    ["Catcher", "포수"],
    ["Infielder", "내야수"],
    ["Outfielder", "외야수"],
    ["Hitter", "지명타자"],
  ];
  // 포지션 선택 (2026-11-25 사용자 요구): 보고 싶은 포지션만 남긴다. 투타겸업은 투수에 넣고, 지명타자는 전체에서만 보인다
  const POS_FILTERS = [
    { key: "", label: "전체" },
    { key: "P", label: "투수", types: ["Pitcher", "Two-Way Player"] },
    { key: "C", label: "포수", types: ["Catcher"] },
    { key: "IF", label: "내야수", types: ["Infielder"] },
    { key: "OF", label: "외야수", types: ["Outfielder"] },
  ];
  const posFilter = () => POS_FILTERS.find((f) => f.key === state.pos) || POS_FILTERS[0];
  const byPos = (rows, filter) => ((filter || posFilter()).types ? rows.filter((r) => (filter || posFilter()).types.includes(r.posType)) : rows);

  const STATUS = {
    // A(액티브)는 시즌 단계에 따라 activeLabel()로 바꿔 보여준다
    RM: "40인",
    "40M": "40인",
    D7: "7일 IL (뇌진탕)",
    D10: "10일 IL",
    D15: "15일 IL",
    D60: "60일 IL",
    BRV: "경조사 명단",
    PL: "출산휴가 명단",
    SU: "출장 정지",
    RES: "제한 명단",
    NYR: "미합류",
  };
  const HAND = { R: "우", L: "좌", S: "양" };

  const state = { id: null, season: null, view: "", pos: "", move: "", month: "", moveDesc: true, sort: { bat: ["PA", "desc"], pit: ["outs", "desc"] } };
  let seasons = FALLBACK_SEASONS;
  let team = null;
  let data = null;
  let clubs = {}; // 구단 ID → {name, level} (MLB·산하 구단, data/teams.json)

  const isInjured = (row) => /^D\d+$/.test(row.status);
  const hands = (r) => (HAND[r.throws] || "-") + "투" + (HAND[r.bats] || "-") + "타";
  const personLink = (r) =>
    r.page ? '<a href="player.html?id=' + r.id + '">' + escapeHtml(r.name) + "</a>" : escapeHtml(r.name);

  // 기준 날짜의 만 나이
  function ageOn(birthDate, day) {
    if (!birthDate) return null;
    const [by, bm, bd] = birthDate.split("-").map(Number);
    const [y, m, d] = day.split("-").map(Number);
    return y - by - (m < bm || (m === bm && d < bd) ? 1 : 0);
  }
  // 시즌 나이: 그해 6월 30일 기준 만 나이 (야구 기록에서 흔히 쓰는 기준)
  const seasonAge = (r) => ageOn(r.birthDate, state.season + "-06-30");

  // 액티브 로스터 크기: 정규시즌 9월(확장 기간)은 28인, 그 밖의 정규시즌·포스트시즌은 26인
  function activeLabel() {
    const september = data.phase === "regular" && data.date.slice(5) >= "09-01";
    return (september ? "28인" : "26인") + " 액티브";
  }

  // 상태 열: 액티브 로스터 선수는 'N인 액티브', 마이너리그로 내려간 40인 선수는 '40인', 부상자 명단은 IL 종류.
  // 비시즌에는 액티브 로스터가 없으므로 원본의 액티브(A) 표시도 40인으로 보여준다.
  function statusLabel(row) {
    if (row.status === "A") return IN_SEASON.includes(data.phase) ? activeLabel() : STATUS["40M"];
    return STATUS[row.status] || row.statusText || "-";
  }

  // ---------- 명단 종류 ----------
  // 60일 IL 선수는 규정상 40인에서 빠지지만, 비시즌에는 원본에 남은 표시일 수 있어 그대로 센다.
  function views() {
    const list = [];
    if (data.current) {
      const inSeason = IN_SEASON.includes(data.phase);
      const rows = data.current;
      if (inSeason) list.push({ key: "active", label: activeLabel() + " 로스터", rows: rows.filter((r) => r.status === "A") });
      list.push({ key: "forty", label: "40인 로스터", rows: inSeason ? rows.filter((r) => r.status !== "D60") : rows });
      list.push({ key: "il", label: "부상자 명단", rows: rows.filter(isInjured) });
    }
    list.push({ key: "season", label: state.season + " 시즌 선수단", rows: data.players });
    if (data.moves) list.push({ key: "moves", label: "선수 이동", rows: data.moves });
    return list;
  }

  // ---------- 기준일 명단 (포지션별 묶음) ----------
  function snapshotTable(view) {
    const injured = view.key === "il";
    const columns = injured ? 7 : 6;
    const head =
      '<tr><th>번호</th><th class="col-name">선수</th><th class="col-team">포지션</th><th class="col-team">투타</th><th>나이</th>' +
      '<th class="col-team">상태</th>' + (injured ? '<th class="col-team">부상 내용 (원문)</th>' : "") + "</tr>";
    const rows = byPos(view.rows);
    let body;
    if (!rows.length) {
      body = '<tr><td class="empty" colspan="' + columns + '">해당하는 선수가 없습니다.</td></tr>';
    } else {
      const known = new Set(POSITION_GROUPS.map(([type]) => type));
      const groups = POSITION_GROUPS.map(([type, label]) => [label, rows.filter((r) => r.posType === type)]);
      groups.push(["기타", rows.filter((r) => !known.has(r.posType))]);
      body = groups.filter(([, rows]) => rows.length).map(([label, rows]) =>
        '<tr class="group-row"><td colspan="' + columns + '">' + escapeHtml(label) + " " + rows.length + "명</td></tr>" +
        rows.map((r) => {
          const age = ageOn(r.birthDate, data.date);
          const status = statusLabel(r);
          return (
            "<tr><td>" + (r.num ? escapeHtml(r.num) : "-") + "</td>" +
            '<td class="col-name">' + personLink(r) + "</td>" +
            '<td class="col-team">' + escapeHtml(r.pos || "-") + "</td>" +
            '<td class="col-team">' + hands(r) + "</td>" +
            "<td>" + (has(age) ? age : "-") + "</td>" +
            '<td class="col-team">' + escapeHtml(status) + "</td>" +
            (injured ? '<td class="col-team">' + escapeHtml(r.note || "-") + "</td>" : "") + "</tr>"
          );
        }).join("")
      ).join("");
    }
    return '<div class="table-scroll"><table class="stats roster"><thead>' + head + "</thead><tbody>" + body + "</tbody></table></div>";
  }

  // ---------- 시즌 선수단 (구단 성적) ----------
  const rate = (v) => (has(v) ? fmt.rate(v) : "-");
  const dec2 = (v) => (has(v) ? fmt.dec2(v) : "-");
  const BAT_COLUMNS = [
    { key: "G", label: "G", desc: "경기" },
    { key: "PA", label: "PA", desc: "타석" },
    { key: "H", label: "H", desc: "안타" },
    { key: "HR", label: "HR", desc: "홈런" },
    { key: "RBI", label: "RBI", desc: "타점" },
    { key: "SB", label: "SB", desc: "도루" },
    { key: "BB", label: "BB", desc: "볼넷" },
    { key: "SO", label: "SO", desc: "삼진", asc: true },
    { key: "AVG", label: "AVG", desc: "타율", format: rate },
    { key: "OBP", label: "OBP", desc: "출루율", format: rate },
    { key: "SLG", label: "SLG", desc: "장타율", format: rate },
    { key: "OPS", label: "OPS", desc: "출루율 + 장타율", format: rate },
  ];
  const PIT_COLUMNS = [
    { key: "G", label: "G", desc: "경기" },
    { key: "GS", label: "GS", desc: "선발 등판" },
    { key: "W", label: "W", desc: "승" },
    { key: "L", label: "L", desc: "패", asc: true },
    { key: "SV", label: "SV", desc: "세이브" },
    { key: "HLD", label: "HLD", desc: "홀드" },
    { key: "outs", label: "IP", desc: "투구 이닝", format: (v) => (has(v) ? fmt.ip(v) : "-") },
    { key: "SO", label: "SO", desc: "탈삼진" },
    { key: "BB", label: "BB", desc: "볼넷 허용", asc: true },
    { key: "ERA", label: "ERA", desc: "평균자책점", format: dec2, asc: true },
    { key: "WHIP", label: "WHIP", desc: "이닝당 출루 허용", format: dec2, asc: true },
  ];

  function statTable(kind, title, rows, columns) {
    const [sortKey, sortDir] = state.sort[kind];
    const sign = sortDir === "asc" ? 1 : -1;
    const value = (r) => (sortKey === "num" ? (/^\d+$/.test(r.num) ? Number(r.num) : null) : sortKey === "age" ? seasonAge(r) : r[kind][sortKey]);
    // 값이 없는 선수는 정렬 방향과 관계없이 맨 아래에 둔다
    const sorted = rows.slice().sort((a, b) => {
      const x = value(a);
      const y = value(b);
      if (!has(x) || !has(y)) return has(x) ? -1 : has(y) ? 1 : a.name.localeCompare(b.name);
      return (x - y) * sign || a.name.localeCompare(b.name);
    });
    const th = (column, extra) => {
      const on = column.key === sortKey;
      return (
        '<th class="sortable ' + (extra || "") + (on ? " sorted" : "") + '" data-table="' + kind + '" data-key="' + column.key + '"' +
        (column.desc ? ' title="' + escapeHtml(column.desc) + '"' : "") +
        ' aria-sort="' + (on ? (sortDir === "asc" ? "ascending" : "descending") : "none") + '">' +
        escapeHtml(column.label) + (on ? (sortDir === "asc" ? " ▲" : " ▼") : "") + "</th>"
      );
    };
    const head =
      "<tr>" + th({ key: "num", label: "번호", asc: true }) + '<th class="col-name">선수</th><th class="col-team">' + (kind === "bat" ? "포지션" : "투타") + "</th>" +
      th({ key: "age", label: "나이", desc: "시즌 나이 (6월 30일 기준 만 나이)", asc: true }) +
      columns.map((column) => th(column)).join("") + "</tr>";
    const body = sorted.map((r) => {
      const stats = r[kind];
      const age = seasonAge(r);
      return (
        "<tr><td>" + (r.num ? escapeHtml(r.num) : "-") + "</td>" +
        '<td class="col-name">' + personLink(r) + "</td>" +
        '<td class="col-team">' + (kind === "bat" ? escapeHtml(r.pos || "-") : hands(r)) + "</td>" +
        '<td class="' + (sortKey === "age" ? "sorted" : "") + '">' + (has(age) ? age : "-") + "</td>" +
        columns.map((column) => {
          const v = stats[column.key];
          return '<td class="' + (column.key === sortKey ? "sorted" : "") + '">' + (column.format ? column.format(v) : has(v) ? v : "-") + "</td>";
        }).join("") + "</tr>"
      );
    }).join("");
    return (
      '<section class="standings-block"><h2>' + escapeHtml(title) + " " + rows.length + "명</h2>" +
      '<div class="table-scroll"><table class="stats roster"><thead>' + head + "</thead><tbody>" + body + "</tbody></table></div></section>"
    );
  }

  function seasonTables() {
    // 투수를 고르면 투수 성적표만, 야수 포지션을 고르면 타자 성적표만 보여준다. 야수의 등판 기록은 전체에서만 보인다
    const players = byPos(data.players);
    const pitcherView = state.pos === "P";
    const batters = pitcherView ? [] : players.filter((r) => r.bat && r.bat.PA > 0);
    const pitchers = state.pos && !pitcherView ? [] : players.filter((r) => r.pit && r.pit.outs + r.pit.G > 0);
    const idle = players.filter((r) => !batters.includes(r) && !pitchers.includes(r) && !(pitcherView && r.bat && r.bat.PA > 0));
    let html = (batters.length || !state.pos ? statTable("bat", "타자", batters, BAT_COLUMNS) : "") +
      (pitchers.length || !state.pos ? statTable("pit", "투수", pitchers, PIT_COLUMNS) : "");
    if (idle.length) {
      html +=
        '<section class="standings-block"><h2>출전 기록 없음 ' + idle.length + "명</h2>" +
        '<p class="idle-list">' + idle.map((r) => personLink(r) + ' <span class="muted">' + escapeHtml(r.pos || "") + "</span>").join(" · ") + "</p></section>";
    }
    return html;
  }

  // ---------- 선수 이동 ----------
  // 묶음: 화면의 거르기 단위. type은 scripts/rosters.py의 classify_move와 같다.
  const MOVE_GROUPS = [
    { key: "up", label: "콜업", types: ["up", "select"] },
    { key: "down", label: "강등·양도지명", types: ["option", "outright", "dfa"] },
    { key: "il", label: "부상자·휴가 명단", types: ["il_on", "il_off", "il_move", "leave_on", "leave_off"] },
    { key: "trans", label: "영입·이적", types: ["trade_in", "trade_out", "claim_in", "claim_out", "sign", "release", "fa"] },
  ];
  const MOVE_LABEL = {
    up: "콜업", select: "콜업 (계약 선택)", option: "옵션 강등", outright: "아웃라이트", dfa: "양도지명 (DFA)",
    il_on: "IL 등록", il_off: "IL 복귀", il_move: "IL 이동", leave_on: "휴가 명단 등록", leave_off: "휴가 명단 복귀",
    trade_in: "트레이드 영입", trade_out: "트레이드 이적", claim_in: "웨이버 영입", claim_out: "웨이버 이탈",
    sign: "FA 계약", release: "방출", fa: "FA 선언",
  };
  const LEAVE = { paternity: "출산휴가 명단", bereavement: "경조사 명단" };
  const groupOf = (type) => MOVE_GROUPS.find((group) => group.types.includes(type));

  // 상대 구단 표시: 산하 구단은 레벨과 현재 이름, 모르는 구단은 원본 이름
  function clubText(team) {
    if (!team) return "";
    const known = clubs[team.id];
    return known ? (known.level === "MLB" ? "" : known.level + " ") + known.name : team.name;
  }

  function moveDetail(m) {
    const club = clubText(m.team);
    switch (m.type) {
      case "up":
      case "select":
      case "trade_in":
      case "claim_in":
        return club ? "← " + escapeHtml(club) : "";
      case "option":
      case "outright":
      case "trade_out":
      case "claim_out":
        return club ? "→ " + escapeHtml(club) : "";
      case "il_on":
      case "il_move":
      case "il_off": {
        const parts = [];
        if (m.days) parts.push(m.days + "일 IL" + (m.type === "il_move" ? "로 이동" : ""));
        if (m.note) parts.push(escapeHtml(m.note));
        if (m.retro && m.retro !== m.date) parts.push('<span class="muted">' + escapeHtml(m.retro) + " 소급</span>");
        return parts.join(" · ");
      }
      case "leave_on":
      case "leave_off":
        return LEAVE[m.list] || "";
      default:
        return "";
    }
  }

  // 이동이 있는 달 (최신 달이 먼저. 사이트의 기간 선택 상자는 모두 내림차순)
  const moveMonths = () => [...new Set((data.moves || []).map((m) => (m.date || "").slice(0, 7)).filter(Boolean))].sort().reverse();

  // 월 거르기: 이동이 있는 달만 고를 수 있다. 건수는 종류 거르기를 적용한 값
  function monthSelect(byType) {
    const months = moveMonths();
    const count = (month) => byType.filter((m) => (m.date || "").startsWith(month)).length;
    return (
      '<label class="field"><span>기간</span><select id="monthSelect">' +
      '<option value="">' + state.season + "년 전체 (" + byType.length + ")</option>" +
      months.map((month) =>
        '<option value="' + month + '"' + (month === state.month ? " selected" : "") + (count(month) || month === state.month ? "" : " disabled") + ">" +
        Number(month.slice(5)) + "월 (" + count(month) + ")</option>"
      ).join("") + "</select></label>"
    );
  }

  function movesTable() {
    // 다른 시즌으로 바꾸면 고른 달이 없을 수 있다
    if (!moveMonths().includes(state.month)) state.month = "";
    const byMonth = (data.moves || []).filter((m) => !state.month || (m.date || "").startsWith(state.month));
    const all = byMonth; // 종류별 건수는 고른 달 기준
    const group = MOVE_GROUPS.find((g) => g.key === state.move);
    const byType = group ? (data.moves || []).filter((m) => group.types.includes(m.type)) : data.moves || [];
    const rows = (group ? all.filter((m) => group.types.includes(m.type)) : all).slice();
    // 저장된 순서는 최신순. 날짜 열을 누르면 오래된 순으로 바꾼다
    if (!state.moveDesc) rows.reverse();
    const filters =
      '<div class="segmented move-filter" id="moveFilter" role="group" aria-label="이동 종류">' +
      [{ key: "", label: "전체", types: null }].concat(MOVE_GROUPS).map((g) => {
        const count = g.types ? all.filter((m) => g.types.includes(m.type)).length : all.length;
        return '<button type="button" data-move="' + g.key + '" aria-pressed="' + (g.key === state.move) + '">' + escapeHtml(g.label) + " " + count + "</button>";
      }).join("") + "</div>";
    const body = rows.length
      ? rows.map((m) => {
          const kind = groupOf(m.type);
          return (
            '<tr title="' + escapeHtml(m.desc || "") + '"><td class="col-team">' + escapeHtml(m.date || "-") + "</td>" +
            '<td class="col-team"><span class="move-tag move-' + (kind ? kind.key : "etc") + '">' + escapeHtml(MOVE_LABEL[m.type] || m.type) + "</span></td>" +
            '<td class="col-name">' + personLink(m) + "</td>" +
            '<td class="col-team move-detail">' + (moveDetail(m) || '<span class="muted">-</span>') + "</td></tr>"
          );
        }).join("")
      : '<tr><td class="empty" colspan="4">해당하는 이동이 없습니다.</td></tr>';
    return (
      '<div class="move-toolbar">' + filters + monthSelect(byType) + "</div>" +
      '<div class="table-scroll"><table class="stats roster moves"><thead><tr>' +
      '<th class="col-team sortable sorted" data-move-sort="date" aria-sort="' + (state.moveDesc ? "descending" : "ascending") + '" title="누르면 날짜 순서를 바꿉니다">날짜 ' + (state.moveDesc ? "▼" : "▲") + "</th>" +
      '<th class="col-team">구분</th>' +
      '<th class="col-name">선수</th><th class="col-team">내용</th></tr></thead><tbody>' + body + "</tbody></table></div>"
    );
  }

  // ---------- 화면 ----------
  function render() {
    const list = views();
    if (!list.some((v) => v.key === state.view)) state.view = list[0].key;
    const view = list.find((v) => v.key === state.view);
    $("viewSwitch").innerHTML = list.map((v) =>
      '<button type="button" data-value="' + v.key + '" aria-pressed="' + (v.key === state.view) + '">' +
      escapeHtml(v.label) + " " + v.rows.length + "</button>"
    ).join("");

    // 포지션 선택은 선수 명단에만 둔다(선수 이동 제외). 숫자는 지금 명단에서 그 포지션 선수 수
    $("posSwitch").hidden = view.key === "moves";
    $("posSwitch").innerHTML = POS_FILTERS.map((f) =>
      '<button type="button" data-value="' + f.key + '" aria-pressed="' + (f.key === state.pos) + '">' +
      escapeHtml(f.label) + " " + byPos(view.rows, f).length + "</button>"
    ).join("");

    const snapshot = view.key !== "season" && view.key !== "moves";
    $("content").innerHTML = view.key === "moves" ? movesTable() : snapshot ? snapshotTable(view) : seasonTables();
    $("rosterDate").textContent = snapshot ? data.date + " 기준" : "";
    $("rosterNote").textContent = snapshot
      ? IN_SEASON.includes(data.phase)
        ? "액티브 로스터는 26인(9월부터 28인)입니다. 40인 로스터는 액티브 선수와 마이너리그에 내려간 선수, 단기 부상자 명단 선수를 포함하고 60일 부상자 명단 선수는 규정에 따라 제외합니다. 나이는 기준일의 만 나이입니다."
        : "지금은 정규시즌이 아니어서 액티브 로스터(26인)가 없으므로 40인 로스터를 보여줍니다. 비시즌의 부상자 명단 표시는 원본에 남은 값이며 실제 명단 운영과 다를 수 있습니다. 나이는 기준일의 만 나이입니다."
      : view.key === "moves"
      ? state.season + "년 1~12월의 MLB 선수 이동입니다. 콜업은 리콜과 계약 선택(40인 명단에 새로 올리며 부르는 것, 첫 콜업인 경우가 많음)을 포함합니다. 마이너리그 내 배정, 마이너 계약, 등번호 변경은 넣지 않았습니다. 행에 마우스를 올리면 원문을 볼 수 있고, 부상 내용은 원문 그대로입니다."
      : "시즌 중 한 번이라도 구단 명단에 있었던 선수와 이 구단에서 거둔 정규시즌 기록입니다. 시즌 중 이적한 선수는 이 구단 기록만 셉니다. 등번호와 포지션은 원본의 마지막 값입니다. 나이는 그해 6월 30일 기준 만 나이입니다.";
    $("status").hidden = true;
    $("updatedText").textContent = "선수단 갱신: " + new Date(data.updated).toLocaleString("ko-KR");
    writeUrl();
  }

  function renderTeam() {
    document.title = "빠따넷 · " + team.name + " 선수단";
    $("teamName").textContent = team.name + " 선수단";
    $("teamSub").innerHTML = '<span class="level level-mlb">MLB</span> ' + escapeHtml(team.division || "");
    const box = $("teamLogo");
    box.innerHTML =
      '<source media="(prefers-color-scheme: dark)" srcset="' + LOGO_BASE + "team-cap-on-dark/" + team.id + '.svg">' +
      '<img src="' + LOGO_BASE + team.id + '.svg" alt="' + escapeHtml(team.name) + ' 로고" width="72" height="72">';
    box.querySelector("img").addEventListener("error", () => { box.hidden = true; });
    box.hidden = false;
  }

  function renderLinks() {
    $("teamLinks").innerHTML =
      '<a href="team.html?id=' + team.id + '">구단 정보</a>' +
      '<a href="leaderboard.html?league=mlb&season=' + state.season + "&team=" + encodeURIComponent(team.abbr) + '">' + state.season + " 리더보드</a>" +
      '<a href="standings.html' + (state.season === seasons[0] ? "" : "?season=" + state.season) + '">' + state.season + " 순위</a>";
  }

  function writeUrl() {
    const params = new URLSearchParams({ id: state.id });
    if (state.season !== seasons[0]) params.set("season", state.season);
    if (state.view) params.set("view", state.view);
    if (state.pos && state.view !== "moves") params.set("pos", state.pos);
    if (state.view === "moves" && state.move) params.set("move", state.move);
    if (state.view === "moves" && state.month) params.set("month", state.month);
    history.replaceState(null, "", "?" + params.toString());
  }

  async function loadSeason() {
    $("status").hidden = false;
    $("status").className = "status";
    $("status").textContent = "불러오는 중...";
    renderLinks();
    try {
      data = await loadJson("data/rosters/" + state.season + "/" + state.id + ".json");
    } catch (error) {
      data = null;
      $("content").innerHTML = "";
      $("viewSwitch").innerHTML = "";
      $("rosterNote").textContent = "";
      $("status").className = "status error";
      $("status").textContent = state.season + " 시즌 선수단을 불러오지 못했습니다: " + error.message;
      return;
    }
    render();
  }

  function bindEvents() {
    $("seasonSelect").addEventListener("change", () => {
      state.season = Number($("seasonSelect").value);
      loadSeason();
    });
    $("posSwitch").addEventListener("click", (event) => {
      const button = event.target.closest("button[data-value]");
      if (!button || !data) return;
      state.pos = button.dataset.value;
      render();
    });
    $("viewSwitch").addEventListener("click", (event) => {
      const button = event.target.closest("button[data-value]");
      if (!button || !data) return;
      state.view = button.dataset.value;
      render();
    });
    $("content").addEventListener("change", (event) => {
      if (event.target.id !== "monthSelect") return;
      state.month = event.target.value;
      render();
    });
    $("content").addEventListener("click", (event) => {
      if (event.target.closest("th[data-move-sort]")) {
        state.moveDesc = !state.moveDesc;
        render();
        return;
      }
      const filter = event.target.closest("button[data-move]");
      if (filter) {
        state.move = filter.dataset.move;
        render();
        return;
      }
      const th = event.target.closest("th[data-table]");
      if (!th) return;
      const kind = th.dataset.table;
      const key = th.dataset.key;
      const [current, dir] = state.sort[kind];
      if (current === key) {
        state.sort[kind] = [key, dir === "asc" ? "desc" : "asc"];
      } else {
        // '낮을수록 좋은' 열과 번호·나이는 오름차순, 나머지는 내림차순으로 시작
        const column = (kind === "bat" ? BAT_COLUMNS : PIT_COLUMNS).find((c) => c.key === key);
        state.sort[kind] = [key, key === "num" || key === "age" || (column && column.asc) ? "asc" : "desc"];
      }
      render();
    });
  }

  function fail(message) {
    $("status").className = "status error";
    $("status").textContent = message;
  }

  async function init() {
    const params = new URLSearchParams(location.search);
    state.id = Number(params.get("id"));
    state.view = params.get("view") || "";
    if (["P", "C", "IF", "OF"].includes(params.get("pos"))) state.pos = params.get("pos");
    state.move = params.get("move") || "";
    state.month = /^\d{4}-\d{2}$/.test(params.get("month") || "") ? params.get("month") : "";
    try {
      const meta = await loadJson("data/meta.json");
      const mlb = meta.leagues.find((league) => league.id === "mlb");
      if (mlb && mlb.seasons.length) seasons = mlb.seasons.slice().sort((a, b) => b - a);
    } catch (error) {
      // meta.json이 없어도 기본 시즌 목록으로 진행한다
    }
    const season = Number(params.get("season"));
    state.season = seasons.includes(season) ? season : seasons[0];

    let teams;
    try {
      teams = await loadJson("data/teams.json");
    } catch (error) {
      fail("구단 데이터를 불러오지 못했습니다: " + error.message);
      return;
    }
    teams.clubs.forEach((club) => {
      clubs[club.id] = { name: club.name, level: "MLB" };
      club.affiliates.forEach((item) => (clubs[item.id] = { name: item.name, level: item.level }));
    });
    team = teams.clubs.find((club) => club.id === state.id);
    if (!team) {
      fail("MLB 구단을 찾을 수 없습니다. 선수단은 MLB 구단만 제공합니다. 구단 목록에서 다시 선택해 주세요.");
      return;
    }
    renderTeam();
    $("seasonSelect").innerHTML = seasons.map((s) => '<option value="' + s + '">' + s + "</option>").join("");
    $("seasonSelect").value = state.season;
    bindEvents();
    loadSeason();
  }

  init();
})();
