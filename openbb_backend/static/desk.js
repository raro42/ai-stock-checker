/*! paper desk — countdown + a11y helpers (no deps) */
(function () {
  "use strict";

  var skip = document.querySelector("a.skip");
  if (skip) {
    skip.addEventListener("click", function () {
      var main = document.getElementById("main");
      if (main) {
        window.setTimeout(function () {
          main.focus();
        }, 0);
      }
    });
  }

  var el = document.getElementById("refresh-eta");
  if (!el) {
    return;
  }

  var raw = el.getAttribute("data-seconds");
  var total = parseInt(raw, 10);
  if (!isFinite(total) || total < 5 || total > 3600) {
    total = 60;
  }

  var left = total;

  function paint() {
    el.textContent = String(left);
  }

  function reloadSafe() {
    var path = window.location.pathname || "/desk";
    if (path.indexOf("/desk") !== 0) {
      path = "/desk";
    }
    window.location.assign(path);
  }

  paint();

  window.setInterval(function () {
    if (document.hidden) {
      return;
    }
    left -= 1;
    if (left <= 0) {
      reloadSafe();
      return;
    }
    paint();
  }, 1000);
})();
