const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const sandbox = { window: { BB: {} } };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../js/contracts.js"), "utf8"), sandbox);
const rows = (record) => JSON.parse(JSON.stringify(sandbox.window.BB.contracts.salaryRows(record)));

test("salary periods expand in latest-season-first order", () => {
  const input = { salaries: [{ from: 2024, to: 2025, baseUSD: 10 }, { from: 2026, to: 2026, baseUSD: 20 }] };
  assert.deepEqual(rows(input).map((r) => [r.season, r.baseUSD]), [[2026, 20], [2025, 10], [2024, 10]]);
  assert.equal(input.salaries.length, 2);
});

test("unknown deferral stays unknown; confirmed zero remains zero", () => {
  const result = rows({ salaries: [{ from: 2025, to: 2025, baseUSD: 0, deferredUSD: 0 }, { from: 2026, to: 2026, baseUSD: 20 }] });
  assert.equal(result[0].deferredUSD, null);
  assert.equal(result[0].nonDeferredUSD, null);
  assert.equal(result[1].baseUSD, 0);
  assert.equal(result[1].nonDeferredUSD, 0);
});

test("non-deferred salary excludes deferral without adding signing bonus", () => {
  const result = rows({ signingBonusUSD: 50, salaries: [{ from: 2026, to: 2026, baseUSD: 70, deferredUSD: 68 }] });
  assert.equal(result[0].nonDeferredUSD, 2);
  assert.equal(result[0].baseUSD, 70);
  assert.deepEqual(rows({}), []);
});
