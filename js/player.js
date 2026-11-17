// 빠따넷 선수 페이지
// player.html?id=선수ID 로 열면 data/players/{id}.json을 읽어 프로필과 연도별 성적을 그린다.

(function () {
  "use strict";

  const { COLUMNS, escapeHtml, loadJson, cell, visibleColumns } = window.BB;

  const $ = (id) => document.getElementById(id);
  const HAND = { L: "좌", R: "우", S: "양" };
  const GROUP_TITLE = { batting: "타격 기록", pitching: "투구 기록" };

  let player = null;
  let recruitment = null;
  let view = "basic";
  // 커리어 표 필터. 시즌은 "" 이면 전체, 레벨은 ""(전체)·"mlb"·"milb"
  const filter = { season: "", league: "" };

  // 은퇴 선수 중 마이너리그 기록을 받는 기준(scripts/careers.py의 PAST_MINOR_FROM과 같게 유지)
  const PAST_MINOR_FROM = 2000;
  const pastWithMinors = (p) =>
    p.batting.concat(p.pitching).some((r) => r.level === "MLB" && r.season >= PAST_MINOR_FROM);

  function showError(message) {
    $("status").className = "status error";
    $("status").textContent = message;
  }

  // 소속 팀·포지션·등번호 줄. teamId가 있으면 팀 이름을 구단 페이지 링크로 만든다.
  function renderSub(teamId) {
    const team = player.team
      ? (teamId ? '<a href="team.html?id=' + teamId + '">' + escapeHtml(player.team) + "</a>" : escapeHtml(player.team))
      : "";
    const sub = [team, escapeHtml(player.pos || ""), player.number ? "#" + escapeHtml(player.number) : ""].filter(Boolean);
    $("playerSub").innerHTML = sub.join(" · ") + (player.past ? " (은퇴)" : player.active ? "" : " (비활동)");
  }

  // 선수 파일에는 팀 이름만 있으므로 구단 정보(MLB와 산하 구단)에서 같은 이름의 구단 ID를 찾는다.
  // 윈터리그 팀처럼 구단 정보에 없는 팀은 링크 없이 둔다.
  function linkTeam(data) {
    if (!player.team) return;
    for (const club of data.clubs) {
      const found = [club].concat(club.affiliates || []).find((t) => t.name === player.team);
      if (found) {
        renderSub(found.id);
        return;
      }
    }
  }

  // MLB 공식 얼굴 사진. 파일을 저장하지 않고 MLB 이미지 서버 주소로만 표시한다.
  // 사진이 없는 선수는 서버가 실루엣 기본 이미지를 주고, 이미지를 못 받으면 사진 자리를 숨긴다.
  const PHOTO_URL = "https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/";
  function renderPhoto(name) {
    const img = $("playerPhoto");
    if (!img) return; // 예전 player.html이 캐시돼 있어도 나머지 화면은 그린다
    img.addEventListener("error", () => { img.hidden = true; }, { once: true });
    img.alt = name + " 사진";
    img.src = PHOTO_URL + encodeURIComponent(player.id) + "/headshot/67/current";
    img.hidden = false;
  }

  function renderProfile() {
    const name = player.nameKo || player.name;
    document.title = "빠따넷 · " + name;
    $("playerName").textContent = name;
    renderPhoto(name);

    renderSub(null);

    const body = [player.heightCm ? player.heightCm + "cm" : "", player.weightKg ? player.weightKg + "kg" : ""].filter(Boolean);
    const hands = (HAND[player.throws] ? HAND[player.throws] + "투" : "") + (HAND[player.bats] ? HAND[player.bats] + "타" : "");
    const signing = recruitment;
    let entryLabel = "지명 정보";
    let entryText = "미확인";
    if (signing && signing.type === "draft") {
      entryText = signing.year + "년 · " + (signing.round ? signing.round + "라운드 · " : "") +
        (signing.overall ? "전체 " + signing.overall + "순위" : "순위 미확인");
    } else if (signing && signing.type === "international") {
      entryLabel = "프로 계약";
      entryText = (signing.date || signing.year + "년") + " · 국제 아마추어 계약 (지명 없음)";
    }
    const facts = [
      ["생년월일", player.birthDate ? player.birthDate + (player.age && !player.deathDate ? " (" + player.age + "세)" : "") : ""],
      ["사망", player.deathDate ? player.deathDate + (player.age ? " (향년 " + player.age + "세)" : "") : ""],
      ["출신", player.country],
      ["신체", body.join(" / ")],
      ["투타", hands],
      ["MLB 데뷔", player.debut || "없음"],
      ["마지막 출전", player.lastPlayed],
      [entryLabel, entryText],
      [signing && signing.type === "international" ? "계약 구단" : "지명 구단", signing && signing.team],
      ["계약금", signing && Number.isFinite(signing.bonusUSD) ? "$" + signing.bonusUSD.toLocaleString("en-US") + " USD" : "미확인"],
    ];
    $("playerFacts").innerHTML = facts
      .filter((fact) => fact[1])
      .map((fact) => "<div><dt>" + fact[0] + "</dt><dd>" + escapeHtml(fact[1]) + "</dd></div>")
      .join("");
    if (signing && /^https:\/\//.test(signing.source || "")) {
      $("playerFacts").insertAdjacentHTML("beforeend", '<div><dt>입단 정보 출처</dt><dd><a target="_blank" rel="noopener noreferrer" href="' + escapeHtml(signing.source) + '">MLB 공식 자료</a></dd></div>');
    }
    $("profile").hidden = false;
  }

  // MLB Pipeline 유망주면 순위를 프로필에 보여주고, 주차별 순위 기록을 아래에 붙인다
  function renderProspect() {
    const info = player.prospect;
    if (!info) return;
    const items = [];
    if (info.top100) items.push("전체 <strong>" + info.top100 + "위</strong>");
    if (info.orgRank) items.push(escapeHtml(info.org) + " 팀 내 <strong>" + info.orgRank + "위</strong>");
    if (info.eta) items.push("예상 데뷔 " + escapeHtml(info.eta));
    if (info.level) items.push("현재 " + escapeHtml(info.level) + (info.club ? " (" + escapeHtml(info.club) + ")" : ""));
    $("prospectBanner").innerHTML = '<span class="prospect-label">MLB Pipeline</span>' + items.join('<span class="dot">·</span>');
    $("prospectBanner").hidden = false;

    if (info.history.length < 2) return;
    const rows = info.history.slice().reverse().map((item) => {
      const parts = item.week.split("-W");
      return (
        '<tr><td class="col-season">' + parts[0] + "년 " + Number(parts[1]) + "주차</td>" +
        "<td>" + (item.top100 || "-") + "</td><td>" + (item.orgRank || "-") + "</td></tr>"
      );
    }).join("");
    $("prospectHistory").innerHTML =
      '<section class="career-section"><h2>유망주 순위 변동</h2><div class="table-scroll"><table class="stats career rank-history">' +
      '<thead><tr><th class="col-season">주차</th><th>전체 순위</th><th>팀 내 순위</th></tr></thead><tbody>' + rows + "</tbody></table></div></section>";
  }

  // 수상 경력: 명예의 전당을 맨 앞에, 나머지는 상별로 횟수와 시즌을 보여준다
  function renderAwards(awards) {
    const mine = awards.rows.filter((row) => String(row[3]) === String(player.id));
    if (!mine.length) return;
    const items = awards.awards.map((award) => {
      const seasons = mine.filter((row) => row[0] === award.key).map((row) => row[1]).sort((a, b) => a - b);
      if (!seasons.length) return "";
      const link = '<a href="awards.html' + (award.key === "hof" ? "" : "?award=" + encodeURIComponent(award.key)) + '">' + escapeHtml(award.name) + "</a>";
      if (award.key === "hof") {
        return '<li class="award-hof"><span class="prospect-label">' + link + "</span> " + seasons[0] + "년 헌액</li>";
      }
      return "<li><strong>" + link + "</strong> " + seasons.length + '회 <span class="muted">(' + seasons.join(", ") + ")</span></li>";
    }).join("");
    $("awardList").innerHTML = "<h2>수상 경력</h2><ul>" + items + "</ul>";
    $("awardList").hidden = false;
  }

  // 같은 시즌 안에서는 상위 리그부터 보여준다. 원본에 경기 날짜가 없어 시즌 안의 시간 순서는 알 수 없다.
  // 같은 시즌·레벨의 여러 팀은 저장된 순서(팀 약자순)를 유지한다.
  const LEVEL_ORDER = ["MLB", "AAA", "AA", "High-A", "Single-A", "Short-Season A", "Rookie"];
  const levelRank = (level) => {
    const index = LEVEL_ORDER.indexOf(level);
    return index < 0 ? LEVEL_ORDER.length : index;
  };
  const sortRows = (rows) =>
    rows.slice().sort((a, b) => b.season - a.season || levelRank(a.level) - levelRank(b.level));

  function renderTable(group, filtered) {
    const rows = sortRows(filtered);
    if (!rows.length) return "";
    const columns = visibleColumns(COLUMNS[group][view], rows);
    const head =
      '<tr><th class="col-season">시즌</th><th class="col-team">레벨</th><th class="col-team">팀</th><th>나이</th>' +
      columns.map((column) => '<th title="' + escapeHtml(column.desc) + '">' + escapeHtml(column.label) + "</th>").join("") +
      "</tr>";
    const body = rows.map((row) => {
      const team = escapeHtml(row.team || "-") + (row.nt > 1 ? '<span class="team-note">' + row.nt + "팀</span>" : "");
      return (
        '<tr><td class="col-season">' + escapeHtml(row.seasonLabel || String(row.season)) + "</td>" +
        '<td class="col-team"><span class="level level-' + row.league + '">' + escapeHtml(row.level === "Single-A" && row.season === 2021 ? "Low-A" : row.level) + "</span></td>" +
        '<td class="col-team">' + team + "</td>" +
        "<td>" + (row.age || "-") + "</td>" +
        columns.map((column) => "<td>" + cell(column, row) + "</td>").join("") +
        "</tr>"
      );
    }).join("");
    return (
      '<section class="career-section"><h2>' + GROUP_TITLE[group] + "</h2>" +
      '<div class="table-scroll"><table class="stats career"><thead>' + head + "</thead><tbody>" + body + "</tbody></table></div></section>"
    );
  }

  const matchesFilter = (row) =>
    (!filter.season || String(row.season) === filter.season) &&
    (!filter.league || row.league === filter.league);

  function renderCareer() {
    // 투수는 투구 기록을, 야수는 타격 기록을 먼저 보여준다
    const order = player.pos === "P" ? ["pitching", "batting"] : ["batting", "pitching"];
    const hasRows = order.some((group) => player[group].length);
    const html = order.map((group) => renderTable(group, player[group].filter(matchesFilter))).join("");
    $("career").innerHTML = html ||
      '<p class="status">' + (hasRows ? "해당 조건의 기록이 없습니다." : "제공된 프로 경기 기록이 없습니다.") + "</p>";
  }

  // 시즌 목록은 이 선수가 기록을 남긴 시즌만 보여준다. 고른 조건은 주소에 남긴다.
  function setupFilters() {
    const seasons = [...new Set(player.batting.concat(player.pitching).map((row) => row.season))].sort((a, b) => b - a);
    const params = new URLSearchParams(location.search);
    if (seasons.map(String).includes(params.get("season"))) filter.season = params.get("season");
    if (["mlb", "milb"].includes(params.get("level"))) filter.league = params.get("level");
    $("careerSeason").innerHTML = '<option value="">전체 시즌</option>' +
      seasons.map((season) => '<option value="' + season + '">' + season + "</option>").join("");
    $("careerSeason").value = filter.season;
    $("careerLevel").value = filter.league;
    const update = () => {
      filter.season = $("careerSeason").value;
      filter.league = $("careerLevel").value;
      const next = new URLSearchParams(location.search);
      filter.season ? next.set("season", filter.season) : next.delete("season");
      filter.league ? next.set("level", filter.league) : next.delete("level");
      history.replaceState(null, "", "?" + next.toString());
      renderCareer();
    };
    $("careerSeason").addEventListener("change", update);
    $("careerLevel").addEventListener("change", update);
  }

  async function init() {
    const id = new URLSearchParams(location.search).get("id");
    if (!/^\d+$/.test(id || "")) {
      showError("선수를 찾을 수 없습니다. 리더보드에서 선수를 선택해 주세요.");
      return;
    }
    try {
      player = await loadJson("data/players/" + id + ".json");
    } catch (error) {
      showError("선수 데이터를 불러오지 못했습니다. 리더보드에서 다시 선택해 주세요.");
      return;
    }
    try {
      const entries = await loadJson("data/recruitment.json");
      recruitment = entries[id] || null;
    } catch (error) {
      recruitment = null;
    }
    $("status").textContent = "";
    renderProfile();
    renderProspect();
    setupFilters();
    renderCareer();
    // 수상 기록은 없어도 나머지 화면에 영향이 없으므로 따로 불러온다
    loadJson("data/awards.json").then(renderAwards).catch(() => {});
    loadJson("data/teams.json").then(linkTeam).catch(() => {});
    $("careerToolbar").hidden = false;
    $("status").textContent = player.careerStatus === "no_records"
      ? "공식 데이터에서 제공된 프로 경기 기록이 없습니다."
      : player.past && pastWithMinors(player)
      ? "2000년 이후 MLB에 출전한 은퇴 선수는 MLB·마이너리그 정규시즌 기록을 제공합니다. 마이너리그 재활 경기도 포함되며, 해외 리그 기록과 과거 시즌 세이버 지표는 제공하지 않습니다."
      : player.past
      ? "2000년 이전에 MLB 경력을 마친 은퇴 선수는 MLB 정규시즌 기록만 제공합니다. 마이너리그와 해외 리그 기록은 포함하지 않으며, 과거 시즌 세이버 지표는 아직 제공하지 않습니다."
      : player.careerUpdated
      ? "MLB·마이너리그의 최초 제공 시즌부터 표시합니다. 해외 리그 및 원본 미제공 기록은 포함되지 않을 수 있습니다. 과거 세이버 지표는 계산 근거가 있는 경우에만 제공합니다."
      : "저장된 시즌 기록입니다. 전체 프로 커리어 데이터는 아직 수집되지 않았습니다.";

    // 리더보드에서 넘어왔으면 보던 조건 그대로 돌아가게 한다
    if (document.referrer && new URL(document.referrer).origin === location.origin && /(\/|index\.html)$/.test(new URL(document.referrer).pathname)) {
      $("backLink").href = document.referrer;
    }

    $("viewSwitch").addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button || button.dataset.value === view) return;
      view = button.dataset.value;
      $("viewSwitch").querySelectorAll("button").forEach((item) => {
        item.setAttribute("aria-pressed", String(item.dataset.value === view));
      });
      renderCareer();
    });
  }

  init();
})();
