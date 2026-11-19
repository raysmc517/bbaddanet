// 관심 항목은 이 브라우저에만 저장한다. 서버·계정 동기화는 하지 않는다.
(function () {
  "use strict";
  const KEY = "bbaddanet.favorites.v1";
  const { escapeHtml } = window.BB;
  function read() {
    try {
      const data = JSON.parse(localStorage.getItem(KEY) || "{}");
      return { players: valid(data.players), teams: valid(data.teams) };
    } catch (_) { return { players: [], teams: [] }; }
  }
  function valid(items) {
    return Array.isArray(items) ? items.filter((item) => item && /^\d+$/.test(String(item.id)) && typeof item.name === "string") : [];
  }
  function mount(kind, id, name, host) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "link-button favorite-button";
    const update = () => {
      const selected = read()[kind].some((item) => String(item.id) === String(id));
      button.textContent = (selected ? "★ 관심 " : "☆ 관심 ") + (kind === "players" ? "선수" : "팀");
      button.setAttribute("aria-pressed", String(selected));
      button.title = "이 브라우저에 저장됩니다";
    };
    button.addEventListener("click", () => {
      const data = read();
      const found = data[kind].some((item) => String(item.id) === String(id));
      data[kind] = data[kind].filter((item) => String(item.id) !== String(id));
      if (!found) data[kind].push({ id: Number(id), name });
      try { localStorage.setItem(KEY, JSON.stringify(data)); update(); }
      catch (_) { button.textContent = "저장할 수 없습니다 (브라우저 저장 설정 확인)"; }
    });
    window.addEventListener("storage", update);
    host.appendChild(button);
    update();
  }
  window.BB.favorites = { read, mount };
  const root = document.getElementById("favorites");
  if (root) {
    const render = () => {
      const data = read();
      root.innerHTML = ["players", "teams"].map((kind) => '<section class="career-section"><h2>관심 ' +
        (kind === "players" ? "선수" : "팀") + '</h2>' + (data[kind].length ? '<ul class="favorite-list">' +
        data[kind].map((item) => '<li><a href="' + (kind === "players" ? "player" : "team") + '.html?id=' + item.id + '">' +
          escapeHtml(item.name) + '</a> <button class="link-button" data-kind="' + kind + '" data-id="' + item.id + '">해제</button></li>').join("") +
        '</ul>' : '<p class="muted">선수·구단 페이지의 ☆ 버튼으로 추가하세요.</p>') + '</section>').join("");
    };
    root.addEventListener("click", (event) => {
      const button = event.target.closest("[data-kind]");
      if (!button) return;
      const data = read();
      data[button.dataset.kind] = data[button.dataset.kind].filter((item) => String(item.id) !== button.dataset.id);
      try { localStorage.setItem(KEY, JSON.stringify(data)); render(); }
      catch (_) { button.textContent = "저장 실패"; }
    });
    window.addEventListener("storage", render);
    render();
  }
})();
