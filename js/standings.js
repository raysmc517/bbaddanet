// 빠따넷 순위
// data/standings_{시즌}.json을 읽어 리그·지구별 순위표와 MLB 와일드카드 순위표를 그린다.

(function () {
  "use strict";

  const { escapeHtml, loadJson, fmt, has } = window.BB;
  const $ = (id) => document.getElementById(id);

  const FALLBACK_SEASONS = [2026, 2025, 2024];
  const HALF_NAMES = { firstHalf: "전반기", secondHalf: "후반기" };
  const DIRECTIONS = { East: "동부", West: "서부", Central: "중부", North: "북부", South: "남부", Northeast: "북동부", Southwest: "남서부" };
  // MLB 순위표의 확정 표시 (원본 clinchIndicator). 마이너리그 표시는 뜻이 공개돼 있지 않아 보여주지 않는다.
  const CLINCH = {
    z: "리그 1·2번 시드 확정 (와일드카드 시리즈 면제)",
    y: "지구 우승 확정",
    w: "와일드카드 확정",
    x: "포스트시즌 진출 확정",
    e: "포스트시즌 탈락 확정",
  };

  const record = (pair) => (pair ? pair[0] + "-" + pair[1] : "-");
  const pct = (t) => (t.W + t.L ? t.W / (t.W + t.L) : null);
  const back = (value) => (!has(value) ? "-" : value === 0 ? "-" : value.toFixed(1));
  const signed = (value) => (!has(value) ? "-" : value > 0 ? "+" + value : String(value));
  const diff = (t) => (has(t.RS) && has(t.RA) ? t.RS - t.RA : null);
  const luck = (t) => (has(t.xW) ? t.W - t.xW : null);

  function streak(code) {
    const match = /^([WL])(\d+)$/.exec(code || "");
    return match ? match[2] + (match[1] === "W" ? "연승" : "연패") : "-";
  }

  // 와일드카드 승차: 진출권 안쪽 팀은 음수로 저장돼 있으므로 '+'를 붙여 앞선 만큼 보여준다
  function wildCardBack(value) {
    if (!has(value)) return "-";
    if (value === 0) return "-";
    return value < 0 ? "+" + (-value).toFixed(1) : value.toFixed(1);
  }

  // 'AL East' → 'AL 동부', 'INT West' → 'INT 서부'. 방향이 아니면 그대로
  function divisionLabel(short) {
    return String(short || "").split(" ").map((word) => DIRECTIONS[word] || word).join(" ");
  }

  // value: 정렬 값, text: 표시. asc: 낮을수록 좋은 열(처음 누르면 오름차순)
  const BASE_COLUMNS = [
    { key: "G", label: "경기", value: (t) => t.W + t.L, text: (t) => t.W + t.L },
    { key: "W", label: "승", value: (t) => t.W, text: (t) => t.W },
    { key: "L", label: "패", asc: true, value: (t) => t.L, text: (t) => t.L },
    { key: "pct", label: "승률", value: pct, text: (t) => (has(pct(t)) ? fmt.rate(pct(t)) : "-") },
  ];
  const GB = { key: "GB", label: "승차", desc: "지구(리그) 1위와의 승차", asc: true, value: (t) => t.GB, text: (t) => back(t.GB) };
  const WCGB = { key: "wcGB", label: "WC 승차", desc: "와일드카드 마지막 진출 팀과의 승차. +는 앞선 경기 수", asc: true, value: (t) => t.wcGB, text: (t) => wildCardBack(t.wcGB) };
  const TAIL_COLUMNS = [
    { key: "home", label: "홈", value: (t) => (t.home ? t.home[0] / Math.max(t.home[0] + t.home[1], 1) : null), text: (t) => record(t.home) },
    { key: "away", label: "원정", value: (t) => (t.away ? t.away[0] / Math.max(t.away[0] + t.away[1], 1) : null), text: (t) => record(t.away) },
    { key: "last10", label: "최근 10", desc: "최근 10경기 승패", value: (t) => (t.last10 ? t.last10[0] : null), text: (t) => record(t.last10) },
    { key: "streak", label: "연속", value: (t) => { const m = /^([WL])(\d+)$/.exec(t.streak || ""); return m ? (m[1] === "W" ? 1 : -1) * Number(m[2]) : null; }, text: (t) => streak(t.streak) },
    { key: "RS", label: "득점", value: (t) => t.RS, text: (t) => (has(t.RS) ? t.RS : "-") },
    { key: "RA", label: "실점", asc: true, value: (t) => t.RA, text: (t) => (has(t.RA) ? t.RA : "-") },
    { key: "diff", label: "득실", desc: "득점 - 실점", value: diff, text: (t) => signed(diff(t)) },
    { key: "xW", label: "기대 승패", desc: "피타고리안 기대 승패 (자체 계산, 지수 1.83)", value: (t) => t.xW, text: (t) => (has(t.xW) ? t.xW + "-" + t.xL : "-") },
    { key: "luck", label: "차이", desc: "실제 승수 - 기대 승수", value: luck, text: (t) => signed(luck(t)) },
  ];
  // 잔여 경기: 리그의 팀당 경기 수 - 치른 경기. 화면을 그릴 때 리그 경기 수를 넣어 만든다
  const remainingColumn = (games) => ({
    key: "left",
    label: "잔여",
    desc: "남은 정규시즌 경기 (팀당 " + games + "경기 기준)",
    value: (t) => Math.max(games - t.W - t.L, 0),
    text: (t) => Math.max(games - t.W - t.L, 0),
  });
  const MAGIC = { key: "magic", label: "매직넘버", desc: "지구 우승 매직넘버", asc: true, value: (t) => t.magic, text: (t) => (has(t.magic) ? t.magic : "-") };

  const state = { level: "mlb", season: null, league: "", half: "", sortKey: "rank", sortDir: "asc" };
  let seasons = FALLBACK_SEASONS;
  let data = null;
  let pages = new Set(); // 구단 페이지가 있는 팀 ID (data/teams.json)

  function readUrl() {
    const params = new URLSearchParams(location.search);
    if (params.get("level")) state.level = params.get("level");
    if (/^\d{4}$/.test(params.get("season") || "")) state.season = Number(params.get("season"));
    if (params.get("league")) state.league = params.get("league");
    if (HALF_NAMES[params.get("half")]) state.half = params.get("half");
  }

  function writeUrl() {
    const params = new URLSearchParams();
    if (state.level !== "mlb") params.set("level", state.level);
    if (state.season !== seasons[0]) params.set("season", state.season);
    if (state.league) params.set("league", state.league);
    if (state.half) params.set("half", state.half);
    const query = params.toString();
    history.replaceState(null, "", query ? "?" + query : location.pathname);
  }

  const currentLevel = () => data.levels.find((level) => level.id === state.level) || data.levels[0];
  const isMlb = () => currentLevel().id === "mlb";

  // MLB 구단 ID → 약칭 (마이너리그 구단의 모구단 표시용)
  function parentAbbr() {
    const mlb = data.levels.find((level) => level.id === "mlb");
    const map = {};
    if (mlb) mlb.leagues.forEach((league) => league.divisions.forEach((division) => division.teams.forEach((t) => (map[t.id] = t.abbr))));
    return map;
  }

  // columns: 이 표에 보이는 열 (잔여 경기처럼 리그마다 만드는 열도 찾기 위해)
  function sortTeams(teams, columns) {
    const rows = teams.map((team, index) => ({ team, rank: index + 1 }));
    if (state.sortKey === "rank") return rows;
    const column = columns.find((c) => c.key === state.sortKey);
    if (!column) return rows;
    const sign = state.sortDir === "asc" ? 1 : -1;
    // 값이 없는 팀은 정렬 방향과 관계없이 맨 아래에 둔다
    return rows.slice().sort((a, b) => {
      const x = column.value(a.team);
      const y = column.value(b.team);
      if (!has(x) || !has(y)) return has(x) ? -1 : has(y) ? 1 : a.rank - b.rank;
      return (x - y) * sign || a.rank - b.rank;
    });
  }

  function headCell(column, extraClass) {
    const sorted = state.sortKey === column.key;
    const mark = sorted && column.key !== "rank" ? (state.sortDir === "asc" ? " ▲" : " ▼") : "";
    const classes = ["sortable", extraClass, sorted ? "sorted" : ""].filter(Boolean).join(" ");
    return (
      '<th class="' + classes + '" data-key="' + column.key + '"' +
      (column.desc ? ' title="' + escapeHtml(column.desc) + '"' : "") +
      ' aria-sort="' + (sorted && column.key !== "rank" ? (state.sortDir === "asc" ? "ascending" : "descending") : "none") + '">' +
      escapeHtml(column.label) + mark + "</th>"
    );
  }

  function teamCell(team, parents) {
    const name = pages.has(team.id) ? '<a href="team.html?id=' + team.id + '">' + escapeHtml(team.name) + "</a>" : escapeHtml(team.name);
    const clinch = isMlb() && CLINCH[team.clinch]
      ? ' <span class="clinch" title="' + escapeHtml(CLINCH[team.clinch]) + '">' + escapeHtml(team.clinch) + "</span>"
      : "";
    const parent = !isMlb() && parents[team.parentId] ? '<span class="team-note">' + escapeHtml(parents[team.parentId]) + "</span>" : "";
    return '<td class="col-name">' + name + clinch + parent + "</td>";
  }

  // cutoff: 이 순위까지 진출권. 그 아래에 구분선을 긋는다 (정렬하지 않았을 때만)
  function table(title, teams, columns, cutoff) {
    const parents = parentAbbr();
    const rows = sortTeams(teams, columns);
    const head =
      "<tr>" + headCell({ key: "rank", label: "#" }, "col-rank") + '<th class="col-name">구단</th>' +
      columns.map((column) => headCell(column)).join("") + "</tr>";
    const body = rows.map(({ team, rank }) => {
      const line = state.sortKey === "rank" && cutoff && rank === cutoff ? ' class="cutoff"' : "";
      return (
        "<tr" + line + '><td class="col-rank">' + rank + "</td>" + teamCell(team, parents) +
        columns.map((column) => '<td class="' + (state.sortKey === column.key ? "sorted" : "") + '">' + column.text(team) + "</td>").join("") +
        "</tr>"
      );
    }).join("");
    return (
      '<section class="standings-block">' + (title ? "<h2>" + escapeHtml(title) + "</h2>" : "") +
      '<div class="table-scroll"><table class="stats standings"><thead>' + head + "</thead><tbody>" + body + "</tbody></table></div></section>"
    );
  }

  // 정규시즌이 아직 진행 중인지: 갱신 날짜(UTC)가 리그의 정규시즌 마지막 날 이하.
  // 마지막 날 경기는 다음 날 갱신에 반영되므로 그때부터 잔여 경기 열을 숨긴다.
  // 전·후반기 보기에서는 시즌 전체 경기 수 기준이 맞지 않아 숨긴다.
  function inProgress(league) {
    if (state.half || !league || !league.games || !league.endDate) return false;
    return String(data.updated).slice(0, 10) <= league.endDate;
  }

  function columnsFor(teams, gamesBack, league) {
    const base = inProgress(league) ? BASE_COLUMNS.slice(0, 1).concat([remainingColumn(league.games)], BASE_COLUMNS.slice(1)) : BASE_COLUMNS;
    const columns = base.concat([gamesBack], TAIL_COLUMNS);
    if (gamesBack === GB && teams.some((t) => has(t.magic))) columns.push(MAGIC);
    return columns;
  }

  function wildCardTable(league) {
    const teams = league.divisions.flatMap((division) => division.teams).filter((t) => has(t.wcRank));
    teams.sort((a, b) => a.wcRank - b.wcRank);
    if (!teams.length) return "";
    return table(league.abbr + " 와일드카드", teams, columnsFor(teams, WCGB, league), league.wildCards);
  }

  function renderLeague(league) {
    const divisions = state.half ? (league.halves || {})[state.half] || [] : league.divisions;
    // 지구가 없는 리그(예: Northwest League)는 리그 제목만 둔다
    const title = (division) => (division.name === league.name ? "" : divisionLabel(division.short));
    let html = '<div class="standings-league"><h2 class="standings-title">' + escapeHtml(league.name) + "</h2>";
    if (!divisions.length) {
      html += '<p class="status">' + escapeHtml(HALF_NAMES[state.half] || "") + " 순위가 없습니다.</p></div>";
      return html;
    }
    html += '<div class="standings-grid">' + divisions.map((division) => table(title(division), division.teams, columnsFor(division.teams, GB, league))).join("") + "</div>";
    if (isMlb() && league.wildCards) html += wildCardTable(league);
    return html + "</div>";
  }

  function renderControls() {
    $("levelSwitch").innerHTML = data.levels
      .map((level) => '<button type="button" data-value="' + level.id + '" aria-pressed="' + (level.id === currentLevel().id) + '">' + escapeHtml(level.name) + "</button>")
      .join("");
    const leagues = currentLevel().leagues;
    if (!leagues.some((league) => String(league.id) === state.league)) state.league = "";
    $("leagueSelect").innerHTML =
      '<option value="">전체</option>' +
      leagues.map((league) => '<option value="' + league.id + '">' + escapeHtml(isMlb() ? league.abbr + " · " + league.name : league.name) + "</option>").join("");
    $("leagueSelect").value = state.league;
    const split = leagues.some((league) => league.halves && Object.keys(league.halves).length);
    $("halfSwitch").hidden = !split;
    if (!split) state.half = "";
    $("halfSwitch").querySelectorAll("button").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.value === state.half)));
  }

  function render() {
    renderControls();
    const level = currentLevel();
    const leagues = level.leagues.filter((league) => !state.league || String(league.id) === state.league);
    $("content").innerHTML = leagues.map(renderLeague).join("");
    const teams = leagues.reduce((sum, league) => sum + league.divisions.reduce((n, division) => n + division.teams.length, 0), 0);
    $("status").className = "status";
    $("status").textContent = data.season + " " + level.name + " 정규시즌" + (state.half ? " " + HALF_NAMES[state.half] : "") + " · " + teams + "개 구단";
    $("legend").innerHTML = isMlb()
      ? "확정 표시: " + Object.entries(CLINCH).map(([mark, text]) => '<b class="clinch">' + mark + "</b> " + escapeHtml(text)).join(" · ") +
        ". 와일드카드 표의 굵은 선 위가 진출권(리그당 3팀)입니다."
      : "구단 이름 옆 약칭은 MLB 모구단입니다. 마이너리그는 대부분 전·후반기 우승팀이 플레이오프에 나가므로 기간을 바꿔 확인하세요.";
    $("updatedText").textContent = "순위 갱신: " + new Date(data.updated).toLocaleString("ko-KR");
    writeUrl();
  }

  async function loadSeason() {
    $("status").className = "status";
    $("status").textContent = "불러오는 중...";
    try {
      data = await loadJson("data/standings_" + state.season + ".json");
    } catch (error) {
      data = null;
      $("content").innerHTML = "";
      $("status").className = "status error";
      $("status").textContent = state.season + " 시즌 순위를 불러오지 못했습니다: " + error.message;
      return;
    }
    if (!data.levels.some((level) => level.id === state.level)) state.level = data.levels[0].id;
    render();
  }

  function bindEvents() {
    $("seasonSelect").addEventListener("change", () => {
      state.season = Number($("seasonSelect").value);
      loadSeason();
    });
    $("levelSwitch").addEventListener("click", (event) => {
      const button = event.target.closest("button[data-value]");
      if (!button || !data) return;
      state.level = button.dataset.value;
      state.league = "";
      render();
    });
    $("leagueSelect").addEventListener("change", () => {
      state.league = $("leagueSelect").value;
      render();
    });
    $("halfSwitch").addEventListener("click", (event) => {
      const button = event.target.closest("button[data-value]");
      if (!button || !data) return;
      state.half = button.dataset.value;
      render();
    });
    $("content").addEventListener("click", (event) => {
      const th = event.target.closest("th[data-key]");
      if (!th) return;
      const key = th.dataset.key;
      if (key === "rank") {
        state.sortKey = "rank";
        state.sortDir = "asc";
      } else if (state.sortKey === key) {
        state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      } else {
        const column = [GB, WCGB, MAGIC].concat(BASE_COLUMNS, TAIL_COLUMNS).find((c) => c.key === key);
        state.sortKey = key;
        state.sortDir = column && column.asc ? "asc" : "desc";
      }
      render();
    });
  }

  async function init() {
    readUrl();
    try {
      const meta = await loadJson("data/meta.json");
      const mlb = meta.leagues.find((league) => league.id === "mlb");
      if (mlb && mlb.seasons.length) seasons = mlb.seasons.slice().sort((a, b) => b - a);
    } catch (error) {
      // meta.json이 없어도 기본 시즌 목록으로 진행한다
    }
    try {
      const teams = await loadJson("data/teams.json");
      teams.clubs.forEach((club) => {
        pages.add(club.id);
        club.affiliates.forEach((item) => pages.add(item.id));
      });
    } catch (error) {
      pages = new Set(); // 구단 정보가 없으면 링크 없이 이름만 보여준다
    }
    if (!seasons.includes(state.season)) state.season = seasons[0];
    $("seasonSelect").innerHTML = seasons.map((season) => '<option value="' + season + '">' + season + "</option>").join("");
    $("seasonSelect").value = state.season;
    bindEvents();
    loadSeason();
  }

  init();
})();
