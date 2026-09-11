/*! paper desk charts — local D3 v7 (no CDN) */
(function () {
  "use strict";

  var root = document.getElementById("charts-root");
  // Book page uses the same script for since-buy sparklines (no #charts-root).
  if (typeof d3 === "undefined") {
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

  /** Where glance strips append (Charts policy-honesty details). */
  var glanceMount = null;

  function appendGlance(node) {
    (glanceMount || root).appendChild(node);
  }


  function showError(msg) {
    if (!root) return;
    root.innerHTML = "";
    var p = document.createElement("p");
    p.className = "empty";
    p.textContent = msg;
    root.appendChild(p);
  }

  function section(title, id, note) {
    if (!root) return null;
    var wrap = document.createElement("section");
    wrap.className = "block chart-block";
    wrap.setAttribute("aria-labelledby", id);
    var h = document.createElement("h2");
    h.id = id;
    h.textContent = title;
    wrap.appendChild(h);
    if (note) {
      var p = document.createElement("p");
      p.className = "sub";
      p.textContent = note;
      wrap.appendChild(p);
    }
    var mount = document.createElement("div");
    mount.className = "chart-mount";
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
        cash: d.cash != null ? +d.cash : null,
        invested: d.invested != null ? +d.invested : null,
      };
    });

    var width = mount.clientWidth || 640;
    var height = 280;
    var margin = { top: 16, right: 16, bottom: 40, left: 56 };

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
      .attr("aria-label", "Paper book equity over time — hover for values");

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

    appendTimeAxis(svg, x, margin, height);
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
      .attr("stroke-width", 1.5);

    var focus = svg.append("g").style("display", "none");
    focus
      .append("line")
      .attr("class", "focus-x")
      .attr("y1", margin.top)
      .attr("y2", height - margin.bottom)
      .attr("stroke", "rgba(232,239,230,0.35)")
      .attr("stroke-dasharray", "3 3");
    var focusDot = focus
      .append("circle")
      .attr("r", 5)
      .attr("fill", "#e8efe6")
      .attr("stroke", "#d4a574")
      .attr("stroke-width", 1.5);

    var bisect = d3.bisector(function (d) { return d.t; }).left;

    function tipHtml(d) {
      var meta = formatDay(d.t);
      if (d.label) meta += " · " + d.label;
      var extra = "";
      if (d.cash != null && d.invested != null) {
        extra =
          "<span class='chart-tip-val'>cash €" +
          d3.format(",.0f")(d.cash) +
          " · invested €" +
          d3.format(",.0f")(d.invested) +
          "</span>";
      }
      return (
        "<strong>€" +
        d3.format(",.2f")(d.equity) +
        "</strong>" +
        "<span class='chart-tip-meta'>" +
        meta +
        "</span>" +
        extra
      );
    }

    function placeTip(d) {
      tip.hidden = false;
      tip.innerHTML = tipHtml(d);
      var mountRect = mount.getBoundingClientRect();
      var svgRect = svg.node().getBoundingClientRect();
      var scaleX = svgRect.width / width;
      var scaleY = svgRect.height / height;
      var left = svgRect.left - mountRect.left + x(d.t) * scaleX + 14;
      var top = svgRect.top - mountRect.top + y(d.equity) * scaleY - 18;
      if (left + tip.offsetWidth > mountRect.width - 8) {
        left = svgRect.left - mountRect.left + x(d.t) * scaleX - tip.offsetWidth - 14;
      }
      tip.style.left = Math.max(4, left) + "px";
      tip.style.top = Math.max(4, top) + "px";
    }

    svg
      .append("rect")
      .attr("class", "equity-hover")
      .attr("x", margin.left)
      .attr("y", margin.top)
      .attr("width", width - margin.left - margin.right)
      .attr("height", height - margin.top - margin.bottom)
      .attr("fill", "transparent")
      .style("cursor", "crosshair")
      .on("mousemove", function (event) {
        var mx = d3.pointer(event, svg.node())[0];
        var t0 = x.invert(mx);
        var i = bisect(data, t0, 1);
        var a = data[i - 1];
        var b = data[i] || a;
        if (!a) return;
        var d = t0 - a.t > b.t - t0 ? b : a;
        focus.style("display", null);
        focus.select(".focus-x").attr("x1", x(d.t)).attr("x2", x(d.t));
        focusDot.attr("cx", x(d.t)).attr("cy", y(d.equity));
        placeTip(d);
      })
      .on("mouseleave", function () {
        focus.style("display", "none");
        tip.hidden = true;
      });

    appendRangeCaption(mount, data[0].t, data[data.length - 1].t);
  }

  function drawUnrealized(mount, series) {
    if (!series || series.length < 2) {
      mount.innerHTML =
        "<p class='empty'>Need a few marks after fills to chart unrealized P&amp;L.</p>";
      return;
    }
    var data = series.map(function (d) {
      return {
        t: new Date(d.t),
        unrealized: +d.unrealized,
        unrealized_pct: +d.unrealized_pct,
      };
    });
    var width = mount.clientWidth || 640;
    var height = 280;
    var margin = { top: 16, right: 16, bottom: 40, left: 64 };

    var tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.hidden = true;
    tip.setAttribute("role", "status");
    mount.appendChild(tip);

    var svg = d3
      .select(mount)
      .append("svg")
      .attr("viewBox", "0 0 " + width + " " + height)
      .attr("role", "img")
      .attr("aria-label", "Unrealized paper P and L over time");

    var x = d3
      .scaleTime()
      .domain(d3.extent(data, function (d) { return d.t; }))
      .range([margin.left, width - margin.right]);
    var yMin = d3.min(data, function (d) { return d.unrealized; });
    var yMax = d3.max(data, function (d) { return d.unrealized; });
    var pad = Math.max(Math.abs(yMax - yMin) * 0.08, 1);
    var y = d3
      .scaleLinear()
      .domain([Math.min(yMin - pad, 0), Math.max(yMax + pad, 0)])
      .nice()
      .range([height - margin.bottom, margin.top]);

    var defs = svg.append("defs");
    var gradUp = defs
      .append("linearGradient")
      .attr("id", "unrealUp")
      .attr("x1", "0").attr("x2", "0").attr("y1", "0").attr("y2", "1");
    gradUp.append("stop").attr("offset", "0%").attr("stop-color", "#7dcea0").attr("stop-opacity", 0.35);
    gradUp.append("stop").attr("offset", "100%").attr("stop-color", "#7dcea0").attr("stop-opacity", 0.02);
    var gradDn = defs
      .append("linearGradient")
      .attr("id", "unrealDn")
      .attr("x1", "0").attr("x2", "0").attr("y1", "0").attr("y2", "1");
    gradDn.append("stop").attr("offset", "0%").attr("stop-color", "#e07a5f").attr("stop-opacity", 0.02);
    gradDn.append("stop").attr("offset", "100%").attr("stop-color", "#e07a5f").attr("stop-opacity", 0.35);

    appendTimeAxis(svg, x, margin, height);
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

    svg
      .append("line")
      .attr("x1", margin.left)
      .attr("x2", width - margin.right)
      .attr("y1", y(0))
      .attr("y2", y(0))
      .attr("stroke", "rgba(232,239,230,0.35)")
      .attr("stroke-dasharray", "4 4");

    var area = d3
      .area()
      .x(function (d) { return x(d.t); })
      .y0(y(0))
      .y1(function (d) { return y(d.unrealized); })
      .curve(d3.curveMonotoneX);
    var line = d3
      .line()
      .x(function (d) { return x(d.t); })
      .y(function (d) { return y(d.unrealized); })
      .curve(d3.curveMonotoneX);

    var last = data[data.length - 1];
    var stroke = last.unrealized >= 0 ? "#7dcea0" : "#e07a5f";
    var fill = last.unrealized >= 0 ? "url(#unrealUp)" : "url(#unrealDn)";

    svg.append("path").datum(data).attr("fill", fill).attr("d", area);
    svg
      .append("path")
      .datum(data)
      .attr("fill", "none")
      .attr("stroke", stroke)
      .attr("stroke-width", 2.2)
      .attr("d", line);

    var focus = svg.append("g").style("display", "none");
    focus
      .append("line")
      .attr("class", "focus-x")
      .attr("y1", margin.top)
      .attr("y2", height - margin.bottom)
      .attr("stroke", "rgba(232,239,230,0.35)")
      .attr("stroke-dasharray", "3 3");
    var focusDot = focus.append("circle").attr("r", 4.5).attr("fill", stroke);

    var bisect = d3.bisector(function (d) { return d.t; }).left;

    svg
      .append("rect")
      .attr("x", margin.left)
      .attr("y", margin.top)
      .attr("width", width - margin.left - margin.right)
      .attr("height", height - margin.top - margin.bottom)
      .attr("fill", "transparent")
      .style("cursor", "crosshair")
      .on("mousemove", function (event) {
        var mx = d3.pointer(event, svg.node())[0];
        var t0 = x.invert(mx);
        var i = bisect(data, t0, 1);
        var a = data[i - 1];
        var b = data[i] || a;
        if (!a) return;
        var d = t0 - a.t > b.t - t0 ? b : a;
        focus.style("display", null);
        focus.select(".focus-x").attr("x1", x(d.t)).attr("x2", x(d.t));
        focusDot.attr("cx", x(d.t)).attr("cy", y(d.unrealized));
        tip.hidden = false;
        tip.innerHTML =
          "<strong>" +
          (d.unrealized >= 0 ? "+" : "") +
          "€" +
          d3.format(",.2f")(d.unrealized) +
          "</strong>" +
          "<span class='chart-tip-meta'>" +
          formatDay(d.t) +
          "</span>" +
          "<span class='chart-tip-val'>" +
          pctLabel(d.unrealized_pct) +
          " <em>vs cost basis</em></span>";
        var mountRect = mount.getBoundingClientRect();
        var svgRect = svg.node().getBoundingClientRect();
        var scaleX = svgRect.width / width;
        var scaleY = svgRect.height / height;
        var left = svgRect.left - mountRect.left + x(d.t) * scaleX + 14;
        var top = svgRect.top - mountRect.top + y(d.unrealized) * scaleY - 18;
        if (left + tip.offsetWidth > mountRect.width - 8) {
          left = svgRect.left - mountRect.left + x(d.t) * scaleX - tip.offsetWidth - 14;
        }
        tip.style.left = Math.max(4, left) + "px";
        tip.style.top = Math.max(4, top) + "px";
      })
      .on("mouseleave", function () {
        focus.style("display", "none");
        tip.hidden = true;
      });

    appendRangeCaption(mount, data[0].t, data[data.length - 1].t);
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
      return d3.utcFormat("%Y-%m-%d")(d);
    } catch (e) {
      return String(d);
    }
  }

  function spanMs(a, b) {
    return Math.abs(+b - +a);
  }

  function timeTickFormat(domain) {
    var ms = spanMs(domain[0], domain[1]);
    var day = 864e5;
    if (ms < 2 * day) return d3.utcFormat("%H:%M");
    if (ms < 100 * day) return d3.utcFormat("%b %d");
    if (ms < 400 * day) return d3.utcFormat("%b %Y");
    return d3.utcFormat("%Y");
  }

  function formatRangeLabel(a, b) {
    if (!a || !b || isNaN(+a) || isNaN(+b)) return "";
    var ms = spanMs(a, b);
    var day = 864e5;
    var fmt =
      ms < 2 * day
        ? d3.utcFormat("%Y-%m-%d %H:%M")
        : d3.utcFormat("%Y-%m-%d");
    return fmt(a) + " → " + fmt(b) + " UTC";
  }

  function appendTimeAxis(svg, x, margin, height) {
    var domain = x.domain();
    svg
      .append("g")
      .attr("class", "axis axis-x")
      .attr("transform", "translate(0," + (height - margin.bottom) + ")")
      .call(
        d3
          .axisBottom(x)
          .ticks(6)
          .tickFormat(timeTickFormat(domain))
          .tickSizeOuter(0)
      );
  }

  function appendRangeCaption(mount, a, b) {
    var label = formatRangeLabel(a, b);
    if (!label) return;
    var cap = document.createElement("p");
    cap.className = "chart-range";
    cap.textContent = label;
    mount.appendChild(cap);
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
    var margin = { top: 12, right: 16, bottom: 40, left: 44 };

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

    appendTimeAxis(svg, x, margin, height);
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

    var xDomain = x.domain();
    appendRangeCaption(mount, xDomain[0], xDomain[1]);
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

  function drawSparks(panels) {
    var by = {};
    (panels || []).forEach(function (p) {
      by[p.symbol] = p;
    });
    Array.prototype.forEach.call(
      document.querySelectorAll(".hold-spark[data-symbol]"),
      function (el) {
        var panel = by[el.dataset.symbol];
        el.innerHTML = "";
        if (!panel || !panel.points || panel.points.length < 2) {
          el.classList.add("is-empty");
          el.title = "No since-buy path yet";
          return;
        }
        el.classList.remove("is-empty");
        var data = panel.points.map(function (pt) {
          return {
            t: new Date(pt.t),
            close: +pt.close,
            rebased: +pt.rebased,
          };
        });
        var t0 = data[0].t;
        var t1 = data[data.length - 1].t;
        var range = formatRangeLabel(t0, t1);
        var spanH = +panel.span_hours;
        if (!isFinite(spanH)) spanH = spanMs(t0, t1) / 36e5;
        var spanTxt =
          spanH < 48
            ? spanH.toFixed(1) + "h hold"
            : (spanH / 24).toFixed(1) + "d hold";
        var tipLine =
          panel.symbol +
          " · " +
          range +
          " · " +
          pctLabel(panel.change_pct) +
          " vs avg cost (100)";
        el.title = tipLine;
        el.setAttribute(
          "aria-label",
          tipLine + ". Path rebased to average buy; no forecast."
        );

        var chart = document.createElement("div");
        chart.className = "hold-spark-chart";
        el.appendChild(chart);

        var width = Math.max(chart.clientWidth || el.clientWidth || 280, 160);
        var height = 72;
        var pad = { top: 10, right: 44, bottom: 22, left: 8 };
        var innerW = width - pad.left - pad.right;
        var innerH = height - pad.top - pad.bottom;

        var x = d3
          .scaleUtc()
          .domain(d3.extent(data, function (d) {
            return d.t;
          }))
          .range([0, innerW]);
        var yDomain = d3.extent(data, function (d) {
          return d.rebased;
        });
        // Keep avg-cost (100) in view so the dashed baseline means something.
        yDomain = [Math.min(yDomain[0], 99.5), Math.max(yDomain[1], 100.5)];
        var y = d3.scaleLinear().domain(yDomain).nice().range([innerH, 0]);
        var up = panel.change_pct >= 0;
        var stroke = up ? cssVar("--up", "#7dcea0") : cssVar("--down", "#e07a5f");
        var ink = cssVar("--muted", "#8a9688");

        var svg = d3
          .select(chart)
          .append("svg")
          .attr("viewBox", "0 0 " + width + " " + height)
          .attr("aria-hidden", "true");
        var g = svg
          .append("g")
          .attr("transform", "translate(" + pad.left + "," + pad.top + ")");

        // Avg-cost baseline (=100)
        if (y.domain()[0] <= 100 && y.domain()[1] >= 100) {
          g.append("line")
            .attr("x1", 0)
            .attr("x2", innerW)
            .attr("y1", y(100))
            .attr("y2", y(100))
            .attr("stroke", "rgba(232,239,230,0.28)")
            .attr("stroke-dasharray", "3 3");
          g.append("text")
            .attr("x", 0)
            .attr("y", y(100) - 3)
            .attr("fill", ink)
            .attr("font-size", 9)
            .attr("font-family", "ui-monospace, SFMono-Regular, Menlo, monospace")
            .text("avg buy");
        }

        var line = d3
          .line()
          .x(function (d) {
            return x(d.t);
          })
          .y(function (d) {
            return y(d.rebased);
          })
          .curve(d3.curveMonotoneX);
        g.append("path")
          .datum(data)
          .attr("fill", "none")
          .attr("stroke", stroke)
          .attr("stroke-width", 1.7)
          .attr("d", line);

        // Buy marker
        g.append("circle")
          .attr("cx", x(t0))
          .attr("cy", y(data[0].rebased))
          .attr("r", 2.5)
          .attr("fill", ink);
        g.append("text")
          .attr("x", x(t0) + 4)
          .attr("y", y(data[0].rebased) - 4)
          .attr("fill", ink)
          .attr("font-size", 9)
          .attr("font-family", "ui-monospace, SFMono-Regular, Menlo, monospace")
          .text("buy");

        // End %
        g.append("text")
          .attr("x", innerW + 4)
          .attr("y", y(data[data.length - 1].rebased) + 3)
          .attr("fill", stroke)
          .attr("font-size", 10)
          .attr("font-family", "ui-monospace, SFMono-Regular, Menlo, monospace")
          .text(pctLabel(panel.change_pct));

        // Time axis: start / end
        var tickFmt = timeTickFormat([t0, t1]);
        g.append("text")
          .attr("x", 0)
          .attr("y", innerH + 14)
          .attr("fill", ink)
          .attr("font-size", 9)
          .attr("font-family", "ui-monospace, SFMono-Regular, Menlo, monospace")
          .text(tickFmt(t0));
        g.append("text")
          .attr("x", innerW)
          .attr("y", innerH + 14)
          .attr("text-anchor", "end")
          .attr("fill", ink)
          .attr("font-size", 9)
          .attr("font-family", "ui-monospace, SFMono-Regular, Menlo, monospace")
          .text(tickFmt(t1));

        var tip = document.createElement("div");
        tip.className = "hold-spark-tip";
        tip.hidden = true;
        el.appendChild(tip);

        var overlay = g
          .append("rect")
          .attr("width", innerW)
          .attr("height", innerH)
          .attr("fill", "transparent")
          .style("cursor", "crosshair");
        var cross = g
          .append("line")
          .attr("y1", 0)
          .attr("y2", innerH)
          .attr("stroke", "rgba(232,239,230,0.35)")
          .attr("stroke-width", 1)
          .style("display", "none");
        var focus = g
          .append("circle")
          .attr("r", 3)
          .attr("fill", stroke)
          .style("display", "none");

        overlay.on("mousemove", function (event) {
          var xm = d3.pointer(event, this)[0];
          var ht = x.invert(xm);
          var i = d3.bisector(function (d) {
            return d.t;
          }).center(data, ht);
          var d = data[Math.max(0, Math.min(data.length - 1, i))];
          cross
            .attr("x1", x(d.t))
            .attr("x2", x(d.t))
            .style("display", null);
          focus.attr("cx", x(d.t)).attr("cy", y(d.rebased)).style("display", null);
          tip.hidden = false;
          tip.textContent =
            formatDay(d.t) +
            (spanH < 48 ? " " + d3.utcFormat("%H:%M")(d.t) + " UTC" : "") +
            " · €" +
            d.close.toLocaleString(undefined, {
              maximumFractionDigits: 2,
            }) +
            " · " +
            pctLabel(d.rebased - 100) +
            " vs buy";
        });
        overlay.on("mouseleave", function () {
          cross.style("display", "none");
          focus.style("display", "none");
          tip.hidden = true;
        });

        var cap = document.createElement("p");
        cap.className = "hold-spark-cap";
        var nPts = data.length;
        var grain =
          spanH < 36
            ? "buy → current mark (intraday; daily bars not useful yet)"
            : nPts + " marks since buy";
        cap.textContent =
          range + " · " + spanTxt + " · " + grain + " · dashed = avg cost (100)";
        el.appendChild(cap);
      }
    );
  }

  function renderScanFreshness(payload) {
    var fresh = payload && payload.scan_freshness;
    if (!fresh || !fresh.ready) return;
    var p = document.createElement("p");
    p.className = "scan-fresh " + (fresh.tone || "unknown");
    if (fresh.scan_time) p.title = String(fresh.scan_time);
    var tone = document.createElement("span");
    tone.className = "scan-fresh-tone";
    tone.textContent = String(fresh.tone || "unknown");
    p.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    p.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "scan-fresh-body";
    body.textContent = String(fresh.age_label || fresh.line || "");
    p.appendChild(body);
    if (fresh.scan_time && fresh.age_label) {
      var sep2 = document.createElement("span");
      sep2.className = "pretrade-sep";
      sep2.setAttribute("aria-hidden", "true");
      sep2.textContent = "·";
      p.appendChild(sep2);
      var when = document.createElement("span");
      when.className = "scan-fresh-when";
      when.textContent = String(fresh.scan_time);
      p.appendChild(when);
    }
    appendGlance(p);
  }

  function renderBreadthGlance(payload) {
    var glance = payload && payload.breadth_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "breadth-glance";
    wrap.setAttribute("aria-labelledby", "charts-breadth-h");
    var h = document.createElement("h2");
    h.id = "charts-breadth-h";
    h.className = "visually-hidden";
    h.textContent = "Scan breadth beside charts";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "breadth-glance-line";
    var tone = document.createElement("span");
    tone.className = "breadth-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Breadth";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "breadth-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "breadth-glance-link";
    link.href = "/desk/breadth";
    link.textContent = "Full breadth →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Scan-list estimate A/D + near-high (priced counts) — not full-universe; display only, not a gate.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderPretradeGlance(payload) {
    var glance = payload && payload.pretrade_glance;
    if (!glance || !glance.ready || !glance.level) return;
    var wrap = document.createElement("section");
    wrap.className = "pretrade-glance";
    wrap.setAttribute("aria-labelledby", "charts-pretrade-h");
    var h = document.createElement("h2");
    h.id = "charts-pretrade-h";
    h.className = "visually-hidden";
    h.textContent = "Pre-trade checklist";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "pretrade-glance-line";
    var tone = document.createElement("span");
    tone.className = "pretrade-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Pre-trade";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var level = document.createElement("span");
    level.className = "pretrade-level " + (glance.tone || "flat");
    level.textContent = String(glance.level);
    line.appendChild(level);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var body = document.createElement("span");
    body.className = "pretrade-glance-body";
    var notes = glance.notes;
    if (notes && notes.length) {
      body.textContent = notes.join("; ");
    } else {
      body.textContent = String(glance.line || "");
    }
    line.appendChild(body);
    var sep3 = document.createElement("span");
    sep3.className = "pretrade-sep";
    sep3.setAttribute("aria-hidden", "true");
    sep3.textContent = "·";
    line.appendChild(sep3);
    var link = document.createElement("a");
    link.className = "pretrade-glance-link";
    link.href = "/desk";
    link.textContent = "Overview →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Checklist beside charts — FAIL blocks buys; WARN is fee burn / cooldown.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderSoftAllowGlance(payload) {
    var glance = payload && payload.soft_allow_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "soft-allow-glance";
    wrap.setAttribute("aria-labelledby", "charts-soft-allow-h");
    var h = document.createElement("h2");
    h.id = "charts-soft-allow-h";
    h.className = "visually-hidden";
    h.textContent = "Fail-open soft-allows";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "soft-allow-glance-line";
    var tone = document.createElement("span");
    tone.className = "soft-allow-glance-tone " + (glance.tone || "warn");
    tone.textContent = "Soft-allow";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "soft-allow-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "soft-allow-glance-link";
    link.href = "/desk/ops#soft-h";
    link.textContent = "Ops memory →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Gate passed with missing data — not a hard block. Full list on Ops.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderBookRiskGlance(payload) {
    var glance = payload && payload.book_risk_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "book-risk-glance";
    wrap.setAttribute("aria-labelledby", "charts-book-risk-h");
    var h = document.createElement("h2");
    h.id = "charts-book-risk-h";
    h.className = "visually-hidden";
    h.textContent = "Book risk";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "book-risk-glance-line";
    var tone = document.createElement("span");
    tone.className = "book-risk-glance-tone";
    tone.textContent = "Book";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var posture = document.createElement("span");
    posture.className = "risk-posture " + (glance.posture || "open");
    posture.textContent = String(glance.posture || "");
    line.appendChild(posture);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var body = document.createElement("span");
    body.className =
      "book-risk-glance-body" + (glance.concentration_warn ? " warn" : "");
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep3 = document.createElement("span");
    sep3.className = "pretrade-sep";
    sep3.setAttribute("aria-hidden", "true");
    sep3.textContent = "·";
    line.appendChild(sep3);
    var link = document.createElement("a");
    link.className = "book-risk-glance-link";
    link.href = "/desk/book";
    link.textContent = "Full book →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Slots and posture beside charts — overweight means exits-only. Full strip on Book.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderEntryGatesGlance(payload) {
    var glance = payload && payload.entry_gates_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "entry-gates-glance";
    wrap.setAttribute("aria-labelledby", "charts-gates-h");
    var h = document.createElement("h2");
    h.id = "charts-gates-h";
    h.className = "visually-hidden";
    h.textContent = "Entry gates";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "entry-gates-glance-line";
    var tone = document.createElement("span");
    tone.className = "entry-gates-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Gates";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "entry-gates-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "entry-gates-glance-link";
    link.href = "/desk/ops#cfg-h";
    link.textContent = "Ops knobs →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Soft entry filters beside charts — display only; flip toggles on Ops.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderCalmStreakGlance(payload) {
    var glance = payload && payload.calm_streak_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "calm-streak-glance";
    wrap.setAttribute("aria-labelledby", "charts-calm-h");
    var h = document.createElement("h2");
    h.id = "charts-calm-h";
    h.className = "visually-hidden";
    h.textContent = "Paper calm streak";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "calm-streak-glance-line";
    var tone = document.createElement("span");
    tone.className = "calm-streak-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Calm";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "calm-streak-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "calm-streak-glance-link";
    link.href = "/desk/ops#calm-h";
    link.textContent = "Ops calm →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Promote compose-default unlock beside charts — calm ≠ edge; detail on Ops.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderPromoteAbGlance(payload) {
    var glance = payload && payload.promote_ab_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "promote-ab-glance";
    wrap.setAttribute("aria-labelledby", "charts-promote-ab-h");
    var h = document.createElement("h2");
    h.id = "charts-promote-ab-h";
    h.className = "visually-hidden";
    h.textContent = "Promote A/B";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "promote-ab-glance-line";
    var tone = document.createElement("span");
    tone.className = "promote-ab-glance-tone " + (glance.tone || "flat");
    tone.textContent = "A/B";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "promote-ab-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "promote-ab-glance-link";
    link.href = "/desk/ops#ops-promote";
    link.textContent = "Ops promote →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Fee-adjusted A/B window beside charts — do not flip promote mid-window. Not edge.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }


  function renderCryptoPolicyGlance(payload) {
    var glance = payload && payload.crypto_policy_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "crypto-policy-glance";
    wrap.setAttribute("aria-labelledby", "charts-crypto-h");
    var h = document.createElement("h2");
    h.id = "charts-crypto-h";
    h.className = "visually-hidden";
    h.textContent = "Crypto policy";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "crypto-policy-glance-line";
    var tone = document.createElement("span");
    tone.className = "crypto-policy-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Crypto";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "crypto-policy-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "crypto-policy-glance-link";
    link.href = "/desk/screener#crypto-h";
    link.textContent = "Screener crypto →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Live crypto beside charts — BTC/ETH only · one slot · ±10% exits. Leaders ≠ auto-buy.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderExitPolicyGlance(payload) {
    var glance = payload && payload.exit_policy_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "exit-policy-glance";
    wrap.setAttribute("aria-labelledby", "charts-exit-h");
    var h = document.createElement("h2");
    h.id = "charts-exit-h";
    h.className = "visually-hidden";
    h.textContent = "Stock exits";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "exit-policy-glance-line";
    var tone = document.createElement("span");
    tone.className = "exit-policy-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Exits";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "exit-policy-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "exit-policy-glance-link";
    link.href = "/desk/book";
    link.textContent = "Book →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Stock exits beside charts — TP +8% / SL −5% / rotate ≥+5%. Not ATR.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderEarningsBlackoutGlance(payload) {
    var glance = payload && payload.earnings_blackout_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "earnings-blackout-glance";
    wrap.setAttribute("aria-labelledby", "charts-earnings-h");
    var h = document.createElement("h2");
    h.id = "charts-earnings-h";
    h.className = "visually-hidden";
    h.textContent = "Earnings blackout";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "earnings-blackout-glance-line";
    var tone = document.createElement("span");
    tone.className = "earnings-blackout-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Earnings";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "earnings-blackout-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "earnings-blackout-glance-link";
    link.href = "/desk/screener";
    link.textContent = "Screener →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Stock blackout beside charts — 2d/1d; no Yahoo date → allow (fail-open); crypto exempt.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderAiModeGlance(payload) {
    var glance = payload && payload.ai_mode_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "ai-mode-glance";
    wrap.setAttribute("aria-labelledby", "charts-ai-h");
    var h = document.createElement("h2");
    h.id = "charts-ai-h";
    h.className = "visually-hidden";
    h.textContent = "AI mode";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "ai-mode-glance-line";
    var tone = document.createElement("span");
    tone.className = "ai-mode-glance-tone " + (glance.tone || "flat");
    tone.textContent = "AI";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "ai-mode-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "ai-mode-glance-link";
    link.href = "/desk/ops#ops-ai-mode";
    link.textContent = "Ops AI →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "AI path beside charts — off / validate / full + multi-role. Rules first.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderAiRolesGlance(payload) {
    var glance = payload && payload.ai_roles_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "ai-roles-glance";
    wrap.setAttribute("aria-labelledby", "charts-ai-roles-h");
    var h = document.createElement("h2");
    h.id = "charts-ai-roles-h";
    h.className = "visually-hidden";
    h.textContent = "AI multi-role research contract";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "ai-roles-glance-line";
    var tone = document.createElement("span");
    tone.className = "ai-roles-glance-tone " + (glance.tone || "roles");
    tone.textContent = "Roles";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "ai-roles-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "ai-roles-glance-link";
    link.href = "/desk/ideas";
    link.textContent = "Ideas →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Multi-role beside charts — bull/bear/risk; disagreement or risk veto → HOLD. Display only.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderAiDebateGlance(payload) {
    var glance = payload && payload.ai_debate_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "ai-debate-glance";
    wrap.setAttribute("aria-labelledby", "charts-ai-debate-h");
    var h = document.createElement("h2");
    h.id = "charts-ai-debate-h";
    h.className = "visually-hidden";
    h.textContent = "AI debate memory";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "ai-debate-glance-line";
    var tone = document.createElement("span");
    tone.className = "ai-debate-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Debates";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "ai-debate-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "ai-debate-glance-link";
    link.href = "/desk/ideas#debate-h";
    link.textContent = "Ideas debates →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Validate memory beside charts — BUY/HOLD/SELL + gated; Ideas keeps transcripts. Display only.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderAiValidateScopeGlance(payload) {
    var glance = payload && payload.ai_validate_scope_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "ai-validate-scope-glance";
    wrap.setAttribute("aria-labelledby", "charts-ai-scope-h");
    var h = document.createElement("h2");
    h.id = "charts-ai-scope-h";
    h.className = "visually-hidden";
    h.textContent = "AI validate scope";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "ai-validate-scope-glance-line";
    var tone = document.createElement("span");
    tone.className = "ai-validate-scope-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Scope";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "ai-validate-scope-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "ai-validate-scope-glance-link";
    link.href = "/desk/ops#ops-ai-mode";
    link.textContent = "Ops AI →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Top-N LLM scope beside charts — rest keep scanner score. Display only.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderSessionGlance(payload) {
    var glance = payload && payload.session_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "session-glance";
    wrap.setAttribute("aria-labelledby", "charts-session-h");
    var h = document.createElement("h2");
    h.id = "charts-session-h";
    h.className = "visually-hidden";
    h.textContent = "Session mode";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "session-glance-line";
    var tone = document.createElement("span");
    tone.className = "session-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Session";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "session-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "session-glance-link";
    link.href = "/desk/screener";
    link.textContent = "Screener →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "UTC session beside charts — weekend is crypto-only. Display only.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderEquityHoursGlance(payload) {
    var glance = payload && payload.equity_hours_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "equity-hours-glance";
    wrap.setAttribute("aria-labelledby", "charts-equity-hours-h");
    var h = document.createElement("h2");
    h.id = "charts-equity-hours-h";
    h.className = "visually-hidden";
    h.textContent = "Equity cash hours";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "equity-hours-glance-line";
    var tone = document.createElement("span");
    tone.className = "equity-hours-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Hours";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "equity-hours-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "equity-hours-glance-link";
    link.href = "/desk/screener";
    link.textContent = "Screener →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Live US vs Xetra beside charts — .DE is not US hours; crypto 24/7. Display only.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderBreakoutGuardGlance(payload) {
    var glance = payload && payload.breakout_guard_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "breakout-guard-glance";
    wrap.setAttribute("aria-labelledby", "charts-breakout-h");
    var h = document.createElement("h2");
    h.id = "charts-breakout-h";
    h.className = "visually-hidden";
    h.textContent = "Breakout entry guards";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "breakout-guard-glance-line";
    var tone = document.createElement("span");
    tone.className = "breakout-guard-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Breakout";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "breakout-guard-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "breakout-guard-glance-link";
    link.href = "/desk/screener#brk-h";
    link.textContent = "Breakouts →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Breakout entry guards beside charts — AI BUY · LOW blocked · pullback. Display only.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }


  function renderLossRotationGlance(payload) {
    var glance = payload && payload.loss_rotation_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "loss-rotation-glance";
    wrap.setAttribute("aria-labelledby", "charts-loss-rot-h");
    var h = document.createElement("h2");
    h.id = "charts-loss-rot-h";
    h.className = "visually-hidden";
    h.textContent = "Loss rotation policy";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "loss-rotation-glance-line";
    var tone = document.createElement("span");
    tone.className = "loss-rotation-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Rotate";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "loss-rotation-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "loss-rotation-glance-link";
    link.href = "/desk/book";
    link.textContent = "Book →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "No loss-rotation beside charts — losers stay; rotate winners only. Display only.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }


  function renderStaleRotationGlance(payload) {
    var glance = payload && payload.stale_rotation_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "stale-rotation-glance";
    wrap.setAttribute("aria-labelledby", "charts-stale-rot-h");
    var h = document.createElement("h2");
    h.id = "charts-stale-rot-h";
    h.className = "visually-hidden";
    h.textContent = "Stale rotation policy";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "stale-rotation-glance-line";
    var tone = document.createElement("span");
    tone.className = "stale-rotation-glance-tone " + (glance.tone || "stale");
    tone.textContent = "Stale";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "stale-rotation-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "stale-rotation-glance-link";
    link.href = "/desk/book";
    link.textContent = "Book →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Stale rotation beside charts — off full scan list + top-N replacement. Display only.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }


  function renderBookPostureGlance(payload) {
    var glance = payload && payload.book_posture_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "book-posture-glance";
    wrap.setAttribute("aria-labelledby", "charts-book-posture-h");
    var h = document.createElement("h2");
    h.id = "charts-book-posture-h";
    h.className = "visually-hidden";
    h.textContent = "Book posture modes";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "book-posture-glance-line";
    var tone = document.createElement("span");
    tone.className = "book-posture-glance-tone " + (glance.tone || "posture");
    tone.textContent = "Posture";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "book-posture-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "book-posture-glance-link";
    link.href = "/desk/book";
    link.textContent = "Book →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Book posture beside charts — open/at_cap/overweight; overweight is exits+trim only.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderJunkFilterGlance(payload) {
    var glance = payload && payload.junk_filter_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "junk-filter-glance";
    wrap.setAttribute("aria-labelledby", "charts-junk-h");
    var h = document.createElement("h2");
    h.id = "charts-junk-h";
    h.className = "visually-hidden";
    h.textContent = "Junk and noise filters";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "junk-filter-glance-line";
    var tone = document.createElement("span");
    tone.className = "junk-filter-glance-tone " + (glance.tone || "filter");
    tone.textContent = "Filter";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "junk-filter-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "junk-filter-glance-link";
    link.href = "/desk/screener";
    link.textContent = "Screener →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Junk/noise filters beside charts — no stables/leveraged; crypto ≥ $1. Display only.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderUniverseDiscoveryGlance(payload) {
    var glance = payload && payload.universe_discovery_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "universe-discovery-glance";
    wrap.setAttribute("aria-labelledby", "charts-universe-h");
    var h = document.createElement("h2");
    h.id = "charts-universe-h";
    h.className = "visually-hidden";
    h.textContent = "Universe discovery";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "universe-discovery-glance-line";
    var tone = document.createElement("span");
    tone.className = "universe-discovery-glance-tone " + (glance.tone || "discover");
    tone.textContent = "Universe";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "universe-discovery-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "universe-discovery-glance-link";
    link.href = "/desk/screener";
    link.textContent = "Screener →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Universe discovery beside charts — Yahoo movers cache age vs 24h; grows US+DE only; not auto-buy.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderAtrDisplayGlance(payload) {
    var glance = payload && payload.atr_display_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "atr-display-glance";
    wrap.setAttribute("aria-labelledby", "charts-atr-h");
    var h = document.createElement("h2");
    h.id = "charts-atr-h";
    h.className = "visually-hidden";
    h.textContent = "ATR display-only policy";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "atr-display-glance-line";
    var tone = document.createElement("span");
    tone.className = "atr-display-glance-tone " + (glance.tone || "display");
    tone.textContent = "ATR";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "atr-display-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "atr-display-glance-link";
    link.href = "/desk/screener";
    link.textContent = "Screener →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "ATR / R:R beside charts — Screener notes are display-only; live exits use TP/SL.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderEntrySlotsGlance(payload) {
    var glance = payload && payload.entry_slots_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "entry-slots-glance";
    wrap.setAttribute("aria-labelledby", "charts-entry-slots-h");
    var h = document.createElement("h2");
    h.id = "charts-entry-slots-h";
    h.className = "visually-hidden";
    h.textContent = "Entry slot ranking";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "entry-slots-glance-line";
    var tone = document.createElement("span");
    tone.className = "entry-slots-glance-tone " + (glance.tone || "slots");
    tone.textContent = "Slots";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "entry-slots-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "entry-slots-glance-link";
    link.href = "/desk/screener";
    link.textContent = "Screener →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Entry ranking beside charts — stock score band + crypto/stock interleave. Not a gate.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderPromoteContractGlance(payload) {
    var glance = payload && payload.promote_contract_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "promote-contract-glance";
    wrap.setAttribute("aria-labelledby", "charts-promote-contract-h");
    var h = document.createElement("h2");
    h.id = "charts-promote-contract-h";
    h.className = "visually-hidden";
    h.textContent = "Promote entry contract";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "promote-contract-glance-line";
    var tone = document.createElement("span");
    tone.className = "promote-contract-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Promote";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "promote-contract-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "promote-contract-glance-link";
    link.href = "/desk/ops#ops-promote";
    link.textContent = "Ops promote →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Promote beside charts — entry veto only; exits stay exit_policy. Not a new gate.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderGateRolesGlance(payload) {
    var glance = payload && payload.gate_roles_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "gate-roles-glance";
    wrap.setAttribute("aria-labelledby", "charts-gate-roles-h");
    var h = document.createElement("h2");
    h.id = "charts-gate-roles-h";
    h.className = "visually-hidden";
    h.textContent = "Entry gate roles";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "gate-roles-glance-line";
    var tone = document.createElement("span");
    tone.className = "gate-roles-glance-tone " + (glance.tone || "roles");
    tone.textContent = "Roles";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "gate-roles-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "gate-roles-glance-link";
    link.href = "/desk/ops#ops-regime";
    link.textContent = "Ops gates →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Gate roles beside charts — regime abs · RS rel · breadth scan A/D; starve→RS off first.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderGateParamsGlance(payload) {
    var glance = payload && payload.gate_params_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "gate-params-glance";
    wrap.setAttribute("aria-labelledby", "charts-gate-params-h");
    var h = document.createElement("h2");
    h.id = "charts-gate-params-h";
    h.className = "visually-hidden";
    h.textContent = "Entry gate parameters";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "gate-params-glance-line";
    var tone = document.createElement("span");
    tone.className = "gate-params-glance-tone " + (glance.tone || "params");
    tone.textContent = "Params";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "gate-params-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "gate-params-glance-link";
    link.href = "/desk/ops#ops-regime";
    link.textContent = "Ops gates →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Gate params beside charts — SMA / RS lookback / scan A/D mins; fail-open. Display only.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

    function renderBookLimitsGlance(payload) {
    var glance = payload && payload.book_limits_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "book-limits-glance";
    wrap.setAttribute("aria-labelledby", "charts-book-limits-h");
    var h = document.createElement("h2");
    h.id = "charts-book-limits-h";
    h.className = "visually-hidden";
    h.textContent = "Book limits";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "book-limits-glance-line";
    var tone = document.createElement("span");
    tone.className = "book-limits-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Book";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "book-limits-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "book-limits-glance-link";
    link.href = "/desk/ops#ops-max-pos";
    link.textContent = "Ops book →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Slots · min hold · fee preset beside charts — packaging ≠ edge. Not a gate.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderRebuyCooldownGlance(payload) {
    var glance = payload && payload.rebuy_cooldown_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "rebuy-cooldown-glance";
    wrap.setAttribute("aria-labelledby", "charts-rebuy-h");
    var h = document.createElement("h2");
    h.id = "charts-rebuy-h";
    h.className = "visually-hidden";
    h.textContent = "Rebuy cooldown";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "rebuy-cooldown-glance-line";
    var tone = document.createElement("span");
    tone.className = "rebuy-cooldown-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Rebuy";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "rebuy-cooldown-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "rebuy-cooldown-glance-link";
    link.href = "/desk/ops#ops-min-hold";
    link.textContent = "Ops hold →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Same-symbol rebuy lock beside charts — SCHW flip-flop / fee lesson. Not a gate.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderDailyLossGlance(payload) {
    var glance = payload && payload.daily_loss_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "daily-loss-glance";
    wrap.setAttribute("aria-labelledby", "charts-day-loss-h");
    var h = document.createElement("h2");
    h.id = "charts-day-loss-h";
    h.className = "visually-hidden";
    h.textContent = "Daily loss halt";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "daily-loss-glance-line";
    var tone = document.createElement("span");
    tone.className = "daily-loss-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Day loss";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "daily-loss-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "daily-loss-glance-link";
    link.href = "/desk#pretrade-h";
    link.textContent = "Pre-trade →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "UTC-day realized vs −2% halt beside charts — headroom before FAIL. Soft buy block only.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderConcentrationGlance(payload) {
    var glance = payload && payload.concentration_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "concentration-glance";
    wrap.setAttribute("aria-labelledby", "charts-conc-h");
    var h = document.createElement("h2");
    h.id = "charts-conc-h";
    h.className = "visually-hidden";
    h.textContent = "Concentration";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "concentration-glance-line";
    var tone = document.createElement("span");
    tone.className = "concentration-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Conc";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className =
      "concentration-glance-body" + (glance.warn ? " warn" : "");
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "concentration-glance-link";
    link.href = "/desk/book";
    link.textContent = "Book →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Largest name vs 30% entry cap beside charts — headroom before size blocks. Soft fill limit only.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderPostSlCooldownGlance(payload) {
    var glance = payload && payload.post_sl_cooldown_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "post-sl-cooldown-glance";
    wrap.setAttribute("aria-labelledby", "charts-post-sl-h");
    var h = document.createElement("h2");
    h.id = "charts-post-sl-h";
    h.className = "visually-hidden";
    h.textContent = "Post stop-loss cooldown";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "post-sl-cooldown-glance-line";
    var tone = document.createElement("span");
    tone.className = "post-sl-cooldown-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Post-SL";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "post-sl-cooldown-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "post-sl-cooldown-glance-link";
    link.href = "/desk#pretrade-h";
    link.textContent = "Pre-trade →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "After SL, ≥4h buy block beside charts — anti revenge refill. Soft WARN only.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderLoopCadenceGlance(payload) {
    var glance = payload && payload.loop_cadence_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "loop-cadence-glance";
    wrap.setAttribute("aria-labelledby", "charts-loop-cadence-h");
    var h = document.createElement("h2");
    h.id = "charts-loop-cadence-h";
    h.className = "visually-hidden";
    h.textContent = "Loop cadence";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "loop-cadence-glance-line";
    var tone = document.createElement("span");
    tone.className = "loop-cadence-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Cadence";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "loop-cadence-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "loop-cadence-glance-link";
    link.href = "/desk/ops#ops-scan-trade";
    link.textContent = "Ops cadence →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Scan vs trade sleep beside charts — floors ≥15m / ≥5m. Packaging ≠ edge. Not a gate.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderFeeAllowanceGlance(payload) {
    var glance = payload && payload.fee_allowance_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "fee-allowance-glance";
    wrap.setAttribute("aria-labelledby", "charts-fee-allowance-h");
    var h = document.createElement("h2");
    h.id = "charts-fee-allowance-h";
    h.className = "visually-hidden";
    h.textContent = "Fee allowance";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "fee-allowance-glance-line";
    var tone = document.createElement("span");
    tone.className = "fee-allowance-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Free legs";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "fee-allowance-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "fee-allowance-glance-link";
    link.href = "/desk/ops#ops-fee-preset";
    link.textContent = "Ops fees →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Free monthly legs beside charts — Revolut-like quota before paid fills. Crypto fees not modeled. Not a gate.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderFeeBurnGlance(payload) {
    var glance = payload && payload.fee_burn_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "fee-burn-glance";
    wrap.setAttribute("aria-labelledby", "charts-fee-burn-h");
    var h = document.createElement("h2");
    h.id = "charts-fee-burn-h";
    h.className = "visually-hidden";
    h.textContent = "Fee burn";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "fee-burn-glance-line";
    var tone = document.createElement("span");
    tone.className = "fee-burn-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Fees";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "fee-burn-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "fee-burn-glance-link";
    link.href = "/desk/ops#ops-fee-preset";
    link.textContent = "Ops fees →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Fee drag vs start and realized P&L beside charts — high (≥2% or fees>P&L) before chasing adds. Not a gate.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderStuckCapitalGlance(payload) {
    var glance = payload && payload.stuck_capital_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "stuck-capital-glance";
    wrap.setAttribute("aria-labelledby", "charts-stuck-h");
    var h = document.createElement("h2");
    h.id = "charts-stuck-h";
    h.className = "visually-hidden";
    h.textContent = "Stuck capital";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "stuck-capital-glance-line";
    var tone = document.createElement("span");
    tone.className = "stuck-capital-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Stuck";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "stuck-capital-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "stuck-capital-glance-link";
    link.href = "/desk/book";
    link.textContent = "Book →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Past min-hold underwater beside charts — capital trapped until TP/SL/trim. Not a gate.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderMinHoldLockGlance(payload) {
    var glance = payload && payload.min_hold_lock_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "min-hold-lock-glance";
    wrap.setAttribute("aria-labelledby", "charts-min-hold-lock-h");
    var h = document.createElement("h2");
    h.id = "charts-min-hold-lock-h";
    h.className = "visually-hidden";
    h.textContent = "Min-hold lock";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "min-hold-lock-glance-line";
    var tone = document.createElement("span");
    tone.className = "min-hold-lock-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Hold lock";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "min-hold-lock-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "min-hold-lock-glance-link";
    link.href = "/desk/ops#ops-min-hold";
    link.textContent = "Ops hold →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Lots still inside min-hold beside charts — cannot rotate/trim yet. Not a gate.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderPostmortemGlance(payload) {
    var glance = payload && payload.postmortem_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "postmortem-glance";
    wrap.setAttribute("aria-labelledby", "charts-post-h");
    var h = document.createElement("h2");
    h.id = "charts-post-h";
    h.className = "visually-hidden";
    h.textContent = "Last closed round";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "postmortem-glance-line";
    var tone = document.createElement("span");
    tone.className = "postmortem-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Exit";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "postmortem-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "postmortem-glance-link";
    link.href = "/desk/book#post-h";
    link.textContent = "Book rounds →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Newest FIFO exit beside charts — thesis on Book. No MAE/MFE. Not a gate.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }


  function renderNextBuyGlance(payload) {
    var glance = payload && payload.next_buy_glance;
    if (!glance || !glance.ready || !glance.line) return;
    var wrap = document.createElement("section");
    wrap.className = "next-buy-glance";
    wrap.setAttribute("aria-labelledby", "charts-size-h");
    var h = document.createElement("h2");
    h.id = "charts-size-h";
    h.className = "visually-hidden";
    h.textContent = "Next buy size";
    wrap.appendChild(h);
    var line = document.createElement("p");
    line.className = "next-buy-glance-line";
    var tone = document.createElement("span");
    tone.className = "next-buy-glance-tone " + (glance.tone || "flat");
    tone.textContent = "Size";
    line.appendChild(tone);
    var sep1 = document.createElement("span");
    sep1.className = "pretrade-sep";
    sep1.setAttribute("aria-hidden", "true");
    sep1.textContent = "·";
    line.appendChild(sep1);
    var body = document.createElement("span");
    body.className = "next-buy-glance-body";
    body.textContent = String(glance.line);
    line.appendChild(body);
    var sep2 = document.createElement("span");
    sep2.className = "pretrade-sep";
    sep2.setAttribute("aria-hidden", "true");
    sep2.textContent = "·";
    line.appendChild(sep2);
    var link = document.createElement("a");
    link.className = "next-buy-glance-link";
    link.href = "/desk";
    link.textContent = "Overview size →";
    line.appendChild(link);
    wrap.appendChild(line);
    var sub = document.createElement("p");
    sub.className = "sub";
    sub.textContent =
      "Suggested next-buy € beside charts — Overview keeps the full size block. Not a gate.";
    wrap.appendChild(sub);
    appendGlance(wrap);
  }

  function renderChartsPage(payload) {
    root.innerHTML = "";
    glanceMount = null;
    renderScanFreshness(payload);
    renderPretradeGlance(payload);
    renderNextBuyGlance(payload);
    renderSoftAllowGlance(payload);
    renderEntryGatesGlance(payload);
    renderCalmStreakGlance(payload);
    renderPromoteAbGlance(payload);
    renderBookPostureGlance(payload);
    renderBookRiskGlance(payload);

    /* MonsterDeveloper + xang1234: collapse long policy wall (parity with HTML screens). */
    var details = document.createElement("details");
    details.className = "policy-honesty";
    details.id = "policy-honesty";
    var summary = document.createElement("summary");
    summary.appendChild(document.createTextNode("Policy honesty "));
    var meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = "crypto · exits · AI · gates · fees";
    summary.appendChild(meta);
    details.appendChild(summary);
    var intro = document.createElement("p");
    intro.className = "sub";
    intro.textContent =
      "Display-only rules. Not new entry gates. Ops keeps the toggles.";
    details.appendChild(intro);
    root.appendChild(details);
    glanceMount = details;

    renderCryptoPolicyGlance(payload);
    renderExitPolicyGlance(payload);
    renderEarningsBlackoutGlance(payload);
    renderAiModeGlance(payload);
    renderAiRolesGlance(payload);
    renderAiDebateGlance(payload);
    renderAiValidateScopeGlance(payload);
    renderSessionGlance(payload);
    renderEquityHoursGlance(payload);
    renderBreakoutGuardGlance(payload);
    renderLossRotationGlance(payload);
    renderStaleRotationGlance(payload);
    renderJunkFilterGlance(payload);
    renderUniverseDiscoveryGlance(payload);
    renderAtrDisplayGlance(payload);
    renderEntrySlotsGlance(payload);
    renderPromoteContractGlance(payload);
    renderGateRolesGlance(payload);
    renderGateParamsGlance(payload);
    renderBookLimitsGlance(payload);
    renderRebuyCooldownGlance(payload);
    renderDailyLossGlance(payload);
    renderConcentrationGlance(payload);
    renderPostSlCooldownGlance(payload);
    renderLoopCadenceGlance(payload);
    renderFeeAllowanceGlance(payload);
    renderFeeBurnGlance(payload);
    renderStuckCapitalGlance(payload);
    renderMinHoldLockGlance(payload);
    renderPostmortemGlance(payload);

    glanceMount = null;
    renderBreadthGlance(payload);
    drawEquity(
      section(
        "Book equity path",
        "ch-eq",
        "Hover the path to read equity at each fill (cash + invested cost basis)."
      ),
      payload.equity
    );
    drawUnrealized(
      section(
        "Unrealized P&L",
        "ch-unreal",
        "Open-book mark minus cost basis over time (€ and % in the tip). No forecast."
      ),
      payload.unrealized || []
    );
    drawAllocation(section("Allocation", "ch-alloc"), payload.allocation);
    drawPrices(
      section(
        "Since your buy (avg cost = 100)",
        "ch-buy",
        "Open lots only — daily closes from entry vs avg cost. Dates on the axis + range below. No forecast."
      ),
      payload.from_buy || []
    );
    drawPrices(
      section(
        "Relative prices (~3 months, window start = 100)",
        "ch-px",
        "Same calendar window for comparison (not your fill). Dates on the axis + range below."
      ),
      payload.prices
    );
  }

  function drawUnrealSpark(series) {
    var el = document.getElementById("unreal-spark");
    if (!el || !series || series.length < 2) {
      if (el) el.classList.add("is-empty");
      return;
    }
    el.classList.remove("is-empty");
    el.innerHTML = "";
    var data = series.map(function (d) {
      return { t: new Date(d.t), v: +d.unrealized };
    });
    var last = data[data.length - 1];
    el.title =
      "Unrealized " +
      (last.v >= 0 ? "+" : "") +
      "€" +
      d3.format(",.2f")(last.v) +
      " · path since first fill";
    var width = Math.max(el.clientWidth || 160, 120);
    var height = 36;
    var x = d3
      .scaleTime()
      .domain(d3.extent(data, function (d) { return d.t; }))
      .range([2, width - 2]);
    var ext = d3.extent(data, function (d) { return d.v; });
    var y = d3
      .scaleLinear()
      .domain([Math.min(ext[0], 0), Math.max(ext[1], 0)])
      .nice()
      .range([height - 3, 3]);
    var stroke = last.v >= 0 ? cssVar("--up", "#7dcea0") : cssVar("--down", "#e07a5f");
    var svg = d3
      .select(el)
      .append("svg")
      .attr("viewBox", "0 0 " + width + " " + height)
      .attr("aria-hidden", "true");
    if (y.domain()[0] <= 0 && y.domain()[1] >= 0) {
      svg
        .append("line")
        .attr("x1", 0)
        .attr("x2", width)
        .attr("y1", y(0))
        .attr("y2", y(0))
        .attr("stroke", "rgba(232,239,230,0.25)")
        .attr("stroke-dasharray", "2 2");
    }
    svg
      .append("path")
      .datum(data)
      .attr("fill", "none")
      .attr("stroke", stroke)
      .attr("stroke-width", 1.6)
      .attr(
        "d",
        d3
          .line()
          .x(function (d) { return x(d.t); })
          .y(function (d) { return y(d.v); })
          .curve(d3.curveMonotoneX)
      );
  }

  function loadCharts(onOk, onErr) {
    fetch("/desk/api/charts", { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) throw new Error("charts HTTP " + r.status);
        return r.json();
      })
      .then(onOk)
      .catch(onErr || function () {});
  }

  var screen = document.body && document.body.getAttribute("data-screen");
  if (screen === "charts" && root) {
    loadCharts(renderChartsPage, function () {
      showError("Could not load chart data.");
    });
  } else if (screen === "book" && typeof d3 !== "undefined") {
    loadCharts(function (payload) {
      drawSparks(payload.from_buy || []);
    });
  } else if (screen === "overview" && typeof d3 !== "undefined") {
    loadCharts(function (payload) {
      drawUnrealSpark(payload.unrealized || []);
    });
  }
})();
