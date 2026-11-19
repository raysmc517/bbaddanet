// 계약 발표 기준 연봉. 기본 연봉에 계약금·바이아웃을 섞거나 미확인 이연액을 0으로 채우지 않는다.
window.BB.contracts = (function () {
  "use strict";
  const known = (value) => typeof value === "number" && Number.isFinite(value);
  function salaryRows(contract) {
    const rows = [];
    (contract.salaries || []).forEach((period) => {
      for (let season = period.from; season <= period.to; season += 1) {
        const base = known(period.baseUSD) ? period.baseUSD : null;
        const deferred = known(period.deferredUSD) ? period.deferredUSD : null;
        rows.push({ season, baseUSD: base, deferredUSD: deferred,
          nonDeferredUSD: base !== null && deferred !== null ? base - deferred : null });
      }
    });
    return rows.sort((a, b) => b.season - a.season);
  }
  return { salaryRows };
})();
