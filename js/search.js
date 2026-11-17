// 빠따넷 선수 검색
// data/search.json (선수 색인)을 읽어 이름으로 찾는다.
// 색인 한 줄: [ID, 이름, 포지션, 첫 시즌, 마지막 시즌, MLB 출전 여부(1/0)]

(function () {
  "use strict";

  const { escapeHtml, loadJson } = window.BB;
  const $ = (id) => document.getElementById(id);

  const MIN_LENGTH = 2;
  const LIMIT = 100;
  const state = { search: "", scope: "" };
  let players = null; // [{id, name, key, pos, first, last, mlb}]

  // 악센트와 대소문자, 구두점을 무시하고 비교한다 (Martínez → martinez, J.D. → jd)
  const normalize = (text) =>
    text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9 ]/g, "").replace(/\s+/g, " ").trim();

  function readUrl() {
    const params = new URLSearchParams(location.search);
    if (params.get("q")) state.search = params.get("q");
    if (["mlb", "minor"].includes(params.get("scope"))) state.scope = params.get("scope");
  }

  function writeUrl() {
    const params = new URLSearchParams();
    if (state.search) params.set("q", state.search);
    if (state.scope) params.set("scope", state.scope);
    const query = params.toString();
    history.replaceState(null, "", query ? "?" + query : location.pathname);
  }

  // 검색어의 모든 단어가 이름에 들어 있으면 일치. 이름이 검색어로 시작하면 먼저 보여준다.
  function find(keyword) {
    const words = keyword.split(" ");
    const matches = players.filter((p) => {
      if (state.scope === "mlb" && !p.mlb) return false;
      if (state.scope === "minor" && p.mlb) return false;
      return words.every((word) => p.key.includes(word));
    });
    const rank = (p) => (p.key === keyword ? 0 : p.key.startsWith(keyword) ? 1 : 2);
    return matches.sort(
      (a, b) => rank(a) - rank(b) || b.mlb - a.mlb || (b.last || 0) - (a.last || 0) || a.name.localeCompare(b.name)
    );
  }

  function seasons(p) {
    if (p.first === null) return '<span class="muted">기록 없음</span>';
    return p.first === p.last ? String(p.first) : p.first + "~" + p.last;
  }

  function render() {
    const keyword = normalize(state.search);
    writeUrl();
    if (keyword.length < MIN_LENGTH) {
      $("resultWrap").hidden = true;
      $("status").className = "status";
      $("status").textContent = "선수 " + players.length.toLocaleString("ko-KR") + "명 중에서 찾습니다. 이름을 " + MIN_LENGTH + "글자 이상 입력해 주세요.";
      return;
    }
    const found = find(keyword);
    const shown = found.slice(0, LIMIT);
    $("tableBody").innerHTML = shown.length
      ? shown.map((p) =>
          '<tr><td class="col-name"><a href="player.html?id=' + p.id + '">' + escapeHtml(p.name) + "</a></td>" +
          '<td class="col-team">' + escapeHtml(p.pos || "-") + "</td>" +
          '<td class="col-team">' + seasons(p) + "</td>" +
          '<td class="col-team"><span class="level' + (p.mlb ? " level-mlb" : "") + '">' + (p.mlb ? "MLB" : "마이너") + "</span></td></tr>"
        ).join("")
      : '<tr><td class="empty" colspan="4">일치하는 선수가 없습니다. 영문 이름으로 검색해 주세요.</td></tr>';
    $("resultWrap").hidden = false;
    $("status").className = "status";
    $("status").textContent =
      found.length > LIMIT
        ? found.length.toLocaleString("ko-KR") + "명 중 " + LIMIT + "명을 표시합니다. 이름을 더 입력해 주세요."
        : found.length + "명";
  }

  async function init() {
    readUrl();
    let data;
    try {
      data = await loadJson("data/search.json");
    } catch (error) {
      $("status").className = "status error";
      $("status").textContent = "검색 데이터를 불러오지 못했습니다: " + error.message;
      return;
    }
    players = data.players.map((row) => ({
      id: row[0], name: row[1], key: normalize(row[1]), pos: row[2], first: row[3], last: row[4], mlb: row[5],
    }));
    $("searchInput").value = state.search;
    $("scopeSelect").value = state.scope;
    $("searchInput").addEventListener("input", () => {
      state.search = $("searchInput").value;
      render();
    });
    $("scopeSelect").addEventListener("change", () => {
      state.scope = $("scopeSelect").value;
      render();
    });
    render();
  }

  init();
})();
