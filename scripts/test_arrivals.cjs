const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const box = {window:{BB:{}}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../js/arrivals.js'),'utf8'),box);
const describe = (last, entry) => box.window.BB.arrivalInfo({id:119,name:'Los Angeles Dodgers'},last,entry,()=> 'BOS',{international:'국제 아마추어 계약'});
test('Muncy minor-league entry has official date and distinct contract type', () => {
  const info = describe(['2017-04-28','minor_sign',119,null,'https://statsapi.mlb.com/api/v1/transactions?playerId=571970']);
  assert.equal(info.text,'마이너리그 FA 계약 (2017-04-28)');
  assert.equal(info.history,false);
  assert.match(info.source,/571970/);
});
test('unknown entry and previous club cannot imply a pre-2009 move', () => {
  for (const last of [undefined,['2020-01-01','sign',111,null]]) {
    const info = describe(last,{type:'draft',year:2012,team:'Athletics'});
    assert.equal(info.text,'입단 경로 미확인');
    assert.doesNotMatch(info.text,/2009/);
  }
});
test('verified draft and trade paths remain available', () => {
  assert.equal(describe(null,{type:'draft',year:2012,team:'Los Angeles Dodgers'}).text,'드래프트 지명 (2012년)');
  assert.equal(describe(['2020-02-10','trade',119,111]).text,'트레이드 (2020-02-10, BOS에서)');
});
