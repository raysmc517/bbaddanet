// 빠따넷 대문
// 순위·경기·뉴스·이동의 최신 몇 건을 저장된 JSON에서 읽어 미리 보여준다. 각 영역은 따로 실패한다.

(function () {
  "use strict";

  const { loadJson, escapeHtml: esc, fmt, rankMark } = window.BB;
  const $ = (id) => document.getElementById(id);
  const kst = (value, options) => new Date(value).toLocaleString("ko-KR", Object.assign({ timeZone: "Asia/Seoul" }, options));
  const DIRECTIONS = { East: "동부", West: "서부", Central: "중부" };
  const MOVE_TYPES = { trade: "트레이드", sign: "FA 계약", claim: "웨이버 클레임", release: "방출", fa: "FA 선언" };

  const fail = (id, text) => { $(id).innerHTML = '<p class="status">' + esc(text) + "</p>"; };
  // 미리보기 영역은 내용이 길어 화면 읽기 프로그램에 실시간으로 읽히지 않게 두고, 다 불러오면 aria-busy만 끈다
  const done = (id) => () => $(id).setAttribute("aria-busy", "false");

  // MLB 공식 로고. 파일을 저장하지 않고 주소로만 걸며(js/team.js와 같은 방식) 못 받으면 숨긴다
  const LOGO_BASE = "https://www.mlbstatic.com/team-logos/";
  const logo = (team) =>
    '<picture class="home-logo"><source media="(prefers-color-scheme: dark)" srcset="' + LOGO_BASE + "team-cap-on-dark/" + team.id + '.svg">' +
    '<img src="' + LOGO_BASE + team.id + '.svg" alt="" width="32" height="32" loading="lazy"></picture>';
  const hideBrokenLogos = (root) => root.querySelectorAll(".home-logo img").forEach((img) =>
    img.addEventListener("error", () => { img.parentNode.style.visibility = "hidden"; }));

  const currentSeason = loadJson("data/meta.json").then((meta) => ({ meta, season: meta.leagues.find((l) => l.id === "mlb").seasons[0] }));

  // 가장 최근 시즌의 MLB 지구 1위 6팀. 아메리칸리그·내셔널리그로 나눈다
  async function standings() {
    const { meta, season } = await currentSeason;
    const data = await loadJson("data/standings_" + season + ".json");
    const mlb = data.levels.find((level) => level.id === "mlb");
    const leagues = mlb.leagues.map((league) => {
      const rows = league.divisions.map((division) => {
        const t = division.teams[0];
        const word = String(division.short || "").split(" ").pop();
        const pct = t.W + t.L ? fmt.rate(t.W / (t.W + t.L)) : "-";
        return '<li><span class="home-division">' + esc(DIRECTIONS[word] || word) + "</span>" + logo(t) +
          '<a class="home-team" href="team.html?id=' + t.id + '">' + esc(t.name) + "</a>" +
          '<span class="home-record">' + t.W + "-" + t.L + ' <span class="muted">' + pct + "</span></span></li>";
      }).join("");
      return '<section class="home-league"><h4>' + esc(league.name) + '</h4><ul class="home-leaders">' + rows + "</ul></section>";
    });
    $("homeStandings").innerHTML = '<p class="muted">' + season + " MLB 지구 1위</p>" + '<div class="home-leagues">' + leagues.join("") + "</div>";
    hideBrokenLogos($("homeStandings"));
    $("updatedText").textContent = "데이터 갱신: " + kst(meta.updated) + " (한국 시간)";
  }

  // 개인 순위: 최근 시즌 MLB 부문별 상위 3명. 비율 지표는 규정타석·규정이닝(q)을 채운 선수만 센다.
  // 같은 값은 같은 순위이며, 3위 안에 동률이 걸리면 모두 보여준다.
  const CATEGORIES = {
    batting: [
      { key: "HR", label: "홈런", format: fmt.int },
      { key: "AVG", label: "타율", format: fmt.rate, qualified: true },
      { key: "wRCp", label: "wRC+", format: fmt.int, qualified: true, term: "wrc-plus" },
      { key: "OPS", label: "OPS", format: fmt.rate, qualified: true, term: "ops" },
    ],
    pitching: [
      { key: "SO", label: "탈삼진", format: fmt.int },
      { key: "ERA", label: "평균자책점", format: fmt.dec2, qualified: true, asc: true },
      { key: "FIP", label: "FIP", format: fmt.dec2, qualified: true, asc: true, term: "fip" },
      { key: "SV", label: "세이브", format: fmt.int },
    ],
  };
  // 선수 얼굴 사진: 파일을 저장하지 않고 MLB 공식 이미지 주소로만 표시한다(js/player.js와 같은 주소). 사진이 없으면 기본 실루엣이 온다
  const PHOTO_URL = "https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_96,q_auto:best/v1/people/";
  const photo = (id) => '<img class="home-photo" src="' + PHOTO_URL + encodeURIComponent(id) + '/headshot/67/current" alt="" width="32" height="32" loading="lazy">';
  const players = {};
  let group = "batting";

  function top3(rows, category) {
    const pool = rows.filter((p) => typeof p[category.key] === "number" && (!category.qualified || p.q));
    pool.sort((a, b) => (category.asc ? a[category.key] - b[category.key] : b[category.key] - a[category.key]));
    const out = [];
    for (let i = 0, rank = 0; i < pool.length; i++) {
      if (!i || pool[i][category.key] !== pool[i - 1][category.key]) rank = i + 1;
      if (rank > 3) break;
      out.push({ p: pool[i], rank });
    }
    return out;
  }

  function renderLeaders(season) {
    const rows = players[group];
    const groupName = group === "batting" ? "타자" : "투수";
    $("homePlayers").innerHTML = '<p class="muted">' + season + " MLB " + groupName + " · 비율 지표는 " +
      (group === "batting" ? "규정타석" : "규정이닝") + ' 이상</p><div class="home-categories">' +
      CATEGORIES[group].map((category) => {
        const list = top3(rows, category).map(({ p, rank }) =>
          '<li><span class="home-rank">' + rankMark(rank) + "</span>" + photo(p.id) + '<a href="player.html?id=' + p.id + '">' + esc(p.name) + "</a>" +
          ' <span class="muted">' + esc(p.nt > 1 ? p.nt + "팀" : p.team) + '</span><span class="home-value">' + category.format(p[category.key]) + "</span></li>").join("");
        const title = category.term ? '<a href="glossary.html#' + category.term + '">' + esc(category.label) + "</a>" : esc(category.label);
        return '<section class="home-category"><h4>' + title + '</h4><ol class="home-top">' + (list || '<li class="muted">기록 없음</li>') + "</ol></section>";
      }).join("") + "</div>";
  }

  async function leaders() {
    const { season } = await currentSeason;
    const [batting, pitching] = await Promise.all([
      loadJson("data/mlb/batting_" + season + ".json"),
      loadJson("data/mlb/pitching_" + season + ".json"),
    ]);
    players.batting = batting.players;
    players.pitching = pitching.players;
    const buttons = $("homePlayerSwitch").querySelectorAll("button");
    const sync = () => buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.value === group)));
    $("homePlayerSwitch").addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button || button.dataset.value === group) return;
      group = button.dataset.value;
      sync();
      renderLeaders(season);
    });
    sync();
    $("homePlayerSwitch").hidden = false;
    $("homeMoreLeaders").href = "leaderboard.html?league=mlb&season=" + season;
    renderLeaders(season);
  }

  // 수집된 가장 최근 경기일. 경기가 없으면(비시즌) 그렇다고 적고 뉴스 제목을 보여준다
  async function games() {
    let html = "";
    try {
      const dates = await loadJson("data/games/index.json");
      const day = dates.length ? await loadJson("data/games/" + dates[0] + ".json") : null;
      if (!day) html += '<p class="status">수집된 경기 날짜가 없습니다.</p>';
      else if (!day.games.length) html += '<p class="muted">' + esc(day.date) + " (미국 현지) · 이 날 MLB 경기가 없습니다.</p>";
      else {
        html += '<p class="muted">' + esc(day.date) + " (미국 현지)</p><ul class=\"home-list\">" + day.games.slice(0, 4).map((g) => {
          const a = g.teams.away, h = g.teams.home;
          const s = (v) => (v === null || v === undefined ? "-" : v);
          return "<li>" + esc(a.name) + " <strong>" + s(a.score) + " : " + s(h.score) + "</strong> " + esc(h.name) + "</li>";
        }).join("") + "</ul>";
        if (day.games.length > 4) html += '<p class="muted">외 ' + (day.games.length - 4) + "경기</p>";
      }
    } catch (_) { html += '<p class="status">경기 자료를 불러오지 못했습니다.</p>'; }
    try {
      const news = await loadJson("data/news.json");
      html += '<p class="muted home-news-title">MLB.com 뉴스</p><ul class="home-list">' + news.items.slice(0, 3).map((item) =>
        '<li><a href="' + esc(item.url) + '" target="_blank" rel="noopener">' + esc(item.title) + "</a></li>").join("") + "</ul>";
    } catch (_) { html += '<p class="status">뉴스 자료를 불러오지 못했습니다.</p>'; }
    $("homeGames").innerHTML = html;
  }

  // 최근 시즌의 이적(트레이드·FA 계약 등) 최신 5건. 명단 등록·양도지명은 빼고 시장 소식만 둔다
  async function moves() {
    const { season } = await currentSeason;
    const data = await loadJson("data/moves_" + season + ".json");
    const rows = data.events.filter((e) => MOVE_TYPES[e.type]).slice(0, 5);
    if (!rows.length) return fail("homeMoves", season + " 시즌 이적 기록이 없습니다.");
    $("homeMoves").innerHTML = '<ul class="home-list home-moves">' + rows.map((e) => {
      const names = e.players.map((p) => p.page
        ? '<a href="player.html?id=' + p.id + '">' + esc(p.name) + "</a>"
        : esc(p.name)).join(", ");
      return '<li><span class="move-badge move-' + e.type + '">' + MOVE_TYPES[e.type] + "</span> " + names +
        ' <span class="muted">' + esc(e.date.slice(5).replace("-", ".")) + "</span></li>";
    }).join("") + "</ul>";
  }

  standings().catch(() => fail("homeStandings", "순위 자료를 불러오지 못했습니다.")).finally(done("homeStandings"));
  leaders().catch(() => fail("homePlayers", "선수 기록을 불러오지 못했습니다.")).finally(done("homePlayers"));
  games().finally(done("homeGames"));
  moves().catch(() => fail("homeMoves", "이동 자료를 불러오지 못했습니다.")).finally(done("homeMoves"));
})();
