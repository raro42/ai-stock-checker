/*! paper desk charts — local D3 v7 (no CDN) */
(function () {
  "use strict";

  var root = document.getElementById("charts-root");
  if (!root || typeof d3 === "undefined") {
    return;
  }

  var COLORS = [
    "#d4a574",
    "#7dcea0",
    "#6b9acf",
    "#e07a5f",
    "#c4b5a0",
    "#5dade2",
    "#af7ac5",
    "#58d68d",
  ];

  function cssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name);
    return (v && v.trim()) || fallback;
  }

  function showError(msg) {
    root.innerHTML = "";
    var p = document.createElement("p");
    p.className = "empty";
    p.textContent = msg;
    root.appendChild(p);
  }

  function section(title, id) {
    var wrap = document.createElement("section");
    wrap.className = "block chart-block";
    wrap.setAttribute("aria-labelledby", id);
    var h = document.createElement("h2");
    h.id = id;
    h.textContent = title;
    var mount = document.createElement("div");
    mount.className = "chart-mount";
    wrap.appendChild(h);
    wrap.appendChild(mount);
    root.appendChild(wrap);
    return mount;
  }

  function drawEquity(mount, series) {
    if (!series || series.length < 2) {
      mount.innerHTML = "<p class='empty'>Not enough fills yet for an equity path.</p>";
      return;
    }
    var data = series.map(function (d) {
      return {
        t: new Date(d.t),
        equity: +d.equity,
        label: d.label || "",
      };
    });

    var width = mount.clientWidth || 640;
    var height = 280;
    var margin = { top: 16, right: 16, bottom: 32, left: 56 };

    var svg = d3
      .select(mount)
      .append("svg")
      .attr("viewBox", "0 0 " + width + " " + height)
      .attr("role", "img")
      .attr("aria-label", "Paper book equity over time");

    var defs = svg.append("defs");
    var grad = defs
      .append("linearGradient")
      .attr("id", "eqFill")
      .attr("x1", "0")
      .attr("x2", "0")
      .attr("y1", "0")
      .attr("y2", "1");
    grad.append("stop").attr("offset", "0%").attr("stop-color", "#d4a574").attr("stop-opacity", 0.35);
    grad.append("stop").attr("offset", "100%").attr("stop-color", "#d4a574").attr("stop-opacity", 0.02);

    var x = d3
      .scaleTime()
      .domain(d3.extent(data, function (d) { return d.t; }))
      .range([margin.left, width - margin.right]);
    var y = d3
      .scaleLinear()
      .domain([
        d3.min(data, function (d) { return d.equity; }) * 0.995,
        d3.max(data, function (d) { return d.equity; }) * 1.005,
      ])
      .nice()
      .range([height - margin.bottom, margin.top]);

    var area = d3
      .area()
      .x(function (d) { return x(d.t); })
      .y0(y.range()[0])
      .y1(function (d) { return y(d.equity); })
      .curve(d3.curveMonotoneX);
    var line = d3
      .line()
      .x(function (d) { return x(d.t); })
      .y(function (d) { return y(d.equity); })
      .curve(d3.curveMonotoneX);

    svg
      .append("g")
      .attr("class", "axis")
      .attr("transform", "translate(0," + (height - margin.bottom) + ")")
      .call(d3.axisBottom(x).ticks(6).tickSizeOuter(0));
    svg
      .append("g")
      .attr("class", "axis")
      .attr("transform", "translate(" + margin.left + ",0)")
      .call(
        d3
          .axisLeft(y)
          .ticks(5)
          .tickFormat(function (v) {
            return "€" + d3.format(",.0f")(v);
          })
          .tickSizeOuter(0)
      );

    svg.append("path").datum(data).attr("fill", "url(#eqFill)").attr("d", area);
    svg
      .append("path")
      .datum(data)
      .attr("fill", "none")
      .attr("stroke", "#d4a574")
      .attr("stroke-width", 2.2)
      .attr("d", line);

    svg
      .selectAll("circle.pt")
      .data(data.slice(1))
      .join("circle")
      .attr("class", "pt")
      .attr("cx", function (d) { return x(d.t); })
      .attr("cy", function (d) { return y(d.equity); })
      .attr("r", 3.5)
      .attr("fill", "#e8efe6")
      .attr("stroke", "#d4a574")
      .attr("stroke-width", 1.5)
      .append("title")
      .text(function (d) {
        return d.label + " · €" + d3.format(",.2f")(d.equity);
      });
  }

  function drawAllocation(mount, rows) {
    var data = (rows || []).filter(function (d) { return +d.value > 0; });
    if (!data.length) {
      mount.innerHTML = "<p class='empty'>No allocation to chart.</p>";
      return;
    }
    var width = mount.clientWidth || 640;
    var height = 300;
    var radius = Math.min(width, height) / 2 - 8;
    var svg = d3
      .select(mount)
      .append("svg")
      .attr("viewBox", "0 0 " + width + " " + height)
      .attr("role", "img")
      .attr("aria-label", "Portfolio allocation");

    var g = svg
      .append("g")
      .attr("transform", "translate(" + width * 0.38 + "," + height / 2 + ")");

    var pie = d3
      .pie()
      .value(function (d) { return d.value; })
      .sort(null);
    var arc = d3.arc().innerRadius(radius * 0.58).outerRadius(radius * 0.92);
    var arcHover = d3.arc().innerRadius(radius * 0.55).outerRadius(radius * 0.96);

    var color = d3
      .scaleOrdinal()
      .domain(data.map(function (d) { return d.symbol; }))
      .range(COLORS);

    var paths = g
      .selectAll("path")
      .data(pie(data))
      .join("path")
      .attr("fill", function (d) { return color(d.data.symbol); })
      .attr("stroke", cssVar("--bg0", "#0c1410"))
      .attr("stroke-width", 2)
      .attr("d", arc)
      .style("cursor", "pointer");

    paths.append("title").text(function (d) {
      var n = d.data.name ? " — " + d.data.name : "";
      return d.data.symbol + n + ": €" + d3.format(",.2f")(d.data.value) + " (" + d.data.weight_pct + "%)";
    });

    paths
      .on("mouseenter", function (_e, d) {
        d3.select(this).transition().duration(160).attr("d", arcHover);
      })
      .on("mouseleave", function () {
        d3.select(this).transition().duration(160).attr("d", arc);
      });

    g.append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "-0.2em")
      .attr("fill", cssVar("--ink", "#e8efe6"))
      .attr("font-family", "Georgia, serif")
      .attr("font-size", 18)
      .text("Book");
    g.append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "1.2em")
      .attr("fill", cssVar("--muted", "#9aafa0"))
      .attr("font-size", 12)
      .text(data.length + " slices");

    var legend = svg
      .append("g")
      .attr("transform", "translate(" + (width * 0.62) + ",24)");
    var items = legend
      .selectAll("g")
      .data(data)
      .join("g")
      .attr("transform", function (_d, i) {
        return "translate(0," + i * 22 + ")";
      });
    items
      .append("rect")
      .attr("width", 10)
      .attr("height", 10)
      .attr("rx", 2)
      .attr("fill", function (d) { return color(d.symbol); });
    items
      .append("text")
      .attr("x", 16)
      .attr("y", 9)
      .attr("fill", cssVar("--ink", "#e8efe6"))
      .attr("font-size", 12)
      .text(function (d) {
        var label = d.name ? d.symbol + " · " + d.name : d.symbol;
        if (label.length > 28) label = label.slice(0, 27) + "…";
        return label + "  " + d.weight_pct + "%";
      });
  }

  function pctLabel(value) {
    var n = +value;
    if (!isFinite(n)) return "—";
    return (n >= 0 ? "+" : "") + n.toFixed(2) + "%";
  }

  function formatDay(d) {
    try {
      return d3.timeFormat("%Y-%m-%d")(d);
    } catch (e) {
      return String(d);
    }
  }

  function appendHtmlLegend(mount, panels, color) {
    var list = document.createElement("ul");
    list.className = "chart-legend";
    list.setAttribute("aria-label", "Series legend — hover to highlight");
    panels.forEach(function (p) {
      var li = document.createElement("li");
      li.className = "chart-legend-item";
      li.dataset.symbol = p.symbol;
      li.tabIndex = 0;
      li.setAttribute("role", "button");
      li.setAttribute(
        "aria-label",
        "Highlight " + p.symbol + ", " + pctLabel(p.change_pct)
      );
      var swatch = document.createElement("span");
      swatch.className = "chart-legend-swatch";
      swatch.style.background = color(p.symbol);
      swatch.setAttribute("aria-hidden", "true");
      var label = document.createElement("span");
      label.className = "chart-legend-label";
      var nameBit = p.name && p.name !== p.symbol ? " — " + p.name : "";
      label.textContent = p.symbol + " " + pctLabel(p.change_pct);
      label.title = p.symbol + nameBit + " · " + pctLabel(p.change_pct);
      li.appendChild(swatch);
      li.appendChild(label);
      list.appendChild(li);
    });
    mount.appendChild(list);
    return list;
  }

  function nearestPoint(points, date) {
    if (!points || !points.length) return null;
    var bisect = d3.bisector(function (d) {
      return new Date(d.t);
    }).left;
    var i = bisect(points, date, 1);
    var a = points[i - 1];
    var b = points[i];
    if (!a) return b || null;
    if (!b) return a;
    return date - new Date(a.t) > new Date(b.t) - date ? b : a;
  }

  function drawPrices(mount, panels) {
    if (!panels || !panels.length) {
      mount.innerHTML =
        "<p class='empty'>No price history yet (check network / DESK_CHART_LIVE).</p>";
      return;
    }
    mount.classList.add("chart-mount--interactive");
    var width = mount.clientWidth || 640;
    var height = 300;
    var margin = { top: 12, right: 16, bottom: 32, left: 44 };

    var color = d3
      .scaleOrdinal()
      .domain(panels.map(function (p) {
        return p.symbol;
      }))
      .range(COLORS);

    var bySymbol = {};
    panels.forEach(function (p) {
      bySymbol[p.symbol] = p;
    });

    var legend = appendHtmlLegend(mount, panels, color);

    var tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.hidden = true;
    tip.setAttribute("role", "status");
    tip.setAttribute("aria-live", "polite");
    mount.appendChild(tip);

    var svg = d3
      .select(mount)
      .append("svg")
      .attr("viewBox", "0 0 " + width + " " + height)
      .attr("role", "img")
      .attr(
        "aria-label",
        "Relative price performance. Hover a legend item or the chart to highlight a series."
      );

    var all = [];
    panels.forEach(function (p) {
      p.points.forEach(function (pt) {
        all.push({ t: new Date(pt.t), rebased: +pt.rebased, symbol: p.symbol });
      });
    });

    var x = d3
      .scaleTime()
      .domain(d3.extent(all, function (d) {
        return d.t;
      }))
      .range([margin.left, width - margin.right]);
    var y = d3
      .scaleLinear()
      .domain(
        d3.extent(all, function (d) {
          return d.rebased;
        })
      )
      .nice()
      .range([height - margin.bottom, margin.top]);

    svg
      .append("g")
      .attr("class", "axis")
      .attr("transform", "translate(0," + (height - margin.bottom) + ")")
      .call(d3.axisBottom(x).ticks(6).tickSizeOuter(0));
    svg
      .append("g")
      .attr("class", "axis")
      .attr("transform", "translate(" + margin.left + ",0)")
      .call(
        d3
          .axisLeft(y)
          .ticks(5)
          .tickFormat(function (v) {
            return d3.format(".0f")(v);
          })
          .tickSizeOuter(0)
      );

    svg
      .append("line")
      .attr("class", "baseline-100")
      .attr("x1", margin.left)
      .attr("x2", width - margin.right)
      .attr("y1", y(100))
      .attr("y2", y(100))
      .attr("stroke", "rgba(232,239,230,0.2)")
      .attr("stroke-dasharray", "4 4");

    var line = d3
      .line()
      .x(function (d) {
        return x(new Date(d.t));
      })
      .y(function (d) {
        return y(d.rebased);
      })
      .curve(d3.curveMonotoneX);

    var seriesG = svg.append("g").attr("class", "price-series");
    panels.forEach(function (p) {
      seriesG
        .append("path")
        .datum(p.points)
        .attr("class", "price-line")
        .attr("data-symbol", p.symbol)
        .attr("fill", "none")
        .attr("stroke", color(p.symbol))
        .attr("stroke-width", 2)
        .attr("stroke-linejoin", "round")
        .attr("stroke-linecap", "round")
        .attr("d", line);

      var last = p.points[p.points.length - 1];
      if (last) {
        seriesG
          .append("circle")
          .attr("class", "price-end")
          .attr("data-symbol", p.symbol)
          .attr("cx", x(new Date(last.t)))
          .attr("cy", y(last.rebased))
          .attr("r", 3)
          .attr("fill", color(p.symbol));
      }
    });

    var focus = svg.append("g").attr("class", "price-focus").style("display", "none");
    focus
      .append("line")
      .attr("class", "focus-x")
      .attr("y1", margin.top)
      .attr("y2", height - margin.bottom)
      .attr("stroke", "rgba(232,239,230,0.35)")
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "3 3");
    var focusDot = focus
      .append("circle")
      .attr("r", 5)
      .attr("fill", cssVar("--ink", "#e8efe6"))
      .attr("stroke-width", 2);

    var locked = null; // legend / hit lock
    var reduceMotion =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function applyHighlight(symbol) {
      seriesG.selectAll(".price-line").each(function () {
        var s = this.getAttribute("data-symbol");
        var on = !symbol || s === symbol;
        d3.select(this)
          .attr("stroke-opacity", on ? 1 : 0.14)
          .attr("stroke-width", symbol && s === symbol ? 3.2 : 2);
        if (symbol && s === symbol) {
          this.parentNode.appendChild(this);
        }
      });
      seriesG.selectAll(".price-end").each(function () {
        var s = this.getAttribute("data-symbol");
        var on = !symbol || s === symbol;
        d3.select(this)
          .attr("fill-opacity", on ? 1 : 0.14)
          .attr("r", symbol && s === symbol ? 4.5 : 3);
        if (symbol && s === symbol) {
          this.parentNode.appendChild(this);
        }
      });
      Array.prototype.forEach.call(legend.querySelectorAll(".chart-legend-item"), function (li) {
        var on = !symbol || li.dataset.symbol === symbol;
        li.classList.toggle("is-active", !!symbol && li.dataset.symbol === symbol);
        li.classList.toggle("is-dimmed", !!symbol && !on);
      });
    }

    function hideFocus() {
      focus.style("display", "none");
      tip.hidden = true;
    }

    function showFocus(panel, pt) {
      if (!panel || !pt) {
        hideFocus();
        return;
      }
      var tx = x(new Date(pt.t));
      var ty = y(pt.rebased);
      focus.style("display", null);
      focus.select(".focus-x").attr("x1", tx).attr("x2", tx);
      focusDot
        .attr("cx", tx)
        .attr("cy", ty)
        .attr("stroke", color(panel.symbol));

      var fromPar = pt.rebased - 100;
      tip.hidden = false;
      tip.innerHTML =
        "<strong>" +
        panel.symbol +
        "</strong>" +
        (panel.name && panel.name !== panel.symbol
          ? "<span class='chart-tip-name'>" + panel.name + "</span>"
          : "") +
        "<span class='chart-tip-meta'>" +
        formatDay(new Date(pt.t)) +
        "</span>" +
        "<span class='chart-tip-val'>" +
        (+pt.rebased).toFixed(2) +
        " <em>(" +
        pctLabel(fromPar) +
        " vs start)</em></span>";

      var svgNode = svg.node();
      var mountRect = mount.getBoundingClientRect();
      var svgRect = svgNode.getBoundingClientRect();
      var scaleX = svgRect.width / width;
      var scaleY = svgRect.height / height;
      var left = svgRect.left - mountRect.left + tx * scaleX + 14;
      var top = svgRect.top - mountRect.top + ty * scaleY - 18;
      if (left + tip.offsetWidth > mountRect.width - 8) {
        left = svgRect.left - mountRect.left + tx * scaleX - tip.offsetWidth - 14;
      }
      if (top < 4) top = 4;
      tip.style.left = Math.max(4, left) + "px";
      tip.style.top = top + "px";
    }

    function pickSeriesAt(mx, my, preferSymbol) {
      var date = x.invert(mx);
      var candidates = [];
      panels.forEach(function (p) {
        if (preferSymbol && p.symbol !== preferSymbol) return;
        var pt = nearestPoint(p.points, date);
        if (!pt) return;
        var py = y(pt.rebased);
        candidates.push({
          panel: p,
          pt: pt,
          dist: Math.abs(py - my),
        });
      });
      if (!candidates.length && preferSymbol) {
        return pickSeriesAt(mx, my, null);
      }
      candidates.sort(function (a, b) {
        return a.dist - b.dist;
      });
      return candidates[0] || null;
    }

    function onPointer(mx, my) {
      if (
        mx < margin.left ||
        mx > width - margin.right ||
        my < margin.top ||
        my > height - margin.bottom
      ) {
        if (!locked) {
          applyHighlight(null);
          hideFocus();
        }
        return;
      }
      var hit = pickSeriesAt(mx, my, locked);
      if (!hit) return;
      applyHighlight(hit.panel.symbol);
      showFocus(hit.panel, hit.pt);
    }

    function pointerFromEvent(event) {
      var pt = d3.pointer(event, svg.node());
      return { mx: pt[0], my: pt[1] };
    }

    svg
      .append("rect")
      .attr("class", "price-overlay")
      .attr("x", margin.left)
      .attr("y", margin.top)
      .attr("width", width - margin.left - margin.right)
      .attr("height", height - margin.top - margin.bottom)
      .attr("fill", "transparent")
      .style("cursor", "crosshair")
      .on("mousemove", function (event) {
        var p = pointerFromEvent(event);
        onPointer(p.mx, p.my);
      })
      .on("mouseleave", function () {
        if (locked) {
          applyHighlight(locked);
          hideFocus();
        } else {
          applyHighlight(null);
          hideFocus();
        }
      });

    // Wide invisible strokes for direct line hover (under overlay? overlay captures all —
    // so legend + nearest-y on overlay is enough. Also wire legend.)

    function lockSymbol(symbol) {
      locked = symbol;
      applyHighlight(symbol);
      var panel = bySymbol[symbol];
      if (panel && panel.points.length) {
        showFocus(panel, panel.points[panel.points.length - 1]);
      }
    }

    function unlockSymbol() {
      locked = null;
      applyHighlight(null);
      hideFocus();
    }

    Array.prototype.forEach.call(legend.querySelectorAll(".chart-legend-item"), function (li) {
      li.addEventListener("mouseenter", function () {
        lockSymbol(li.dataset.symbol);
      });
      li.addEventListener("mouseleave", function () {
        unlockSymbol();
      });
      li.addEventListener("focus", function () {
        lockSymbol(li.dataset.symbol);
      });
      li.addEventListener("blur", function () {
        unlockSymbol();
      });
      li.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          if (locked === li.dataset.symbol) unlockSymbol();
          else lockSymbol(li.dataset.symbol);
        }
      });
    });

    if (!reduceMotion) {
      seriesG.selectAll(".price-line").classed("price-line--animated", true);
    }
  }

  function render(payload) {
    root.innerHTML = "";
    drawEquity(section("Book equity path", "ch-eq"), payload.equity);
    drawAllocation(section("Allocation", "ch-alloc"), payload.allocation);
    drawPrices(section("Relative prices (rebased 100)", "ch-px"), payload.prices);
  }

  fetch("/desk/api/charts", { credentials: "same-origin" })
    .then(function (r) {
      if (!r.ok) throw new Error("charts HTTP " + r.status);
      return r.json();
    })
    .then(render)
    .catch(function () {
      showError("Could not load chart data.");
    });
})();
