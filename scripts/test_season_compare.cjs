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
const player = {
  id:1, pos:'RF',
  batting:[
    {league:'mlb', season:2026, PA:300, OPS:.700},
    {league:'milb', season:2025, PA:200, OPS:.900},   // 마이너 기록은 비교 시즌이 아니다
    {league:'mlb', season:2023, team:'AAA', PA:100, H:30},
    {league:'mlb', season:2023, team:'BBB', PA:150, H:40},
    {league:'mlb', season:2024, PA:500, OPS:.850},
  ],
  pitching:[{league:'mlb', season:2022, outs:3}],
};

test('earlier seasons are MLB only, newest first, and skip missing seasons', () => {
  const v = client();
  assert.deepEqual([...v.earlierSeasons(player, 2026)], [2024, 2023, 2022]);
  assert.deepEqual([...v.earlierSeasons(player, 2022)], []);
});

test('season row uses the single row or the shared aggregate for multi-team seasons', () => {
  const v = client();
  const aggregate = (group, rows) => ({PA: rows.reduce((a, r) => a + r.PA, 0), H: rows.reduce((a, r) => a + r.H, 0)});
  assert.equal(v.seasonRow(player, 'batting', 2024, aggregate).OPS, .850);
  assert.deepEqual({...v.seasonRow(player, 'batting', 2023, aggregate)}, {PA:250, H:70});
  assert.equal(v.seasonRow(player, 'batting', 2025, aggregate), null);
});
