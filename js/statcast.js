// Baseball Savant 시즌 집계. 브라우저는 저장된 JSON만 읽고 공식 사이트에 수집 요청하지 않는다.
(function () {
  "use strict";
  const { loadJson, escapeHtml: esc } = window.BB;
  const known = (v) => typeof v === "number" && Number.isFinite(v);
  const fixed = (v, digits = 1) => known(v) ? v.toFixed(digits) : "-";
  const signed = (v) => known(v) ? (v > 0 ? "+" : "") + v.toFixed(1) : "-";
  const speed = (mph) => known(mph) ? (mph * 1.609344).toFixed(1) + ' km/h <span class="muted">(' + mph.toFixed(1) + ' mph)</span>' : "-";
  const movement = (inches) => known(inches) ? signed(inches * 2.54) + ' cm <span class="muted">(' + signed(inches) + ' in)</span>' : "-";
  const PITCHES = {
    FF: ["포심", "#c83e4d"], SI: ["싱커", "#d77722"], FC: ["커터", "#a26b14"],
    SL: ["슬라이더", "#4c76d0"], ST: ["스위퍼", "#8656c7"], CU: ["커브", "#36a0bf"],
    SV: ["슬러브", "#678ab3"], CH: ["체인지업", "#328d55"], FS: ["스플리터", "#298d8d"],
    FO: ["포크볼", "#757c2b"], KN: ["너클볼", "#8b6b55"], SC: ["스크루볼", "#b04791"],
    FA: ["패스트볼 (세부 미분류)", "#b55d68"], FT: ["투심", "#c56b37"], KC: ["너클커브", "#4896b2"],
    CS: ["슬로 커브", "#60a9bd"], EP: ["이퍼스", "#a07861"], GY: ["자이로볼", "#865a9c"],
    PO: ["피치아웃", "#738077"], IN: ["고의볼", "#929c95"], UN: ["미분류", "#777"],
    AB: ["자동볼", "#777"], AS: ["자동 스트라이크", "#777"], NP: ["투구 없음", "#777"],
  };
  const pitchName = (type) => (PITCHES[type] || [type])[0];
  const color = (type) => (PITCHES[type] || ["", "#777"])[1];
  const note = (text) => '<p class="page-note">' + text + '</p>';
  const link = (path, season, label) => '<a href="https://baseballsavant.mlb.com/leaderboard/' + path + '?year=' + season + '&amp;min=1" target="_blank" rel="noopener">' + label + '</a>';
  function table(headers, rows) {
    return '<div class="table-scroll"><table class="stats"><thead><tr>' + headers.map(([title, desc]) =>
      '<th scope="col" title="' + esc(desc || title) + '">' + esc(title) + '</th>').join("") + '</tr></thead><tbody>' +
      rows.map((row) => '<tr>' + row.map((v) => '<td>' + v + '</td>').join("") + '</tr>').join("") + '</tbody></table></div>';
  }

  // 지표 읽는 법. 단일 값의 우열을 단정하지 않고 구종별로 유리한 방향의 '경향'만 적는다.
  function guide(summary, items, outro) {
    return '<details class="metric-help statcast-help"><summary>' + summary + '</summary><dl>' +
      items.map(([term, text]) => '<div><dt>' + term + '</dt><dd>' + text + '</dd></div>').join("") + '</dl>' +
      (outro ? '<p>' + outro + '</p>' : '') + '</details>';
  }
  const PITCH_GUIDE = guide("지표 읽는 법 · 높을수록 좋은가요?", [
    ["평균 구속", "같은 구종이면 대체로 빠를수록 타자가 대응할 시간이 줄어 유리합니다. 체인지업·스플리터는 직구와 팔 동작은 같고 속도는 충분히 느려야 효과가 있어, 직구와의 구속 차이도 함께 봅니다."],
    ["회전수", "공이 1분에 도는 횟수입니다. 높다고 무조건 좋지 않습니다. 회전 방향(축)에 따라 같은 회전수도 움직임이 달라집니다. 포심·커브·슬라이더는 높은 편이, 싱커·스플리터처럼 가라앉혀야 하는 공은 낮은 편이 유리한 경향입니다."],
    ["수평 이동", "포수 쪽에서 본 좌우 휨입니다. +는 포수 기준 오른쪽, −는 왼쪽으로 방향만 뜻하며 크기는 절댓값으로 봅니다. 싱커·체인지업은 투구하는 팔 쪽으로, 슬라이더·커브는 반대쪽으로 휩니다. 좌투수와 우투수는 부호가 반대라 같은 손 평균과 비교합니다."],
    ["수직 IVB", "중력이 없다고 가정했을 때의 위아래 움직임입니다. 포심은 클수록 덜 떨어져 타자 눈에 '떠오르는' 듯 보여 헛스윙에 유리한 경향이고, 싱커·체인지업·스플리터는 작을수록(더 가라앉을수록), 커브는 음수가 클수록(더 크게 떨어질수록) 유리한 경향입니다."],
  ], "결국 기준은 같은 구종·같은 손의 MLB 평균과 비교한 차이, 그리고 구종끼리의 구속·움직임 차이입니다. 수치만으로 구위를 판정할 수 없으며 실제 결과는 제구·투구 위치·구종 조합에 크게 좌우됩니다.");
  const BATTING_GUIDE = guide("지표 읽는 법 · 높을수록 좋은가요?", [
    ["타구 속도", "빠를수록 좋습니다. 빠른 타구일수록 안타·장타가 될 가능성이 커집니다."],
    ["발사각", "높을수록 좋은 지표가 아닙니다. 너무 낮으면 땅볼, 너무 높으면 뜬공 아웃이 늘어 중간 범위(약 8~32도)가 유리합니다."],
    ["강한 타구%", "높을수록 좋습니다. 95 mph(약 153 km/h) 이상 타구의 비율입니다."],
    ["배럴%", "높을수록 좋습니다. 장타 가능성이 매우 높은 속도·각도 조합의 타구 비율입니다."],
    ["스위트스폿%", "높을수록 좋은 경향입니다. 안타가 되기 좋은 각도(8~32도)로 날아간 타구의 비율입니다."],
  ], "타구 수가 적은 시즌은 값이 크게 흔들리므로 표본(타구 수)을 함께 보세요.");

  // 부호 있는 원본 인치 좌표를 사용한다. 수직 값은 중력 없는 IVB이며 실제 궤적이 아니다.
  function movementPlot(pitches) {
    const points = pitches.filter((p) => known(p.horizontal) && known(p.ivb));
    if (!points.length) return "";
    const range = Math.max(20, Math.ceil(Math.max(...points.flatMap((p) => [Math.abs(p.horizontal), Math.abs(p.ivb)])) / 10) * 10);
    const x = (v) => 310 + v / range * 230;
    const y = (v) => 160 - v / range * 115;
    const ticks = [-range, -range / 2, 0, range / 2, range];
    const grid = ticks.map((v) => '<line x1="' + x(v) + '" y1="45" x2="' + x(v) + '" y2="275"/>' +
      '<line x1="80" y1="' + y(v) + '" x2="540" y2="' + y(v) + '"/>').join("");
    const labels = ticks.map((v) => '<text x="' + x(v) + '" y="292" text-anchor="middle">' + v + '</text>' +
      '<text x="70" y="' + (y(v) + 4) + '" text-anchor="end">' + v + '</text>').join("");
    const marks = points.map((p) => '<g><title>' + esc(pitchName(p.type)) + ' · ' + fixed(p.velocity) + ' mph · 수평 ' + signed(p.horizontal) +
      ' in · IVB ' + signed(p.ivb) + ' in</title><circle cx="' + x(p.horizontal) + '" cy="' + y(p.ivb) + '" r="6" fill="' + color(p.type) + '"/>' +
      '<text x="' + (x(p.horizontal) + 9) + '" y="' + (y(p.ivb) - 7) + '">' + esc(p.type) + '</text></g>').join("");
    return '<figure class="pitch-plot"><svg viewBox="0 0 620 325" role="img" aria-label="구종별 평균 수평 이동과 중력을 제외한 수직 이동. 아래 표에서도 같은 값을 확인할 수 있습니다.">' +
      '<g class="pitch-grid">' + grid + '</g><g class="pitch-axis"><line x1="80" y1="160" x2="540" y2="160"/>' +
      '<line x1="310" y1="45" x2="310" y2="275"/></g><g class="pitch-labels">' + labels + marks +
      '<text x="310" y="20" text-anchor="middle">수직 이동 IVB (in) · 중력 제외</text><text x="310" y="318" text-anchor="middle">수평 이동 (in) · 포수 시점</text></g></svg>' +
      '<figcaption class="page-note">점은 구종별 평균이며 공의 실제 궤적이 아닙니다. 약자는 위 구종 표와 같습니다.</figcaption></figure>';
  }

  function comparison(value, average, format, unit) {
    if (!known(average)) return '<span class="muted">미제공</span>';
    return format(average) + (known(value) ? '<br><span class="muted">차이 ' + signed(value - average) + unit + '</span>' : '');
  }

  function difference(value, average, unit) {
    if (!known(value) || !known(average)) return "-";
    const delta = value - average;
    if (unit === "mph") return signed(delta * 1.609344) + ' km/h <span class="muted">(' + signed(delta) + ' mph)</span>';
    return signed(delta) + unit;
  }

  function batting(row, season, average) {
    return '<h4>타구 속도·발사각</h4>' + BATTING_GUIDE + table([
      ["타구 수", "BBE: 결과가 발생한 타구 수. 모든 타구에 측정값이 있는 것은 아닙니다."],
      ["평균 타구 속도", "EV: km/h, 괄호 안은 mph"], ["최고 타구 속도", "시즌 중 최고 EV, km/h (mph)"],
      ["평균 발사각", "LA: 수평 기준 발사각(도)"], ["강한 타구%", "95 mph(약 152.9 km/h) 이상인 타구 비율"],
      ["배럴%", "Statcast 배럴 타구 / 타구 수. 타구 속도와 발사각의 조합으로 분류"],
      ["스위트스폿%", "발사각 8~32도인 타구 비율"],
    ], [[String(row.bbe), speed(row.exitVelocity), speed(row.maxExitVelocity), fixed(row.launchAngle) + (known(row.launchAngle) ? "°" : ""),
      fixed(row.hardHitPct) + (known(row.hardHitPct) ? "%" : ""), fixed(row.barrelPct) + (known(row.barrelPct) ? "%" : ""),
      fixed(row.sweetSpotPct) + (known(row.sweetSpotPct) ? "%" : "")]]) +
      (average ? '<h4>' + season + ' MLB 리그 평균과 비교</h4>' + table([["지표"], ["선수"], ["MLB 평균 (근사)"], ["평균 대비 차이", "선수 − 같은 시즌 MLB 평균. 양수는 더 큰 값이며 항상 더 좋다는 뜻은 아닙니다."]], [
        ["평균 타구 속도", speed(row.exitVelocity), speed(average.exitVelocity), difference(row.exitVelocity, average.exitVelocity, "mph")],
        ["평균 발사각", fixed(row.launchAngle) + (known(row.launchAngle) ? "°" : ""), fixed(average.launchAngle) + (known(average.launchAngle) ? "°" : ""), difference(row.launchAngle, average.launchAngle, "°")],
        ...[["hardHitPct", "강한 타구%"], ["barrelPct", "배럴%"], ["sweetSpotPct", "스위트스폿%"]].map(([key, label]) =>
          [label, fixed(row[key]) + (known(row[key]) ? "%" : ""), fixed(average[key]) + (known(average[key]) ? "%" : ""), difference(row[key], average[key], "%p")]),
      ]) + note('차이는 선수 − 리그 평균입니다. +는 평균보다 높고 −는 낮다는 뜻이며 발사각 등이 높다고 항상 좋은 것은 아닙니다. 선수별 집계에 타구 수(BBE)를 가중한 근사 평균입니다. 측정 누락·반올림으로 공식 공별 평균과 다를 수 있습니다. 최고 타구 속도는 평균 비교에서 제외합니다.') : '') +
      note('강한 타구는 95 mph 이상, 스위트스폿은 발사각 8~32도입니다. 배럴은 속도와 각도를 함께 보는 별도 분류입니다. ' +
        '발사각이 높을수록 항상 좋은 것은 아니며 소수 표본의 최고값도 주의해서 보세요. ' + link("statcast", season, "공식 타구 리더보드 ↗"));
  }

  function pitching(row, season, averages) {
    if (row.handSplits) {
      return '<h4>양손 투수 · 투구 손별 구종</h4>' + note('좌투·우투 표본을 따로 표시합니다. 각 사용률은 해당 손의 투구 수 기준이며 서로 합산하지 않습니다.') +
        row.handSplits.map((part) => '<h4>' + (part.hand === "L" ? "좌투" : "우투") + '</h4>' + pitching(part, season, averages)).join("");
    }
    const compare = (pitch, key, format, unit) => {
      const average = averages && averages[row.hand + ":" + pitch.type];
      return format(pitch[key]) + (averages ? '<div class="statcast-average">MLB 평균 (근사)<br>' + comparison(pitch[key], average && average[key], format, unit) + '</div>' : '');
    };
    return '<h4>구종 특징·구속</h4>' + '<p class="muted">집계 투구 수: ' + row.pitches.toLocaleString("ko-KR") + '구</p>' + PITCH_GUIDE +
      table([["구종", "Baseball Savant의 구종 분류"], ["사용률", "전체 투구 중 비율. 반올림·미분류로 합이 100%와 다를 수 있습니다."],
        ["평균 구속", "km/h, 괄호 안은 mph"], ["회전수 (rpm)", "평균 회전수(rpm). 회전 효율·구위 등급과 다릅니다."],
        ["수평 이동", "포수 시점, cm (in). 음수는 왼쪽, 양수는 오른쪽."],
        ["수직 IVB", "중력을 제외한 평균 수직 이동, cm (in). 양수는 위쪽, 음수는 아래쪽. 실제 낙폭과 다릅니다."]],
        row.arsenal.map((p) => ['<span class="pitch-key" style="--pitch-color:' + color(p.type) + '"></span>' + esc(pitchName(p.type)) + ' <span class="muted">' + esc(p.type) + '</span>',
          fixed(p.usagePct) + "%", compare(p, "velocity", speed, " mph"), compare(p, "spin", (v) => fixed(v, 0), " rpm"),
          compare(p, "horizontal", movement, " in"), compare(p, "ivb", movement, " in")])) +
      (averages ? note(season + ' MLB의 같은 구종·같은 투구 손(' + (row.hand === "L" ? "좌투" : "우투") + ')과 비교합니다. 전체 투구 수 × 반올림 사용률을 가중치로 쓴 근사 평균이며 정확한 구종별 투구 수는 아닙니다. 지표별 미측정 값은 제외합니다. 차이는 선수 − 평균이며 회전수·움직임이 크다고 항상 좋은 것은 아닙니다.') : '') + movementPlot(row.arsenal) +
      note('수평은 포수 시점의 좌우 이동, IVB는 중력을 제외한 수직 움직임입니다. 양의 IVB가 공이 실제로 위로 떠오른다는 뜻은 아닙니다. ' +
        '사용률은 반올림 값이며 미분류 구종이 빠질 수 있습니다. ' + link("pitch-arsenals", season, "공식 구종 리더보드 ↗"));
  }

  let request = 0;
  let index;
  async function render(player, season, root) {
    const version = ++request;
    const title = '<h3>Statcast · 타구와 구종</h3>';
    root.innerHTML = title + note("불러오는 중…");
    try {
      if (!index) index = loadJson("data/statcast/index.json");
      const available = await index;
      if (version !== request) return;
      if (!available.seasons.includes(season)) {
        root.innerHTML = title + note("이 시즌의 Statcast 자료는 아직 제공하지 않습니다. 제공 시즌: " + available.seasons.join(" · ") + " · MLB 정규시즌 기준");
        return;
      }
      const data = await loadJson("data/statcast/" + season + ".json");
      if (version !== request) return;
      const batter = data.batters[player.id], pitcher = data.pitchers[player.id];
      const content = (batter ? batting(batter, season, data.averages && data.averages.batters) : "") + (pitcher ? pitching(pitcher, season, data.averages && data.averages.pitchers) : "");
      root.innerHTML = title + (content || note("이 선수의 해당 시즌 Statcast 집계가 없습니다. 측정·공개 범위 밖일 수 있으며 0을 뜻하지 않습니다.")) +
        (season <= 2016 ? note("2015~2016 구속은 PITCHf/x 기반이며 이후 Statcast 측정과 장비가 다릅니다. 초기 타구·회전수 측정에는 누락이 있을 수 있습니다.") : "") +
        note('MLB 정규시즌 · 출처: Baseball Savant / Statcast (MLB) · 갱신: ' + new Date(data.updated).toLocaleString("ko-KR", {timeZone:"Asia/Seoul"}) + ' (한국 시간)');
    } catch (_) {
      if (version === request) root.innerHTML = title + note("Statcast 자료를 불러오지 못했습니다.");
    }
  }
  window.BB.statcast = { render, pitchColor: color, pitchName };
})();
