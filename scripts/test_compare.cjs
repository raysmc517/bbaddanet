const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const common = fs.readFileSync(path.join(__dirname, '../js/common.js'), 'utf8');
const source = fs.readFileSync(path.join(__dirname, '../js/compare.js'), 'utf8');
function client() {
  const context = {window:{}, fetch:async () => ({ok:false,status:404}), document:{querySelectorAll:() => [], body:{}},
    MutationObserver:class { observe() {} }, requestAnimationFrame:() => {}, URLSearchParams};
  vm.runInNewContext(common, context);
  vm.runInNewContext(source, context);
  return context.window.BB.compare;
}
const find = (c, g, k) => c.METRICS[g].find((m) => m.key === k);

test('worse direction is reversed for lower-is-better stats', () => {
  const c = client();
  const pair = {before:{OPS:.800, ERA:3.00, Kp:.20}, after:{OPS:.700, ERA:4.50, Kp:.25}};
  assert.ok(Math.abs(c.delta(pair,'OPS') - (-.1)) < 1e-9);
  assert.ok(c.gain(pair, find(c,'batting','OPS')) < 0);   // OPS 하락 = 나빠짐
  assert.ok(c.gain(pair, find(c,'pitching','ERA')) < 0);  // ERA 상승 = 나빠짐
  assert.ok(c.gain(pair, find(c,'batting','Kp')) < 0);    // 타자 K% 상승 = 나빠짐
  assert.ok(c.gain(pair, find(c,'pitching','Kp')) > 0);   // 투수 K% 상승 = 좋아짐
});

test('missing values are not treated as zero', () => {
  const c = client();
  const war = find(c,'batting','WAR');
  const pair = {before:{WAR:null}, after:{WAR:2.0}};
  assert.equal(c.delta(pair,'WAR'), null);
  assert.equal(c.gain(pair, war), null);
  assert.equal(c.signed(war, null), '-');
});

test('signed changes use each stat format and percentage points', () => {
  const c = client();
  assert.equal(c.signed(find(c,'batting','OPS'), -.0325), '−.033');
  assert.equal(c.signed(find(c,'batting','Kp'), .034), '+3.4%p');
  assert.equal(c.signed(find(c,'pitching','ERA'), 1.234), '+1.23');
  assert.equal(c.signed(find(c,'batting','wRCp'), -12), '−12');
  assert.equal(c.signed(find(c,'batting','OPS'), 0), '±.000');
});
