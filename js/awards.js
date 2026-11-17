// 빠따넷 수상 기록
// data/awards.json (명예의 전당과 역대 수상자)을 읽어 상별 표로 그린다.

(function () {
  "use strict";

  const { escapeHtml, loadJson, has } = window.BB;
  const $ = (id) => document.getElementById(id);

  // value: 정렬에 쓰는 값. left: 왼쪽 정렬 열
  const COLUMNS = [
    { key: "season", label: "시즌", value: (r) => r.season },
    { key: "league", label: "리그", left: true, value: (r) => r.league },
    { key: "name", label: "선수", left: true, value: (r) => r.name },
    { key: "pos", label: "포지션", left: true, value: (r) => r.pos },
    { key: "team", label: "팀", left: true, value: (r) => r.team },
    { key: "count", label: "통산", desc: "이 상을 받은 통산 횟수", value: (r) => r.count },
  ];

  const state = { award: "hof", league: "", season: "", search: "", sortKey: "season", sortDir: "desc" };
  let data = null;
  let rowsByAward = {}; // 상 키 → 행 목록

  // 원본 행 [상 키, 시즌, 리그, 선수 ID, 팀]을 표시용 객체로 바꾸고 상별 통산 횟수를 붙인다
  function prepare() {
    const counts = {};
    data.rows.forEach((row) => {
      const mark = row[0] + ":" + row[3];
      counts[mark] = (counts[mark] || 0) + 1;
    });
    data.rows.forEach((row) => {
      const person = data.people[row[3]] || ["", "", 0];
      (rowsByAward[row[0]] = rowsByAward[row[0]] || []).push({
        season: row[1],
        league: row[2],
        id: row[3],
        team: row[4],
        name: person[0],
        pos: person[1],
        page: person[2] === 1,
        count: counts[row[0] + ":" + row[3]],
      });
    });
  }

  function readUrl() {
    const params = new URLSearchParams(location.search);
    if (params.get("award")) state.award = params.get("award");
    if (["AL", "NL"].includes(params.get("league"))) state.league = params.get("league");
    if (/^\d{4}$/.test(params.get("season") || "")) state.season = params.get("season");
    if (params.get("q")) state.search = params.get("q");
    if (params.get("sort")) {
      state.sortKey = params.get("sort");
      state.sortDir = params.get("dir") === "asc" ? "asc" : "desc";
    }
  }

  function writeUrl() {
    const params = new URLSearchParams();
    if (state.award !== "hof") params.set("award", state.award);
    if (state.league) params.set("league", state.league);
    if (state.season) params.set("season", state.season);
    if (state.search) params.set("q", state.search);
    if (state.sortKey !== "season" || state.sortDir !== "desc") {
      params.set("sort", state.sortKey);
      params.set("dir", state.sortDir);
    }
    const query = params.toString();
    history.replaceState(null, "", query ? "?" + query : location.pathname);
  }

  const awardRows = () => rowsByAward[state.award] || [];
  const hasLeagues = () => awardRows().some((r) => r.league);

  // 상을 바꾸면 그 상에 없는 리그·시즌 조건은 푼다
  function renderFilters() {
    $("leagueField").hidden = !hasLeagues();
    if (!hasLeagues()) state.league = "";
    $("leagueSelect").value = state.league;

    const seasons = [...new Set(awardRows().map((r) => r.season))].sort((a, b) => b - a);
    if (!seasons.includes(Number(state.season))) state.season = "";
    $("seasonLabel").textContent = state.award === "hof" ? "헌액 연도" : "시즌";
    $("seasonSelect").innerHTML =
      '<option value="">전체</option>' + seasons.map((s) => '<option value="' + s + '">' + s + "</option>").join("");
    $("seasonSelect").value = state.season;
  }

  // 값이 없는 행은 정렬 방향과 관계없이 맨 아래에 둔다. 같은 값이면 최근 시즌, 이름 순
  function sortRows(rows) {
    const column = COLUMNS.find((c) => c.key === state.sortKey) || COLUMNS[0];
    const sign = state.sortDir === "asc" ? 1 : -1;
    return rows.slice().sort((a, b) => {
      const x = column.value(a);
      const y = column.value(b);
      if (!has(x) || !has(y)) {
        if (has(x) !== has(y)) return has(x) ? -1 : 1;
      } else {
        const diff = typeof x === "number" ? x - y : String(x).localeCompare(String(y));
        if (diff) return diff * sign;
      }
      return b.season - a.season || a.name.localeCompare(b.name);
    });
  }

  function headCell(column) {
    const sorted = state.sortKey === column.key;
    const mark = sorted ? (state.sortDir === "asc" ? " ▲" : " ▼") : "";
    const label = column.key === "season" && state.award === "hof" ? "헌액 연도" : column.label;
    const classes = ["sortable", column.key === "name" ? "col-name" : column.left ? "col-team" : "", sorted ? "sorted" : ""].filter(Boolean).join(" ");
    return (
      '<th class="' + classes + '" data-key="' + column.key + '"' +
      (column.desc ? ' title="' + escapeHtml(column.desc) + '"' : "") +
      ' aria-sort="' + (sorted ? (state.sortDir === "asc" ? "ascending" : "descending") : "none") + '">' +
      escapeHtml(label) + mark + "</th>"
    );
  }

  function bodyCell(column, row) {
    const sortedClass = state.sortKey === column.key ? " sorted" : "";
    if (column.key === "name") {
      const name = escapeHtml(row.name || "-");
      return '<td class="col-name' + sortedClass + '">' + (row.page ? '<a href="player.html?id=' + row.id + '">' + name + "</a>" : name) + "</td>";
    }
    const value = column.value(row);
    const text = column.key === "count" ? value + "회" : has(value) ? escapeHtml(value) : "-";
    return '<td class="' + (column.left ? "col-team" : "") + sortedClass + '">' + text + "</td>";
  }

  function render() {
    const all = awardRows();
    // 리그 구분이 없는 상은 리그 열을, 모두 1회뿐인 상은 통산 열을 뺀다
    const columns = COLUMNS.filter((column) => {
      if (column.key === "league") return hasLeagues();
      if (column.key === "count") return all.some((r) => r.count > 1);
      return true;
    });
    if (!columns.some((column) => column.key === state.sortKey)) {
      state.sortKey = "season";
      state.sortDir = "desc";
    }

    const keyword = state.search.trim().toLowerCase();
    const rows = sortRows(
      all.filter((r) => {
        if (state.league && r.league !== state.league) return false;
        if (state.season && r.season !== Number(state.season)) return false;
        if (keyword && !(r.name + " " + r.team).toLowerCase().includes(keyword)) return false;
        return true;
      })
    );

    $("tableHead").innerHTML = "<tr>" + columns.map(headCell).join("") + "</tr>";
    $("tableBody").innerHTML = rows.length
      ? rows.map((row) => "<tr>" + columns.map((column) => bodyCell(column, row)).join("") + "</tr>").join("")
      : '<tr><td class="empty" colspan="' + columns.length + '">조건에 맞는 수상 기록이 없습니다.</td></tr>';

    const award = data.awards.find((a) => a.key === state.award);
    const seasons = all.map((r) => r.season);
    $("status").className = "status";
    $("status").textContent = all.length
      ? award.name + " · " + Math.min(...seasons) + "~" + Math.max(...seasons) + " · " + rows.length.toLocaleString("ko-KR") + "건" +
        (state.award === "hof" ? "" : " (수상자 " + new Set(rows.map((r) => r.id)).size.toLocaleString("ko-KR") + "명)")
      : "수상 기록이 없습니다.";
    writeUrl();
  }

  function bindEvents() {
    $("awardSelect").addEventListener("change", () => {
      state.award = $("awardSelect").value;
      renderFilters();
      render();
    });
    $("leagueSelect").addEventListener("change", () => {
      state.league = $("leagueSelect").value;
      render();
    });
    $("seasonSelect").addEventListener("change", () => {
      state.season = $("seasonSelect").value;
      render();
    });
    $("searchInput").addEventListener("input", () => {
      state.search = $("searchInput").value;
      render();
    });
    $("tableHead").addEventListener("click", (event) => {
      const th = event.target.closest("th[data-key]");
      if (!th) return;
      const column = COLUMNS.find((c) => c.key === th.dataset.key);
      if (state.sortKey === column.key) {
        state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      } else {
        // 글자 열은 오름차순, 숫자 열은 내림차순으로 시작
        state.sortKey = column.key;
        state.sortDir = column.left ? "asc" : "desc";
      }
      render();
    });
  }

  async function init() {
    readUrl();
    try {
      data = await loadJson("data/awards.json");
    } catch (error) {
      $("status").className = "status error";
      $("status").textContent = "수상 기록을 불러오지 못했습니다: " + error.message;
      return;
    }
    prepare();
    if (!data.awards.some((a) => a.key === state.award)) state.award = "hof";
    $("awardSelect").innerHTML = data.awards
      .map((a) => '<option value="' + escapeHtml(a.key) + '">' + escapeHtml(a.name) + "</option>")
      .join("");
    $("awardSelect").value = state.award;
    $("searchInput").value = state.search;
    renderFilters();
    bindEvents();
    render();
    $("updatedText").textContent = "수상 기록 갱신: " + new Date(data.updated).toLocaleString("ko-KR");
  }

  init();
})();
