// 빠따넷 리더보드
// data/ 아래의 JSON을 불러와 표로 그린다. 계산은 모두 Python 쪽에서 끝나 있다.

(function () {
  "use strict";

  const PAGE_SIZE = 50;
  const mobile = window.matchMedia("(max-width: 640px)");
  const CORE_KEYS = {
    batting: { basic: ["OPS", "HR", "AVG", "RBI", "PA"], saber: ["wRCp", "sWAR", "wOBA", "OPS", "PA"] },
    pitching: { basic: ["ERA", "outs", "SO", "WHIP", "W", "SV"], saber: ["FIP", "ERAm", "KBBp", "WHIP", "sWAR", "outs"] },
  };

  // 화면에 보여줄 리그 순서. meta.json에 없는 리그는 "준비 중"으로 비활성화된다.
  const LEAGUE_ORDER = [
    { id: "mlb", name: "MLB" },
    { id: "milb", name: "MiLB" },
    { id: "kbo", name: "KBO" },
    { id: "npb", name: "NPB" },
  ];

  const { COLUMNS, escapeHtml, loadJson, isStarter, visibleColumns } = window.BB;

  const DEFAULT_SORT = {
    batting: { key: "OPS", dir: "desc" },
    pitching: { key: "ERA", dir: "asc" },
  };

  // 최소 출장 조건
  const MIN_OPTIONS = {
    batting: [
      { value: "q", label: "규정타석", test: (p) => p.q },
      { value: "100", label: "100타석 이상", test: (p) => p.PA >= 100 },
      { value: "0", label: "전체", test: () => true },
    ],
    pitching: [
      { value: "q", label: "규정이닝", test: (p) => p.q },
      { value: "30", label: "30이닝 이상", test: (p) => p.outs >= 90 },
      { value: "0", label: "전체", test: () => true },
    ],
  };

  const POSITION_ORDER = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "OF", "DH", "TWP", "P"];

  // ---------- 상태 ----------
  const state = {
    league: "mlb",
    level: "", // 레벨이 여러 개인 리그(MiLB)에서만 쓴다
    sub: "", // 하위 리그 (MLB의 AL/NL, AAA의 INT/PCL 등)
    season: null,
    group: "batting",
    view: "basic",
    columns: "auto",
    team: "",
    pos: "",
    min: "q",
    search: "",
    sortKey: DEFAULT_SORT.batting.key,
    sortDir: DEFAULT_SORT.batting.dir,
    page: 1,
  };

  let meta = null;
  let players = [];

  const $ = (id) => document.getElementById(id);
  const el = {
    leagueTabs: $("leagueTabs"),
    groupSwitch: $("groupSwitch"),
    viewSwitch: $("viewSwitch"),
    columnsSwitch: $("columnsSwitch"),
    columnsHelp: $("columnsHelp"),
    season: $("seasonSelect"),
    level: $("levelSelect"),
    levelField: $("levelField"),
    sub: $("subSelect"),
    subField: $("subField"),
    team: $("teamSelect"),
    pos: $("posSelect"),
    posLabel: $("posLabel"),
    min: $("minSelect"),
    minLabel: $("minLabel"),
    search: $("searchInput"),
    status: $("status"),
    filters: $("filterSummary"),
    sort: $("sortSummary"),
    definitions: $("metricDefinitions"),
    head: $("tableHead"),
    body: $("tableBody"),
    pager: $("pager"),
    updated: $("updatedText"),
  };

  // ---------- 주소창과 상태 맞추기 ----------
  function readUrl() {
    const params = new URLSearchParams(location.search);
    const pick = (name, allowed) => {
      const value = params.get(name);
      if (value !== null && (!allowed || allowed.includes(value))) state[name] = value;
    };
    pick("league");
    pick("level");
    pick("sub");
    pick("group", ["batting", "pitching"]);
    pick("view", ["basic", "saber"]);
    pick("columns", ["core", "full"]);
    pick("team");
    pick("pos");
    pick("min");
    if (params.get("season")) state.season = Number(params.get("season"));
    if (params.get("q")) state.search = params.get("q");
    if (params.get("sort")) {
      state.sortKey = params.get("sort");
      state.sortDir = params.get("dir") === "asc" ? "asc" : "desc";
    } else {
      Object.assign(state, { sortKey: DEFAULT_SORT[state.group].key, sortDir: DEFAULT_SORT[state.group].dir });
    }
  }

  function writeUrl() {
    const params = new URLSearchParams();
    params.set("league", state.league);
    if (state.level) params.set("level", state.level);
    params.set("season", state.season);
    params.set("group", state.group);
    if (state.view !== "basic") params.set("view", state.view);
    if (state.columns !== "auto") params.set("columns", state.columns);
    if (state.sub) params.set("sub", state.sub);
    if (state.team) params.set("team", state.team);
    if (state.pos) params.set("pos", state.pos);
    if (state.min !== "q") params.set("min", state.min);
    if (state.search) params.set("q", state.search);
    const def = DEFAULT_SORT[state.group];
    if (state.sortKey !== def.key || state.sortDir !== def.dir) {
      params.set("sort", state.sortKey);
      params.set("dir", state.sortDir);
    }
    history.replaceState(null, "", "?" + params.toString());
  }

  // ---------- 조회 조건 그리기 ----------
  function currentLeague() {
    return meta.leagues.find((league) => league.id === state.league);
  }

  function renderLeagueTabs() {
    el.leagueTabs.innerHTML = LEAGUE_ORDER.map((league) => {
      const ready = meta.leagues.some((item) => item.id === league.id);
      return (
        '<button type="button" data-value="' + league.id + '"' +
        ' aria-pressed="' + (league.id === state.league) + '"' +
        (ready ? "" : ' disabled title="준비 중"') + ">" + league.name + "</button>"
      );
    }).join("");
  }

  function setPressed(container, value) {
    container.querySelectorAll("button").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.value === value));
    });
  }

  function fillSelect(select, options, value) {
    select.innerHTML = options
      .map((option) => '<option value="' + escapeHtml(option.value) + '">' + escapeHtml(option.label) + "</option>")
      .join("");
    const exists = options.some((option) => option.value === String(value));
    select.value = exists ? String(value) : options[0].value;
    return select.value;
  }

  function renderSeasonSelect() {
    const seasons = currentLeague().seasons;
    if (!seasons.includes(state.season)) state.season = seasons[0];
    fillSelect(el.season, seasons.map((season) => ({ value: String(season), label: String(season) })), state.season);
  }

  // 레벨이 여러 개인 리그에서만 레벨 선택을 보여준다
  function renderLevelSelect() {
    const levels = currentLeague().levels || [];
    el.levelField.hidden = !levels.length;
    state.level = levels.length
      ? fillSelect(el.level, levels.map((level) => ({ value: level.id, label: level.name })), state.level)
      : "";
  }

  function levelName() {
    const level = (currentLeague().levels || []).find((item) => item.id === state.level);
    return level ? level.name : currentLeague().name;
  }

  // 팀, 포지션, 최소 조건은 불러온 데이터에 맞춰 다시 채운다
  function renderDataFilters() {
    // 하위 리그가 둘 이상일 때만 리그 선택을 보여준다
    const subs = [...new Set(players.map((p) => p.lg).filter(Boolean))].sort();
    el.subField.hidden = subs.length < 2;
    state.sub = subs.length < 2
      ? ""
      : fillSelect(el.sub, [{ value: "", label: "전체" }].concat(subs.map((s) => ({ value: s, label: s }))), state.sub);

    // 리그를 골랐으면 그 리그의 팀만 팀 목록에 남긴다
    const teams = [...new Set(players.filter((p) => !state.sub || p.lg === state.sub).map((p) => p.team).filter(Boolean))].sort();
    state.team = fillSelect(el.team, [{ value: "", label: "전체" }].concat(teams.map((t) => ({ value: t, label: t }))), state.team);

    if (state.group === "batting") {
      el.posLabel.textContent = "포지션";
      const found = new Set(players.map((p) => p.pos).filter(Boolean));
      const ordered = POSITION_ORDER.filter((pos) => found.has(pos)).concat([...found].filter((pos) => !POSITION_ORDER.includes(pos)).sort());
      state.pos = fillSelect(el.pos, [{ value: "", label: "전체" }].concat(ordered.map((pos) => ({ value: pos, label: pos }))), state.pos);
    } else {
      el.posLabel.textContent = "보직";
      state.pos = fillSelect(el.pos, [{ value: "", label: "전체" }, { value: "SP", label: "선발" }, { value: "RP", label: "구원" }], state.pos);
    }

    el.minLabel.textContent = state.group === "batting" ? "타석" : "이닝";
    state.min = fillSelect(el.min, MIN_OPTIONS[state.group], state.min);
  }

  // ---------- 표 그리기 ----------
  function activeColumns() {
    const columns = visibleColumns(COLUMNS[state.group][state.view], players);
    if (!coreView()) return columns;
    // 정렬 지표를 맨 앞에 두고 보기를 바꿔도 정렬 기준을 유지한다.
    return [...new Set([state.sortKey].concat(CORE_KEYS[state.group][state.view]))]
      .map((key) => columns.find((column) => column.key === key)).filter(Boolean);
  }

  function coreView() {
    return state.columns === "core" || state.columns === "auto" && mobile.matches;
  }

  // 악센트와 대소문자를 무시한다 (Rodriguez → Rodríguez). 한글은 그대로 둔다.
  const fold = (text) => String(text || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const matchesName = (p, keyword) => fold(p.nameKo).includes(keyword) || fold(p.name).includes(keyword);

  function filteredPlayers() {
    const minTest = MIN_OPTIONS[state.group].find((option) => option.value === state.min).test;
    const keyword = fold(state.search.trim());
    return players.filter((p) => {
      if (!minTest(p)) return false;
      if (state.sub && p.lg !== state.sub) return false;
      if (state.team && p.team !== state.team) return false;
      if (state.pos) {
        if (state.group === "batting" && p.pos !== state.pos) return false;
        if (state.group === "pitching" && (state.pos === "SP") !== isStarter(p)) return false;
      }
      if (keyword && !matchesName(p, keyword)) return false;
      return true;
    });
  }

  function sortPlayers(list) {
    const key = state.sortKey;
    const sign = state.sortDir === "asc" ? 1 : -1;
    return list.slice().sort((a, b) => {
      const av = a[key], bv = b[key];
      const aNone = av === null || av === undefined;
      const bNone = bv === null || bv === undefined;
      if (aNone || bNone) return aNone - bNone; // 값이 없으면 항상 맨 뒤
      if (av !== bv) return (av - bv) * sign;
      return a.name.localeCompare(b.name);
    });
  }

  function renderHead() {
    const arrow = state.sortDir === "asc" ? " ▲" : " ▼";
    const cells = activeColumns().map((column) => {
      const sorted = column.key === state.sortKey;
      const nextDir = sorted ? (state.sortDir === "asc" ? "desc" : "asc") : (column.asc ? "asc" : "desc");
      return (
        '<th class="sortable' + (sorted ? " sorted" : "") + '" data-key="' + column.key + '"' +
        ' title="' + escapeHtml(column.desc) + '"' +
        (sorted ? ' aria-sort="' + (state.sortDir === "asc" ? "ascending" : "descending") + '"' : "") +
        '><button type="button" class="sort-button" data-sort="' + column.key +
        '" aria-label="' + escapeHtml(column.label) + " " + (nextDir === "asc" ? "낮은 순" : "높은 순") + ' 정렬">' +
        escapeHtml(column.label) + '<span aria-hidden="true">' + (sorted ? arrow : "") + "</span></button></th>"
      );
    });
    el.head.innerHTML =
      '<tr><th class="col-rank">#</th><th class="col-name">선수</th><th class="col-team">팀</th>' +
      (coreView() ? "" : '<th class="col-pos">' + (state.group === "batting" ? "포지션" : "보직") + "</th>") + cells.join("") + "</tr>";
  }

  function renderBody(list) {
    const columns = activeColumns();
    const start = (state.page - 1) * PAGE_SIZE;
    const rows = list.slice(start, start + PAGE_SIZE);
    if (!rows.length) {
      el.body.innerHTML = '<tr><td class="empty leaderboard-empty" colspan="' + (columns.length + (coreView() ? 3 : 4)) + '">' +
        '<p>선택한 시즌·레벨과 조건에 맞는 선수가 없습니다.</p>' +
        '<button type="button" class="reset-filters">조회 조건 초기화</button> · ' +
        '<a href="search.html' + (state.search.trim() ? '?q=' + encodeURIComponent(state.search.trim()) : "") + '">전체 선수 검색</a></td></tr>';
      return;
    }
    el.body.innerHTML = rows.map((p, index) => {
      const team = escapeHtml(p.team || "-") + (p.nt > 1 ? '<span class="team-note">' + p.nt + "팀</span>" : "");
      const role = state.group === "batting" ? escapeHtml(p.pos || "-") : isStarter(p) ? "선발" : "구원";
      const cells = columns.map((column) => {
        const value = p[column.key];
        const text = value === null || value === undefined ? "-" : column.format(value);
        return "<td" + (column.key === state.sortKey ? ' class="sorted"' : "") + ">" + text + "</td>";
      });
      return (
        '<tr><td class="col-rank">' + (start + index + 1) + "</td>" +
        '<td class="col-name"><a href="player.html?id=' + p.id + '" title="' + escapeHtml(p.nameKo || p.name) + '"><span class="player-name-text">' + escapeHtml(p.nameKo || p.name) + "</span></a></td>" +
        '<td class="col-team">' + team + "</td>" +
        (coreView() ? "" : '<td class="col-pos">' + role + "</td>") + cells.join("") + "</tr>"
      );
    }).join("");
  }

  function renderPager(total) {
    const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    if (pages <= 1) {
      el.pager.innerHTML = "";
      return;
    }
    el.pager.innerHTML =
      '<button type="button" data-step="-1"' + (state.page <= 1 ? " disabled" : "") + ">이전</button>" +
      "<span>" + state.page + " / " + pages + "</span>" +
      '<button type="button" data-step="1"' + (state.page >= pages ? " disabled" : "") + ">다음</button>";
  }

  function renderTable() {
    // 보기 전환으로 정렬 기준 열이 사라졌으면 기본 정렬로 되돌린다
    if (!activeColumns().some((column) => column.key === state.sortKey)) {
      Object.assign(state, { sortKey: DEFAULT_SORT[state.group].key, sortDir: DEFAULT_SORT[state.group].dir });
    }
    const list = sortPlayers(filteredPlayers());
    const pages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
    if (state.page > pages) state.page = pages;
    renderHead();
    renderBody(list);
    renderPager(list.length);
    setPressed(el.columnsSwitch, coreView() ? "core" : "full");
    $("statsTable").classList.toggle("core-columns", coreView());
    el.columnsHelp.textContent = coreView()
      ? "핵심 기록 · 정렬한 지표를 먼저 표시합니다. 전체 기록에서 모든 열을 볼 수 있습니다."
      : "전체 기록 · 표를 가로로 넘기면 나머지 지표를 볼 수 있습니다.";
    el.status.className = "status";
    el.status.textContent =
      levelName() + (state.sub ? " " + state.sub : "") + " " + state.season + " " + (state.group === "batting" ? "타자" : "투수") + " · " + list.length + "명";
    const selected = (select) => select.options[select.selectedIndex].textContent;
    el.filters.hidden = false;
    el.filters.textContent = "적용 조건: " + [state.sub || "전체 리그", state.team || "전체 팀", state.pos ? selected(el.pos) : "전체 " + el.posLabel.textContent, state.min === "0" ? "출장 제한 없음" : selected(el.min)]
      .concat(state.search.trim() ? ['이름 “' + state.search.trim() + '”'] : []).join(" · ");
    const sortColumn = activeColumns().find((column) => column.key === state.sortKey);
    el.sort.textContent = sortColumn
      ? "정렬: " + sortColumn.label + (state.sortDir === "asc" ? " 낮은 순" : " 높은 순") + " · 열 제목을 눌러 변경"
      : "";
    el.definitions.innerHTML = activeColumns().map((column) => '<div><dt>' + escapeHtml(column.label) + '</dt><dd>' + escapeHtml(column.desc) + '</dd></div>').join("");
    writeUrl();
    showOtherGroupMatches();
  }

  // 검색 중이면 반대쪽(타자↔투수) 기록에서 같은 이름이 몇 명인지 알려 주고 바로 넘어갈 수 있게 한다.
  // 반대쪽은 최소 출장 조건 없이 센다. 다른 조건으로 다시 그려졌으면 늦게 온 결과는 버린다.
  let otherToken = 0;
  async function showOtherGroupMatches() {
    const token = ++otherToken;
    const keyword = fold(state.search.trim());
    if (!keyword) return;
    const other = state.group === "batting" ? "pitching" : "batting";
    const folder = "data/" + state.league + "/" + (state.level ? state.level + "/" : "");
    let count = 0;
    try {
      const data = await loadJson(folder + other + "_" + state.season + ".json");
      count = data.players.filter((p) => matchesName(p, keyword)).length;
    } catch (error) {
      return;
    }
    if (token !== otherToken || !count) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "link-button";
    button.textContent = (other === "batting" ? "타자" : "투수") + " 기록에서 " + count + "명 보기";
    button.addEventListener("click", () => switchGroup(other));
    el.status.append(" · ", button);
  }

  // ---------- 데이터 불러오기 ----------
  async function loadPlayers() {
    el.status.className = "status";
    el.status.textContent = "불러오는 중...";
    el.filters.hidden = true;
    el.sort.textContent = "";
    el.definitions.innerHTML = "";
    const folder = "data/" + state.league + "/" + (state.level ? state.level + "/" : "");
    const url = folder + state.group + "_" + state.season + ".json";
    try {
      const data = await loadJson(url);
      players = data.players;
    } catch (error) {
      players = [];
      el.body.innerHTML = "";
      el.pager.innerHTML = "";
      showError("데이터를 불러오지 못했습니다: " + error.message);
      return;
    }
    renderDataFilters();
    renderTable();
  }

  function showError(message) {
    el.status.className = "status error";
    el.status.textContent =
      location.protocol === "file:"
        ? "파일을 직접 열면 데이터를 읽을 수 없습니다. 프로젝트 폴더에서 python -m http.server 8000 을 실행한 뒤 http://localhost:8000 으로 접속하세요."
        : message;
  }

  // 타자↔투수 전환. 검색 중이면 출장 조건 없이 이름이 맞는 선수를 모두 보여준다.
  function switchGroup(group) {
    Object.assign(state, { group, pos: "", min: state.search.trim() ? "0" : "q", page: 1 });
    resetSort();
    setPressed(el.groupSwitch, state.group);
    loadPlayers();
  }

  function resetSort() {
    Object.assign(state, { sortKey: DEFAULT_SORT[state.group].key, sortDir: DEFAULT_SORT[state.group].dir });
  }

  // ---------- 이벤트 ----------
  function bindEvents() {
    el.columnsSwitch.addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button) return;
      state.columns = button.dataset.value;
      renderTable();
    });
    mobile.addEventListener("change", () => {
      if (state.columns === "auto" && meta && players.length) renderTable();
    });
    el.leagueTabs.addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button || button.disabled || button.dataset.value === state.league) return;
      Object.assign(state, { league: button.dataset.value, level: "", sub: "", team: "", pos: "", page: 1 });
      renderLeagueTabs();
      renderSeasonSelect();
      renderLevelSelect();
      loadPlayers();
    });

    el.level.addEventListener("change", () => {
      Object.assign(state, { level: el.level.value, sub: "", team: "", page: 1 });
      loadPlayers();
    });

    el.sub.addEventListener("change", () => {
      Object.assign(state, { sub: el.sub.value, team: "", page: 1 });
      renderDataFilters();
      renderTable();
    });

    el.groupSwitch.addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button || button.dataset.value === state.group) return;
      switchGroup(button.dataset.value);
    });

    el.viewSwitch.addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button || button.dataset.value === state.view) return;
      state.view = button.dataset.value;
      setPressed(el.viewSwitch, state.view);
      renderTable();
    });

    el.season.addEventListener("change", () => {
      Object.assign(state, { season: Number(el.season.value), page: 1 });
      loadPlayers();
    });

    const onFilter = (name, input) => () => {
      state[name] = input.value;
      state.page = 1;
      renderTable();
    };
    el.team.addEventListener("change", onFilter("team", el.team));
    el.pos.addEventListener("change", onFilter("pos", el.pos));
    el.min.addEventListener("change", onFilter("min", el.min));
    // 검색을 새로 시작하면 리그·팀·포지션·출장 조건을 풀어 이름이 맞는 선수를 모두 보여준다.
    // 검색하는 동안 다시 고른 조건은 그대로 적용한다.
    el.search.addEventListener("input", () => {
      const starting = !state.search.trim() && el.search.value.trim();
      state.search = el.search.value;
      state.page = 1;
      if (starting) {
        Object.assign(state, { sub: "", team: "", pos: "", min: "0" });
        renderDataFilters();
      }
      renderTable();
    });

    el.head.addEventListener("click", (event) => {
      const th = event.target.closest("th.sortable");
      if (!th) return;
      const column = activeColumns().find((item) => item.key === th.dataset.key);
      if (state.sortKey === column.key) {
        state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = column.key;
        state.sortDir = column.asc ? "asc" : "desc";
      }
      state.page = 1;
      renderTable();
      el.head.querySelector('button[data-sort="' + column.key + '"]').focus({ preventScroll: true });
    });

    el.body.addEventListener("click", (event) => {
      if (!event.target.closest(".reset-filters")) return;
      Object.assign(state, { sub: "", team: "", pos: "", min: "q", search: "", page: 1 });
      el.search.value = "";
      renderDataFilters();
      renderTable();
      el.search.focus();
    });

    el.pager.addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button || button.disabled) return;
      state.page += Number(button.dataset.step);
      renderTable();
      $("tableScroll").scrollIntoView({ block: "start" });
    });
  }

  // ---------- 시작 ----------
  async function init() {
    readUrl();
    bindEvents();
    try {
      meta = await loadJson("data/meta.json");
    } catch (error) {
      showError("데이터 목록을 불러오지 못했습니다: " + error.message);
      return;
    }
    if (!currentLeague()) state.league = meta.leagues[0].id;
    renderLeagueTabs();
    renderSeasonSelect();
    renderLevelSelect();
    setPressed(el.groupSwitch, state.group);
    setPressed(el.viewSwitch, state.view);
    el.search.value = state.search;
    el.updated.textContent = "마지막 갱신: " + new Date(meta.updated).toLocaleString("ko-KR");
    await loadPlayers();
  }

  init();
})();
