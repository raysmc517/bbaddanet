// 빠따넷 유망주 페이지
// data/milb/prospects.json (MLB Pipeline 랭킹 + 올 시즌 성적)을 읽어 표로 그린다.

(function () {
  "use strict";

  const { fmt, escapeHtml, loadJson } = window.BB;

  const LEVEL_ORDER = ["MLB", "AAA", "AA", "A+", "A", "ROK"];
  const STAT_LEVELS = ["MLB", "AAA", "AA", "A+", "A", "High-A", "Single-A", "Low-A"]; // 성적을 제공하는 레벨

  const $ = (id) => document.getElementById(id);
  const state = { list: "top100", type: "", level: "", search: "" };
  let data = null;

  const isPitcher = (pos) => pos.includes("HP") || ["P", "SP", "RP"].includes(pos);
  const levelLabel = (level) => ({ "A+": "High-A", A: "Single-A", ROK: "Rookie" }[level] || level);
  const levelBadge = (level) =>
    level ? '<span class="level' + (level === "MLB" ? " level-mlb" : "") + '">' + escapeHtml(levelLabel(level)) + "</span>" : "-";

  function weekLabel(week) {
    const parts = week.split("-W");
    return parts[0] + "년 " + Number(parts[1]) + "주차";
  }

  function currentPlayers() {
    if (state.list === "top100") return data.top100;
    const team = data.teams.find((item) => item.abbr === state.list);
    return team ? team.players : [];
  }

  function readUrl() {
    const params = new URLSearchParams(location.search);
    if (params.get("list")) state.list = params.get("list");
    if (["bat", "pit"].includes(params.get("type"))) state.type = params.get("type");
    if (params.get("level")) state.level = params.get("level");
    if (params.get("q")) state.search = params.get("q");
  }

  function writeUrl() {
    const params = new URLSearchParams();
    if (state.list !== "top100") params.set("list", state.list);
    if (state.type) params.set("type", state.type);
    if (state.level) params.set("level", state.level);
    if (state.search) params.set("q", state.search);
    const query = params.toString();
    history.replaceState(null, "", query ? "?" + query : location.pathname);
  }

  function renderListSelect() {
    const options = [{ value: "top100", label: "전체 Top 100" }].concat(
      data.teams.map((team) => ({ value: team.abbr, label: team.abbr + " · " + team.name }))
    );
    $("listSelect").innerHTML = options
      .map((option) => '<option value="' + escapeHtml(option.value) + '">' + escapeHtml(option.label) + "</option>")
      .join("");
    if (!options.some((option) => option.value === state.list)) state.list = "top100";
    $("listSelect").value = state.list;
  }

  function renderLevelSelect() {
    const found = new Set(currentPlayers().map((p) => p.level).filter(Boolean));
    const levels = LEVEL_ORDER.filter((level) => found.has(level)).concat([...found].filter((level) => !LEVEL_ORDER.includes(level)).sort());
    $("levelSelect").innerHTML =
      '<option value="">전체</option>' +
      levels.map((level) => '<option value="' + escapeHtml(level) + '">' + escapeHtml(levelLabel(level)) + "</option>").join("");
    if (!levels.includes(state.level)) state.level = "";
    $("levelSelect").value = state.level;
  }

  // 지난주 대비 순위 변동
  function changeCell(player) {
    if (player.prev === null || player.prev === undefined) return '<span class="move move-new">NEW</span>';
    const diff = player.prev - player.rank;
    if (diff > 0) return '<span class="move move-up">▲' + diff + "</span>";
    if (diff < 0) return '<span class="move move-down">▼' + -diff + "</span>";
    return '<span class="move">-</span>';
  }

  function statLine(player) {
    const s = player.stat;
    if (!s) {
      const covered = STAT_LEVELS.includes(player.level);
      return '<span class="muted">' + (covered ? "올 시즌 기록 없음" : "해당 레벨 성적 미제공") + "</span>";
    }
    const parts =
      s.group === "pitching"
        ? [
            fmt.ip(s.outs) + "이닝",
            "ERA " + (s.ERA === null ? "-" : fmt.dec2(s.ERA)),
            "FIP " + (s.FIP === null ? "-" : fmt.dec2(s.FIP)),
            "K% " + (s.Kp === null ? "-" : (s.Kp * 100).toFixed(1)),
            "BB% " + (s.BBp === null ? "-" : (s.BBp * 100).toFixed(1)),
          ]
        : [
            s.PA + "타석",
            [s.AVG, s.OBP, s.SLG].map((v) => (v === null ? "-" : fmt.rate(v))).join("/"),
            s.HR + "홈런",
            s.SB + "도루",
            "wRC+ " + (s.wRCp === null ? "-" : s.wRCp),
          ];
    return levelBadge(s.level) + ' <span class="stat-line">' + parts.join(" · ") + "</span>";
  }

  function top100Ranks() {
    return new Map(data.top100.map((p) => [p.id, p.rank]));
  }

  function render() {
    const isTop100 = state.list === "top100";
    const hasPrev = !!data.previousWeek;
    const keyword = state.search.trim().toLowerCase();
    const rows = currentPlayers().filter((p) => {
      if (state.type && (state.type === "pit") !== isPitcher(p.pos)) return false;
      if (state.level && p.level !== state.level) return false;
      if (keyword && !(p.nameKo || "").toLowerCase().includes(keyword) && !p.name.toLowerCase().includes(keyword)) return false;
      return true;
    });

    // 구단 Top 30에서 같은 주 Top 100에 든 선수의 Top 100 순위
    const top100 = isTop100 ? null : top100Ranks();
    const top100Cell = (p) => (top100
      ? '<td class="col-top100">' + (top100.has(p.id) ? top100.get(p.id) + "위" : "-") + "</td>"
      : "");

    $("tableHead").innerHTML =
      '<tr><th class="col-rank">순위</th>' +
      (hasPrev ? '<th class="col-move" title="지난주 대비 순위 변동">변동</th>' : "") +
      '<th class="col-name">선수</th>' +
      (isTop100 ? '<th class="col-team">구단</th>' : "") +
      (isTop100 ? "" : '<th class="col-top100" title="같은 주 MLB Pipeline 전체 Top 100 순위. 없으면 Top 100 밖">Top 100</th>') +
      '<th class="col-team">포지션</th><th>나이</th><th class="col-team">현재 레벨</th>' +
      '<th title="MLB Pipeline이 예상하는 MLB 데뷔 연도">예상 데뷔</th>' +
      '<th class="col-team">' + data.season + " 성적</th></tr>";

    const columnCount = 7 + (hasPrev ? 1 : 0) + 1;
    $("tableBody").innerHTML = rows.length
      ? rows.map((p) =>
          '<tr><td class="col-rank">' + p.rank + "</td>" +
          (hasPrev ? '<td class="col-move">' + changeCell(p) + "</td>" : "") +
          '<td class="col-name"><a href="player.html?id=' + p.id + '">' + escapeHtml(p.nameKo || p.name) + "</a></td>" +
          (isTop100 ? '<td class="col-team">' + escapeHtml(p.org || "-") + "</td>" : "") +
          top100Cell(p) +
          '<td class="col-team">' + escapeHtml(p.pos || "-") + "</td>" +
          "<td>" + (p.age || "-") + "</td>" +
          '<td class="col-team" title="' + escapeHtml(p.club || "") + '">' + levelBadge(p.level) + "</td>" +
          "<td>" + escapeHtml(p.eta || "-") + "</td>" +
          '<td class="col-team">' + statLine(p) + "</td></tr>"
        ).join("")
      : '<tr><td class="empty" colspan="' + columnCount + '">조건에 맞는 선수가 없습니다.</td></tr>';

    const team = data.teams.find((item) => item.abbr === state.list);
    $("status").className = "status";
    $("status").textContent =
      "MLB Pipeline " + (isTop100 ? "Top 100" : team.name + " Top 30") +
      " · " + weekLabel(data.week) + " (" + data.date + " 기준) · " + rows.length + "명";
    writeUrl();
  }

  function bindEvents() {
    $("listSelect").addEventListener("change", () => {
      state.list = $("listSelect").value;
      renderLevelSelect();
      render();
    });
    $("typeSelect").addEventListener("change", () => {
      state.type = $("typeSelect").value;
      render();
    });
    $("levelSelect").addEventListener("change", () => {
      state.level = $("levelSelect").value;
      render();
    });
    $("searchInput").addEventListener("input", () => {
      state.search = $("searchInput").value;
      render();
    });
  }

  async function init() {
    readUrl();
    try {
      data = await loadJson("data/milb/prospects.json");
    } catch (error) {
      $("status").className = "status error";
      $("status").textContent = "유망주 데이터를 불러오지 못했습니다: " + error.message;
      return;
    }
    renderListSelect();
    renderLevelSelect();
    $("typeSelect").value = state.type;
    $("searchInput").value = state.search;
    bindEvents();
    render();
  }

  init();
})();
