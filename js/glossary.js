// 빠따넷 용어 설명
// 용어 찾기(입력한 글자가 들어간 항목만 남김)와 최근 시즌 MLB 리그 상수 표(data/mlb/constants_{시즌}.json)

(function () {
  "use strict";

  const { loadJson, escapeHtml: esc } = window.BB;
  const $ = (id) => document.getElementById(id);

  // ---------- 용어 찾기 ----------
  const items = Array.from(document.querySelectorAll(".glossary-list > div"));
  const sections = Array.from(document.querySelectorAll(".glossary-section"));
  const normalize = (text) => text.toLowerCase().replace(/\s+/g, "");

  function filter() {
    const query = normalize($("glossaryFilter").value);
    let shown = 0;
    items.forEach((item) => {
      const match = !query || normalize(item.textContent).includes(query);
      item.hidden = !match;
      if (match) shown += 1;
    });
    // 남은 항목이 없는 묶음은 제목째 숨긴다. 리그 상수 표는 항목이 없으니 찾는 중에만 숨긴다
    sections.forEach((section) => {
      const list = section.querySelectorAll(".glossary-list > div");
      section.hidden = query ? !list.length || Array.from(list).every((item) => item.hidden) : false;
    });
    $("glossaryStatus").hidden = !query;
    $("glossaryStatus").textContent = shown ? shown + "개 용어" : "맞는 용어가 없습니다.";
  }
  $("glossaryFilter").addEventListener("input", filter);

  // ---------- 리그 상수 ----------
  const EVENTS = [["BB", "볼넷"], ["HBP", "몸에 맞는 공"], ["1B", "단타"], ["2B", "2루타"], ["3B", "3루타"], ["HR", "홈런"]];

  async function constants() {
    const meta = await loadJson("data/meta.json");
    const season = meta.leagues.find((l) => l.id === "mlb").seasons[0];
    const c = await loadJson("data/mlb/constants_" + season + ".json");
    const row = (label, value, note) => "<tr><th>" + label + "</th><td>" + value + "</td><td>" + note + "</td></tr>";
    const num = (value, digits) => (typeof value === "number" ? value.toFixed(digits).replace(/^0\./, ".") : "-");
    $("constantsTable").innerHTML =
      '<div class="table-scroll"><table class="stats glossary-constants"><caption>' + season + " MLB</caption>" +
      "<thead><tr><th>항목</th><th>값</th><th>뜻</th></tr></thead><tbody>" +
      row("리그 wOBA", num(c.wOBA, 3), "리그 평균 가중 출루율") +
      row("wOBA 배율", num(c.wOBAScale, 3), "wOBA 차이를 득점으로 바꿀 때 나누는 값") +
      EVENTS.map(([key, label]) => row(label + " 가중치", num((c.weights || {})[key], 3), "wOBA에서 " + label + " 하나의 무게")).join("") +
      row("타석당 득점", num(c.runsPerPA, 4), "리그 전체 득점 ÷ 타석") +
      row("1승당 득점", num(c.runsPerWin, 2), "1승을 더하는 데 필요한 득점 (WAR 환산)") +
      row("리그 평균자책점", num(c.ERA, 2), "") +
      row("FIP 상수", num(c.cFIP, 3), "리그 FIP를 리그 평균자책점에 맞추는 값") +
      "</tbody></table></div>" +
      '<p class="page-note">자체 계산값이며 매일 갱신으로 바뀝니다. 다른 사이트의 상수와 조금 다를 수 있습니다. 하위 리그(AL·NL)별 평균은 wRC+·ERA-·FIP-의 분모로 따로 씁니다.</p>';
  }

  constants()
    .catch(() => { $("constantsTable").innerHTML = '<p class="status">리그 상수를 불러오지 못했습니다.</p>'; })
    .finally(() => $("constantsTable").setAttribute("aria-busy", "false"));
})();
