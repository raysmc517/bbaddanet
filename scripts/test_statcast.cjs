const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../js/statcast.js"), "utf8");
const escapeHtml = (v) => String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
function client(loadJson) {
  const box = { window: { BB: { loadJson, escapeHtml } } };
  vm.runInNewContext(source, box);
  return box.window.BB.statcast;
}
function seasonData() {
  return { season: 2025, updated: "2026-11-19T14:00:00Z", batters: {
    1: { bbe: 10, exitVelocity: 100, maxExitVelocity: null, launchAngle: -2, hardHitPct: 0, barrelPct: 0, sweetSpotPct: null },
  }, pitchers: { 1: { pitches: 100, arsenal: [{ type: "FF", usagePct: 100, velocity: 100, spin: null, horizontal: -10, ivb: 15 }] } } };
}

test("two-way player shows converted units and preserves missing versus zero", async () => {
  const view = client(async (url) => url.includes("index") ? { seasons: [2025] } : seasonData());
  const root = {};
  await view.render({ id: 1 }, 2025, root);
  assert.match(root.innerHTML, /160\.9/);
  assert.match(root.innerHTML, /-25\.4/);
  assert.match(root.innerHTML, /\+38\.1/);
  assert.match(root.innerHTML, /-2\.0°/);
  assert.match(root.innerHTML, /0\.0%/);
  assert.match(root.innerHTML, /<td>-<\/td>/);
  assert.match(root.innerHTML, /포심/);
  assert.match(root.innerHTML, /타구 속도·발사각/);
  assert.match(root.innerHTML, /<svg/);
});

test("unsupported season and missing player do not pretend to have zero measurements", async () => {
  const view = client(async (url) => url.includes("index") ? { seasons: [2025] } : seasonData());
  const root = {};
  await view.render({ id: 1 }, 2023, root);
  assert.match(root.innerHTML, /아직 제공하지/);
  await view.render({ id: 2 }, 2025, root);
  assert.match(root.innerHTML, /집계가 없습니다/);
  assert.doesNotMatch(root.innerHTML, /<table/);
});

test("late response cannot replace the newly selected season", async () => {
  let releaseOld, started;
  const waiting = new Promise((resolve) => { started = resolve; });
  const old = new Promise((resolve) => { releaseOld = resolve; });
  const view = client(async (url) => {
    if (url.includes("index")) return { seasons: [2025, 2024] };
    if (url.includes("2024")) { started(); return old; }
    return seasonData();
  });
  const root = {};
  const first = view.render({ id: 1 }, 2024, root);
  await waiting;
  await view.render({ id: 1 }, 2025, root);
  const latest = root.innerHTML;
  releaseOld({ updated: "2026-11-19T14:00:00Z", batters: {}, pitchers: {} });
  await first;
  assert.equal(root.innerHTML, latest);
});

test("2015 switch pitcher displays separate hand samples and tracking-era note", async () => {
  const data = seasonData();
  const pitcher = data.pitchers[1];
  data.pitchers[1] = { hand: "S", pitches: 200, arsenal: [], handSplits: [
    { ...pitcher, hand: "L" }, { ...pitcher, hand: "R" },
  ] };
  const view = client(async (url) => url.includes("index") ? { seasons: [2015] } : data);
  const root = {};
  await view.render({ id: 1 }, 2015, root);
  assert.match(root.innerHTML, /좌투/);
  assert.match(root.innerHTML, /우투/);
  assert.match(root.innerHTML, /서로 합산하지/);
  assert.match(root.innerHTML, /PITCHf\/x/);
  assert.equal((root.innerHTML.match(/<svg/g) || []).length, 2);
});

test("season averages show signed differences and retain missing metrics", async () => {
  const data = seasonData();
  data.pitchers[1].hand = "R";
  data.averages = { batters: { exitVelocity: 90, launchAngle: 10, hardHitPct: 40, barrelPct: 8 },
    pitchers: { "R:FF": { velocity: 95, spin: 2200, horizontal: -5, ivb: null } } };
  const view = client(async (url) => url.includes("index") ? { seasons: [2025] } : data);
  const root = {};
  await view.render({ id: 1 }, 2025, root);
  assert.match(root.innerHTML, /MLB 평균 \(근사\)/);
  assert.match(root.innerHTML, /평균 대비 차이/);
  assert.match(root.innerHTML, /\+16\.1 km\/h/);
  assert.match(root.innerHTML, /<td>-40\.0%p<\/td>/);
  assert.match(root.innerHTML, /차이 \+5\.0 mph/);
  assert.match(root.innerHTML, /차이 -5\.0 in/);
  assert.match(root.innerHTML, /미제공/);
  assert.doesNotMatch(root.innerHTML, /차이 .*NaN/);
});
