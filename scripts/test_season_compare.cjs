const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const read = (f) => fs.readFileSync(path.join(__dirname, '../js', f), 'utf8');
function client() {
  const context = {window:{}, fetch:async () => ({ok:false,status:404}), document:{querySelectorAll:() => [], body:{}, getElementById:() => null},
    MutationObserver:class { observe() {} }, requestAnimationFrame:() => {}, URLSearchParams};
  for (const f of ['common.js', 'compare.js', 'season-compare.js']) vm.runInNewContext(read(f), context);
  return context.window.BB.seasonCompare;
}
const plain = (v) => JSON.parse(JSON.stringify(v));
const keys = (list) => plain(list).map((e) => e.season + ' ' + e.level);

// 2024 AA → 2025 AA·AAA 승격 → 2026 MLB 데뷔한 선수
const prospect = {
  id:1, pos:'SS',
  batting:[
    {league:'mlb', season:2026, PA:120, OPS:.650},
    {league:'milb', level:'AAA', season:2026, PA:300, OPS:.900},
    {league:'milb', level:'AAA', season:2025, PA:150, OPS:.820},
    {league:'milb', level:'AA', season:2025, PA:350, OPS:.880},
    {league:'milb', level:'AA', season:2024, team:'A', PA:100, H:20},
    {league:'milb', level:'AA', season:2024, team:'B', PA:200, H:50},
    {league:'kbo', season:2023, PA:500},                 // MLB·마이너 밖 기록은 넣지 않는다
  ],
  pitching:[],
};

test('entries are season·level units, newest first and higher level first', () => {
  const v = client();
  assert.deepEqual(keys(v.entries(prospect)), ['2026 MLB', '2026 AAA', '2025 AAA', '2025 AA', '2024 AA']);
});

test('default pair prefers analysed MLB season, then the same or nearest level in the latest earlier season', () => {
  const v = client();
  const list = v.entries(prospect);
  const after = v.defaultAfter(list, 2026);
  assert.deepEqual(keys([after]), ['2026 MLB']);
  // 2025에 MLB 기록이 없으므로 가장 가까운 레벨(AAA). 타석이 더 많은 AA보다 레벨 차이를 먼저 본다.
  assert.deepEqual(keys([v.defaultBefore(list, after)]), ['2025 AAA']);
  const aaa = list.find((e) => e.season === 2026 && e.level === 'AAA');
  assert.deepEqual(keys([v.defaultBefore(list, aaa)]), ['2025 AAA']);
});

test('minor-only player defaults to the level with the most playing time in the latest season', () => {
  const v = client();
  const minors = {...prospect, batting: prospect.batting.filter((r) => r.league !== 'mlb')};
  const list = v.entries(minors);
  assert.deepEqual(keys([v.defaultAfter(list, null)]), ['2026 AAA']);
  assert.equal(v.available(minors), true);
  assert.equal(v.available({batting:[{league:'milb', level:'AA', season:2026, PA:10}], pitching:[]}), false);
});

test('a single-season promotion compares the two levels of the same season', () => {
  const v = client();
  const p = {batting:[{league:'milb', level:'AA', season:2026, PA:200}, {league:'milb', level:'AAA', season:2026, PA:100}], pitching:[]};
  const list = v.entries(p);
  const after = v.defaultAfter(list, null);
  assert.deepEqual(keys([after, v.defaultBefore(list, after)]), ['2026 AA', '2026 AAA']);
});

test('rows of one season·level from several teams use the shared aggregate', () => {
  const v = client();
  const aggregate = (group, rows) => ({PA: rows.reduce((a, r) => a + r.PA, 0), H: rows.reduce((a, r) => a + r.H, 0)});
  assert.deepEqual(plain(v.entryRow(prospect, 'batting', {season:2024, level:'AA'}, aggregate)), {PA:300, H:70});
  assert.equal(v.entryRow(prospect, 'batting', {season:2025, level:'AAA'}, aggregate).OPS, .820);
  assert.equal(v.entryRow(prospect, 'pitching', {season:2025, level:'AAA'}, aggregate), null);
});

test('nearest level wins over playing time; ties go to more playing time', () => {
  const v = client();
  const season = (rows) => ({batting: rows.map(([level, s, PA]) => ({league:'milb', level, season:s, PA})), pitching:[]});
  const pick = (p) => { const list = v.entries(p); return keys([v.defaultBefore(list, list.find((e) => e.level === 'AA'))])[0]; };
  // 레벨 순서 MLB·AAA·AA·High-A·Single-A·Rookie: AA와의 거리는 Single-A 2, Rookie 3 → 타석이 많아도 Rookie가 아니다
  assert.equal(pick(season([['AA',2026,200], ['Single-A',2025,80], ['Rookie',2025,120]])), '2025 Single-A');
  // AAA와 High-A는 모두 거리 1 → 더 많이 뛴 High-A
  assert.equal(pick(season([['AA',2026,200], ['AAA',2025,30], ['High-A',2025,90]])), '2025 High-A');
});

test('MLB-only defaults on with two MLB seasons and falls back to defaults when a pick leaves the list', () => {
  const v = client();
  assert.equal(v.defaultMlbOnly(prospect), false);           // MLB 기록 1시즌 → 마이너와 비교
  const veteran = {batting:[...prospect.batting, {league:'mlb', season:2025, PA:400, OPS:.780}], pitching:[]};
  assert.equal(v.defaultMlbOnly(veteran), true);
  const all = v.entries(veteran), mlb = v.mlbList(all);
  assert.deepEqual(keys(mlb), ['2026 MLB', '2025 MLB']);
  // 마이너 기록(2025 AAA)을 고른 상태에서 MLB만 켜면 MLB 기본 선택으로 바뀐다
  const [a, b] = v.pick(mlb, {season:2026, level:'MLB'}, {season:2025, level:'AAA'}, 2026);
  assert.deepEqual(keys([a, b]), ['2026 MLB', '2025 MLB']);
  // 끄면 고른 기록을 그대로 둔다
  const [c, d] = v.pick(all, a, b, 2026);
  assert.deepEqual(keys([c, d]), ['2026 MLB', '2025 MLB']);
});
