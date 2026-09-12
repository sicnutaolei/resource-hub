/* 主题切换：auto（跟随系统）/ light / dark 三态循环，存 localStorage */
(function () {
  var STORAGE_KEY = "rh-theme";
  var ORDER = ["auto", "light", "dark"];
  var LABEL = { auto: "跟随系统", light: "浅色", dark: "深色" };

  function readPreference() {
    try {
      var value = window.localStorage.getItem(STORAGE_KEY);
      return ORDER.indexOf(value) >= 0 ? value : "auto";
    } catch (error) {
      return "auto";
    }
  }

  function apply(preference) {
    var root = document.documentElement;
    if (preference === "auto") {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", preference);
    }
    document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
      button.setAttribute("title", "当前主题：" + LABEL[preference] + "（点击切换）");
      button.setAttribute("aria-label", "当前主题：" + LABEL[preference] + "，点击切换");
      var slot = button.querySelector("[data-theme-icon]");
      if (slot) {
        slot.textContent = preference === "auto" ? "◐" : preference === "light" ? "☀" : "☾";
      }
    });
  }

  function save(preference) {
    try {
      window.localStorage.setItem(STORAGE_KEY, preference);
    } catch (error) {
      /* 隐私模式下忽略 */
    }
  }

  // 页面加载前尽早应用，避免闪白
  apply(readPreference());

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-theme-toggle]");
    if (!button) return;
    var current = readPreference();
    var next = ORDER[(ORDER.indexOf(current) + 1) % ORDER.length];
    save(next);
    apply(next);
  });

  window.matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", function () {
    if (readPreference() === "auto") apply("auto");
  });
})();
