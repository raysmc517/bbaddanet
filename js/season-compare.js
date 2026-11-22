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

  // 비교 단위는 "시즌 · 레벨"이다(MLB, AAA, AA, High-A, Single-A, Rookie …). 레벨이 다르면 리그 수준이 다르므로 합치지 않는다.
  const LEVEL_ORDER = ["MLB", "AAA", "AA", "High-A", "Single-A", "Rookie"];
  const levelOf = (r) => r.league === "mlb" ? "MLB" : r.league === "milb" ? r.level || "MiLB" : null;
  const rank = (level) => { const i = LEVEL_ORDER.indexOf(level); return i < 0 ? LEVEL_ORDER.length : i; };
  const label = (e) => e.season + " · " + e.level;
  // 표 머리글: 좁은 화면에서도 변화 열이 보이도록 레벨을 시즌 아래 줄에 둔다.
  const headLabel = (e) => e.season + '<br><span class="muted">' + esc(e.level) + "</span>";
  const sameEntry = (a, b) => a && b && a.season === b.season && a.level === b.level;

  // 한 시즌·레벨의 합계 행. 팀이 여러 개면 화면과 같은 합산 함수를 쓴다(합산 행에는 세이버 지표가 없을 수 있음).
  function entryRow(player, group, entry, aggregate) {
    const rows = (player[group] || []).filter((r) => r.season === entry.season && levelOf(r) === entry.level);
    if (!rows.length) return null;
    return rows.length === 1 ? rows[0] : aggregate(group, rows);
  }
  // 선수의 MLB·마이너 기록 단위 목록: 최신 시즌 먼저, 같은 시즌은 높은 레벨 먼저. volume은 타석+상대 타자 수.
  function entries(player) {
    const map = new Map();
    for (const r of (player.batting || []).concat(player.pitching || [])) {
      const level = levelOf(r);
      if (!level || !known(r.season)) continue;
      const key = r.season + "|" + level;
      const e = map.get(key) || { season: r.season, level, volume: 0 };
      e.volume += (known(r.PA) ? r.PA : 0) + (known(r.BF) ? r.BF : 0);
      map.set(key, e);
    }
    return [...map.values()].sort((a, b) => b.season - a.season || rank(a.level) - rank(b.level));
  }
  const biggest = (list) => list.reduce((best, e) => (!best || e.volume > best.volume ? e : best), null);
  // 기본 기준: 분석 중인 MLB 시즌이 있으면 그것, 없으면 가장 최근 시즌에서 가장 많이 뛴 레벨.
  function defaultAfter(list, season) {
    const mlb = list.find((e) => e.season === season && e.level === "MLB");
    if (mlb) return mlb;
    return list.length ? biggest(list.filter((e) => e.season === list[0].season)) : null;
  }
  // 기본 비교: 기준보다 앞선 가장 최근 시즌에서 같은 레벨, 없으면 가장 가까운 레벨(같으면 더 많이 뛴 쪽).
  function defaultBefore(list, after) {
    const earlier = list.filter((e) => e.season < after.season);
    if (!earlier.length) return list.find((e) => !sameEntry(e, after)) || null; // 같은 시즌 다른 레벨(승격 전후)
    const season = earlier[0].season;
    const gap = (e) => Math.abs(rank(e.level) - rank(after.level));
    return earlier.filter((e) => e.season === season)
      .reduce((best, e) => (!best || gap(e) < gap(best) || (gap(e) === gap(best) && e.volume > best.volume) ? e : best), null);
  }

  function statTable(group, before, after, beforeSeason, afterSeason) {
    const { METRICS, delta, gain, signed } = window.BB.compare;
    const pair = { before, after };
    const volume = group === "batting" ?
      ["타석", String(before.PA ?? "-"), String(after.PA ?? "-")] :
      ["이닝", known(before.outs) ? fmt.ip(before.outs) : "-", known(after.outs) ? fmt.ip(after.outs) : "-"];
    const tone = (c) => { const g = gain(pair, c); return g === null || Math.abs(g) < 1e-9 ? "" : g < 0 ? "delta-worse" : "delta-better"; };
    const rows = METRICS[group].filter((c) => known(before[c.key]) || known(after[c.key])).map((c) => '<tr><th scope="row" title="' + esc(c.desc) + '">' + esc(c.label) + '</th><td>' +
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

  const select = (cls, list, chosen, skip) => '<select class="' + cls + '">' + list.filter((e) => !sameEntry(e, skip)).map((e) =>
    '<option value="' + e.season + "|" + esc(e.level) + '"' + (sameEntry(e, chosen) ? " selected" : "") + '>' + esc(label(e)) + '</option>').join("") + '</select>';
  const parse = (value) => { const [season, level] = value.split("|"); return { season: Number(season), level }; };

  // "MLB 기록만": MLB 기록이 두 시즌 이상이고 마이너 기록도 있을 때만 보인다.
  const mlbList = (list) => list.filter((e) => e.level === "MLB");
  const canMlbOnly = (list) => mlbList(list).length >= 2;
  const hasMinor = (list) => list.some((e) => e.level !== "MLB");
  // 기본은 MLB 기록이 두 시즌 이상이면 MLB만 본다.
  const defaultMlbOnly = (player) => canMlbOnly(entries(player));
  // 목록 범위가 바뀌어 고른 기록이 빠지면 기본 선택으로 되돌린다.
  function pick(list, after, before, season) {
    const inList = (e) => e && list.some((x) => sameEntry(x, e));
    const a = inList(after) ? after : defaultAfter(list, season);
    const b = inList(before) && !sameEntry(before, a) ? before : a && defaultBefore(list, a);
    return [a, b];
  }

  async function draw(player, aggregate, after, before, mlbOnly) {
    const version = ++request;
    const all = entries(player);
    const list = mlbOnly ? mlbList(all) : all;
    const groups = (player.pos === "P" ? ["pitching", "batting"] : ["batting", "pitching"])
      .filter((g) => entryRow(player, g, after, aggregate) && entryRow(player, g, before, aggregate));
    const minor = after.level !== "MLB" || before.level !== "MLB";
    const head = '<div class="season-compare-head"><h2 id="seasonCompareTitle">시즌 비교</h2>' +
      '<button type="button" class="season-compare-close" aria-label="닫기">×</button></div>' +
      '<p class="muted">' + esc(player.name) + ' · MLB와 마이너리그 기록을 시즌·레벨 단위로 나란히 봅니다.</p>' +
      '<div class="season-compare-pickers"><label class="field"><span>기준</span>' + select("season-compare-after", list, after) + '</label>' +
      '<label class="field"><span>비교 대상</span>' + select("season-compare-before", list, before, after) + '</label>' +
      // MLB 기록이 두 시즌 이상이고 마이너 기록도 있을 때만 보인다. 첫 콜업 시즌에는 숨기고 마이너 기록과 비교한다.
      (hasMinor(all) && canMlbOnly(all) ? '<label class="season-compare-mlb"><input type="checkbox" class="season-compare-mlb-only"' +
        (mlbOnly ? " checked" : "") + '> MLB 기록만</label>' : "") + '</div>' +
      (before.season < after.season - 1 && !list.some((e) => e.season === after.season - 1) ? note("직전 시즌(" + (after.season - 1) + ") 기록이 없어 그 이전 시즌과 비교합니다.") : "") +
      (after.level !== before.level ? note("레벨이 다릅니다 (" + esc(before.level) + " → " + esc(after.level) + "). 상대 수준과 리그 환경이 달라 같은 기록도 의미가 다릅니다. wRC+·ERA-·FIP-처럼 그 리그 평균과 비교한 지표가 덜 흔들리지만, 100이 레벨 간 같은 실력을 뜻하지는 않습니다.") : "");
    const body = groups.map((g) => {
      const b = entryRow(player, g, before, aggregate), a = entryRow(player, g, after, aggregate);
      return '<section class="season-compare-group"><h3>' + (g === "batting" ? "타격" : "투구") + '</h3>' + headline(g, b, a) +
        statTable(g, b, a, headLabel(before), headLabel(after)) +
        (after.level === "MLB" && before.level === "MLB" ? '<div data-statcast-group="' + g + '">' + note("Statcast 비교를 불러오는 중…") + '</div>' : "") + '</section>';
    }).join("") || note("두 기록 모두 같은 역할(타격·투구)의 기록이 있어야 비교할 수 있습니다.");
    dialog.innerHTML = head + body +
      note("변화는 기준 − 비교 대상입니다. 빨강은 나빠진 방향, 파랑은 좋아진 방향이며 ERA·K%(타자)처럼 낮을수록 좋은 지표는 방향을 반대로 판단합니다. wOBA·wRC+·FIP 같은 세이버 지표는 자체 계산한 시즌(2024년부터)·레벨(AAA~Single-A)만 있어 그 밖의 기록과 여러 팀 합산 행은 '-'입니다. 두 기록 모두 값이 없는 지표는 표에서 뺍니다. 표본이 작으면 큰 변화도 우연일 수 있습니다." +
        (minor ? " 마이너리그는 Statcast 비교를 제공하지 않습니다." : ""));
    dialog.querySelector(".season-compare-close").addEventListener("click", () => dialog.close());
    dialog.querySelector(".season-compare-after").addEventListener("change", (e) => {
      const next = parse(e.target.value);
      draw(player, aggregate, next, defaultBefore(list, next), mlbOnly);
    });
    dialog.querySelector(".season-compare-before").addEventListener("change", (e) => draw(player, aggregate, after, parse(e.target.value), mlbOnly));
    const toggle = dialog.querySelector(".season-compare-mlb-only");
    if (toggle) toggle.addEventListener("change", (e) => {
      const next = e.target.checked;
      const [a, b] = pick(next ? mlbList(all) : all, after, before, after.season);
      draw(player, aggregate, a, b, next); // 첫 await 전에 화면을 다시 그리므로 바로 초점을 옮길 수 있다
      const box = dialog.querySelector(".season-compare-mlb-only");
      if (box) box.focus();
    });
    for (const g of groups) {
      if (minor) break;
      const html = await statcastPart(player, g, before.season, after.season);
      if (version !== request) return;
      const slot = dialog.querySelector('[data-statcast-group="' + g + '"]');
      if (slot) slot.innerHTML = html;
    }
  }

  // 비교할 기록 단위가 둘 이상이면 열 수 있다.
  const available = (player) => entries(player).length >= 2;
  function open(player, aggregate, season, opener) {
    const mlbOnly = defaultMlbOnly(player);
    const list = mlbOnly ? mlbList(entries(player)) : entries(player);
    const after = defaultAfter(list, season);
    const before = after && defaultBefore(list, after);
    if (!before) return;
    const d = ensureDialog();
    d.onclose = () => { if (opener) opener.focus(); };
    draw(player, aggregate, after, before, mlbOnly);
    if (!d.open) d.showModal();
  }

  window.BB.seasonCompare = { open, available, entries, entryRow, defaultAfter, defaultBefore, defaultMlbOnly, pick, mlbList };
})();
