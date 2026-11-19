const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../js/zones.js'), 'utf8');
function client(loadJson = async () => { throw new Error('missing'); }) {
  const context = {window:{BB:{loadJson, escapeHtml:(v) => String(v)}}};
  vm.runInNewContext(source, context);
  return context.window.BB.zones;
}
function sample(pitch = 'FF', hand = 'R') {
  const zones = Array.from({length:25}, () => [0,0,0,0,0,0]);
  zones[12] = [20,10,2,5,0,0];
  return {pitch,hand,seen:22,missing:2,outside:0,zones,density:[[210,20]]};
}
test('AVG, SLG and whiff use their own denominators; actual zero differs from missing', () => {
  const v = client();
  assert.equal(v.measure([20,10,2,5,0,0],'avg',20), 0);
  assert.equal(v.measure([20,10,2,5,2,5],'slg',20), 1);
  assert.equal(v.measure([20,10,2,5,0,0],'whiff',20), .2);
  assert.equal(v.measure([0,0,0,0,0,0],'avg',0), null);
  assert.equal(v.enough([100,10,5,9,2,2],'avg'), false);
});
test('pitch and opponent hand filters never add overlapping totals', () => {
  const v = client();
  const data = [sample(),sample('SL'),sample('FF','L')];
  assert.equal(v.combine(data).seen, 66);
  assert.equal(v.combine(data,'FF','R').seen, 22);
  assert.equal(v.combine(data,'FF','R').zones[12][0], 20);
  assert.equal(v.combine(data,'CH').seen, 0);
});
test('two-way data renders plot, heatmap and accessible per-cell sample counts', async () => {
  const v = client(async (url) => url === 'data/zones/index.json' ? {seasons:[2026]} : url.endsWith('index.json') ? {season:2026,gameType:'R',buckets:{'01':'01.0123456789ab.json'},through:'2026-09-30',updated:'2026-11-20T00:00:00Z'} :
    {season:2026,players:{1:{pitching:[sample()],batting:[sample()]}}});
  const root = {};
  await v.render({id:1},2026,root);
  assert.match(root.innerHTML,/20×20/);
  assert.match(root.innerHTML,/타자 · 핫콜드존/);
  assert.match(root.innerHTML,/투수 · 투구 위치 분포/);
  assert.match(root.innerHTML,/0\.000|\.000/);
  assert.match(root.innerHTML,/5타수/);
  assert.match(root.innerHTML,/위치·존 높이 미제공 2구/);
});
test('unsupported season uses availability index without fetching nonexistent data', async () => {
  const calls = [];
  const v = client(async (url) => {calls.push(url); return {seasons:[2026]};});
  const root = {};
  await v.render({id:1},2025,root);
  assert.deepEqual(calls,['data/zones/index.json']);
  assert.match(root.innerHTML,/제공 시즌: 2026/);
  assert.doesNotMatch(root.innerHTML,/<table/);
});
test('late season response cannot replace the new season or turn unavailable into zeros', async () => {
  let release;
  const old = new Promise((resolve) => {release=resolve;});
  const v = client(async (url) => url === 'data/zones/index.json' ? {seasons:[2025,2024]} : url.includes('2025') ? old : Promise.reject(new Error('missing')));
  const root = {};
  const first = v.render({id:1},2025,root);
  await v.render({id:1},2024,root);
  const current = root.innerHTML;
  release({season:2025,gameType:'R',buckets:[]});
  await first;
  assert.equal(root.innerHTML,current);
  assert.match(root.innerHTML,/불러오지 못/);
  assert.doesNotMatch(root.innerHTML,/<table/);
});
