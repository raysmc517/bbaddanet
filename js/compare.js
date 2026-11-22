// 빠따넷 시즌 간 변화 계산: 같은 선수의 두 시즌 기록 값끼리 빼기만 한다. 새 지표를 만들지 않는다.
// 선수 상세의 "지난 시즌과 비교" 팝업(js/season-compare.js)이 쓴다.
(function () {
  "use strict";
  const { fmt } = window.BB;

  // asc: 낮을수록 좋은 지표. 부진(나빠짐)은 좋은 방향의 반대로 움직인 것이다.
  const m = (key, label, desc, format, asc) => ({ key, label, desc, format, asc: !!asc });
  const METRICS = {
    batting: [
      m("OPS", "OPS", "출루율 + 장타율", fmt.rate), m("wOBA", "wOBA", "가중 출루율", fmt.rate),
      m("wRCp", "wRC+", "조정 득점 창출력 (리그 평균 100)", fmt.int), m("AVG", "AVG", "타율", fmt.rate),
      m("OBP", "OBP", "출루율", fmt.rate), m("SLG", "SLG", "장타율", fmt.rate), m("ISO", "ISO", "순수 장타력", fmt.rate),
      m("BBp", "BB%", "타석당 볼넷 비율", fmt.pct), m("Kp", "K%", "타석당 삼진 비율", fmt.pct, true),
      m("BABIP", "BABIP", "인플레이 타구 타율", fmt.rate), m("HR", "HR", "홈런", fmt.int),
      m("sWAR", "간이WAR", "자체 계산, 수비 제외", fmt.dec1), m("WAR", "WAR", "MLB 공식 WAR", fmt.dec1),
    ],
    pitching: [
      m("ERA", "ERA", "평균자책점", fmt.dec2, true), m("FIP", "FIP", "수비 무관 평균자책점", fmt.dec2, true),
      m("ERAm", "ERA-", "조정 평균자책점 (리그 평균 100, 낮을수록 좋음)", fmt.int, true),
      m("FIPm", "FIP-", "조정 FIP (리그 평균 100, 낮을수록 좋음)", fmt.int, true),
      m("WHIP", "WHIP", "이닝당 출루 허용", fmt.dec2, true), m("Kp", "K%", "상대 타자당 탈삼진 비율", fmt.pct),
      m("BBp", "BB%", "상대 타자당 볼넷 비율", fmt.pct, true), m("KBBp", "K-BB%", "탈삼진 비율 - 볼넷 비율", fmt.pct),
      m("HR9", "HR/9", "9이닝당 피홈런", fmt.dec2, true), m("BABIP", "BABIP", "인플레이 타구 피안타율", fmt.rate, true),
      m("LOBp", "LOB%", "잔루 처리율", fmt.pct), m("sWAR", "간이WAR", "자체 계산", fmt.dec1), m("WAR", "WAR", "MLB 공식 WAR", fmt.dec1),
    ],
  };
  const known = (v) => typeof v === "number" && Number.isFinite(v);

  // 변화량 = 기준 시즌 − 비교 시즌. 어느 한쪽이 없으면 null(0이 아님).
  const delta = (pair, key) => known(pair.before[key]) && known(pair.after[key]) ? pair.after[key] - pair.before[key] : null;
  // 좋은 방향으로 움직인 양. 음수면 나빠진 것이다.
  const gain = (pair, column) => { const d = delta(pair, column.key); return d === null ? null : column.asc ? -d : d; };
  // 지표 형식대로 부호를 붙인다. 비율 지표는 퍼센트포인트(%p).
  function signed(column, d) {
    if (d === null) return "-";
    const sign = d > 0 ? "+" : d < 0 ? "−" : "±";
    if (column.format === fmt.pct) return sign + Math.abs(d * 100).toFixed(1) + "%p";
    return sign + column.format(Math.abs(d));
  }

  window.BB.compare = { METRICS, delta, gain, signed };
})();
