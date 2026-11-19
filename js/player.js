// 빠따넷 선수 페이지
// player.html?id=선수ID 로 열면 data/players/{id}.json을 읽어 프로필과 연도별 성적을 그린다.

(function () {
  "use strict";

  const { COLUMNS, escapeHtml, loadJson, cell, visibleColumns, fmt, hof, pedData, pedMark } = window.BB;

  const $ = (id) => document.getElementById(id);
  const HAND = { L: "좌", R: "우", S: "양" };
  const GROUP_TITLE = { batting: "타격 기록", pitching: "투구 기록" };

  let player = null;
  let recruitment = null;
  let view = "basic";
  // 커리어 표 필터. 시즌은 "" 이면 전체, 레벨은 "all"(전체)·"mlb"·"milb"
  // from·to: 기간(시즌). 빈 값이면 처음·끝까지 (2026-11-18 사용자 요구: 기간 선택)
  const filter = { from: "", to: "", league: "all" };
  const inPeriod = (row) =>
    (!filter.from || row.season >= Number(filter.from)) && (!filter.to || row.season <= Number(filter.to));
  const periodSet = () => Boolean(filter.from || filter.to);

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
        // 산하 마이너리그 구단 소속이면 모구단 기준으로 입단 경로를 찾는다
        if (!player.past) loadJson("data/arrivals.json").then((arrivals) => renderArrival(club, data, arrivals)).catch(() => {});
        return;
      }
    }
  }

  // 입단 경로: 현재 소속 구단(조직)에 어떻게 왔는지 (2026-11-18 사용자 요구)
  // data/arrivals.json(scripts/moves.py)의 마지막 영입이 현재 구단이면 트레이드·FA 계약·웨이버 클레임을,
  // 아니면 지명·국제 계약 구단이 현재 구단일 때 그 경로를 보여준다. 둘 다 아니면 원본 이동 기록(2009년~) 이전의 이동이다.
  const ARRIVAL_LABEL = { trade: "트레이드", sign: "FA 계약", claim: "웨이버 클레임" };
  // 지명 없는 첫 계약의 종류 (scripts/recruitment.py, scripts/signings.py)
  const ENTRY_TYPE = {
    international: "국제 아마추어 계약",
    free_agent: "FA 계약 (지명 없음)",
    posting: "포스팅",
    foreign: "해외 리그 이적 (포스팅 아님)",
  };
  const SOURCE_LABEL = (url) =>
    url.includes("wikipedia.org") ? "위키백과 (CC BY-SA)" :
    url.includes("/transactions") ? "MLB 공식 이동 기록" :
    url.includes("/prospects/") ? "MLB Pipeline" : "MLB 공식 자료";
  function renderArrival(club, teams, arrivals) {
    const abbr = (id) => (teams.clubs.find((item) => item.id === id) || {}).abbr || "";
    const last = arrivals[String(player.id)];
    let text = "";
    if (last && last[2] === club.id) {
      const from = last[3] ? ", " + abbr(last[3]) + "에서" : "";
      text = ARRIVAL_LABEL[last[1]] + " (" + last[0] + from + ")";
    } else if (recruitment && recruitment.team === club.name) {
      text = recruitment.type === "draft" ? "드래프트 지명 (" + recruitment.year + "년)" : ENTRY_TYPE[recruitment.type] || "지명 없이 계약";
    } else {
      text = "2009년 이전 이동 (기록 범위 밖)";
    }
    $("playerFacts").insertAdjacentHTML("afterbegin",
      '<div><dt>입단 경로</dt><dd>' + escapeHtml(text) +
      (last && last[2] === club.id ? ' <a class="muted" href="moves.html?season=' + last[0].slice(0, 4) + "&q=" +
        encodeURIComponent(player.name) + '">기록</a>' : "") + "</dd></div>");
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
    } else if (signing && ENTRY_TYPE[signing.type]) {
      // 포스팅·해외 FA는 전 소속 리그·구단을 함께 적는다. 계약일을 모르면 MLB 데뷔 연도만 있으므로 날짜를 쓰지 않는다.
      entryLabel = "프로 계약";
      const when = signing.date || (signing.type === "foreign" ? "" : signing.year ? signing.year + "년" : "");
      const from = signing.foreignTeam ? " · " + signing.league + " " + signing.foreignTeam : "";
      entryText = (when ? when + " · " : "") + ENTRY_TYPE[signing.type] + from;
    }
    const contract = signing && (signing.type === "posting" || signing.type === "foreign" || signing.type === "free_agent");
    const facts = [
      ["생년월일", player.birthDate ? player.birthDate + (player.age && !player.deathDate ? " (" + player.age + "세)" : "") : ""],
      ["사망", player.deathDate ? player.deathDate + (player.age ? " (향년 " + player.age + "세)" : "") : ""],
      ["출신", player.country],
      ["신체", body.join(" / ")],
      ["투타", hands],
      ["MLB 데뷔", player.debut || "없음"],
      ["마지막 출전", player.lastPlayed],
      [entryLabel, entryText],
      [signing && signing.type !== "draft" ? "계약 구단" : "지명 구단", signing && signing.team],
      ["포스팅 금액", signing && signing.type === "posting" ? signing.fee : ""],
      // MLB 계약 내용은 포스팅 표에 있는 것만 보여준다. 국제 계약금과 같은 칸에 넣지 않는다.
      ["MLB 계약", signing && signing.contract],
      ["계약금", contract ? "" : signing && Number.isFinite(signing.bonusUSD) ? "$" + signing.bonusUSD.toLocaleString("en-US") + " USD" : "미확인"],
    ];
    $("playerFacts").innerHTML = facts
      .filter((fact) => fact[1])
      .map((fact) => "<div><dt>" + fact[0] + "</dt><dd>" + escapeHtml(fact[1]) + "</dd></div>")
      .join("");
    if (signing && /^https:\/\//.test(signing.source || "")) {
      $("playerFacts").insertAdjacentHTML("beforeend", '<div><dt>입단 정보 출처</dt><dd><a target="_blank" rel="noopener noreferrer" href="' + escapeHtml(signing.source) + '">' +
        SOURCE_LABEL(signing.source) + "</a></dd></div>");
    }
    $("profile").hidden = false;
  }

  // MLB Pipeline 유망주면 순위를 프로필에 보여주고, 주차별 순위 기록을 아래에 붙인다
  function renderProspect() {
    const info = player.prospect;
    if (!info) return;
    const items = [];
    // Top 100 순위는 있을 때만 적는다. 밖이면 표시하지 않는다 (2026-11-19 사용자 결정)
    if (info.top100) items.push("Top 100 <strong>" + info.top100 + "위</strong>");
    if (info.orgRank) items.push(escapeHtml(info.org) + " 팀 내 유망주 <strong>" + info.orgRank + "위</strong>");
    if (info.eta) items.push("예상 데뷔 " + escapeHtml(info.eta));
    if (info.level) items.push("현재 " + escapeHtml(info.level) + (info.club ? " (" + escapeHtml(info.club) + ")" : ""));
    // MLB Pipeline 표시는 Top 100 선수에게만 붙인다. 팀 내 순위도 Pipeline 자료이므로 출처는 툴팁에 남긴다 (2026-11-19 사용자 결정)
    $("prospectBanner").innerHTML = (info.top100 ? '<span class="prospect-label">MLB Pipeline</span>' : "") +
      items.join('<span class="dot">·</span>');
    $("prospectBanner").title = "출처: MLB Pipeline 유망주 순위 (주 1회 갱신)";
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

  // 수상 경력 (2026-11-18 가독성 개선): 명예의 전당은 맨 위 한 줄에 선출 방식·득표율·투표 차수와 함께,
  // 나머지 상은 상별 카드(횟수 + 수상 연도)로 보여준다. 횟수가 많은 상이 먼저다.
  // 금지약물 징계: 이름 뒤 *와 징계 목록 (data/ped.json, 위키백과의 공식 징계 목록)
  function renderPed(data) {
    const items = (data.players || {})[String(player.id)];
    if (!items || !items.length) return;
    $("playerName").insertAdjacentHTML("beforeend", pedMark());
    $("pedList").innerHTML = "<h2>금지약물 징계 <sup class=\"ped-mark\">*</sup></h2><ul>" +
      items.map((item) => "<li><strong>" + escapeHtml(item.date) + "</strong> " +
        escapeHtml([item.team, item.penalty ? item.penalty.replace(/(\d+) games?/, "$1경기").replace("season", "시즌") + " 출장 정지" : "",
          item.drug ? "검출 약물: " + item.drug : ""].filter(Boolean).join(" · ")) + "</li>").join("") + "</ul>" +
      '<p class="muted">MLB·마이너리그 약물 방지 프로그램에 따른 공식 징계 발표만 표시합니다. 출처: <a target="_blank" rel="noopener noreferrer" href="' +
      escapeHtml(data.source) + '">위키백과 (CC BY-SA)</a></p>';
    $("pedList").hidden = false;
  }

  function renderAwards(awards, votes) {
    const mine = awards.rows.filter((row) => String(row[3]) === String(player.id));
    if (!mine.length) return;
    const link = (award) => '<a href="awards.html' + (award.key === "hof" ? "" : "?award=" + encodeURIComponent(award.key)) + '">' +
      escapeHtml(award.name) + "</a>";
    let hofLine = "";
    const cards = [];
    awards.awards.forEach((award, order) => {
      const seasons = mine.filter((row) => row[0] === award.key).map((row) => row[1]).sort((a, b) => a - b);
      if (!seasons.length) return;
      if (award.key === "hof") {
        const vote = votes && votes[String(player.id)];
        const detail = [];
        if (vote) {
          detail.push(hof.method(vote));
          if (hof.isWriters(vote)) {
            if (Number.isFinite(vote.pct)) detail.push("득표율 " + hof.pct(vote) + (vote.votes ? " (" + vote.votes + "표)" : ""));
            if (vote.ballot) detail.push(hof.ballot(vote));
          } else if (Number.isFinite(vote.pct)) {
            detail.push("위원회 득표 " + hof.pct(vote));
          }
        }
        hofLine = '<div class="award-hof"><span class="award-hof-badge">명예의 전당</span> <strong>' + seasons[0] + "년 헌액</strong>" +
          (detail.length ? ' <span class="muted">' + detail.map(escapeHtml).join(" · ") + "</span>" : "") +
          ' <a class="muted" href="awards.html">전체 보기</a></div>';
        return;
      }
      cards.push({ order, count: seasons.length, html:
        '<li class="award-card"><span class="award-count">' + seasons.length + '<small>회</small></span>' +
        '<span class="award-name">' + link(award) + "</span>" +
        '<span class="award-years">' + seasons.join(" · ") + "</span></li>" });
    });
    cards.sort((a, b) => b.count - a.count || a.order - b.order);
    $("awardList").innerHTML = "<h2>수상 경력</h2>" + hofLine +
      (cards.length ? '<ul class="award-cards">' + cards.map((card) => card.html).join("") + "</ul>" : "");
    $("awardList").hidden = false;
  }

  // 레벨 순서. 원본에 경기 날짜가 없어 시즌 안의 시간 순서는 알 수 없으므로 레벨로 정렬한다.
  // 같은 시즌·레벨의 여러 팀은 저장된 순서(팀 약자순)를 유지한다.
  const LEVEL_ORDER = ["MLB", "AAA", "AA", "High-A", "Single-A", "Short-Season A", "Rookie"];
  const levelRank = (level) => {
    const index = LEVEL_ORDER.indexOf(level);
    return index < 0 ? LEVEL_ORDER.length : index;
  };

  // ---------- 통산 행 ----------
  // 누적 기록은 더하고, 비율 기록은 시즌 값을 평균 내지 않고 합친 누적 기록으로 다시 계산한다.
  // 한 시즌이라도 값이 없는 항목(옛 시즌의 도루 실패 등)은 0으로 채우지 않고 미제공으로 둔다.
  // 시즌별 리그 기준이 필요한 지표(wOBA, wRC+, FIP, ERA-, FIP-, LOB%)와 피BABIP는 계산하지 않는다.
  const SUM_KEYS = {
    batting: ["G", "PA", "AB", "R", "H", "2B", "3B", "HR", "RBI", "SB", "CS", "BB", "IBB", "SO", "HBP", "SF", "TB", "GO", "AO", "sWAR", "WAR"],
    pitching: ["G", "GS", "CG", "SHO", "W", "L", "SV", "SVO", "HLD", "outs", "H", "R", "ER", "HR", "BB", "IBB", "SO", "HBP", "BF",
      "NP", "AB", "GO", "AO", "sWAR", "WAR"],
  };
  const ok = (v) => v !== null && v !== undefined && Number.isFinite(v);
  const div = (a, b) => (ok(a) && ok(b) && b > 0 ? a / b : null);

  function sumRows(group, rows) {
    const total = {};
    SUM_KEYS[group].forEach((key) => {
      total[key] = rows.every((row) => ok(row[key])) ? rows.reduce((sum, row) => sum + row[key], 0) : null;
    });
    return total;
  }

  function addRates(group, t) {
    if (group === "batting") {
      t.AVG = div(t.H, t.AB);
      t.OBP = ok(t.H) && ok(t.BB) && ok(t.HBP) && ok(t.SF) ? div(t.H + t.BB + t.HBP, t.AB + t.BB + t.HBP + t.SF) : null;
      t.SLG = div(t.TB, t.AB);
      // MLB 공식 표기와 같게 소수 셋째 자리로 반올림한 출루율·장타율을 더한다 (예: .194 + .188 = .382)
      const r3 = (v) => Math.round(v * 1000) / 1000;
      t.OPS = ok(t.OBP) && ok(t.SLG) ? r3(t.OBP) + r3(t.SLG) : null;
      t.ISO = ok(t.SLG) && ok(t.AVG) ? t.SLG - t.AVG : null;
      t.BABIP = ok(t.H) && ok(t.HR) && ok(t.SO) && ok(t.SF) ? div(t.H - t.HR, t.AB - t.SO - t.HR + t.SF) : null;
      t.BBp = div(t.BB, t.PA);
      t.Kp = div(t.SO, t.PA);
    } else {
      t.ERA = ok(t.ER) ? div(t.ER * 27, t.outs) : null;
      t.WHIP = ok(t.H) && ok(t.BB) ? div((t.H + t.BB) * 3, t.outs) : null;
      t.K9 = ok(t.SO) ? div(t.SO * 27, t.outs) : null;
      t.BB9 = ok(t.BB) ? div(t.BB * 27, t.outs) : null;
      t.HR9 = ok(t.HR) ? div(t.HR * 27, t.outs) : null;
      t.Kp = div(t.SO, t.BF);
      t.BBp = div(t.BB, t.BF);
      t.KBBp = ok(t.Kp) && ok(t.BBp) ? t.Kp - t.BBp : null;
    }
    return derive(group, t);
  }

  // 저장된 누적 기록으로 만드는 MLB.com 표 항목: 땅볼/뜬공 아웃 비율(GO/AO), 투수의 피안타율(AVG)
  function derive(group, row) {
    row.GOAO = div(row.GO, row.AO);
    if (group === "pitching") row.oAVG = div(row.H, row.AB);
    return row;
  }

  // MLB와 MiLB를 따로 합친다(2026-11-17 사용자 결정: 평균 행 없이 통산만).
  function summaryRows(group, rows) {
    const result = [];
    [["mlb", "MLB"], ["milb", "MiLB"]].forEach(([league, label]) => {
      const mine = rows.filter((row) => row.league === league);
      if (mine.length < 2) return; // 한 줄이면 통산이 그 줄과 같다
      const seasons = new Set(mine.map((row) => row.season)).size;
      const total = addRates(group, sumRows(group, mine));
      // 한 시즌만 남으면(시즌 필터, 시즌 중 이적) 여러 팀 기록의 시즌 합계다
      // 기간을 골랐거나 한 시즌만 남으면(시즌 중 이적) "합계", 전체 기간이면 "통산"
      result.push({ title: seasons > 1 && !periodSet() ? "통산" : "합계", label, league, note: seasons + "시즌", row: total });
    });
    return result;
  }

  // ---------- 리그 1위·수상 표시 (2026-11-18) ----------
  // 리그 1위: data/leaders.json(scripts/leaders.py). MLB 행에만 굵게 표시한다.
  // 수상: data/awards.json. MLB 행의 "수상" 열에 약칭으로 표시한다. 명예의 전당·감독상은 시즌 성적과 무관해 뺀다.
  let leaders = null;
  let awardData = null;
  const AWARD_SHORT = {
    mvp: "MVP", cy: "CY", roy: "ROY", wsmvp: "WS MVP", lcsmvp: "LCS MVP", asmvp: "AS MVP", allstar: "AS",
    allmlb1: "All-MLB 1", allmlb2: "All-MLB 2", gg: "GG", pg: "PG", ss: "SS", haa: "HAA", rel: "REL",
    cpoy: "CPOY", clemente: "RC", wschamp: "WS",
  };
  const GROUP_LEADER_KEY = { batting: "b", pitching: "p" };

  // 시즌·기록 묶음별 {열 키: "AL"|"NL"}
  function leaderMarks(season, group) {
    const marks = {};
    const bySeason = leaders && leaders[String(season)];
    if (!bySeason) return marks;
    Object.entries(bySeason).forEach(([league, groups]) => {
      Object.entries(groups[GROUP_LEADER_KEY[group]] || {}).forEach(([key, ids]) => {
        if (ids.includes(player.id)) marks[key] = league;
      });
    });
    return marks;
  }

  function awardBadges(season) {
    if (!awardData) return "";
    const names = Object.fromEntries(awardData.awards.map((award) => [award.key, award.name]));
    const mine = awardData.rows.filter((row) => row[1] === season && String(row[3]) === String(player.id) && AWARD_SHORT[row[0]]);
    const keys = Object.keys(AWARD_SHORT).filter((key) => mine.some((row) => row[0] === key));
    return keys.map((key) =>
      '<span class="award-tag award-' + key + '" title="' + escapeHtml(season + " " + names[key]) + '">' + AWARD_SHORT[key] + "</span>"
    ).join("");
  }

  // ---------- 한 시즌 여러 팀 ----------
  // MLB.com처럼 같은 시즌·레벨에 팀별 행이 여러 개면(과거 시즌) "N팀" 합계 행 바로 아래에 팀별 행을 붙인다.
  // 최근 시즌(리더보드 자료)은 합계 한 줄이다. 커리어 캐시의 팀별 행 합이 맞으면 scripts/careers.py가
  // splits로 붙이며(마지막 소속 팀이 맨 아래), 그 아래에 같은 방식으로 팀별 행을 보여준다.
  function groupBySeason(rows) {
    const groups = [];
    rows.forEach((row) => {
      const last = groups[groups.length - 1];
      if (last && last.season === row.season && last.level === row.level) last.rows.push(row);
      else groups.push({ season: row.season, level: row.level, league: row.league, rows: [row] });
    });
    return groups;
  }

  // 연도별 표의 기본 지표는 MLB.com 선수 페이지의 Standard 표와 같은 순서다 (2026-11-18 확인).
  // 옛 시즌처럼 원본에 없는 항목은 "-"로 표시한다. 타석(PA)은 세이버 보기에 있다.
  const extra = (key, label, desc) => ({ key, label, desc, format: fmt.int, asc: false });
  const GOAO = { key: "GOAO", label: "GO/AO", desc: "땅볼 아웃 / 뜬공 아웃", format: fmt.dec2, asc: false };
  const EXTRA_COLUMNS = {
    batting: { TB: extra("TB", "TB", "루타"), IBB: extra("IBB", "IBB", "고의4구"), GOAO },
    pitching: {
      CG: extra("CG", "CG", "완투"), SHO: extra("SHO", "SHO", "완봉"), SVO: extra("SVO", "SVO", "세이브 기회"),
      NP: extra("NP", "NP", "투구 수"), HBP: extra("HBP", "HB", "몸에 맞는 공 허용"), IBB: extra("IBB", "IBB", "고의4구 허용"),
      oAVG: { key: "oAVG", label: "AVG", desc: "피안타율", format: fmt.rate, asc: true }, GOAO,
    },
  };
  const CAREER_BASIC = {
    batting: ["G", "AB", "R", "H", "TB", "2B", "3B", "HR", "RBI", "BB", "IBB", "SO", "SB", "CS", "AVG", "OBP", "SLG", "OPS", "GOAO"],
    pitching: ["W", "L", "ERA", "G", "GS", "CG", "SHO", "HLD", "SV", "SVO", "outs", "H", "R", "ER", "HR", "NP", "HBP", "BB", "IBB",
      "SO", "oAVG", "WHIP", "GOAO"],
  };
  const careerColumns = (group) => view === "basic"
    ? CAREER_BASIC[group].map((key) => EXTRA_COLUMNS[group][key] || COLUMNS[group].basic.find((column) => column.key === key))
    : COLUMNS[group][view];

  const levelLabel = (row) => (row.level === "Single-A" && row.season === 2021 ? "Low-A" : row.level);

  // MLB.com처럼 오래된 시즌부터. 같은 시즌에서는 낮은 레벨부터(승격 순서) 놓는다.
  const chronological = (rows) =>
    rows.slice().sort((a, b) => a.season - b.season || levelRank(b.level) - levelRank(a.level));

  function renderTable(group, filtered, withAwards) {
    const rows = chronological(filtered.map((row) => derive(group, Object.assign({}, row))));
    if (!rows.length) return "";
    const groups = groupBySeason(rows).map((item) => {
      const total = item.rows.length > 1
        ? Object.assign(addRates(group, sumRows(group, item.rows)), { season: item.season, level: item.level, league: item.league })
        : item.rows[0];
      const isMajor = item.level === "MLB";
      const splits = item.rows.length === 1 && item.rows[0].splits
        ? item.rows[0].splits.map((child) => derive(group, Object.assign({ league: item.league }, child)))
        : null;
      return Object.assign(item, {
        total,
        children: item.rows.length > 1 ? item.rows : splits,
        marks: isMajor ? leaderMarks(item.season, group) : {},
        awards: isMajor && withAwards ? awardBadges(item.season) : "",
      });
    });
    const columns = visibleColumns(careerColumns(group), rows);
    const showAwards = groups.some((item) => item.awards);
    // 레벨 칸은 MLB와 마이너리그가 섞여 있을 때만 보여준다 (MLB만 보면 MLB.com 표와 같은 모양)
    const showLevel = new Set(rows.map((row) => row.level)).size > 1;
    const head =
      '<tr><th class="col-season">시즌</th>' + (showLevel ? '<th class="col-team">레벨</th>' : "") + '<th class="col-team">팀</th>' +
      columns.map((column) => '<th title="' + escapeHtml(column.desc) + '">' + escapeHtml(column.label) + "</th>").join("") +
      (showAwards ? '<th class="col-awards">수상</th>' : "") +
      "</tr>";

    const statCells = (row, marks) => columns.map((column) => {
      const league = marks && marks[column.key];
      return league
        ? '<td class="lead" title="' + escapeHtml(row.season + " " + league + " " + column.desc + " 1위") + '">' + cell(column, row) + "</td>"
        : "<td>" + cell(column, row) + "</td>";
    }).join("");
    const levelCell = (row) => (showLevel
      ? '<td class="col-team"><span class="level level-' + row.league + '">' + escapeHtml(levelLabel(row)) + "</span></td>"
      : "");

    const body = groups.map((item) => {
      const row = item.total;
      const split = !!item.children;
      const team = split
        ? item.children.length + "팀"
        : escapeHtml(row.team || "-") + (row.nt > 1
          ? '<span class="team-note" title="시즌 중 ' + row.nt + '팀 기록의 합계입니다. 표시된 팀은 마지막 소속입니다.">' + row.nt + "팀 합계</span>"
          : "");
      const main =
        "<tr" + (split ? ' class="split-total"' : "") + '><td class="col-season">' + escapeHtml(row.seasonLabel || String(row.season)) + "</td>" +
        levelCell(row) +
        '<td class="col-team">' + team + "</td>" +
        statCells(row, item.marks) +
        (showAwards ? '<td class="col-awards">' + item.awards + "</td>" : "") +
        "</tr>";
      if (!split) return main;
      return main + item.children.map((child) =>
        '<tr class="split-row"><td class="col-season">' + child.season + "</td>" +
        levelCell(child) +
        '<td class="col-team"' + (child.teamName ? ' title="' + escapeHtml(child.teamName) + '"' : "") + ">" + escapeHtml(child.team || "-") + "</td>" +
        statCells(child, null) +
        (showAwards ? "<td></td>" : "") +
        "</tr>"
      ).join("");
    }).join("");

    const foot = summaryRows(group, rows).map((item) =>
      '<tr class="summary-row"><td class="col-season">' + item.label + " " + item.title + "</td>" +
      (showLevel ? "<td></td>" : "") +
      '<td class="col-team muted">' + item.note + "</td>" +
      columns.map((column) => "<td>" + cell(column, item.row) + "</td>").join("") +
      (showAwards ? "<td></td>" : "") +
      "</tr>"
    ).join("");

    // MLB만 보는 중이면 숨겨진 마이너리그 기록이 있다는 것을 알리고 바로 펼칠 수 있게 한다
    let more = "";
    if (filter.league === "mlb") {
      const minors = player[group].filter((row) => row.league === "milb" && inPeriod(row));
      const seasons = new Set(minors.map((row) => row.season)).size;
      if (seasons) more = '<p class="career-more"><button type="button" class="link-button" data-show-minors>마이너리그 기록 ' + seasons + "시즌도 함께 보기</button></p>";
    }
    const leadNote = groups.some((item) => Object.keys(item.marks).length)
      ? '<p class="career-legend"><span class="lead">굵은 숫자</span>는 그 시즌 소속 리그(AL·NL) 1위입니다.</p>'
      : "";

    return (
      '<section class="career-section"><h2>' + GROUP_TITLE[group] + "</h2>" +
      '<div class="table-scroll"><table class="stats career"><thead>' + head + "</thead><tbody>" + body + "</tbody>" +
      (foot ? "<tfoot>" + foot + "</tfoot>" : "") + "</table></div>" + leadNote + more + "</section>"
    );
  }

  // ---------- 상단 통산 요약 (MLB.com 방식: 최근 시즌과 통산) ----------
  // MLB.com 선수 페이지 상단 요약과 같은 항목·순서 (2026-11-18 확인). 승-패는 한 칸으로 보여준다.
  const SUMMARY_KEYS = {
    // 경기 수(G)는 MLB.com 요약에는 없지만 출전 경기를 중요하게 보므로 맨 앞에 둔다 (2026-11-18 사용자 요구)
    // 안타·볼넷·삼진·출루율·장타율도 따로 보여준다 (2026-11-18 사용자 요구)
    batting: ["G", "AB", "H", "HR", "RBI", "BB", "SO", "SB", "AVG", "OBP", "SLG", "OPS"],
    // 볼넷·세이브·홀드를 더해 마무리·중간 투수의 성적도 보이게 한다 (2026-11-18 사용자 요구: 리베라·호프먼 등)
    pitching: ["G", "WL", "ERA", "outs", "SO", "BB", "SV", "HLD", "WHIP"],
  };
  const WIN_LOSS = {
    key: "WL", label: "W-L", desc: "승-패",
    format: (v) => v,
  };
  const withWinLoss = (row) => Object.assign({}, row, {
    WL: row.W !== null && row.W !== undefined && row.L !== null && row.L !== undefined ? row.W + "-" + row.L : null,
  });
  // 주 포지션이 아닌 기록은 투타겸업 수준일 때만 요약에 넣는다 (1,000타석 또는 100이닝 이상).
  // 지명타자 제도 이전 투수의 타석, 야수의 패전처리 등판은 연도별 표에서만 보여준다.
  const SECONDARY_MIN = { batting: (rows) => rows.reduce((s, r) => s + (r.PA || 0), 0) >= 1000,
    pitching: (rows) => rows.reduce((s, r) => s + (r.outs || 0), 0) >= 300 };

  function renderSummary() {
    const order = player.pos === "P" ? ["pitching", "batting"] : ["batting", "pitching"];
    const parts = order.map((group, index) => {
      const all = player[group];
      const league = all.some((row) => row.league === "mlb") ? "mlb" : "milb";
      const rows = all.filter((row) => row.league === league);
      if (!rows.length || (index > 0 && !SECONDARY_MIN[group](rows))) return "";
      const latest = Math.max(...rows.map((row) => row.season));
      const recent = rows.filter((row) => row.season === latest);
      const seasonRow = recent.length > 1 ? addRates(group, sumRows(group, recent)) : recent[0];
      const careerRow = addRates(group, sumRows(group, rows));
      const seasons = new Set(rows.map((row) => row.season)).size;
      const columns = SUMMARY_KEYS[group].map((key) =>
        key === "WL" ? WIN_LOSS : COLUMNS[group].basic.find((column) => column.key === key));
      const label = league === "mlb" ? "MLB" : "마이너리그";
      const line = (title, row, cls) =>
        "<tr" + (cls ? ' class="' + cls + '"' : "") + '><th scope="row" class="col-season">' + title + "</th>" +
        columns.map((column) => "<td>" + cell(column, withWinLoss(row)) + "</td>").join("") + "</tr>";
      return (
        '<div class="summary-block"><h3>' + (group === "batting" ? "타격" : "투구") + " · " + label + "</h3>" +
        '<div class="table-scroll"><table class="stats career summary-table"><thead><tr><th class="col-season"></th>' +
        columns.map((column) => '<th title="' + escapeHtml(column.desc) + '">' + escapeHtml(column.label) + "</th>").join("") +
        "</tr></thead><tbody>" +
        line(latest + " 시즌", seasonRow) +
        line(label + " 통산 <span class=\"muted\">" + seasons + "시즌</span>", careerRow, "summary-career") +
        "</tbody></table></div></div>"
      );
    }).join("");
    $("careerSummary").innerHTML = parts;
    $("careerSummary").hidden = !parts;
  }

  const matchesFilter = (row) =>
    inPeriod(row) &&
    (filter.league === "all" || row.league === filter.league);

  function renderCareer() {
    // 투수는 투구 기록을, 야수는 타격 기록을 먼저 보여준다. 수상은 앞의 표에만 붙인다.
    const order = player.pos === "P" ? ["pitching", "batting"] : ["batting", "pitching"];
    const hasRows = order.some((group) => player[group].length);
    let awardsUsed = false;
    const html = order.map((group) => {
      const rows = player[group].filter(matchesFilter);
      const table = renderTable(group, rows, !awardsUsed);
      if (table) awardsUsed = true;
      return table;
    }).join("");
    $("career").innerHTML = html ||
      '<p class="status">' + (hasRows ? "해당 조건의 기록이 없습니다." : "제공된 프로 경기 기록이 없습니다.") + "</p>";
  }

  // 시즌 목록은 이 선수가 기록을 남긴 시즌만 보여준다. 고른 조건은 주소에 남긴다.
  // MLB 기록이 있는 선수는 기본으로 MLB만, 없는 선수는 전체 레벨을 보여준다(2026-11-18 사용자 결정).
  let defaultLeague = "all";
  function setupFilters() {
    const rowsAll = player.batting.concat(player.pitching);
    defaultLeague = rowsAll.some((row) => row.league === "mlb") && rowsAll.some((row) => row.league === "milb") ? "mlb" : "all";
    const seasons = [...new Set(rowsAll.map((row) => row.season))].sort((a, b) => b - a);
    const params = new URLSearchParams(location.search);
    if (seasons.map(String).includes(params.get("from"))) filter.from = params.get("from");
    if (seasons.map(String).includes(params.get("to"))) filter.to = params.get("to");
    // 예전 주소(season=한 시즌)는 그 시즌 하나의 기간으로 연다
    if (seasons.map(String).includes(params.get("season"))) filter.from = filter.to = params.get("season");
    filter.league = ["all", "mlb", "milb"].includes(params.get("level")) ? params.get("level") : defaultLeague;
    // 시즌 목록은 최신 시즌부터(내림차순)
    const options = seasons.map((season) => '<option value="' + season + '">' + season + "</option>").join("");
    $("careerFrom").innerHTML = '<option value="">처음부터</option>' + options;
    $("careerTo").innerHTML = '<option value="">최근까지</option>' + options;
    $("careerFrom").value = filter.from;
    $("careerTo").value = filter.to;
    $("careerLevel").value = filter.league;
    const update = () => {
      filter.from = $("careerFrom").value;
      filter.to = $("careerTo").value;
      if (filter.from && filter.to && Number(filter.from) > Number(filter.to)) {
        [filter.from, filter.to] = [filter.to, filter.from]; // 시작이 끝보다 늦으면 맞바꾼다
        $("careerFrom").value = filter.from;
        $("careerTo").value = filter.to;
      }
      filter.league = $("careerLevel").value;
      const next = new URLSearchParams(location.search);
      next.delete("season");
      filter.from ? next.set("from", filter.from) : next.delete("from");
      filter.to ? next.set("to", filter.to) : next.delete("to");
      filter.league !== defaultLeague ? next.set("level", filter.league) : next.delete("level");
      history.replaceState(null, "", "?" + next.toString());
      renderCareer();
    };
    $("careerFrom").addEventListener("change", update);
    $("careerTo").addEventListener("change", update);
    $("careerLevel").addEventListener("change", update);
    // 표 아래 버튼: 마이너리그 기록 함께 보기
    $("career").addEventListener("click", (event) => {
      if (event.target.closest("[data-show-minors]")) {
        $("careerLevel").value = "all";
        update();
      }
    });
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
    renderSummary();
    renderCareer();
    // 수상·리그 1위 기록은 없어도 나머지 화면에 영향이 없으므로 따로 불러오고, 오면 표를 다시 그린다
    loadJson("data/awards.json").then(async (data) => {
      awardData = data;
      // 명예의 전당 투표 자료는 없어도 수상 경력은 그린다
      const votes = await loadJson("data/hof_votes.json").then((item) => item.players).catch(() => null);
      renderAwards(data, votes);
      renderCareer();
    }).catch(() => {});
    loadJson("data/leaders.json").then((data) => {
      leaders = data.seasons;
      renderCareer();
    }).catch(() => {});
    loadJson("data/teams.json").then(linkTeam).catch(() => {});
    if (pedData) pedData.then(renderPed); // 예전 common.js가 캐시돼 있으면 건너뛴다
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
