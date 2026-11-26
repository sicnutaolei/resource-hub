/* 后台交互：移动端侧栏、删除确认、表单集加行、封面上传预览、设置预览 */
(function () {
  "use strict";

  var sidebar = document.getElementById("mg-sidebar");
  var backdrop = document.querySelector("[data-mg-backdrop]");
  var menuButton = document.querySelector("[data-mg-menu]");

  function setMenu(open) {
    if (!sidebar) return;
    sidebar.classList.toggle("is-open", open);
    if (backdrop) backdrop.hidden = !open;
    if (menuButton) menuButton.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.style.overflow = open ? "hidden" : "";
  }

  if (menuButton) {
    menuButton.addEventListener("click", function () {
      setMenu(!sidebar.classList.contains("is-open"));
    });
  }
  if (backdrop) {
    backdrop.addEventListener("click", function () {
      setMenu(false);
    });
  }
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") setMenu(false);
  });

  document.addEventListener("submit", function (event) {
    var form = event.target.closest("[data-confirm]");
    if (!form) return;
    if (!window.confirm(form.getAttribute("data-confirm"))) {
      event.preventDefault();
    }
  });

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-add-formset]");
    if (!button) return;

    var prefix = button.getAttribute("data-add-formset");
    var container = document.querySelector('[data-formset="' + prefix + '"]');
    if (!container) return;

    var total = container.querySelector('input[name="' + prefix + '-TOTAL_FORMS"]');
    var template = container.querySelector("template[data-empty-form]");
    var rows = container.querySelector(".formset__rows");
    if (!total || !template || !rows) return;

    var index = parseInt(total.value, 10) || 0;
    var wrapper = document.createElement("div");
    wrapper.innerHTML = template.innerHTML.replace(/__prefix__/g, String(index));
    if (wrapper.firstElementChild) rows.appendChild(wrapper.firstElementChild);
    total.value = index + 1;
  });

  var coverInput = document.querySelector('input[type="file"][name="cover_image"]');
  var coverPreview = document.querySelector("[data-cover-preview]");
  if (coverInput && coverPreview) {
    coverInput.addEventListener("change", function () {
      var file = coverInput.files && coverInput.files[0];
      if (!file) return;
      var url = URL.createObjectURL(file);
      var image = coverPreview.querySelector("img");
      if (!image) {
        coverPreview.innerHTML = "";
        image = document.createElement("img");
        image.alt = "封面预览";
        coverPreview.appendChild(image);
      }
      image.src = url;
      image.onload = function () {
        URL.revokeObjectURL(url);
      };
    });
  }

  var settingsForm = document.querySelector("[data-settings-form]");
  if (settingsForm) {
    var nameInput = settingsForm.querySelector('input[name="site_name"]');
    var sloganInput = settingsForm.querySelector('input[name="homepage_slogan"]');
    var namePreview = document.querySelector("[data-preview-name]");
    var sloganPreview = document.querySelector("[data-preview-slogan]");

    function syncPreview() {
      if (nameInput && namePreview) {
        namePreview.textContent = nameInput.value || "站点名称";
      }
      if (sloganInput && sloganPreview) {
        sloganPreview.textContent = sloganInput.value || "首页 Slogan";
      }
    }

    if (nameInput) nameInput.addEventListener("input", syncPreview);
    if (sloganInput) sloganInput.addEventListener("input", syncPreview);
  }
})();