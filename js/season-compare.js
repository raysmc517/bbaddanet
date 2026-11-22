// 선수 상세 분석의 "지난 시즌과 비교" 팝업.
// 선수 파일의 MLB 시즌 기록과 저장된 Statcast 집계만 읽어 두 시즌을 나란히 놓는다. 새 지표를 만들지 않는다.
(function () {
  "use strict";
  const { loadJson, escapeHtml: esc, fmt } = window.BB;
  const known = (v) => typeof v === "number" && Number.isFinite(v);
  const note = (text) => '<p class="page-note">' + text + '</p>';
  const kmh = (mph) => (mph * 1.609344).toFixed(1);
  const sign = (d) => (d > 0 ? "+" : d < 0 ? "−" : "±");
  // 속도 차이: km/h 기준, 괄호 안 mph
  const speedDiff = (d) => sign(d) + Math.abs(d * 1.609344).toFixed(1) + ' km/h <span class="muted">(' + sign(d) + Math.abs(d).toFixed(1) + " mph)</span>";

  // 한 시즌의 MLB 합계 행. 팀이 여러 개면 화면과 같은 합산 함수를 쓴다(합산 행에는 세이버 지표가 없을 수 있음).
  function seasonRow(player, group, season, aggregate) {
    const rows = (player[group] || []).filter((r) => r.league === "mlb" && r.season === season);
    if (!rows.length) return null;
    return rows.length === 1 ? rows[0] : aggregate(group, rows);
  }
  // 기준 시즌보다 앞선 MLB 시즌(최신순). 타격·투구 중 하나라도 있으면 포함한다.
  function earlierSeasons(player, season) {
    return [...new Set(player.batting.concat(player.pitching).filter((r) => r.league === "mlb" && r.season < season).map((r) => r.season))]
      .sort((a, b) => b - a);
  }

  function statTable(group, before, after, beforeSeason, afterSeason) {
    const { METRICS, delta, gain, signed } = window.BB.compare;
    const pair = { before, after };
    const volume = group === "batting" ?
      ["타석", String(before.PA ?? "-"), String(after.PA ?? "-")] :
      ["이닝", known(before.outs) ? fmt.ip(before.outs) : "-", known(after.outs) ? fmt.ip(after.outs) : "-"];
    const tone = (c) => { const g = gain(pair, c); return g === null || Math.abs(g) < 1e-9 ? "" : g < 0 ? "delta-worse" : "delta-better"; };
    const rows = METRICS[group].map((c) => '<tr><th scope="row" title="' + esc(c.desc) + '">' + esc(c.label) + '</th><td>' +
      (known(before[c.key]) ? c.format(before[c.key]) : "-") + '</td><td>' + (known(after[c.key]) ? c.format(after[c.key]) : "-") +
      '</td><td class="' + tone(c) + '">' + signed(c, delta(pair, c.key)) + '</td></tr>').join("");
    return '<div class="table-scroll"><table class="stats season-compare-table"><thead><tr><th>지표</th><th>' + beforeSeason + '</th><th>' + afterSeason +
      '</th><th>변화</th></tr></thead><tbody><tr class="season-compare-volume"><th scope="row">' + volume[0] + '</th><td>' + volume[1] + '</td><td>' + volume[2] +
      '</td><td></td></tr>' + rows + '</tbody></table></div>';
  }

  // 한 줄 요약: 대표 지표(타자 OPS, 투수 ERA)의 변화.
  function headline(group, before, after) {
    const { METRICS, delta, gain, signed } = window.BB.compare;
    const c = METRICS[group][0];
    const d = delta({ before, after }, c.key);
    if (d === null) return "";
    const g = gain({ before, after }, c);
    return '<p class="season-compare-headline">' + c.label + ' ' + c.format(before[c.key]) + ' → ' + c.format(after[c.key]) +
      ' <strong class="' + (Math.abs(g) < 1e-9 ? "" : g < 0 ? "delta-worse" : "delta-better") + '">' + signed(c, d) + '</strong></p>';
  }

  // Statcast 타구 질. 발사각은 높낮이로 좋고 나쁨을 판정하지 않는다.
  const BATTED = [
    ["exitVelocity", "평균 타구 속도", (v) => kmh(v) + " km/h", 1, "speed"],
    ["hardHitPct", "강한 타구%", (v) => v.toFixed(1) + "%", 1, "%p"],
    ["barrelPct", "배럴%", (v) => v.toFixed(1) + "%", 1, "%p"],
    ["sweetSpotPct", "스위트스폿%", (v) => v.toFixed(1) + "%", 1, "%p"],
    ["launchAngle", "평균 발사각", (v) => v.toFixed(1) + "°", 0, "°"],
  ];
  function battedTable(before, after, beforeSeason, afterSeason) {
    const rows = BATTED.map(([key, label, format, direction, unit]) => {
      const a = before[key], b = after[key], d = known(a) && known(b) ? b - a : null;
      const cls = d === null || !direction || Math.abs(d) < 1e-9 ? "" : d * direction < 0 ? "delta-worse" : "delta-better";
      return '<tr><th scope="row">' + label + '</th><td>' + (known(a) ? format(a) : "-") + '</td><td>' + (known(b) ? format(b) : "-") + '</td><td class="' + cls + '">' +
        (d === null ? "-" : unit === "speed" ? speedDiff(d) : sign(d) + Math.abs(d).toFixed(1) + unit) + '</td></tr>';
    }).join("");
    return '<div class="table-scroll"><table class="stats season-compare-table"><thead><tr><th>타구</th><th>' + beforeSeason + '</th><th>' + afterSeason +
      '</th><th>변화</th></tr></thead><tbody><tr class="season-compare-volume"><th scope="row">타구 수</th><td>' + (before.bbe ?? "-") + '</td><td>' + (after.bbe ?? "-") +
      '</td><td></td></tr>' + rows + '</tbody></table></div>' + note("타구 속도 변화는 mph 기준입니다. 발사각은 높낮이만으로 좋고 나쁨을 판단할 수 없어 색을 칠하지 않습니다.");
  }

  // 구종 사용률·구속 변화. 구종마다 유리한 방향이 달라 색을 칠하지 않는다.
  function arsenalTable(before, after, beforeSeason, afterSeason) {
    if (before.handSplits || after.handSplits) return note("양손 투수는 투구 손별 표본이 달라 구종 비교를 생략합니다. 아래 Statcast 구역에서 시즌별로 확인하세요.");
    const name = (t) => (window.BB.statcast && window.BB.statcast.pitchName ? window.BB.statcast.pitchName(t) : t);
    const map = (row) => new Map((row.arsenal || []).map((p) => [p.type, p]));
    const a = map(before), b = map(after);
    const types = [...new Set([...a.keys(), ...b.keys()])].sort((x, y) => ((b.get(y) || {}).usagePct || 0) - ((b.get(x) || {}).usagePct || 0));
    const usage = (p) => p && known(p.usagePct) ? p.usagePct.toFixed(1) + "%" : "-";
    const speed = (p) => p && known(p.velocity) ? kmh(p.velocity) + " km/h" : "-";
    const diff = (x, y, key, unit) => !(x && y && known(x[key]) && known(y[key])) ? "-" :
      unit === "speed" ? speedDiff(y[key] - x[key]) : sign(y[key] - x[key]) + Math.abs(y[key] - x[key]).toFixed(1) + unit;
    const rows = types.map((t) => {
      const x = a.get(t), y = b.get(t);
      return '<tr><th scope="row">' + esc(name(t)) + ' <span class="muted">' + esc(t) + '</span></th><td>' + usage(x) + ' → ' + usage(y) + '</td><td>' + diff(x, y, "usagePct", "%p") +
        '</td><td>' + speed(x) + ' → ' + speed(y) + '</td><td>' + diff(x, y, "velocity", "speed") + '</td></tr>';
    }).join("");
    return '<div class="table-scroll"><table class="stats season-compare-table season-compare-arsenal"><thead><tr><th>구종</th><th>사용률 ' + beforeSeason + ' → ' + afterSeason +
      '</th><th>변화</th><th>평균 구속</th><th>변화</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
      note("한쪽 시즌에 없는 구종은 '-'입니다. 구종마다 유리한 방향이 달라 색을 칠하지 않습니다. 사용률은 반올림 값입니다.");
  }

  async function statcastPart(player, group, beforeSeason, afterSeason) {
    if (beforeSeason < 2015) return "";
    try {
      const [x, y] = await Promise.all([beforeSeason, afterSeason].map((s) => loadJson("data/statcast/" + s + ".json")));
      const key = group === "batting" ? "batters" : "pitchers";
      const a = x[key][player.id], b = y[key][player.id];
      if (!a || !b) return note("두 시즌 중 한 시즌의 Statcast 집계가 없어 " + (group === "batting" ? "타구" : "구종") + " 비교를 생략합니다.");
      return '<h4>' + (group === "batting" ? "타구 질" : "구종 사용률·구속") + '</h4>' +
        (group === "batting" ? battedTable(a, b, beforeSeason, afterSeason) : arsenalTable(a, b, beforeSeason, afterSeason));
    } catch (_) {
      return note("Statcast 자료를 불러오지 못했습니다.");
    }
  }

  let dialog = null;
  let request = 0;
  function ensureDialog() {
    if (dialog) return dialog;
    dialog = document.createElement("dialog");
    dialog.className = "season-compare-dialog";
    dialog.setAttribute("aria-labelledby", "seasonCompareTitle");
    dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); }); // 바깥(배경) 누르면 닫기
    document.body.appendChild(dialog);
    return dialog;
  }

  async function draw(player, aggregate, afterSeason, beforeSeason) {
    const version = ++request;
    const options = earlierSeasons(player, afterSeason);
    const groups = (player.pos === "P" ? ["pitching", "batting"] : ["batting", "pitching"])
      .filter((g) => seasonRow(player, g, afterSeason, aggregate) && seasonRow(player, g, beforeSeason, aggregate));
    const head = '<div class="season-compare-head"><h2 id="seasonCompareTitle">지난 시즌과 비교</h2>' +
      '<button type="button" class="season-compare-close" aria-label="닫기">×</button></div>' +
      '<p class="muted">' + esc(player.name) + ' · ' + afterSeason + ' 시즌을 비교 시즌과 나란히 봅니다.</p>' +
      '<label class="field"><span>비교 시즌</span><select class="season-compare-select">' +
      options.map((s) => '<option value="' + s + '"' + (s === beforeSeason ? " selected" : "") + '>' + s + (s === afterSeason - 1 ? " (직전 시즌)" : "") + '</option>').join("") + '</select></label>' +
      (!options.includes(afterSeason - 1) ? note("직전 시즌(" + (afterSeason - 1) + ") MLB 기록이 없어 그 이전 시즌과 비교합니다.") : "");
    const body = groups.map((g) => {
      const before = seasonRow(player, g, beforeSeason, aggregate), after = seasonRow(player, g, afterSeason, aggregate);
      return '<section class="season-compare-group"><h3>' + (g === "batting" ? "타격" : "투구") + '</h3>' + headline(g, before, after) +
        statTable(g, before, after, beforeSeason, afterSeason) + '<div data-statcast-group="' + g + '">' + note("Statcast 비교를 불러오는 중…") + '</div></section>';
    }).join("") || note("두 시즌 모두 같은 역할(타격·투구)의 MLB 기록이 있어야 비교할 수 있습니다.");
    dialog.innerHTML = head + body +
      note("변화는 " + afterSeason + " − " + beforeSeason + "입니다. 빨강은 나빠진 방향, 파랑은 좋아진 방향이며 ERA·K%(타자)처럼 낮을수록 좋은 지표는 방향을 반대로 판단합니다. wOBA·wRC+·FIP 같은 세이버 지표는 자체 계산한 시즌(2024년부터)만 있어 그 이전 시즌과 여러 팀 합산 행은 '-'입니다. 표본이 작으면 큰 변화도 우연일 수 있습니다.");
    dialog.querySelector(".season-compare-close").addEventListener("click", () => dialog.close());
    dialog.querySelector(".season-compare-select").addEventListener("change", (e) => draw(player, aggregate, afterSeason, Number(e.target.value)));
    for (const g of groups) {
      const html = await statcastPart(player, g, beforeSeason, afterSeason);
      if (version !== request) return;
      const slot = dialog.querySelector('[data-statcast-group="' + g + '"]');
      if (slot) slot.innerHTML = html;
    }
  }

  function open(player, aggregate, afterSeason, opener) {
    const options = earlierSeasons(player, afterSeason);
    if (!options.length) return;
    const d = ensureDialog();
    d.onclose = () => { if (opener) opener.focus(); };
    draw(player, aggregate, afterSeason, options[0]);
    if (!d.open) d.showModal();
  }

  window.BB.seasonCompare = { open, earlierSeasons, seasonRow };
})();
