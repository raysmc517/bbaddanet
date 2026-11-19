(function () {
  "use strict";
  const labels = {trade:"트레이드", sign:"FA 계약", minor_sign:"마이너리그 FA 계약", claim:"웨이버 클레임"};
  window.BB.arrivalInfo = (club, last, entry, teamAbbr, entryLabels) => {
    if (last && last[2] === club.id && labels[last[1]]) {
      const from = last[3] && teamAbbr(last[3]);
      return {text: labels[last[1]] + " (" + last[0] + (from ? ", " + from + "에서" : "") + ")", source: last[4] || null, history: last[1] !== "minor_sign"};
    }
    if (entry && entry.team === club.name) {
      return {text: entry.type === "draft" ? "드래프트 지명 (" + entry.year + "년)" : entryLabels[entry.type] || "지명 없이 계약"};
    }
    return {text:"입단 경로 미확인"};
  };
})();
