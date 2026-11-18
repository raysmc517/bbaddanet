// 빠따넷 구단 상세
// data/teams.json에서 구단 하나를 찾아 홈구장과 같은 조직의 구단들을 보여준다.
// MLB 구단과 산하 마이너리그 구단 모두 team.html?id={구단 ID}로 연다.

(function () {
  "use strict";

  const { escapeHtml, loadJson, venue, has } = window.BB;
  const $ = (id) => document.getElementById(id);

  // 리더보드가 있는 레벨 → 리더보드 주소의 조건
  const BOARD = {
    MLB: "league=mlb",
    AAA: "league=milb&level=aaa",
    AA: "league=milb&level=aa",
    "High-A": "league=milb&level=high_a",
    "Single-A": "league=milb&level=single_a",
  };

  const levelBadge = (level) =>
    '<span class="level' + (level === "MLB" ? " level-mlb" : "") + '">' + escapeHtml(level) + "</span>";

  const facts = (pairs) =>
    pairs.map(([label, value]) => "<div><dt>" + escapeHtml(label) + "</dt><dd>" + value + "</dd></div>").join("");

  const feet = (value) => (has(value) ? value + "ft (" + venue.meters(value) + "m)" : "-");

  function boardLink(team, season) {
    if (!BOARD[team.level] || !team.abbr) return "";
    return "./?" + BOARD[team.level] + "&season=" + season + "&team=" + encodeURIComponent(team.abbr);
  }

  // 펜스 거리 다섯 지점으로 그린 구장 윤곽. 값이 하나라도 없으면 그리지 않는다.
  function fieldSvg(fence) {
    if (!fence.every(has)) return "";
    const scale = 0.5;
    const home = { x: 180, y: 262 };
    const angles = [-45, -22.5, 0, 22.5, 45];
    const point = (distance, angle) => {
      const rad = (angle * Math.PI) / 180;
      return { x: home.x + distance * scale * Math.sin(rad), y: home.y - distance * scale * Math.cos(rad) };
    };
    const wall = fence.map((distance, index) => point(distance, angles[index]));

    // 다섯 지점을 부드럽게 잇는다 (Catmull-Rom 곡선을 베지어로 변환)
    let path = "M" + home.x + " " + home.y + " L" + wall[0].x.toFixed(1) + " " + wall[0].y.toFixed(1);
    for (let i = 0; i < wall.length - 1; i += 1) {
      const p0 = wall[Math.max(i - 1, 0)];
      const p1 = wall[i];
      const p2 = wall[i + 1];
      const p3 = wall[Math.min(i + 2, wall.length - 1)];
      const c1 = { x: p1.x + (p2.x - p0.x) / 6, y: p1.y + (p2.y - p0.y) / 6 };
      const c2 = { x: p2.x - (p3.x - p1.x) / 6, y: p2.y - (p3.y - p1.y) / 6 };
      path += " C" + [c1.x, c1.y, c2.x, c2.y, p2.x, p2.y].map((n) => n.toFixed(1)).join(" ");
    }
    path += " Z";

    const bases = [point(90, -45), point(90 * Math.SQRT2, 0), point(90, 45)];
    const diamond = "M" + home.x + " " + home.y + bases.map((b) => " L" + b.x.toFixed(1) + " " + b.y.toFixed(1)).join("") + " Z";
    const labels = fence
      .map((distance, index) => {
        const at = point(distance + 34, angles[index]);
        return '<text x="' + at.x.toFixed(1) + '" y="' + at.y.toFixed(1) + '" text-anchor="middle" dominant-baseline="middle">' + distance + "</text>";
      })
      .join("");

    return (
      '<svg viewBox="0 0 360 280" role="img" aria-label="펜스 거리: 좌 ' + fence[0] + ", 좌중 " + fence[1] + ", 중 " + fence[2] +
      ", 우중 " + fence[3] + ", 우 " + fence[4] + ' 피트">' +
      '<path class="field-grass" d="' + path + '"/>' +
      '<path class="field-dirt" d="' + diamond + '"/>' +
      labels +
      "</svg><figcaption>홈플레이트에서 펜스까지 거리 (피트)</figcaption>"
    );
  }

  // MLB 공식 로고. 파일을 저장하지 않고 MLB 이미지 서버 주소로만 표시한다.
  // 이미지를 못 받으면 로고 자리를 숨긴다.
  const LOGO_BASE = "https://www.mlbstatic.com/team-logos/";
  function renderLogo(team, isMajor) {
    const box = $("teamLogo");
    if (!isMajor || !Number.isInteger(team.id)) return;
    box.innerHTML =
      '<source media="(prefers-color-scheme: dark)" srcset="' + LOGO_BASE + "team-cap-on-dark/" + team.id + '.svg">' +
      '<img src="' + LOGO_BASE + team.id + '.svg" alt="' + escapeHtml(team.name) + ' 로고" width="72" height="72">';
    box.querySelector("img").addEventListener("error", () => { box.hidden = true; });
    box.hidden = false;
  }

  function renderProfile(team, parent, season) {
    document.title = "빠따넷 · " + team.name;
    $("teamName").textContent = team.name;
    const isMajor = team.level === "MLB";
    renderLogo(team, isMajor);
    $("teamSub").innerHTML =
      levelBadge(team.level) + " " + escapeHtml(isMajor ? team.division : team.league) +
      (isMajor ? "" : ' · 모구단 <a href="team.html?id=' + parent.id + '">' + escapeHtml(parent.name) + "</a>");

    $("teamFacts").innerHTML = facts([
      ["약칭", escapeHtml(team.abbr || "-")],
      ["리그", escapeHtml(team.league || "-")],
      ["지구", escapeHtml(team.division || "-")],
      ["첫 시즌", has(team.firstYear) ? team.firstYear + "년" : "-"],
    ]);

    const links = [];
    // MLB 구단의 선수 성적은 선수단 페이지에 있으므로 리더보드 링크는 산하 구단에만 둔다 (2026-11-18 사용자 결정)
    const board = isMajor ? "" : boardLink(team, season);
    if (board) links.push('<a href="' + board + '">' + season + " 선수 성적</a>");
    if (isMajor) links.push('<a href="roster.html?id=' + team.id + '">선수단</a>');
    if (isMajor) links.push('<a href="prospects.html?list=' + encodeURIComponent(team.abbr) + '">유망주 Top 30</a>');
    // 공식 홈페이지는 외부 사이트이므로 새 탭으로 연다
    if (team.site) links.push('<a href="' + escapeHtml(team.site) + '" target="_blank" rel="noopener">공식 홈페이지 ↗</a>');
    links.push('<a href="teams.html">구단 목록</a>');
    $("teamLinks").innerHTML = links.join("");
  }

  const personLink = (item) =>
    item.page ? '<a href="player.html?id=' + item.id + '">' + escapeHtml(item.name) + "</a>" : escapeHtml(item.name);

  // 구단 역사: 월드시리즈 우승, 주요 수상 횟수, 영구결번, 명예의 전당, 소개 글. MLB 구단에만 있다.
  // 값이 null이면 수집되지 않은 것이므로 0회가 아니라 미제공으로 표시한다.
  function renderHistory(team) {
    const history = team.history;
    if (!history) return;
    $("clubNote").textContent = team.note || "";
    $("clubNote").hidden = !team.note;

    const count = (value) => (has(value) ? value + "회" : "미제공");
    const awards = history.awards || {};
    $("historyFacts").innerHTML = facts([
      ["월드시리즈 우승", history.titles ? '<a href="awards.html?award=wschamp">' + history.titles.length + "회</a>" : "미제공"],
      ["최근 우승", history.titles ? (history.titles.length ? history.titles[0] + "년" : "없음") : "미제공"],
      ["MVP 배출", count(awards.mvp)],
      ["사이영상 배출", count(awards.cy)],
      ["신인왕 배출", count(awards.roy)],
      ["영구결번", history.retired.length + "건"],
    ]);

    const blocks = [];
    if (history.titles && history.titles.length) {
      blocks.push("<h3>월드시리즈 우승 연도</h3><p class=\"title-years\">" + history.titles.slice().reverse().join(", ") + "</p>");
    }
    if (history.retired.length) {
      blocks.push(
        "<h3>영구결번</h3><ul class=\"legend-list\">" +
        history.retired.map((item) =>
          '<li><span class="uniform">' + (item.number ? escapeHtml(item.number) : "-") + "</span>" + personLink(item) +
          ' <span class="muted">' + item.year + "</span></li>"
        ).join("") + "</ul>"
      );
    }
    if (history.hof && history.hof.length) {
      blocks.push(
        "<h3>명예의 전당 (" + history.hof.length + "명)</h3><ul class=\"legend-list\">" +
        history.hof.map((item) => "<li>" + personLink(item) + ' <span class="muted">' + item.year + "</span></li>").join("") + "</ul>"
      );
    }
    $("historyLists").innerHTML = blocks.join("");
    $("historySection").hidden = false;
  }

  // ---------- 연도별 성적 (data/franchise/{구단 ID}.json, scripts/franchise.py) ----------
  const POST_LABEL = {
    WS: "월드시리즈 우승", W: "월드시리즈 준우승", L: "챔피언십시리즈 탈락", D: "디비전시리즈 탈락", F: "와일드카드 탈락",
  };
  const RECENT_SEASONS = 20;
  const pct = (w, l) => (w + l ? (w / (w + l)).toFixed(3).replace(/^0/, "") : "-");

  function renderSeasons(team, rows) {
    if (!rows.length) return;
    const wins = rows.reduce((sum, row) => sum + row.W, 0);
    const losses = rows.reduce((sum, row) => sum + row.L, 0);
    const playoffs = rows.filter((row) => row.post).length;
    // 리그 우승: 월드시리즈 진출. 월드시리즈가 없던 시즌(1903년 이전, 1904년)은 리그 1위를 리그 우승으로 센다.
    const NO_WORLD_SERIES = (season) => season < 1903 || season === 1904;
    const pennants = rows.filter((row) =>
      row.post === "WS" || row.post === "W" || (NO_WORLD_SERIES(row.season) && row.rankType === "lg" && row.rank === 1)).length;
    const titles = rows.filter((row) => row.post === "WS").length;
    const divisions = rows.filter((row) => row.rankType === "div" && row.rank === 1).length;
    const first = rows[rows.length - 1].season;
    $("seasonFacts").innerHTML = facts([
      ["통산 승패", wins.toLocaleString("ko-KR") + "승 " + losses.toLocaleString("ko-KR") + "패"],
      ["통산 승률", pct(wins, losses)],
      ["포스트시즌 진출", playoffs + "회"],
      ["리그 우승", pennants + "회"],
      ["월드시리즈 우승", titles + "회"],
      ["지구 1위", divisions + "회"],
    ]);

    const current = team.name;
    let showAll = false;
    const draw = () => {
      const shown = showAll ? rows : rows.slice(0, RECENT_SEASONS);
      const ties = shown.some((row) => row.T);
      $("seasonHead").innerHTML =
        '<tr><th class="col-season">시즌</th><th class="col-name">팀</th><th class="col-team">리그</th>' +
        "<th>승</th><th>패</th>" + (ties ? "<th>무</th>" : "") +
        '<th>승률</th><th class="col-team">순위</th><th title="1위와의 승차">게임차</th>' +
        '<th>득점</th><th>실점</th><th title="득점 - 실점">득실차</th>' +
        '<th title="득점·실점으로 계산한 피타고리안 기대 승패 (지수 1.83)">기대 승패</th>' +
        '<th class="col-team">포스트시즌</th></tr>';
      $("seasonBody").innerHTML = shown.map((row) => {
        const diff = has(row.RS) && has(row.RA) ? row.RS - row.RA : null;
        const rank = has(row.rank) ? (row.rankType === "div" ? "지구 " : "리그 ") + row.rank + "위" : "-";
        const post = row.post
          ? '<span class="post-result post-' + row.post + '">' + POST_LABEL[row.post] + "</span>"
          : '<span class="muted">-</span>';
        return (
          "<tr" + (row.post === "WS" ? ' class="title-season"' : "") + '><td class="col-season">' + row.season + "</td>" +
          '<td class="col-name' + (row.name === current ? " muted" : "") + '">' + escapeHtml(row.name || "-") + "</td>" +
          '<td class="col-team">' + escapeHtml(row.lg || "-") + "</td>" +
          "<td>" + row.W + "</td><td>" + row.L + "</td>" + (ties ? "<td>" + (row.T || 0) + "</td>" : "") +
          "<td>" + pct(row.W, row.L) + "</td>" +
          '<td class="col-team' + (row.rank === 1 ? " rank-first" : "") + '">' + rank + "</td>" +
          "<td>" + escapeHtml(row.GB || "-") + "</td>" +
          "<td>" + (has(row.RS) ? row.RS : "-") + "</td><td>" + (has(row.RA) ? row.RA : "-") + "</td>" +
          "<td>" + (diff === null ? "-" : (diff > 0 ? "+" : "") + diff) + "</td>" +
          "<td>" + (has(row.xW) ? row.xW + "-" + row.xL : "-") + "</td>" +
          '<td class="col-team">' + post + "</td></tr>"
        );
      }).join("");
      $("seasonMore").innerHTML = rows.length > RECENT_SEASONS
        ? '<button type="button" class="link-button">' + (showAll ? "최근 " + RECENT_SEASONS + "시즌만 보기" : "전체 " + rows.length + "시즌 보기 (" + first + "년부터)") + "</button>"
        : "";
    };
    $("seasonMore").addEventListener("click", (event) => {
      if (!event.target.closest("button")) return;
      showAll = !showAll;
      draw();
    });
    draw();
    $("seasonSection").hidden = false;
  }

  function renderVenue(team, season) {
    const v = team.venue;
    $("venueName").textContent = v.name || "구장 정보 없음";
    $("venueAddress").textContent = [v.address, venue.place(v) === "-" ? "" : venue.place(v)].filter(has).join(", ");

    $("venueFacts").innerHTML = facts([
      ["수용 인원", venue.capacity(v.capacity)],
      ["잔디", venue.turf(v.turf)],
      ["지붕", venue.roof(v.roof)],
      ["해발", has(v.elevationFt) ? venue.meters(v.elevationFt) + "m" : "-"],
      ["좌측 폴", feet(v.fence[0])],
      ["좌중간", feet(v.fence[1])],
      ["중앙", feet(v.fence[2])],
      ["우중간", feet(v.fence[3])],
      ["우측 폴", feet(v.fence[4])],
      [season + " 파크팩터", venue.pf(team.pf)],
    ]);

    // 지도는 좌표로 외부 지도 서비스를 새 창에서 연다
    if (has(v.lat) && has(v.lon)) {
      const at = v.lat + "," + v.lon;
      $("venueLinks").innerHTML =
        '<a href="https://www.google.com/maps/search/?api=1&query=' + at + '" target="_blank" rel="noopener">Google 지도에서 보기</a>' +
        '<a href="https://www.openstreetmap.org/?mlat=' + v.lat + "&mlon=" + v.lon + "#map=16/" + v.lat + "/" + v.lon +
        '" target="_blank" rel="noopener">OpenStreetMap에서 보기</a>';
    } else {
      $("venueLinks").innerHTML = '<span class="muted">위치 좌표 미제공</span>';
    }

    const svg = fieldSvg(v.fence);
    $("venueField").innerHTML = svg;
    $("venueField").hidden = !svg;
  }

  function renderOrg(team, parent, season) {
    $("orgTitle").textContent = parent.name + " 조직";
    $("orgHead").innerHTML =
      '<tr><th class="col-team">레벨</th><th class="col-name">구단</th><th class="col-team">리그</th>' +
      '<th class="col-team">구장</th><th class="col-team">위치</th><th>수용 인원</th>' +
      '<th title="좌측 폴-중앙-우측 폴 거리(피트)">펜스</th>' +
      '<th title="자체 계산 득점 파크팩터. 1.000이 중립">파크팩터</th><th class="col-team">성적</th></tr>';

    $("orgBody").innerHTML = [parent].concat(parent.affiliates).map((item) => {
      const v = item.venue;
      const fence = [v.fence[0], v.fence[2], v.fence[4]].every(has) ? [v.fence[0], v.fence[2], v.fence[4]].join("-") : "-";
      const board = boardLink(item, season);
      return (
        "<tr" + (item.id === team.id ? ' class="current"' : "") + ">" +
        '<td class="col-team">' + levelBadge(item.level) + "</td>" +
        '<td class="col-name"><a href="team.html?id=' + item.id + '">' + escapeHtml(item.name) + "</a></td>" +
        '<td class="col-team">' + escapeHtml(item.league || "-") + "</td>" +
        '<td class="col-team">' + escapeHtml(v.name || "-") + "</td>" +
        '<td class="col-team">' + escapeHtml(venue.place(v)) + "</td>" +
        "<td>" + (has(v.capacity) ? v.capacity.toLocaleString("ko-KR") : "-") + "</td>" +
        "<td>" + fence + "</td>" +
        "<td>" + venue.pf(item.pf) + "</td>" +
        '<td class="col-team">' + (board ? '<a href="' + board + '">선수 성적</a>' : '<span class="muted">미제공</span>') + "</td></tr>"
      );
    }).join("");
  }

  function fail(message) {
    $("status").className = "status error";
    $("status").textContent = message;
  }

  async function init() {
    const id = Number(new URLSearchParams(location.search).get("id"));
    let data;
    try {
      data = await loadJson("data/teams.json");
    } catch (error) {
      fail("구단 데이터를 불러오지 못했습니다: " + error.message);
      return;
    }

    let team = null;
    let parent = null;
    for (const club of data.clubs) {
      const found = club.id === id ? club : club.affiliates.find((item) => item.id === id);
      if (found) {
        team = found;
        parent = club;
        break;
      }
    }
    if (!team) {
      fail("구단을 찾을 수 없습니다. 구단 목록에서 다시 선택해 주세요.");
      return;
    }

    renderProfile(team, parent, data.season);
    renderHistory(team);
    if (team.level === "MLB") {
      loadJson("data/franchise/" + team.id + ".json").then((item) => renderSeasons(team, item.seasons)).catch(() => {});
    }
    renderVenue(team, data.season);
    renderOrg(team, parent, data.season);
    $("status").hidden = true;
    $("content").hidden = false;
    $("updatedText").textContent = "구단 정보 갱신: " + new Date(data.updated).toLocaleString("ko-KR");
  }

  init();
})();
