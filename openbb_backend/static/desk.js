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

  var form = document.querySelector("[data-ops-config]");
  if (form) {
    var status = document.getElementById("ops-config-status");
    var saveBtn = form.querySelector(".ops-save");

    function setStatus(text, kind) {
      if (!status) {
        return;
      }
      status.textContent = text || "";
      status.classList.remove("is-ok", "is-err");
      if (kind) {
        status.classList.add(kind);
      }
    }

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var modeEl = document.getElementById("ops-ai-mode");
      var modelEl = document.getElementById("ops-ai-model");
      var multiEl = document.getElementById("ops-multi-role");
      var regimeEl = document.getElementById("ops-regime");
      var promoteEl = document.getElementById("ops-promote");
      var feeEl = document.getElementById("ops-fee-preset");
      var maxEl = document.getElementById("ops-max-pos");
      var holdEl = document.getElementById("ops-min-hold");
      var body = {
        ai_mode: modeEl ? modeEl.value : "off",
        ai_model: modelEl ? String(modelEl.value || "").trim() : "",
        ai_multi_role: multiEl ? !!multiEl.checked : true,
        regime_gate: regimeEl ? !!regimeEl.checked : true,
        promote_experiment_strategy: promoteEl ? !!promoteEl.checked : false,
        fee_preset: feeEl ? feeEl.value : "revolut_standard",
        max_positions: maxEl ? parseInt(maxEl.value, 10) : 5,
        min_hold_hours: holdEl ? parseFloat(holdEl.value) : 24,
      };
      if (saveBtn) {
        saveBtn.disabled = true;
      }
      setStatus("Saving…", null);

      fetch("/desk/api/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(body),
      })
        .then(function (res) {
          return res.json().then(function (data) {
            return { ok: res.ok, status: res.status, data: data };
          });
        })
        .then(function (result) {
          if (!result.ok) {
            var detail =
              (result.data && (result.data.detail || result.data.note)) ||
              "Save failed (" + result.status + ")";
            setStatus(String(detail), "is-err");
            return;
          }
          setStatus(
            "Saved · AI " +
              result.data.ai_mode +
              " · applies on next trader loop",
            "is-ok"
          );
        })
        .catch(function () {
          setStatus("Network error — is openbb-backend up?", "is-err");
        })
        .finally(function () {
          if (saveBtn) {
            saveBtn.disabled = false;
          }
        });
    });
  }

  var el = document.getElementById("refresh-eta");
  if (!el) {
    return;
  }

  // Paper desk: marks/scans move slowly — default 5 minutes (was 60s).
  var raw = el.getAttribute("data-seconds");
  var total = parseInt(raw, 10);
  if (!isFinite(total) || total < 30 || total > 3600) {
    total = 300;
  }

  var left = total;

  function formatLeft(sec) {
    if (sec >= 60) {
      var m = Math.floor(sec / 60);
      var s = sec % 60;
      return m + "m " + (s < 10 ? "0" : "") + s + "s";
    }
    return sec + "s";
  }

  function paint() {
    el.textContent = formatLeft(left);
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
