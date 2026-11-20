// 정규시즌 투구 위치 집계. 공별 원본 대신 위치 격자 빈도와 구역별 분모를 읽는다.
(function () {
  "use strict";
  const { loadJson, escapeHtml: esc } = window.BB;
  const PITCH = {FF:"포심", SI:"싱커", FC:"커터", SL:"슬라이더", ST:"스위퍼", CU:"커브", KC:"너클커브", CS:"슬로 커브",
    CH:"체인지업", FS:"스플리터", SV:"슬러브", FO:"포크볼", KN:"너클볼", SC:"스크루볼", EP:"이퍼스", UN:"미분류",
    FA:"패스트볼 (세부 미분류)", FT:"투심", GY:"자이로볼", PO:"피치아웃", IN:"고의볼",
    AB:"자동볼", AS:"자동 스트라이크", NP:"투구 없음"};
  const ROWS = ["높은 바깥", "상단", "중단", "하단", "낮은 바깥"];
  const COLS = ["왼쪽 바깥", "왼쪽", "가운데", "오른쪽", "오른쪽 바깥"];
  const ratio = (n, d) => d > 0 ? n / d : null;
  const fixed = (n, metric) => n === null ? "-" : metric === "usage" || metric === "whiff" ? (n * 100).toFixed(1) + "%" : n.toFixed(3).replace(/^0\./, ".");
  const name = (i) => ROWS[Math.floor(i / 5)] + " · " + COLS[i % 5];
  function combine(rows, pitch = "", hand = "") {
    const out = {seen:0, missing:0, outside:0, zones:Array.from({length:25}, () => Array(6).fill(0)), density:{}};
    rows.filter((r) => (!pitch || r.pitch === pitch) && (!hand || r.hand === hand)).forEach((r) => {
      for (const key of ["seen", "missing", "outside"]) out[key] += r[key];
      Object.entries(r.zones).forEach(([i, cell]) => cell.forEach((n, j) => { out.zones[Number(i)][j] += n; }));
      r.density.forEach(([i, n]) => { out.density[i] = (out.density[i] || 0) + n; });
    });
    return out;
  }
  function measure(cell, metric, total) {
    if (metric === "avg") return ratio(cell[4], cell[3]);
    if (metric === "slg") return ratio(cell[5], cell[3]);
    if (metric === "whiff") return ratio(cell[2], cell[1]);
    return ratio(cell[0], total);
  }
  const denominator = (cell, metric) => metric === "avg" || metric === "slg" ? cell[3] : metric === "whiff" ? cell[1] : cell[0];
  const enough = (cell, metric) => denominator(cell, metric) >= (metric === "usage" ? 1 : metric === "whiff" ? 20 : 10);
  const note = (text) => '<p class="page-note">' + text + '</p>';
  function plot(data, rows, pitch, hand) {
    const types = [...new Set(rows.filter((r) => (!pitch || r.pitch === pitch) && (!hand || r.hand === hand)).map((r) => r.pitch))];
    const groups = types.map((type) => ({type, ...combine(rows, type, hand)})).sort((a,b) => b.seen - a.seen);
    const entries = groups.flatMap((g) => Object.entries(g.density).map(([key,n]) => [key,n,g.type]));
    const max = Math.max(1, ...entries.map(([,n]) => n));
    const color = (type) => window.BB.statcast && window.BB.statcast.pitchColor ? window.BB.statcast.pitchColor(type) : 'var(--accent)';
    const points = entries.map(([key, n, type]) => {
      const i = Number(key), x = 40 + ((i % 20) + .5) * 14, y = 40 + (Math.floor(i / 20) + .5) * 12;
      return '<circle cx="' + x + '" cy="' + y + '" r="' + (2 + 6 * Math.sqrt(n / max)).toFixed(2) + '" fill="' + color(type) + '" opacity="' + (.25 + .7 * n / max).toFixed(2) + '"><title>' + esc(PITCH[type] || type) + ' ' + n + '구</title></circle>';
    }).join("");
    return '<figure class="zone-plot"><svg viewBox="0 0 360 325" role="img" aria-label="포수 시점 투구 위치 분포. 점은 20×20 위치 격자의 중심이며 크기는 해당 격자의 투구 수입니다.">' +
      '<path class="zone-axis" d="M40 40V280H320"/><rect class="zone-strike" x="130.42" y="100" width="99.16" height="120"/>' +
      '<g class="zone-dots">' + points + '</g>' +
      '<g class="zone-axis-label"><text x="40" y="298">-2</text><text x="110" y="298">-1</text><text x="180" y="298">0</text><text x="250" y="298">1</text><text x="320" y="298">2</text>' +
      '<text x="25" y="104">1</text><text x="25" y="224">0</text><text x="180" y="320" text-anchor="middle">수평 위치 (ft) · 포수 시점</text>' +
      '<text x="180" y="22" text-anchor="middle">높이: 타자별 존 하단 0 · 상단 1</text></g></svg>' +
      '<figcaption><ul class="zone-legend">' + groups.map((g) => '<li><span style="background:' + color(g.type) + '"></span>' + esc(PITCH[g.type] || g.type) + '</li>').join('') + '</ul>' +
      '<p class="page-note">작은 격자 안의 공을 구종별 한 점으로 합친 분포입니다. 점의 크기·진하기는 현재 조건 안의 상대 투구 수이며 공별 실제 점이나 목표 대비 제구 정확도가 아닙니다. 그림 범위 밖 ' + data.outside + '구도 아래 구역 집계에는 포함됩니다.</p></figcaption></figure>';
  }
  function heatmap(data, metric, role, selected) {
    const totals = data.zones.reduce((a, c) => a.map((n, j) => n + c[j]), Array(6).fill(0));
    const total = totals[0], average = measure(totals, metric, total);
    const rows = Array.from({length:5}, (_, r) => '<tr>' + Array.from({length:5}, (_, c) => {
      const i = r * 5 + c, cell = data.zones[i], value = measure(cell, metric, total), sample = denominator(cell, metric);
      let fill = "var(--surface-alt)";
      if (value !== null && enough(cell, metric)) {
        if (metric === "usage") fill = 'rgba(31,107,69,' + (.12 + .43 * value / Math.max(.01, ...data.zones.map((z) => measure(z, metric, total) || 0))).toFixed(2) + ')';
        else {
          const delta = (value - average) * (metric === "whiff" ? -1 : 1);
          if (Math.abs(delta) > 1e-9) fill = (delta > 0 ? 'rgba(205,67,62,' : 'rgba(54,116,190,') + (.12 + Math.min(.55, Math.abs(delta) * 1.5)).toFixed(2) + ')';
        }
      }
      const label = metric === "usage" ? cell[0] + "구" : metric === "whiff" ? sample + "스윙" : sample + "타수";
      return '<td class="' + (r > 0 && r < 4 && c > 0 && c < 4 ? 'in-zone' : 'out-zone') + '"><button type="button" style="--zone-fill:' + fill + '" data-zone-role="' + role + '" data-zone-cell="' + i + '" aria-pressed="' + (i === selected) + '" aria-label="' + name(i) + ' ' + fixed(value, metric) + ', ' + label + '">' +
        '<strong>' + fixed(value, metric) + '</strong><small>' + label + '</small></button></td>';
    }).join("") + '</tr>').join("");
    return '<div class="zone-table-wrap"><table class="zone-grid"><caption>포수 시점 · 가운데 3×3은 스트라이크존</caption><tbody>' + rows + '</tbody></table></div>' +
      note(metric === "usage" ? '숫자는 위치가 확인된 공 중 해당 구역 비율입니다. 진할수록 공이 많습니다.' :
        '색은 선택 조건의 선수 전체 기록(' + fixed(average, metric) + ') 대비입니다. 빨강은 타자에게 유리, 파랑은 불리한 결과이며 리그 평균과의 비교가 아닙니다. ' + (metric === 'whiff' ? '20스윙' : '10타수') + ' 미만은 회색으로 두고 수치·분모는 표시합니다.') +
      detail(data.zones[selected], selected, role);
  }
  function detail(cell, selected, role) {
    const pitching = role === 'pitching';
    return '<div class="zone-detail" role="status"><strong>' + name(selected) + '</strong>' +
      '<p>' + (pitching ? '상대 ' : '') + cell[3] + '타수 / ' + cell[4] + (pitching ? '피안타' : '안타') +
      ' · ' + (pitching ? '피안타율 ' : '타율 ') + fixed(measure(cell, 'avg'), 'avg') +
      ' · ' + (pitching ? '피장타율 ' : '장타율 ') + fixed(measure(cell, 'slg'), 'slg') + '</p>' +
      '<p>' + cell[0] + '구 · ' + cell[1] + '스윙 / 헛스윙 ' + cell[2] + '회 · ' +
      cell[5] + (pitching ? '허용 루타' : '루타') + ' · 헛스윙률 ' + fixed(measure(cell, 'whiff'), 'whiff') + '</p></div>';
  }
  function options(rows, key, value, labels) {
    return '<option value="">전체</option>' + [...new Set(rows.map((r) => r[key]))].sort().map((v) => '<option value="' + esc(v) + '"' + (v === value ? ' selected' : '') + '>' + esc(labels[v] || v) + '</option>').join("");
  }
  let request = 0;
  async function render(player, season, root) {
    const version = ++request;
    const title = '<h3>투구 위치 분포·핫콜드존</h3>';
    root.innerHTML = title + note('위치 집계를 불러오는 중...');
    try {
      const available = await loadJson('data/zones/index.json', {cache:'no-cache'});
      if (version !== request) return;
      if (!available.seasons.includes(season)) {
        root.innerHTML = title + note('이 시즌의 위치 집계는 아직 제공하지 않습니다. 제공 시즌: ' + available.seasons.join(', '));
        return;
      }
      const index = await loadJson('data/zones/' + season + '/index.json', {cache:'no-cache'});
      if (version !== request) return;
      if (index.season !== season || index.gameType !== 'R') throw new Error('시즌 불일치');
      const key = String(Number(player.id) % 100).padStart(2, '0');
      const filename = Array.isArray(index.buckets) ? (index.buckets.includes(key) ? key + '.json' : null) : index.buckets[key];
      if (filename && !/^\d{2}(\.[a-f0-9]{12})?\.json$/.test(filename)) throw new Error('위치 파일 이름 오류');
      const bucket = filename ? await loadJson('data/zones/' + season + '/' + filename) : {season, players:{}};
      if (version !== request) return;
      if (bucket.season !== season) throw new Error('시즌 불일치');
      const mine = bucket.players[player.id] || {};
      const state = {pitching:{pitch:'', hand:'', metric:'usage', cell:12}, batting:{pitch:'', hand:'', metric:'avg', cell:12}};
      const draw = () => {
        const groups = (player.pos === 'P' ? ['pitching','batting'] : ['batting','pitching']).filter((role) => mine[role] && mine[role].length);
        root.innerHTML = title + note(season + ' 정규시즌 · ' + esc(index.through) + ' 경기일까지의 위치 집계') + (groups.map((role) => {
          const s = state[role], rows = mine[role], data = combine(rows, s.pitch, s.hand), pitching = role === 'pitching';
          const hands = pitching ? {L:'좌타자',R:'우타자',U:'타석 미확인'} : {L:'좌투수',R:'우투수',U:'투구 손 미확인'};
          const report = !data.seen ? note('선택한 조건의 투구 기록이 없습니다.') : data.seen === data.missing ?
            note('이 조건에는 위치·존 높이가 확인된 공이 없어 위치 분포·구역별 성적을 제공하지 않습니다.') :
            (pitching ? plot(data, rows, s.pitch, s.hand) : '') + heatmap(data, s.metric, role, s.cell);
          return '<section class="zone-section"><h4>' + (pitching ? '투수 · 투구 위치 분포' : '타자 · 핫콜드존') + '</h4><div class="zone-controls">' +
            '<label class="field"><span>구종</span><select data-zone-role="' + role + '" data-zone-filter="pitch">' + options(rows, 'pitch', s.pitch, PITCH) + '</select></label>' +
            '<label class="field"><span>' + (pitching ? '상대 타석' : '상대 투구 손') + '</span><select data-zone-role="' + role + '" data-zone-filter="hand">' + options(rows, 'hand', s.hand, hands) + '</select></label>' +
            '</div>' + (pitching ? '' : note('구역의 숫자와 색상은 타율입니다. 구역을 선택하면 아래에서 타수·안타수·장타율·헛스윙률을 확인할 수 있습니다.')) +
            note('전체 ' + data.seen + '구 · 위치 확인 ' + (data.seen - data.missing) + '구 · 위치·존 높이 미제공 ' + data.missing + '구 제외') +
            report + '</section>';
        }).join('') || note('이 선수의 해당 시즌 투구 위치 집계가 없습니다.')) +
          note('타율·장타율은 타석을 끝낸 공의 위치로 분류합니다(타수·안타·루타 기준). 헛스윙률은 헛스윙/스윙입니다. 바깥 테두리 칸은 그 방향의 먼 공도 포함하며 실제 존 판정과 같지 않습니다. 서로 다른 타자의 존 높이를 하단 0·상단 1로 맞췄습니다.') +
          note((season >= 2026 ? '2026년부터 좌표는 홈플레이트 중앙·ABS 존 기준입니다.' : '2025년까지 좌표는 홈플레이트 앞면·원본 존 높이 기준입니다.') + ' 다른 기준의 시즌을 합쳐 비교하지 않습니다.') +
          (season < 2015 ? note('이 시즌은 Statcast 도입 전 PITCHf/x 자료입니다. 초기 측정 누락이 있으며 위치가 확인된 공만 구역별 기록에 포함합니다.') : '') +
          note('MLB 정규시즌 · ' + esc(index.through) + ' 경기일까지 · 갱신: ' + new Date(index.updated).toLocaleString('ko-KR', {timeZone:'Asia/Seoul'}) +
            ' (한국 시간) · <a href="https://baseballsavant.mlb.com/csv-docs" target="_blank" rel="noopener">Baseball Savant 위치·구역 정의</a>');
      };
      root.onchange = (event) => {
        const input = event.target.closest('[data-zone-filter]');
        if (!input) return;
        const role = input.dataset.zoneRole, filter = input.dataset.zoneFilter, value = input.value;
        state[role][filter] = value;
        draw();
        root.querySelector('[data-zone-role="' + role + '"][data-zone-filter="' + filter + '"]').focus({preventScroll:true});
      };
      root.onclick = (event) => {
        const button = event.target.closest('[data-zone-cell]');
        if (!button) return;
        const role = button.dataset.zoneRole;
        state[role].cell = Number(button.dataset.zoneCell);
        draw();
        root.querySelector('[data-zone-role="' + role + '"][data-zone-cell="' + state[role].cell + '"]').focus({preventScroll:true});
      };
      draw();
    } catch (_) {
      if (version === request) root.innerHTML = title + '<p role="status">투구 위치 집계를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.</p>';
    }
  }
  window.BB.zones = { render, combine, measure, enough };
})();
