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

  function appendHtmlLegend(mount, panels, color) {
    var list = document.createElement("ul");
    list.className = "chart-legend";
    list.setAttribute("aria-label", "Series legend");
    panels.forEach(function (p) {
      var li = document.createElement("li");
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

  function drawPrices(mount, panels) {
    if (!panels || !panels.length) {
      mount.innerHTML =
        "<p class='empty'>No price history yet (check network / DESK_CHART_LIVE).</p>";
      return;
    }
    var width = mount.clientWidth || 640;
    var height = 300;
    var margin = { top: 12, right: 16, bottom: 32, left: 44 };

    var color = d3
      .scaleOrdinal()
      .domain(panels.map(function (p) { return p.symbol; }))
      .range(COLORS);

    // HTML flex-wrap legend — never pack fixed-width SVG labels (they overlap).
    appendHtmlLegend(mount, panels, color);

    var svg = d3
      .select(mount)
      .append("svg")
      .attr("viewBox", "0 0 " + width + " " + height)
      .attr("role", "img")
      .attr("aria-label", "Relative price performance");

    var all = [];
    panels.forEach(function (p) {
      p.points.forEach(function (pt) {
        all.push({ t: new Date(pt.t), rebased: +pt.rebased, symbol: p.symbol });
      });
    });

    var x = d3
      .scaleTime()
      .domain(d3.extent(all, function (d) { return d.t; }))
      .range([margin.left, width - margin.right]);
    var y = d3
      .scaleLinear()
      .domain(d3.extent(all, function (d) { return d.rebased; }))
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
          .tickFormat(function (v) { return d3.format(".0f")(v); })
          .tickSizeOuter(0)
      );

    svg
      .append("line")
      .attr("x1", margin.left)
      .attr("x2", width - margin.right)
      .attr("y1", y(100))
      .attr("y2", y(100))
      .attr("stroke", "rgba(232,239,230,0.2)")
      .attr("stroke-dasharray", "4 4");

    var line = d3
      .line()
      .x(function (d) { return x(new Date(d.t)); })
      .y(function (d) { return y(d.rebased); })
      .curve(d3.curveMonotoneX);

    panels.forEach(function (p) {
      svg
        .append("path")
        .datum(p.points)
        .attr("fill", "none")
        .attr("stroke", color(p.symbol))
        .attr("stroke-width", 2)
        .attr("d", line)
        .append("title")
        .text(p.symbol + (p.name ? " — " + p.name : "") + " · " + pctLabel(p.change_pct));
    });

    panels.forEach(function (p) {
      var last = p.points[p.points.length - 1];
      if (!last) return;
      svg
        .append("circle")
        .attr("cx", x(new Date(last.t)))
        .attr("cy", y(last.rebased))
        .attr("r", 3)
        .attr("fill", color(p.symbol));
    });
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
