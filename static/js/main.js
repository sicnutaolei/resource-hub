/* 站点交互：下拉菜单、复制提取码、收藏切换 */
(function () {
  "use strict";

  function csrfToken() {
    var input = document.querySelector("input[name=csrfmiddlewaretoken]");
    if (input) return input.value;
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  /* ---------------- 下拉菜单 ---------------- */
  document.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-dropdown-trigger]");
    var openMenus = document.querySelectorAll(".dropdown.is-open");

    if (trigger) {
      var dropdown = trigger.closest(".dropdown");
      var wasOpen = dropdown.classList.contains("is-open");
      openMenus.forEach(function (item) {
        item.classList.remove("is-open");
      });
      if (!wasOpen) dropdown.classList.add("is-open");
      event.preventDefault();
      return;
    }

    if (!event.target.closest(".dropdown__menu")) {
      openMenus.forEach(function (item) {
        item.classList.remove("is-open");
      });
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    document.querySelectorAll(".dropdown.is-open").forEach(function (item) {
      item.classList.remove("is-open");
    });
  });

  /* ---------------- 复制提取码 / 链接 ---------------- */
  document.addEventListener("click", async function (event) {
    var button = event.target.closest("[data-copy]");
    if (!button) return;

    var text = button.getAttribute("data-copy") || "";
    var original = button.textContent;

    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        var helper = document.createElement("textarea");
        helper.value = text;
        helper.style.position = "fixed";
        helper.style.opacity = "0";
        document.body.appendChild(helper);
        helper.select();
        document.execCommand("copy");
        document.body.removeChild(helper);
      }
      button.textContent = "已复制";
    } catch (error) {
      button.textContent = "复制失败";
    }

    window.setTimeout(function () {
      button.textContent = original;
    }, 1600);
  });

  /* ---------------- 收藏切换 ---------------- */
  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-favorite-url]");
    if (!button) return;

    var url = button.getAttribute("data-favorite-url");
    var countLabel = document.querySelector("[data-favorite-count]");

    button.disabled = true;

    fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken(),
        "X-Requested-With": "XMLHttpRequest"
      }
    })
      .then(function (response) {
        if (response.status === 403) {
          window.location.href = "/accounts/login/";
          return null;
        }
        return response.json();
      })
      .then(function (data) {
        if (!data) return;
        button.classList.toggle("is-on", data.favorited);
        button.setAttribute("aria-pressed", data.favorited ? "true" : "false");
        var label = button.querySelector("[data-favorite-label]");
        if (label) label.textContent = data.favorited ? "已收藏" : "收藏";
        if (countLabel) countLabel.textContent = data.total;
      })
      .catch(function () {
        window.alert("操作失败，请稍后重试。");
      })
      .finally(function () {
        button.disabled = false;
      });
  });

  /* ---------------- 危险操作二次确认 ---------------- */
  document.addEventListener("submit", function (event) {
    var form = event.target.closest("[data-confirm]");
    if (!form) return;
    if (!window.confirm(form.getAttribute("data-confirm"))) {
      event.preventDefault();
    }
  });
})();
