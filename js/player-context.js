// 선수 커리어의 맥락: 같은 시즌 MLB 평균, 기록 기반 요약, 상황별 기록, 전체 이적, 출처 있는 계약.
(function () {
  "use strict";
  const { loadJson, escapeHtml: esc } = window.BB;
  const $ = (id) => document.getElementById(id);
  const numeric = (v) => v !== null && v !== undefined && Number.isFinite(Number(v));
  const f = (v, digits = 3) => numeric(v) ? Number(v).toFixed(digits) : "-";
  const pct = (v) => numeric(v) ? (Number(v) * 100).toFixed(1) + "%" : "-";
  const money = (v) => numeric(v) ? "$" + Number(v).toLocaleString("en-US") : "미확인";
  const box = (title, content) => '<section class="career-section context-card"><h2>' + title + '</h2>' + content + '</section>';
  const note = (text) => '<p class="page-note">' + text + '</p>';
  function table(headers, rows) {
    return '<div class="table-scroll"><table class="stats"><thead><tr>' + headers.map((v) => '<th>' + v + '</th>').join("") +
      '</tr></thead><tbody>' + rows.map((row) => '<tr>' + row.map((v) => '<td>' + v + '</td>').join("") + '</tr>').join("") + '</tbody></table></div>';
  }

  async function transfers(player) {
    try {
      const [history, teams] = await Promise.all([loadJson("data/player_moves.json"), loadJson("data/teams.json")]);
      const rows = history[player.id] || [];
      const label = { trade: "트레이드", sign: "FA 계약", claim: "웨이버 클레임", release: "방출", fa: "FA 선언" };
      const club = (id) => {
        const item = teams.clubs.find((t) => t.id === id);
        return item ? '<a href="team.html?id=' + item.id + '">' + esc(item.abbr) + '</a>' : "-";
      };
      $("playerTransfers").innerHTML = box("이적 내역", (rows.length ? table(["날짜", "종류", "이전 구단", "이후 구단"],
        rows.map((r) => [esc(r.date), label[r.type], club(r.from), club(r.to)])) : '<p class="muted">제공 범위에서 확인된 이적이 없습니다.</p>') +
        note('2009년 이후 MLB 공식 처리 기록 · 최신순 · 트레이드·메이저 FA 계약·클레임·방출·FA 선언. 마이너 계약·연장계약과 그 이전 이적은 포함하지 않습니다.'));
    } catch (_) { $("playerTransfers").innerHTML = box("이적 내역", note("이적 자료를 불러오지 못했습니다.")); }
  }

  async function contracts(player) {
    try {
      const data = await loadJson("data/contracts.json");
      const rows = data.players[player.id] || [];
      const source = (url, label) => '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(label || "MLB.com") + '</a>';
      const season = Number(data.checked.slice(0, 4));
      const salaryTable = (r) => {
        const salaries = window.BB.contracts.salaryRows(r);
        if (!salaries.length) return "";
        const hasDeferred = salaries.some((s) => s.deferredUSD !== null);
        return '<details class="contract-salaries"><summary>시즌별 기본 연봉 · ' + salaries.length + '시즌' +
          (r.salaryComplete ? "" : " (확인된 시즌만)") + '</summary>' +
          table(["시즌", "기본 연봉 (USD)", ...(hasDeferred ? ["이 중 이연액", "이연 제외 기본 연봉"] : [])],
            salaries.map((s) => [s.season, money(s.baseUSD), ...(hasDeferred ? [money(s.deferredUSD), money(s.nonDeferredUSD)] : [])])) +
          note('연봉 출처: ' + source(r.salarySource || r.source, r.salarySourceLabel || r.sourceLabel) +
            ' · 계약서상 금액이며 계약금·옵션 바이아웃·성과급을 제외합니다. 징계·마이너 배정·단축 시즌 등에 따른 실제 지급액은 다를 수 있습니다.') + '</details>';
      };
      $("playerContracts").innerHTML = box("계약·연봉", rows.length ? rows.map((r) => {
        const current = window.BB.contracts.salaryRows(r).find((s) => s.season === season);
        return (
        '<h3>' + esc(r.team) + ' · ' + r.from + '–' + r.to + '</h3>' +
        '<p class="muted">' + (r.listedTeam ? '자료 분류 구단 · 공개 계약 표제의 기간' : '계약 당시 구단 · 발표된 보장 기간') + '</p>' +
        '<dl class="profile-facts"><div><dt>' + (r.listedTeam ? '공개 계약 표제' : '보장 계약') + '</dt><dd>' + (r.to - r.from + 1) + '년 · ' + money(r.totalUSD) + '</dd></div>' +
        '<div><dt>단순 연평균</dt><dd>' + money(numeric(r.totalUSD) ? Math.round(r.totalUSD / (r.to - r.from + 1)) : null) + '</dd></div>' +
        '<div><dt>' + season + ' 기본 연봉</dt><dd>' + money(current && current.baseUSD) + '</dd></div>' +
        (numeric(r.signingBonusUSD) ? '<div><dt>계약금</dt><dd>' + money(r.signingBonusUSD) + ' (보장 총액에 포함)</dd></div>' : "") +
        (numeric(r.buyoutUSD) ? '<div><dt>옵션 바이아웃</dt><dd>' + money(r.buyoutUSD) + ' (보장 총액에 포함)</dd></div>' : "") + '</dl>' +
        (r.salaryNote ? note(esc(r.salaryNote)) : "") + salaryTable(r) +
        note(esc(r.note) + ' 출처: ' + source(r.source, r.sourceLabel) +
          (r.termsSource ? ' · 조건 확인: ' + source(r.termsSource, r.termsSourceLabel) : "") + ' · 자료 확인 ' + esc(r.checked || data.checked))
        );
      }).join("") + note("등록된 계약의 발표 조건입니다. 단순 연평균은 총액÷연수이며 연봉·실수령액·사치세 기준 AAV와 다릅니다. 옵션 연봉과 성과급은 보장 총액에 더하지 않으며, 옵트아웃·이적·계약 변경에 따라 기간과 지급 조건이 달라질 수 있습니다.") :
        '<p class="muted">출처를 확인해 등록한 계약이 없습니다. 계약이 없거나 연봉이 0이라는 뜻은 아닙니다.</p>');
    } catch (_) { $("playerContracts").innerHTML = box("계약·연봉", note("계약 자료를 불러오지 못했습니다.")); }
  }

  function report(group, row, average) {
    const pitching = group === "pitching";
    const sample = pitching ? row.outs : row.PA;
    const enough = numeric(sample) && sample >= (pitching ? 90 : 100);
    if (!enough) return note("이 시즌은 표본이 작아 강점·약점 요약을 제공하지 않습니다 (100타석 또는 30이닝부터).");
    const measures = pitching ? [["Kp", "탈삼진 비율", true], ["BBp", "볼넷 허용 비율", false], ["WHIP", "이닝당 출루 허용", false]] :
      [["BBp", "볼넷 비율", true], ["Kp", "삼진 억제", false], ["ISO", "순장타율", true]];
    const strengths = [], weaknesses = [];
    measures.forEach(([key, title, high]) => {
      const value = row[key], base = average[key];
      if (!numeric(value) || !numeric(base) || base <= 0) return;
      const delta = value / base - 1;
      if (Math.abs(delta) < 0.1) return;
      const good = high ? delta > 0 : delta < 0;
      (good ? strengths : weaknesses).push(title + " (" + (key.endsWith("p") ? pct(value) : f(value)) + ", 평균 " +
        (key.endsWith("p") ? pct(base) : f(base)) + ")");
    });
    return '<p><strong>강점:</strong> ' + (strengths.join(" · ") || "선택 지표에서 평균보다 10% 이상 유리한 항목 없음") + '</p>' +
      '<p><strong>약점:</strong> ' + (weaknesses.join(" · ") || "선택 지표에서 평균보다 10% 이상 불리한 항목 없음") + '</p>' +
      note("해당 시즌 MLB 전체 평균과 10% 이상 차이 나는 항목을 기록으로 요약합니다. 수비·주루·구종·부상·미래 성적을 평가하는 스카우팅 리포트는 아닙니다.");
  }

  function comparison(group, row, average) {
    const key = group === "batting" ? "OPS" : "ERA";
    if (!numeric(row[key]) || !numeric(average[key]) || average[key] <= 0) return "";
    const delta = (row[key] / average[key] - 1) * 100;
    return '<p><strong>' + key + '</strong>는 같은 해 MLB 평균보다 ' + Math.abs(delta).toFixed(1) + "% " +
      (delta >= 0 ? "높습니다" : "낮습니다") + (group === "pitching" ? " (낮을수록 좋은 기록)" : "") + '.</p>';
  }

  // 시즌 비교 팝업 버튼. MLB·마이너 기록 단위가 둘 이상이면 열린다.
  const compareButtonHtml = '<button type="button" class="season-compare-open" id="seasonCompareOpen" aria-haspopup="dialog"><span aria-hidden="true">⇄</span> 지난 시즌과 비교</button>';
  function bindCompare(player, aggregate, season) {
    const button = $("seasonCompareOpen");
    const ok = window.BB.seasonCompare && window.BB.seasonCompare.available(player);
    button.disabled = !ok;
    button.title = ok ? "MLB·마이너리그 시즌 기록을 나란히 비교" : "비교할 다른 시즌 기록이 없습니다";
    button.onclick = (e) => window.BB.seasonCompare.open(player, aggregate, season(), e.currentTarget);
  }

  async function analysis(player, aggregate) {
    const seasons = [...new Set(player.batting.concat(player.pitching).filter((r) => r.league === "mlb").map((r) => r.season))].sort((a, b) => b - a);
    if (!seasons.length) {
      $("playerAnalysis").innerHTML = box("시즌 맥락", compareButtonHtml + note("현재 리그 평균 비교·상황별 성적·Statcast·위치 구역 분석은 MLB 정규시즌을 제공합니다. 마이너리그 기록은 '지난 시즌과 비교'에서 시즌·레벨별로 비교할 수 있습니다."));
      bindCompare(player, aggregate, () => null);
      return;
    }
    let averages = {};
    try { averages = await loadJson("data/mlb_averages.json"); } catch (_) { /* 아래에 미제공 표시 */ }
    $("playerAnalysis").innerHTML = box("리그 평균 비교·선수 리포트", '<label class="field"><span>분석 시즌</span><select id="analysisSeason">' +
      seasons.map((s) => '<option>' + s + '</option>').join("") + '</select></label>' +
      compareButtonHtml +
      '<nav class="analysis-jumps" aria-label="분석 구역"><a href="#seasonReport">평균·리포트</a><a href="#situationReport">상황별</a><a href="#statcastReport">타구·구종</a><a href="#zonesReport">탄착군·핫콜드존</a></nav>' +
      '<div id="seasonReport"></div><div id="situationReport"></div><div id="statcastReport"></div><div id="zonesReport"></div>');
    const requestedSeason = Number(new URLSearchParams(location.search).get("season"));
    if (seasons.includes(requestedSeason)) $("analysisSeason").value = String(requestedSeason);
    let request = 0;
    const render = async () => {
      const version = ++request;
      const season = Number($("analysisSeason").value);
      const url = new URL(location.href);
      url.searchParams.set("view", "analysis");
      url.searchParams.set("season", String(season));
      history.replaceState(null, "", url);
      for (const id of ["playerOverviewLink", "playerAnalysisLink"]) {
        const link = new URL($(id).href);
        link.searchParams.set("season", String(season));
        $(id).href = link.pathname + link.search;
      }
      const statcastReady = window.BB.statcast.render(player, season, $("statcastReport"));
      const zonesReady = window.BB.zones && window.BB.zones.render(player, season, $("zonesReport"));
      const groups = player.pos === "P" ? ["pitching", "batting"] : ["batting", "pitching"];
      $("seasonReport").innerHTML = groups.map((group) => {
        const rows = player[group].filter((r) => r.league === "mlb" && r.season === season);
        if (!rows.length) return "";
        const row = rows.length === 1 ? rows[0] : aggregate(group, rows);
        const average = (averages[season] || {})[group === "batting" ? "hitting" : "pitching"];
        if (!average) return note(season + " " + (group === "batting" ? "타격" : "투구") + " 리그 평균 미제공");
        const metrics = group === "batting" ? ["AVG", "OBP", "SLG", "OPS"] : ["ERA", "WHIP", "Kp", "BBp"];
        const format = (key, value) => key.endsWith("p") ? pct(value) : f(value, key === "ERA" ? 2 : 3);
        return '<h3>' + season + ' ' + (group === "batting" ? "타격" : "투구") + '</h3>' + table(["기준", ...metrics.map((k) => ({Kp:"K%", BBp:"BB%"}[k] || k))],
          [["선수", ...metrics.map((k) => format(k, row[k]))], ["MLB 평균", ...metrics.map((k) => format(k, average[k]))]]) +
          comparison(group, row, average) + report(group, row, average);
      }).join("") + note("평균은 해당 시즌 MLB 전체 구단의 누적 기록을 합산해 계산합니다. AL/NL·구장 보정은 하지 않았으며 OPS+·ERA-가 아닙니다. 시대별 성적 비교 시 경기 수·역할·구장도 함께 보세요.");
      $("situationReport").innerHTML = '<h3>상황별 성적</h3><p class="muted">불러오는 중…</p>';
      try {
        const data = await loadJson("data/situations/" + season + ".json");
        if (request !== version) return;
        const mine = data.players[player.id] || {};
        const content = ["hitting", "pitching"].map((group) => {
          if (!mine[group]) return "";
          const pitching = group === "pitching";
          // 투수도 타자와 같은 비율 열(피AVG~피OPS)을 보여주고 이닝·WHIP를 더한다.
          // ERA는 원본이 홈/원정에만 있어 주자 상황·좌우 표와 맞출 수 없으므로 넣지 않는다.
          const keys = pitching ? ["inningsPitched", "battersFaced", "atBats", "hits", "homeRuns", "baseOnBalls", "strikeOuts", "avg", "obp", "slg", "ops", "whip"] :
            ["plateAppearances", "atBats", "hits", "homeRuns", "rbi", "baseOnBalls", "strikeOuts", "avg", "obp", "slg", "ops"];
          const titles = pitching ? ["IP", "BF", "AB", "H", "HR", "BB", "SO", "피AVG", "피OBP", "피SLG", "피OPS", "WHIP"] : ["PA", "AB", "H", "HR", "RBI", "BB", "SO", "AVG", "OBP", "SLG", "OPS"];
          // 서로 짝이 되는 상황끼리 표를 나눠 한 쌍씩 비교한다.
          const pairs = [
            ["주자 상황", [["risp", "득점권"], ["nr", "평시"]]],
            [pitching ? "타자 유형" : "투수 유형", pitching ? [["vl", "좌타자 상대"], ["vr", "우타자 상대"]] : [["vl", "좌투수 상대"], ["vr", "우투수 상대"]]],
            ["홈 / 원정", [["h", "홈"], ["a", "원정"]]]
          ];
          const cell = (code, key) => { const value = (mine[group][code] || {})[key]; return ["avg","obp","slg","ops"].includes(key) ? f(value) : key === "whip" ? f(value, 2) : numeric(value) ? esc(String(value)) : "-"; };
          return '<h4>' + (pitching ? "투구" : "타격") + '</h4><div class="situation-tables">' + pairs.map(([title, rows]) =>
            '<h5 class="situation-title">' + title + '</h5>' + table(["상황", ...titles], rows.map(([code, label]) => [label, ...keys.map((key) => cell(code, key))]))).join("") + '</div>';
        }).join("");
        $("situationReport").innerHTML = '<h3>상황별 성적</h3>' + (content || note("이 시즌의 상황별 기록이 없습니다.")) +
          note("MLB 정규시즌 · 득점권은 2루 또는 3루에 주자가 있는 타석, 평시는 주자가 없거나 1루에만 있는 타석입니다. 각 표의 두 줄은 겹치지 않지만 표끼리는 같은 타석을 다시 나눈 것이므로 합산하지 않습니다. 적은 타석으로 장기적인 능력을 단정할 수 없습니다. 갱신: " + new Date(data.updated).toLocaleString("ko-KR"));
      } catch (_) {
        if (request === version) $("situationReport").innerHTML = '<h3>상황별 성적</h3>' + note("이 시즌은 상황별 자료가 아직 없거나 불러오지 못했습니다. 현재 2024~2026 시즌을 수집합니다.");
      }
      await Promise.allSettled([statcastReady, zonesReady]);
      if (request === version && location.hash === "#zonesReport") $("zonesReport").scrollIntoView({block:"start"});
    };
    $("analysisSeason").addEventListener("change", render);
    bindCompare(player, aggregate, () => Number($("analysisSeason").value));
    render();
  }
  window.BB.renderPlayerContext = (player, aggregate) => {
    window.BB.favorites.mount("players", player.id, player.name, $("playerSub").parentElement);
    if (document.body.dataset.playerView === "analysis") {
      analysis(player, aggregate);
    } else {
      transfers(player);
      contracts(player);
    }
  };
})();
