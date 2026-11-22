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
    {season:2026,players:{1:{pitching:[sample(),sample('FA'),sample('PO')],batting:[sample()]}}});
  const root = {};
  await v.render({id:1},2026,root);
  assert.match(root.innerHTML,/20×20/);
  assert.match(root.innerHTML,/타자 · 핫콜드존/);
  assert.match(root.innerHTML,/투수 · 투구 위치 분포/);
  assert.match(root.innerHTML,/패스트볼 \(세부 미분류\)/);
  assert.match(root.innerHTML,/피치아웃/);
  assert.match(root.innerHTML,/0\.000|\.000/);
  assert.match(root.innerHTML,/5타수/);
  assert.match(root.innerHTML,/구역의 숫자와 색상은 타율/);
  assert.doesNotMatch(root.innerHTML,/data-zone-filter="metric"/);
  assert.match(root.innerHTML,/헛스윙률 20.0%/);
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

test('mutable manifests revalidate HTTP cache while hashed bucket uses its content version', async () => {
  const calls = [];
  const v = client(async (url, options) => {
    calls.push([url,options && options.cache]);
    return url === 'data/zones/index.json' ? {seasons:[2026]} : url.endsWith('index.json') ?
      {season:2026,gameType:'R',buckets:{'01':'01.0123456789ab.json'},through:'2026-09-27',updated:'2026-11-20T00:00:00Z'} :
      {season:2026,players:{}};
  });
  await v.render({id:1},2026,{});
  assert.deepEqual(calls,[['data/zones/index.json','no-cache'],['data/zones/2026/index.json','no-cache'],
    ['data/zones/2026/01.0123456789ab.json',undefined]]);
});

test('selected zone preserves counts and shows AVG and SLG for each role, including zero AB', async () => {
  const row = sample();
  row.zones[12] = [40,25,4,13,6,10];
  const v = client(async (url) => url === 'data/zones/index.json' ? {seasons:[2026]} : url.endsWith('index.json') ?
    {season:2026,gameType:'R',buckets:['01'],through:'2026-09-27',updated:'2026-11-20T00:00:00Z'} :
    {season:2026,players:{1:{pitching:[row],batting:[row]}}});
  const root = {querySelector:() => ({focus:() => {}})};
  await v.render({id:1},2026,root);
  assert.match(root.innerHTML,/13타수 \/ 6안타 · 타율 .462 · 장타율 .769/);
  assert.match(root.innerHTML,/상대 13타수 \/ 6피안타 · 피안타율 .462 · 피장타율 .769/);
  assert.match(root.innerHTML,/10허용 루타/);
  root.onclick({target:{closest:() => ({dataset:{zoneRole:'batting',zoneCell:'0'}})}});
  assert.match(root.innerHTML,/0타수 \/ 0안타 · 타율 - · 장타율 -/);
  assert.doesNotMatch(root.innerHTML,/NaN|Infinity/);
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

test('entirely unmeasured player records do not appear as zero-hit zone statistics', async () => {
  const row = {...sample(),missing:22,zones:{},density:[]};
  const v = client(async (url) => url === 'data/zones/index.json' ? {seasons:[2008]} : url.endsWith('index.json') ?
    {season:2008,gameType:'R',buckets:['01'],through:'2008-09-30',updated:'2026-11-20T00:00:00Z'} :
    {season:2008,players:{1:{batting:[row],pitching:[row]}}});
  const root = {};
  await v.render({id:1},2008,root);
  assert.match(root.innerHTML,/위치·존 높이가 확인된 공이 없어/);
  assert.match(root.innerHTML,/PITCHf\/x/);
  assert.doesNotMatch(root.innerHTML,/class="zone-grid"|class="zone-plot"|0타수 \/ 0안타/);
});

test('pitcher zones show usage, pitch count and opponent AVG colored only with enough at-bats', async () => {
  const row = sample();
  row.zones[12] = [40,25,4,20,2,3];   // 20타수 2피안타 → 전체보다 낮음(파랑)
  row.zones[6] = [10,5,1,12,6,8];     // 12타수 6피안타 → 전체보다 높음(빨강)
  row.zones[0] = [5,2,0,3,3,3];       // 3타수 → 표본 미달(회색)
  const v = client(async (url) => url === 'data/zones/index.json' ? {seasons:[2026]} : url.endsWith('index.json') ?
    {season:2026,gameType:'R',buckets:['01'],through:'2026-09-27',updated:'2026-11-20T00:00:00Z'} :
    {season:2026,players:{1:{pitching:[row]}}});
  const root = {};
  await v.render({id:1,pos:'P'},2026,root);
  const cell = (i) => root.innerHTML.match(new RegExp('<button[^>]*data-zone-cell="' + i + '"[^>]*>(.*?)</button>'))[0];
  assert.match(cell(12),/<strong>72\.7%<\/strong><small>40구<\/small><small><span class="zone-avg-label">피안타율 <\/span>\.100<\/small>/);
  assert.match(cell(12),/rgba\(54,116,190/);
  assert.match(cell(6),/피안타율 <\/span>\.500/);
  assert.match(cell(6),/rgba\(205,67,62/);
  assert.match(cell(0),/var\(--surface-alt\)/);
  assert.match(cell(1),/피안타율 <\/span>-/);
  assert.match(root.innerHTML,/전체 피안타율\(\.314\) 대비/);
  assert.doesNotMatch(root.innerHTML,/NaN|Infinity/);
});
