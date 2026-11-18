// 빠따넷 구단 연도별 성적
// franchise.html?id={MLB 구단 ID}로 열면 data/franchise/{구단 ID}.json(scripts/franchise.py)을 읽어
// 통산 기록과 시즌별 승패·순위·득실점·기대 승패·포스트시즌 결과를 보여준다.
// 구단 페이지의 "구단 역사"에서 들어온다 (2026-11-18 사용자 결정: 연도별 성적은 별도 페이지).

(function () {
  "use strict";

  const { escapeHtml, loadJson, has } = window.BB;
  const $ = (id) => document.getElementById(id);

  const POST_LABEL = {
    WS: "월드시리즈 우승", W: "월드시리즈 준우승", L: "챔피언십시리즈 탈락", D: "디비전시리즈 탈락", F: "와일드카드 탈락",
  };
  const pct = (w, l) => (w + l ? (w / (w + l)).toFixed(3).replace(/^0/, "") : "-");
  // 월드시리즈가 없던 시즌(1903년 이전, 1904년)은 리그 1위를 리그 우승으로 센다
  const noWorldSeries = (season) => season < 1903 || season === 1904;
  const isPennant = (row) =>
    row.post === "WS" || row.post === "W" || (noWorldSeries(row.season) && row.rankType === "lg" && row.rank === 1);

  const facts = (pairs) =>
    pairs.map(([label, value]) => "<div><dt>" + escapeHtml(label) + "</dt><dd>" + value + "</dd></div>").join("");

  function renderFacts(rows) {
    const wins = rows.reduce((sum, row) => sum + row.W, 0);
    const losses = rows.reduce((sum, row) => sum + row.L, 0);
    $("seasonFacts").innerHTML = facts([
      ["기간", rows[rows.length - 1].season + "~" + rows[0].season + " (" + rows.length + "시즌)"],
      ["통산 승패", wins.toLocaleString("ko-KR") + "승 " + losses.toLocaleString("ko-KR") + "패"],
      ["통산 승률", pct(wins, losses)],
      ["포스트시즌 진출", rows.filter((row) => row.post).length + "회"],
      ["리그 우승", rows.filter(isPennant).length + "회"],
      ["월드시리즈 우승", rows.filter((row) => row.post === "WS").length + "회"],
      ["지구 1위", rows.filter((row) => row.rankType === "div" && row.rank === 1).length + "회"],
    ]);
  }

  function renderTable(team, rows) {
    const ties = rows.some((row) => row.T);
    $("seasonHead").innerHTML =
      '<tr><th class="col-season">시즌</th><th class="col-name">팀</th><th class="col-team">리그</th>' +
      "<th>승</th><th>패</th>" + (ties ? "<th>무</th>" : "") +
      '<th>승률</th><th class="col-team">순위</th><th title="1위와의 승차">게임차</th>' +
      '<th>득점</th><th>실점</th><th title="득점 - 실점">득실차</th>' +
      '<th title="득점·실점으로 계산한 피타고리안 기대 승패 (지수 1.83)">기대 승패</th>' +
      '<th class="col-team">포스트시즌</th></tr>';
    $("seasonBody").innerHTML = rows.map((row) => {
      const diff = has(row.RS) && has(row.RA) ? row.RS - row.RA : null;
      const rank = has(row.rank) ? (row.rankType === "div" ? "지구 " : "리그 ") + row.rank + "위" : "-";
      const post = row.post
        ? '<span class="post-result post-' + row.post + '">' + POST_LABEL[row.post] + "</span>"
        : isPennant(row) ? '<span class="post-result post-W">리그 우승</span>' : '<span class="muted">-</span>';
      return (
        "<tr" + (row.post === "WS" ? ' class="title-season"' : "") + '><td class="col-season">' + row.season + "</td>" +
        '<td class="col-name' + (row.name === team.name ? " muted" : "") + '">' + escapeHtml(row.name || "-") + "</td>" +
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
    }).join("") || '<tr><td colspan="14" class="muted">해당 조건의 시즌이 없습니다.</td></tr>';
  }

  // 기간(시작~끝 시즌) 선택. 목록은 최신 시즌부터(내림차순). 고른 조건은 주소(from, to, post)에 남긴다.
  // 통산 칸도 고른 기간 기준으로 다시 센다 (2026-11-18 사용자 요구: 기간 선택)
  function setupFilters(team, rows) {
    const seasons = rows.map((row) => row.season); // rows는 최신 시즌부터
    const options = seasons.map((season) => '<option value="' + season + '">' + season + "</option>").join("");
    $("fromSelect").innerHTML = '<option value="">처음부터</option>' + options;
    $("toSelect").innerHTML = '<option value="">최근까지</option>' + options;
    const params = new URLSearchParams(location.search);
    if (seasons.map(String).includes(params.get("from"))) $("fromSelect").value = params.get("from");
    if (seasons.map(String).includes(params.get("to"))) $("toSelect").value = params.get("to");
    $("postOnly").checked = params.get("post") === "1";

    const update = () => {
      let from = $("fromSelect").value;
      let to = $("toSelect").value;
      if (from && to && Number(from) > Number(to)) {
        [from, to] = [to, from]; // 시작이 끝보다 늦으면 맞바꾼다
        $("fromSelect").value = from;
        $("toSelect").value = to;
      }
      const inPeriod = rows.filter((row) => (!from || row.season >= Number(from)) && (!to || row.season <= Number(to)));
      const postOnly = $("postOnly").checked;
      const shown = inPeriod.filter((row) => !postOnly || row.post);
      if (inPeriod.length) renderFacts(inPeriod);
      renderTable(team, shown);
      $("seasonCount").textContent = shown.length + "시즌";
      const next = new URLSearchParams(location.search);
      from ? next.set("from", from) : next.delete("from");
      to ? next.set("to", to) : next.delete("to");
      postOnly ? next.set("post", "1") : next.delete("post");
      history.replaceState(null, "", "?" + next.toString());
    };
    $("fromSelect").addEventListener("change", update);
    $("toSelect").addEventListener("change", update);
    $("postOnly").addEventListener("change", update);
    update();
  }

  function fail(message) {
    $("status").className = "status error";
    $("status").textContent = message;
  }

  async function init() {
    const id = Number(new URLSearchParams(location.search).get("id"));
    let teams;
    try {
      teams = await loadJson("data/teams.json");
    } catch (error) {
      fail("구단 데이터를 불러오지 못했습니다: " + error.message);
      return;
    }
    const team = teams.clubs.find((club) => club.id === id);
    if (!team) {
      fail("MLB 구단을 찾을 수 없습니다. 구단 목록에서 다시 선택해 주세요.");
      return;
    }
    let rows;
    try {
      rows = (await loadJson("data/franchise/" + id + ".json")).seasons;
    } catch (error) {
      fail("연도별 성적을 불러오지 못했습니다.");
      return;
    }
    if (!rows.length) {
      fail("제공된 연도별 성적이 없습니다.");
      return;
    }

    document.title = "빠따넷 · " + team.name + " 연도별 성적";
    $("teamName").textContent = team.name + " 연도별 성적";
    $("teamSub").innerHTML = '<span class="level level-mlb">MLB</span> ' + escapeHtml(team.division || "");
    const logo = $("teamLogo");
    logo.innerHTML =
      '<source media="(prefers-color-scheme: dark)" srcset="https://www.mlbstatic.com/team-logos/team-cap-on-dark/' + team.id + '.svg">' +
      '<img src="https://www.mlbstatic.com/team-logos/' + team.id + '.svg" alt="' + escapeHtml(team.name) + ' 로고" width="72" height="72">';
    logo.querySelector("img").addEventListener("error", () => { logo.hidden = true; });
    logo.hidden = false;
    $("teamLinks").innerHTML =
      '<a href="team.html?id=' + team.id + '">구단 정보</a>' +
      '<a href="roster.html?id=' + team.id + '">선수단</a>' +
      '<a href="standings.html">순위</a>';

    setupFilters(team, rows);
    $("status").hidden = true;
    $("content").hidden = false;
  }

  init();
})();
