/* 前台最小交互：危险操作二次确认 */
(function () {
  "use strict";

  document.addEventListener("submit", function (event) {
    var form = event.target.closest("[data-confirm]");
    if (!form) return;
    if (!window.confirm(form.getAttribute("data-confirm"))) {
      event.preventDefault();
    }
  });
})();