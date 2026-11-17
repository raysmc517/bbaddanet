// 빠따넷 구단 목록
// data/teams.json (MLB 구단과 홈구장)을 읽어 표로 그린다.

(function () {
  "use strict";

  const { escapeHtml, loadJson, venue, has } = window.BB;
  const $ = (id) => document.getElementById(id);

  // value: 정렬에 쓰는 값, text: 표시 문자열. left: 왼쪽 정렬 열
  const COLUMNS = [
    { key: "division", label: "지구", left: true, value: (c) => c.divisionShort, text: (c) => escapeHtml(c.divisionShort || "-") },
    { key: "venue", label: "구장", left: true, value: (c) => c.venue.name, text: (c) => escapeHtml(c.venue.name || "-") },
    { key: "place", label: "위치", left: true, value: (c) => venue.place(c.venue), text: (c) => escapeHtml(venue.place(c.venue)) },
    { key: "first", label: "창단", desc: "구단 첫 시즌", asc: true, value: (c) => c.firstYear, text: (c) => (has(c.firstYear) ? c.firstYear : "-") },
    { key: "titles", label: "우승", desc: "월드시리즈 우승 횟수", value: (c) => titles(c), text: (c) => (has(titles(c)) ? titles(c) + "회" : "-") },
    { key: "capacity", label: "수용 인원", value: (c) => c.venue.capacity, text: (c) => (has(c.venue.capacity) ? c.venue.capacity.toLocaleString("ko-KR") : "-") },
    { key: "turf", label: "잔디", left: true, value: (c) => venue.turf(c.venue.turf), text: (c) => venue.turf(c.venue.turf) },
    { key: "roof", label: "지붕", left: true, value: (c) => venue.roof(c.venue.roof), text: (c) => venue.roof(c.venue.roof) },
    { key: "lf", label: "좌", desc: "좌측 폴까지 거리(피트)", value: (c) => c.venue.fence[0], text: (c) => fence(c, 0) },
    { key: "cf", label: "중", desc: "중앙 펜스까지 거리(피트)", value: (c) => c.venue.fence[2], text: (c) => fence(c, 2) },
    { key: "rf", label: "우", desc: "우측 폴까지 거리(피트)", value: (c) => c.venue.fence[4], text: (c) => fence(c, 4) },
    { key: "pf", label: "파크팩터", desc: "자체 계산 득점 파크팩터. 1.000이 중립, 클수록 타자에게 유리", value: (c) => c.pf, text: (c) => venue.pf(c.pf) },
    { key: "farm", label: "산하 구단", desc: "산하 마이너리그 구단 수 (Rookie 포함)", value: (c) => c.affiliates.length, text: (c) => c.affiliates.length },
  ];
  const NAME = { key: "name", value: (c) => c.name };

  const state = { league: "", division: "", search: "", sortKey: "name", sortDir: "asc" };
  let data = null;

  // 월드시리즈 우승 횟수. 수집되지 않았으면 0이 아닌 null
  const titles = (club) => (club.history && club.history.titles ? club.history.titles.length : null);

  function fence(club, index) {
    const value = club.venue.fence[index];
    return has(value) ? value : "-";
  }

  function readUrl() {
    const params = new URLSearchParams(location.search);
    if (["AL", "NL"].includes(params.get("league"))) state.league = params.get("league");
    if (params.get("division")) state.division = params.get("division");
    if (params.get("q")) state.search = params.get("q");
    if (params.get("sort")) {
      state.sortKey = params.get("sort");
      state.sortDir = params.get("dir") === "desc" ? "desc" : "asc";
    }
  }

  function writeUrl() {
    const params = new URLSearchParams();
    if (state.league) params.set("league", state.league);
    if (state.division) params.set("division", state.division);
    if (state.search) params.set("q", state.search);
    if (state.sortKey !== "name" || state.sortDir !== "asc") {
      params.set("sort", state.sortKey);
      params.set("dir", state.sortDir);
    }
    const query = params.toString();
    history.replaceState(null, "", query ? "?" + query : location.pathname);
  }

  function renderDivisionSelect() {
    const divisions = [...new Set(data.clubs.filter((c) => !state.league || c.leagueAbbr === state.league).map((c) => c.divisionShort))].sort();
    $("divisionSelect").innerHTML =
      '<option value="">전체</option>' +
      divisions.map((d) => '<option value="' + escapeHtml(d) + '">' + escapeHtml(d) + "</option>").join("");
    if (!divisions.includes(state.division)) state.division = "";
    $("divisionSelect").value = state.division;
  }

  // 값이 없는 구단은 정렬 방향과 관계없이 맨 아래에 둔다
  function sortRows(rows) {
    const column = [NAME].concat(COLUMNS).find((c) => c.key === state.sortKey) || NAME;
    const sign = state.sortDir === "asc" ? 1 : -1;
    return rows.slice().sort((a, b) => {
      const x = column.value(a);
      const y = column.value(b);
      if (!has(x) || !has(y)) return has(x) ? -1 : has(y) ? 1 : 0;
      const diff = typeof x === "number" ? x - y : String(x).localeCompare(String(y), "ko");
      return (diff || a.name.localeCompare(b.name)) * sign;
    });
  }

  function headCell(column, extraClass) {
    const sorted = state.sortKey === column.key;
    const mark = sorted ? (state.sortDir === "asc" ? " ▲" : " ▼") : "";
    const classes = ["sortable", extraClass, column.left ? "col-team" : "", sorted ? "sorted" : ""].filter(Boolean).join(" ");
    return (
      '<th class="' + classes + '" data-key="' + column.key + '"' +
      (column.desc ? ' title="' + escapeHtml(column.desc) + '"' : "") +
      ' aria-sort="' + (sorted ? (state.sortDir === "asc" ? "ascending" : "descending") : "none") + '">' +
      escapeHtml(column.label) + mark + "</th>"
    );
  }

  function render() {
    const keyword = state.search.trim().toLowerCase();
    const rows = sortRows(
      data.clubs.filter((c) => {
        if (state.league && c.leagueAbbr !== state.league) return false;
        if (state.division && c.divisionShort !== state.division) return false;
        if (keyword) {
          const text = [c.name, c.abbr, c.venue.name, c.venue.city, c.venue.state].filter(has).join(" ").toLowerCase();
          if (!text.includes(keyword)) return false;
        }
        return true;
      })
    );

    $("tableHead").innerHTML =
      "<tr>" + headCell({ key: "name", label: "구단" }, "col-name") + COLUMNS.map((column) => headCell(column)).join("") + "</tr>";
    $("tableBody").innerHTML = rows.length
      ? rows.map((c) =>
          '<tr><td class="col-name"><a href="team.html?id=' + c.id + '">' + escapeHtml(c.name) + "</a>" +
          '<span class="team-note">' + escapeHtml(c.abbr) + "</span></td>" +
          COLUMNS.map((column) =>
            '<td class="' + (column.left ? "col-team" : "") + (state.sortKey === column.key ? " sorted" : "") + '">' + column.text(c) + "</td>"
          ).join("") + "</tr>"
        ).join("")
      : '<tr><td class="empty" colspan="' + (COLUMNS.length + 1) + '">조건에 맞는 구단이 없습니다.</td></tr>';

    $("status").className = "status";
    $("status").textContent = data.season + " 시즌 기준 · MLB " + rows.length + "개 구단";
    writeUrl();
  }

  function bindEvents() {
    $("leagueSelect").addEventListener("change", () => {
      state.league = $("leagueSelect").value;
      renderDivisionSelect();
      render();
    });
    $("divisionSelect").addEventListener("change", () => {
      state.division = $("divisionSelect").value;
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
      if (state.sortKey === th.dataset.key) {
        state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      } else {
        // 글자 열과 '낮은 값이 먼저'인 열은 오름차순, 숫자 열은 내림차순으로 시작
        state.sortKey = th.dataset.key;
        state.sortDir = !column || column.left || column.asc ? "asc" : "desc";
      }
      render();
    });
  }

  async function init() {
    readUrl();
    try {
      data = await loadJson("data/teams.json");
    } catch (error) {
      $("status").className = "status error";
      $("status").textContent = "구단 데이터를 불러오지 못했습니다: " + error.message;
      return;
    }
    $("leagueSelect").value = state.league;
    $("searchInput").value = state.search;
    renderDivisionSelect();
    bindEvents();
    render();
    $("updatedText").textContent = "구단 정보 갱신: " + new Date(data.updated).toLocaleString("ko-KR");
  }

  init();
})();
