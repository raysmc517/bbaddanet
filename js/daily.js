(function () {
  "use strict";
  const { loadJson, escapeHtml: esc } = window.BB;
  const $ = (id) => document.getElementById(id);
  const time = (value) => value ? new Date(value).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" }) : "시각 미제공";
  const score = (value) => value === null || value === undefined ? "-" : value;
  const teamLink = (team) => '<a href="team.html?id=' + team.id + '">' + esc(team.name) + '</a>';
  let request = 0;
  async function renderGames() {
    const version = ++request;
    $("gamesFeed").textContent = "불러오는 중…";
    try {
      const data = await loadJson("data/games/" + $("gameDate").value + ".json");
      if (version !== request) return;
      const favorites = window.BB.favorites.read().teams.map((t) => t.id);
      const rows = data.games.filter((game) => !$("favoriteGames").checked ||
        favorites.includes(game.teams.home.id) || favorites.includes(game.teams.away.id));
      $("gameUpdated").textContent = "경기 자료 갱신: " + time(data.updated) + " (한국 시간) · 수집 당시 상태";
      $("gamesFeed").innerHTML = rows.map((game) => {
        const away = game.teams.away, home = game.teams.home;
        const labels = {Final:"종료", Live:"진행 중", Preview:"예정"};
        const decisions = Object.entries(game.decisions).map(([kind, person]) =>
          ({winner:"승",loser:"패",save:"세이브"}[kind] || kind) + ': <a href="player.html?id=' + person.id + '">' + esc(person.name) + '</a>').join(" · ");
        return '<article class="game-card"><p class="muted">' + (labels[game.state] || esc(game.state)) + " · " + esc(game.status) +
          " · " + time(game.start) + ' (한국 시간)</p><h3>' + teamLink(away) + ' ' + score(away.score) + ' : ' + score(home.score) + ' ' + teamLink(home) + '</h3>' +
          (game.innings.length ? '<div class="table-scroll"><table class="stats"><thead><tr><th>구단</th>' +
            game.innings.map((i) => '<th>' + i.n + '</th>').join("") + '</tr></thead><tbody>' + ["away", "home"].map((side) =>
              '<tr><th>' + teamLink(game.teams[side]) + '</th>' + game.innings.map((i) => '<td>' + score(i[side]) + '</td>').join("") + '</tr>').join("") + '</tbody></table></div>' : "") +
          '<p>' + decisions + '</p><a href="https://www.mlb.com/gameday/' + game.id + '" target="_blank" rel="noopener">MLB 경기 상세</a></article>';
      }).join("") || '<p class="status">' + ($("favoriteGames").checked ? "이 날짜에 관심 팀 경기가 없습니다. 관심 팀은 구단 페이지에서 설정하세요." : "이 날짜의 MLB 경기가 없습니다.") + '</p>';
      const params = new URLSearchParams();
      params.set("date", data.date);
      history.replaceState(null, "", "?" + params);
    } catch (_) {
      if (version === request) { $("gamesFeed").textContent = "경기 자료를 불러오지 못했습니다."; $("gameUpdated").textContent = ""; }
    }
  }
  async function init() {
    try {
      const dates = await loadJson("data/games/index.json");
      $("gameDate").innerHTML = dates.map((d) => '<option>' + esc(d) + '</option>').join("");
      const selected = new URLSearchParams(location.search).get("date");
      if (dates.includes(selected)) $("gameDate").value = selected;
      $("gameDate").addEventListener("change", renderGames);
      $("favoriteGames").addEventListener("change", renderGames);
      if (dates.length) renderGames();
      else $("gamesFeed").textContent = "수집된 경기 날짜가 없습니다.";
    } catch (_) { $("gamesFeed").textContent = "경기 날짜 목록을 불러오지 못했습니다."; }
    try {
      const news = await loadJson("data/news.json");
      $("newsUpdated").textContent = "뉴스 갱신: " + time(news.updated) + " (한국 시간)";
      $("newsFeed").innerHTML = news.items.map((item) => '<li><a href="' + esc(item.url) + '" target="_blank" rel="noopener">' + esc(item.title) +
        '</a><p class="muted">보도 · ' + esc(item.source) + " · " + time(item.published) + ' (한국 시간)</p></li>').join("");
    } catch (_) { $("newsFeed").textContent = "뉴스 자료를 불러오지 못했습니다."; }
    const favorites = window.BB.favorites.read();
    $("favoriteStats").innerHTML = favorites.players.length ? favorites.players.map((p) => '<a class="favorite-stat" href="player.html?id=' + p.id + '">' + esc(p.name) + ' 성적</a>').join(" · ") :
      '<a href="search.html">선수를 찾아 관심 선수로 설정하세요.</a>';
  }
  init();
})();
