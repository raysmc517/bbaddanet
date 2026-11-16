// 빠따넷 선수 페이지
// player.html?id=선수ID 로 열면 data/players/{id}.json을 읽어 프로필과 연도별 성적을 그린다.

(function () {
  "use strict";

  const { COLUMNS, escapeHtml, loadJson, cell, visibleColumns } = window.BB;

  const $ = (id) => document.getElementById(id);
  const HAND = { L: "좌", R: "우", S: "양" };
  const GROUP_TITLE = { batting: "타격 기록", pitching: "투구 기록" };

  let player = null;
  let view = "basic";

  function showError(message) {
    $("status").className = "status error";
    $("status").textContent = message;
  }

  function renderProfile() {
    const name = player.nameKo || player.name;
    document.title = "빠따넷 · " + name;
    $("playerName").textContent = name;

    const sub = [player.team, player.pos, player.number ? "#" + player.number : ""].filter(Boolean);
    $("playerSub").textContent = sub.join(" · ") + (player.active ? "" : " (비활동)");

    const body = [player.heightCm ? player.heightCm + "cm" : "", player.weightKg ? player.weightKg + "kg" : ""].filter(Boolean);
    const hands = (HAND[player.throws] ? HAND[player.throws] + "투" : "") + (HAND[player.bats] ? HAND[player.bats] + "타" : "");
    const facts = [
      ["생년월일", player.birthDate ? player.birthDate + (player.age ? " (" + player.age + "세)" : "") : ""],
      ["출신", player.country],
      ["신체", body.join(" / ")],
      ["투타", hands],
      ["MLB 데뷔", player.debut || "없음"],
    ];
    $("playerFacts").innerHTML = facts
      .filter((fact) => fact[1])
      .map((fact) => "<div><dt>" + fact[0] + "</dt><dd>" + escapeHtml(fact[1]) + "</dd></div>")
      .join("");
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

  function renderTable(group) {
    const rows = player[group];
    if (!rows.length) return "";
    const columns = visibleColumns(COLUMNS[group][view], rows);
    const head =
      '<tr><th class="col-season">시즌</th><th class="col-team">레벨</th><th class="col-team">팀</th><th>나이</th>' +
      columns.map((column) => '<th title="' + escapeHtml(column.desc) + '">' + escapeHtml(column.label) + "</th>").join("") +
      "</tr>";
    const body = rows.map((row) => {
      const team = escapeHtml(row.team || "-") + (row.nt > 1 ? '<span class="team-note">' + row.nt + "팀</span>" : "");
      return (
        '<tr><td class="col-season">' + row.season + "</td>" +
        '<td class="col-team"><span class="level level-' + row.league + '">' + escapeHtml(row.level) + "</span></td>" +
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

  function renderCareer() {
    // 투수는 투구 기록을, 야수는 타격 기록을 먼저 보여준다
    const order = player.pos === "P" ? ["pitching", "batting"] : ["batting", "pitching"];
    const html = order.map(renderTable).join("");
    $("career").innerHTML = html || '<p class="status">AA 이상 리그의 최근 3개 시즌 기록이 없습니다.</p>';
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
    $("status").textContent = "";
    renderProfile();
    renderProspect();
    renderCareer();
    $("careerToolbar").hidden = false;

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
