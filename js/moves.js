// 빠따넷 선수 이동 소식
// data/moves_{시즌}.json(scripts/moves.py)을 읽어 MLB 리그 전체의 공식 이동을 날짜별로 보여준다.
// 트레이드는 한 건으로 묶고 구단마다 영입한 선수를 나눠 보여준다.

(function () {
  "use strict";

  const { escapeHtml, loadJson } = window.BB;
  const $ = (id) => document.getElementById(id);

  const SEASONS = [2026, 2025, 2024]; // scripts/moves.py와 같게 유지 (최신 시즌부터)
  const PAGE = 80; // 한 번에 보여줄 소식 수

  // 종류: 이름, 배지 색 구분
  const TYPES = {
    trade: "트레이드",
    sign: "FA 계약",
    claim: "웨이버 클레임",
    select: "40인 명단 등록",
    dfa: "양도지명",
    outright: "아웃라이트",
    release: "방출",
    fa: "FA 선언",
  };

  const state = { season: String(SEASONS[0]), type: "", team: "", month: "", search: "", shown: PAGE };
  let clubs = {}; // 구단 ID → {abbr, name}
  let events = [];

  const teamLink = (id) => {
    const club = clubs[id];
    if (!club) return '<span class="muted">-</span>';
    return '<a class="move-team" href="team.html?id=' + id + '" title="' + escapeHtml(club.name) + '">' + escapeHtml(club.abbr) + "</a>";
  };
  const playerLink = (p) => {
    const name = escapeHtml(p.name || "-");
    return p.page ? '<a href="player.html?id=' + p.id + '">' + name + "</a>" : name;
  };
  const names = (players) => players.map(playerLink).join(", ");

  // 소식 한 건의 본문
  function describe(event) {
    const p = event.players;
    const first = p[0];
    switch (event.type) {
      case "trade": {
        // 구단마다 "영입" 줄을 만든다 (그 구단으로 간 선수들)
        const lines = event.teams.map((team) => {
          const gets = p.filter((item) => item.to === team);
          if (!gets.length) return "";
          return '<li>' + teamLink(team) + ' <span class="muted">영입</span> ' + names(gets) + "</li>";
        }).join("");
        return '<div class="move-title">' + event.teams.map(teamLink).join(' <span class="muted">↔</span> ') + "</div>" +
          '<ul class="move-lines">' + lines + "</ul>" +
          '<p class="move-desc">' + escapeHtml(event.desc || "") + "</p>";
      }
      case "claim":
        return '<div class="move-title">' + teamLink(first.to) + ' <span class="muted">←</span> ' + teamLink(first.from) + "</div>" +
          "<p>" + names(p) + " 웨이버 클레임</p>";
      case "sign":
        return '<div class="move-title">' + teamLink(first.to) + "</div><p>" + names(p) + " FA 계약 (메이저리그 계약)</p>";
      case "select":
        return '<div class="move-title">' + teamLink(first.to) + "</div><p>" + names(p) + " 40인 명단 등록 (계약 선택)</p>";
      case "dfa":
        return '<div class="move-title">' + teamLink(first.from) + "</div><p>" + names(p) + " 양도지명 (40인 명단 제외)</p>";
      case "outright":
        return '<div class="move-title">' + teamLink(first.from) + "</div><p>" + names(p) + " 아웃라이트 (40인 명단에서 빼 마이너리그로 이관)</p>";
      case "release":
        return '<div class="move-title">' + teamLink(first.from) + "</div><p>" + names(p) + " 방출</p>";
      case "fa":
        return '<div class="move-title">' + teamLink(first.from) + "</div><p>" + names(p) + " FA 선언</p>";
      default:
        return "";
    }
  }

  function filtered() {
    const keyword = state.search.trim().toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
    const team = Number(state.team);
    return events.filter((event) => {
      if (state.type && event.type !== state.type) return false;
      if (team && !event.teams.includes(team)) return false;
      if (state.month && event.date.slice(0, 7) !== state.month) return false;
      if (keyword && !event.players.some((p) =>
        p.name.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").includes(keyword))) return false;
      return true;
    });
  }

  function render() {
    const rows = filtered();
    const shown = rows.slice(0, state.shown);
    let html = "";
    let lastDate = "";
    shown.forEach((event) => {
      if (event.date !== lastDate) {
        if (lastDate) html += "</ol>";
        html += '<h2 class="move-date">' + escapeHtml(event.date) + '</h2><ol class="move-list">';
        lastDate = event.date;
      }
      html += '<li class="move-item"><span class="move-badge move-' + event.type + '">' + TYPES[event.type] + "</span>" +
        '<div class="move-body">' + describe(event) + "</div></li>";
    });
    if (lastDate) html += "</ol>";
    $("feed").innerHTML = html || '<p class="status">조건에 맞는 이동이 없습니다.</p>';
    $("status").textContent = state.season + " 시즌 · " + rows.length.toLocaleString("ko-KR") + "건" +
      (rows.length > shown.length ? " 중 최근 " + shown.length + "건" : "");
    $("more").innerHTML = rows.length > shown.length
      ? '<button type="button" class="link-button" id="moreButton">' + Math.min(PAGE, rows.length - shown.length) + "건 더 보기</button>"
      : "";
    writeUrl();
  }

  function readUrl() {
    const params = new URLSearchParams(location.search);
    if (SEASONS.map(String).includes(params.get("season"))) state.season = params.get("season");
    if (TYPES[params.get("type")]) state.type = params.get("type");
    if (/^\d+$/.test(params.get("team") || "")) state.team = params.get("team");
    if (/^\d{4}-\d{2}$/.test(params.get("month") || "")) state.month = params.get("month");
    if (params.get("q")) state.search = params.get("q");
  }

  function writeUrl() {
    const params = new URLSearchParams();
    if (state.season !== String(SEASONS[0])) params.set("season", state.season);
    if (state.type) params.set("type", state.type);
    if (state.team) params.set("team", state.team);
    if (state.month) params.set("month", state.month);
    if (state.search) params.set("q", state.search);
    const query = params.toString();
    history.replaceState(null, "", query ? "?" + query : location.pathname);
  }

  // 월 목록은 그 시즌에 이동이 있는 달만, 최신 달부터. 건수를 함께 보여준다
  function renderMonths() {
    const counts = {};
    events.forEach((event) => {
      const month = event.date.slice(0, 7);
      counts[month] = (counts[month] || 0) + 1;
    });
    const months = Object.keys(counts).sort().reverse();
    if (!months.includes(state.month)) state.month = "";
    $("monthSelect").innerHTML = '<option value="">전체</option>' +
      months.map((m) => '<option value="' + m + '">' + Number(m.slice(5)) + "월 (" + counts[m] + ")</option>").join("");
    $("monthSelect").value = state.month;
  }

  async function loadSeason() {
    $("status").textContent = "불러오는 중...";
    try {
      const data = await loadJson("data/moves_" + state.season + ".json");
      events = data.events;
      $("updatedText").textContent = data.updated ? "이동 기록 갱신: " + new Date(data.updated).toLocaleString("ko-KR") : "";
    } catch (error) {
      events = [];
      $("status").className = "status error";
      $("status").textContent = "이동 기록을 불러오지 못했습니다.";
      $("feed").innerHTML = "";
      return;
    }
    $("status").className = "status";
    state.shown = PAGE;
    renderMonths();
    render();
  }

  async function init() {
    readUrl();
    $("seasonSelect").innerHTML = SEASONS.map((s) => '<option value="' + s + '">' + s + "</option>").join("");
    $("seasonSelect").value = state.season;
    $("typeSelect").innerHTML = '<option value="">전체</option>' +
      Object.entries(TYPES).map(([key, label]) => '<option value="' + key + '">' + label + "</option>").join("");
    $("typeSelect").value = state.type;
    $("searchInput").value = state.search;
    try {
      const teams = await loadJson("data/teams.json");
      teams.clubs.forEach((club) => { clubs[club.id] = { abbr: club.abbr, name: club.name }; });
      $("teamSelect").innerHTML += teams.clubs.slice().sort((a, b) => a.name.localeCompare(b.name))
        .map((club) => '<option value="' + club.id + '">' + escapeHtml(club.name) + "</option>").join("");
      if (!clubs[state.team]) state.team = "";
      $("teamSelect").value = state.team;
    } catch (error) {
      clubs = {};
    }

    const reset = () => { state.shown = PAGE; render(); };
    $("seasonSelect").addEventListener("change", () => { state.season = $("seasonSelect").value; loadSeason(); });
    $("typeSelect").addEventListener("change", () => { state.type = $("typeSelect").value; reset(); });
    $("teamSelect").addEventListener("change", () => { state.team = $("teamSelect").value; reset(); });
    $("monthSelect").addEventListener("change", () => { state.month = $("monthSelect").value; reset(); });
    $("searchInput").addEventListener("input", () => { state.search = $("searchInput").value; reset(); });
    $("more").addEventListener("click", (event) => {
      if (!event.target.closest("#moreButton")) return;
      state.shown += PAGE;
      render();
    });
    loadSeason();
  }

  init();
})();
