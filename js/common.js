// 빠따넷 공통 코드: 표시 형식, 열 정의, 데이터 불러오기
// 리더보드와 선수 페이지가 함께 쓴다.

window.BB = (function () {
  "use strict";

  // ---------- 표시 형식 ----------
  const fmt = {
    int: (v) => String(v),
    rate: (v) => v.toFixed(3).replace(/^(-?)0\./, "$1."), // .300
    dec2: (v) => v.toFixed(2),
    pct: (v) => (v * 100).toFixed(1) + "%",
    ip: (outs) => Math.floor(outs / 3) + "." + (outs % 3),
    dec1: (v) => v.toFixed(1),
  };

  // ---------- 열 정의 ----------
  // asc: true면 낮을수록 좋은 지표 (처음 눌렀을 때 오름차순)
  const col = (key, label, desc, format, asc) => ({ key, label, desc, format: format || fmt.int, asc: !!asc });

  const C = {
    G: col("G", "G", "경기"),
    PA: col("PA", "PA", "타석"),
    AB: col("AB", "AB", "타수"),
    R: col("R", "R", "득점"),
    H: col("H", "H", "안타"),
    D2: col("2B", "2B", "2루타"),
    D3: col("3B", "3B", "3루타"),
    HR: col("HR", "HR", "홈런"),
    RBI: col("RBI", "RBI", "타점"),
    SB: col("SB", "SB", "도루"),
    CS: col("CS", "CS", "도루 실패"),
    BB: col("BB", "BB", "볼넷"),
    SO: col("SO", "SO", "삼진"),
    AVG: col("AVG", "AVG", "타율", fmt.rate),
    OBP: col("OBP", "OBP", "출루율", fmt.rate),
    SLG: col("SLG", "SLG", "장타율", fmt.rate),
    OPS: col("OPS", "OPS", "출루율 + 장타율", fmt.rate),
    ISO: col("ISO", "ISO", "순수 장타력 (장타율 - 타율)", fmt.rate),
    BABIP: col("BABIP", "BABIP", "인플레이 타구 타율", fmt.rate),
    BBp: col("BBp", "BB%", "타석당 볼넷 비율", fmt.pct),
    Kp: col("Kp", "K%", "타석당 삼진 비율", fmt.pct, true),
    wOBA: col("wOBA", "wOBA", "가중 출루율: 출루 사건마다 득점 가치만큼 가중치를 준 출루율", fmt.rate),
    wRCp: col("wRCp", "wRC+", "조정 득점 창출력: 리그 평균이 100, 구장 보정 포함"),
    sWAR: col("sWAR", "간이WAR", "간이 WAR: 자체 계산, 수비 기여 제외", fmt.dec1),
    WAR: col("WAR", "WAR", "MLB 공식 WAR (수비 포함)", fmt.dec1),
    // 투수
    GS: col("GS", "GS", "선발 등판"),
    W: col("W", "W", "승"),
    L: col("L", "L", "패"),
    SV: col("SV", "SV", "세이브"),
    HLD: col("HLD", "HLD", "홀드"),
    IP: col("outs", "IP", "투구 이닝", fmt.ip),
    pH: col("H", "H", "피안타", fmt.int, true),
    pR: col("R", "R", "실점", fmt.int, true),
    ER: col("ER", "ER", "자책점", fmt.int, true),
    pHR: col("HR", "HR", "피홈런", fmt.int, true),
    pBB: col("BB", "BB", "볼넷 허용", fmt.int, true),
    pSO: col("SO", "SO", "탈삼진"),
    ERA: col("ERA", "ERA", "평균자책점", fmt.dec2, true),
    WHIP: col("WHIP", "WHIP", "이닝당 출루 허용", fmt.dec2, true),
    K9: col("K9", "K/9", "9이닝당 탈삼진", fmt.dec2),
    BB9: col("BB9", "BB/9", "9이닝당 볼넷", fmt.dec2, true),
    HR9: col("HR9", "HR/9", "9이닝당 피홈런", fmt.dec2, true),
    pKp: col("Kp", "K%", "상대 타자당 탈삼진 비율", fmt.pct),
    pBBp: col("BBp", "BB%", "상대 타자당 볼넷 비율", fmt.pct, true),
    KBBp: col("KBBp", "K-BB%", "탈삼진 비율 - 볼넷 비율", fmt.pct),
    pBABIP: col("BABIP", "BABIP", "인플레이 타구 피안타율", fmt.rate, true),
    FIP: col("FIP", "FIP", "수비 무관 평균자책점: 홈런, 볼넷, 삼진만으로 계산", fmt.dec2, true),
    ERAm: col("ERAm", "ERA-", "조정 평균자책점: 리그 평균이 100, 낮을수록 좋음, 구장 보정 포함", fmt.int, true),
    FIPm: col("FIPm", "FIP-", "조정 FIP: 리그 평균이 100, 낮을수록 좋음, 구장 보정 포함", fmt.int, true),
    LOBp: col("LOBp", "LOB%", "잔루 처리율: 내보낸 주자를 득점시키지 않은 비율", fmt.pct),
  };

  const COLUMNS = {
    batting: {
      basic: [C.G, C.PA, C.AB, C.R, C.H, C.D2, C.D3, C.HR, C.RBI, C.SB, C.CS, C.BB, C.SO, C.AVG, C.OBP, C.SLG, C.OPS],
      saber: [C.PA, C.AVG, C.OBP, C.SLG, C.OPS, C.ISO, C.BABIP, C.BBp, C.Kp, C.wOBA, C.wRCp, C.sWAR, C.WAR],
    },
    pitching: {
      basic: [C.G, C.GS, C.W, C.L, C.SV, C.HLD, C.IP, C.pH, C.pR, C.ER, C.pHR, C.pBB, C.pSO, C.ERA, C.WHIP],
      saber: [C.IP, C.ERA, C.FIP, C.ERAm, C.FIPm, C.WHIP, C.K9, C.BB9, C.HR9, C.pKp, C.pBBp, C.KBBp, C.pBABIP, C.LOBp, C.sWAR, C.WAR],
    },
  };

  const isStarter = (p) => p.G > 0 && p.GS * 2 >= p.G;

  const escapeHtml = (text) =>
    String(text).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));

  const cache = new Map();
  async function loadJson(url) {
    if (!cache.has(url)) {
      const res = await fetch(url);
      if (!res.ok) throw new Error(url + " (" + res.status + ")");
      cache.set(url, await res.json());
    }
    return cache.get(url);
  }

  // 값이 없으면 "-"로 표시
  const cell = (column, row) => {
    const value = row[column.key];
    return value === null || value === undefined ? "-" : column.format(value);
  };

  // 데이터에 값이 하나도 없는 열은 뺀다 (예: 공식 WAR은 MLB에만 있다)
  const visibleColumns = (columns, rows) =>
    columns.filter((column) => rows.some((row) => row[column.key] !== null && row[column.key] !== undefined));

  // ---------- 구단·구장 표시 ----------
  const has = (v) => v !== null && v !== undefined && v !== "";
  const TURF = { Grass: "천연잔디", "Artificial Turf": "인조잔디" };
  const ROOF = { Open: "개방형", Retractable: "개폐식", Dome: "돔" };
  const venue = {
    turf: (v) => (has(v) ? TURF[v] || v : "-"),
    roof: (v) => (has(v) ? ROOF[v] || v : "-"),
    capacity: (v) => (has(v) ? v.toLocaleString("ko-KR") + "명" : "-"),
    meters: (feet) => Math.round(feet * 0.3048),
    place: (v) => [v.city, v.state, v.country && v.country !== "USA" ? v.country : ""].filter(has).join(", ") || "-",
    pf: (v) => (has(v) ? v.toFixed(3) : "-"),
  };

  return { fmt, COLUMNS, isStarter, escapeHtml, loadJson, cell, visibleColumns, venue, has };
})();
