"""Render data/latest.json into docs/index.html.

docs/ because GitHub Pages serves a project site from / or /docs and nothing else.

The chart is drawn client-side: hover, the filters and the sortable table all need
it, and the axis rescales to whatever is on screen so a filtered selection never
sits squashed in the corner of a fixed frame. The table is server-rendered HTML,
so with scripting off you still get every number.

Every node is built with createElementNS / textContent - no innerHTML anywhere, so
a company name coming from Yahoo can never be parsed as markup.
"""

import html
import json
import os

# A name is called out once the two moves diverge by more than this many points.
# 10 is roughly the median absolute gap across the universe, so "In Line" means the
# two moves genuinely tracked each other rather than merely pointing the same way.
# It also puts NVDA (estimates +14.8%, price +3.8%, gap +11) on the right side of the
# line, which was the case that exposed the original sign-based model as wrong.
GAP_THRESHOLD_PP = 10.0

BANDS = {
    "behind": ("#82a8ca", "Price Behind"),   # estimates outran the price
    "inline": ("#6b7480", "In Line"),        # the two moved together
    "ahead":  ("#c98a6a", "Price Ahead"),    # price outran the estimates
}


def band(gap):
    """Classify on the DELTA between the two moves, not the sign of each.

    Sign-of-each-axis was the original model and it was wrong: it filed NVDA
    (estimates +14.8%, price +3.8%) alongside a name whose price had run 43% on a
    1.4% upgrade, because both were "up and up". Those are opposite situations.
    """
    if gap is None:
        return "inline"
    if gap >= GAP_THRESHOLD_PP:
        return "behind"
    if gap <= -GAP_THRESHOLD_PP:
        return "ahead"
    return "inline"


def nice_bound(vals, floor=5.0):
    """Symmetric axis bound, rounded out to something readable."""
    # pad the DATA, then apply the floor - padding the floor itself made an empty
    # universe round up to the next step (caught by tests/test_calc.py)
    m = max((abs(v) for v in vals), default=0.0) * 1.12
    m = max(m, floor)
    for step in (5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150):
        if m <= step:
            return float(step)
    return float(int(m / 25 + 1) * 25)


def mcap_band(bn):
    if bn is None:
        return "Unknown"
    if bn < 50:
        return "Under $50bn"
    if bn < 250:
        return "$50bn to $250bn"
    return "Over $250bn"


def build_rows(rows):
    out = []
    for r in rows:
        colour, label = BANDS[band(r["gap_pp"])]
        out.append(
            f'<tr><td class="tk">{html.escape(r["ticker"])}</td>'
            f'<td>{html.escape(r["name"])}</td>'
            f'<td class="sec">{html.escape(r["sector"])}</td>'
            f'<td class="n">{r["revision_pct"]:+.1f}%</td>'
            f'<td class="n">{r["price_chg_pct"]:+.1f}%</td>'
            f'<td class="n" style="color:{colour}"><b>{r["gap_pp"]:+.1f}</b></td>'
            f'<td class="n muted">{r["analysts"] or "-"}</td>'
            f'<td class="q" style="color:{colour}">{label}</td></tr>')
    return "\n".join(out)


def options(values, label):
    opts = "".join(f'<option value="{html.escape(v)}">{html.escape(v)}</option>'
                   for v in values)
    return f'<option value="">{label}</option>{opts}'


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Consensus Drift</title>
<meta name="description" content="Where analyst earnings estimates and share prices have moved apart, ranked by the size of the gap.">
<link rel="canonical" href="https://charlietrenorden.com/consensus-drift/">
<meta property="og:title" content="Consensus Drift">
<meta property="og:description" content="Where analyst earnings estimates and share prices have moved apart.">
<meta property="og:url" content="https://charlietrenorden.com/consensus-drift/">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='24' fill='%231a212b'/><path d='M72.5 37 A26 26 0 1 0 72.5 63' fill='none' stroke='%2382a8ca' stroke-width='13' stroke-linecap='round'/><circle cx='50' cy='50' r='6.5' fill='%2382a8ca'/></svg>">
<style>
  *,*::before,*::after{box-sizing:border-box}
  :root{--bg:#0f1319;--raised:#171c24;--ink:#e6e9ee;--soft:#8a94a3;--faint:#5d6675;
        --rule:#262d38;--accent:#82a8ca}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:400 17px/1.65 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
       -webkit-font-smoothing:antialiased}
  .wrap{max-width:1060px;margin:0 auto;padding:2.2rem 1.5rem 5rem}

  .bar{display:flex;align-items:center;justify-content:space-between;gap:1rem;margin-bottom:2.6rem}
  /* navigation, not a title - kept lighter than the page's own name */
  .home{font:500 13px/1 ui-sans-serif,system-ui,sans-serif;letter-spacing:.1em;
        text-transform:uppercase;color:var(--soft);text-decoration:none;
        display:inline-flex;align-items:center;gap:.5rem;transition:color .2s}
  .home:hover{color:var(--accent)}
  .home .back{color:var(--accent);font-size:14px}
  .mark{font:600 13px/1 ui-sans-serif,system-ui,sans-serif;letter-spacing:.16em;
        text-transform:uppercase;color:var(--ink)}

  h1{font-weight:400;font-size:clamp(1.9rem,3.6vw,2.5rem);line-height:1.1;
     letter-spacing:-.015em;margin:0 0 .8rem;max-width:20ch}
  .lede{font-size:1.05rem;color:var(--soft);max-width:60ch;margin:0}

  .meta-row{display:flex;flex-wrap:wrap;gap:.5rem;margin:1.6rem 0 0}
  .chip{font:500 12px/1 ui-sans-serif,system-ui,sans-serif;letter-spacing:.04em;
        color:var(--soft);background:var(--raised);border:1px solid var(--rule);
        border-radius:999px;padding:.52rem .8rem}
  .chip b{color:var(--ink);font-weight:600}

  .controls{display:flex;flex-wrap:wrap;gap:.6rem;margin:2.2rem 0 1rem;align-items:center}
  select,input[type=search]{font:500 13px/1 ui-sans-serif,system-ui,sans-serif;color:var(--ink);
        background:var(--raised);border:1px solid var(--rule);border-radius:7px;
        padding:.6rem .7rem;min-width:9.5rem}
  select:focus,input:focus{outline:2px solid var(--accent);outline-offset:1px}
  .reset{background:none;border:0;color:var(--faint);cursor:pointer;
         font:500 12.5px/1 ui-sans-serif,system-ui,sans-serif;padding:.6rem .2rem}
  .reset:hover{color:var(--accent)}

  figure{margin:0;background:var(--raised);border:1px solid var(--rule);
         border-radius:8px;padding:.6rem;position:relative}
  figure svg{display:block;width:100%;height:auto}
  circle.pt{cursor:pointer}
  #tip{position:absolute;pointer-events:none;opacity:0;transition:opacity .12s;
       background:#0b0e13;border:1px solid var(--rule);border-radius:7px;
       padding:.5rem .65rem;font:500 12.5px/1.5 ui-sans-serif,system-ui,sans-serif;
       color:var(--ink);white-space:nowrap;z-index:5;box-shadow:0 6px 20px rgba(0,0,0,.45)}
  #tip .t-sub{color:var(--soft);font-weight:400;display:block}

  .key{display:flex;flex-wrap:wrap;gap:1.3rem;margin:1.2rem 0 0;
       font:500 13px/1.4 ui-sans-serif,system-ui,sans-serif;color:var(--soft)}
  .key b{font-weight:600}

  h2{font-weight:400;font-size:1.5rem;letter-spacing:-.01em;margin:3.4rem 0 .4rem}
  .sub{color:var(--faint);font:400 14px/1.5 ui-sans-serif,system-ui,sans-serif;margin:0 0 .4rem}
  p{max-width:70ch;color:var(--soft)}

  table{width:100%;border-collapse:collapse;margin-top:1rem;
        font:400 14.5px/1.5 ui-sans-serif,system-ui,sans-serif}
  th{text-align:left;font:600 11.5px/1.3 ui-sans-serif,system-ui,sans-serif;letter-spacing:.11em;
     text-transform:uppercase;color:var(--faint);padding:0 .6rem .7rem;
     border-bottom:1px solid var(--rule);cursor:pointer;user-select:none;white-space:nowrap}
  th:hover{color:var(--soft)}
  th .ar{opacity:0;margin-left:.25rem}
  th.asc .ar,th.desc .ar{opacity:1;color:var(--accent)}
  th.desc .ar{display:inline-block;transform:rotate(180deg)}
  td{padding:.58rem .6rem;border-bottom:1px solid var(--rule);color:var(--ink)}
  td.n{text-align:right;font-family:ui-monospace,Consolas,monospace;font-size:13px}
  td.tk{font-family:ui-monospace,Consolas,monospace;font-size:12.5px;color:var(--soft)}
  td.sec{color:var(--soft);font-size:13.5px}
  td.q{font-size:13px;white-space:nowrap}
  td.muted{color:var(--faint)}
  th.n{text-align:right}
  tr.hide{display:none}
  #empty{display:none;color:var(--faint);padding:1.3rem .2rem;
         font:400 14px/1.5 ui-sans-serif,system-ui,sans-serif}

  .foot{margin-top:3.4rem;padding-top:1.3rem;border-top:1px solid var(--rule);
        color:var(--faint);font:400 13px/1.7 ui-sans-serif,system-ui,sans-serif;max-width:70ch}
  .foot a{color:var(--accent)}
  @media (max-width:700px){ td,th{padding-left:.3rem;padding-right:.3rem}
    td.sec,th.sec-h{display:none} }
</style>
</head>
<body>
<div class="wrap">
  <div class="bar">
    <a class="home" href="https://charlietrenorden.com/"><span class="back">&larr;</span>Other projects</a>
    <span class="mark">Consensus Drift</span>
  </div>

  <h1>__HEADLINE__</h1>
  <p class="lede">__LEDE__</p>

  <div class="meta-row">
    <span class="chip"><b>__N__</b> names</span>
    <span class="chip">90-day window</span>
    <span class="chip">Updated <b>__DATE__</b></span>
  </div>

  <div class="controls">
    <select id="f-market" aria-label="Market">__MARKETS__</select>
    <select id="f-sector" aria-label="Sector">__SECTORS__</select>
    <select id="f-band" aria-label="Company size">__BANDS__</select>
    <select id="f-gap" aria-label="Gap">__GAPS__</select>
    <input type="search" id="f-text" placeholder="Search name or ticker" aria-label="Search">
    <button class="reset" id="reset" type="button">Reset</button>
  </div>

  <figure>
    <div id="chart"></div>
    <div id="tip"></div>
  </figure>

  <div class="key">
    <span><b style="color:#82a8ca">Price Behind</b> &middot; Estimates rose more than the price</span>
    <span><b style="color:#c98a6a">Price Ahead</b> &middot; Price rose more than the estimates</span>
    <span><b style="color:#6b7480">In Line</b> &middot; Within __THRESH__ points</span>
  </div>

  <h2>Full List</h2>
  <p class="sub" id="count"></p>
  <table>
    <thead><tr>
      <th data-k="ticker">Ticker<span class="ar">&#9650;</span></th>
      <th data-k="name">Name<span class="ar">&#9650;</span></th>
      <th data-k="sector" class="sec-h">Sector<span class="ar">&#9650;</span></th>
      <th data-k="rev" class="n">Estimates<span class="ar">&#9650;</span></th>
      <th data-k="price" class="n">Price<span class="ar">&#9650;</span></th>
      <th data-k="gap" class="n">Gap (pp)<span class="ar">&#9650;</span></th>
      <th data-k="analysts" class="n">Analysts<span class="ar">&#9650;</span></th>
      <th data-k="bandlabel">Reading<span class="ar">&#9650;</span></th>
    </tr></thead>
    <tbody id="tbody">
__ROWS__
    </tbody>
  </table>
  <p id="empty">Nothing matches those filters.</p>

  <h2>Method</h2>
  <p>The vertical axis is the change in consensus FY2 earnings per share over 90 days,
  taken from Yahoo's published estimate history rather than reconstructed. The horizontal
  axis is total price change over the same window. The <em>gap</em> is the difference
  between the two in percentage points, and it is what the colouring and the default sort
  key off, on the basis that a 15% upgrade against a 4% price move is a different
  situation from a 1% upgrade against a 43% move.</p>
  <p>Revisions divide by the absolute prior estimate, so a loss-maker narrowing from
  -1.00 to -0.50 registers as an upgrade. A name drops out when Yahoo carries no
  comparable figure 90 days back, which it reports as <code>0.0</code> rather than as
  missing.__DROPNOTE__ Estimates are opinions, and a revision records only that analysts
  changed their minds.</p>

  <p class="foot">Built by <a href="https://charlietrenorden.com/">Charlie Trenorden</a>.
  Data from Yahoo Finance, refreshed weekly.</p>
</div>

<script id="rows" type="application/json">__JSON__</script>
<script>
(function () {
  var DATA = JSON.parse(document.getElementById("rows").textContent);
  var BANDS = __BANDCFG__;
  var THRESH = __THRESHNUM__;
  var NS = "http://www.w3.org/2000/svg";
  var W = 940, H = 620, PAD = {l: 74, r: 26, t: 30, b: 62};

  var chart = document.getElementById("chart");
  var tip = document.getElementById("tip");
  var tbody = document.getElementById("tbody");
  var els = {
    market: document.getElementById("f-market"),
    sector: document.getElementById("f-sector"),
    band:   document.getElementById("f-band"),
    gap:    document.getElementById("f-gap"),
    text:   document.getElementById("f-text")
  };

  function svgEl(tag, attrs, text) {
    var e = document.createElementNS(NS, tag), k;
    for (k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }

  function bound(vals) {
    var m = 0, i;
    for (i = 0; i < vals.length; i++) m = Math.max(m, Math.abs(vals[i]));
    m = Math.max(m * 1.12, 5);
    var steps = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150];
    for (i = 0; i < steps.length; i++) if (m <= steps[i]) return steps[i];
    return Math.ceil(m / 25) * 25;
  }

  function sign(v, d) { return (v > 0 ? "+" : "") + v.toFixed(d == null ? 1 : d); }

  function matches(r) {
    if (els.market.value && r.market !== els.market.value) return false;
    if (els.sector.value && r.sector !== els.sector.value) return false;
    if (els.band.value && r.band !== els.band.value) return false;
    if (els.gap.value && r.bandkey !== els.gap.value) return false;
    var q = els.text.value.trim().toLowerCase();
    if (q && (r.ticker + " " + r.name + " " + r.sector).toLowerCase().indexOf(q) < 0) return false;
    return true;
  }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  function draw(rows) {
    clear(chart);
    if (!rows.length) return;

    var all = rows.map(function (r) { return r.price; }).concat(rows.map(function (r) { return r.rev; }));
    var b = bound(all);                       // one scale on both axes so the 45 degree line means something
    var x0 = PAD.l, x1 = W - PAD.r, y0 = PAD.t, y1 = H - PAD.b;
    var cx = x0 + (x1 - x0) / 2, cy = y0 + (y1 - y0) / 2;
    var px = function (v) { return x0 + (v + b) / (2 * b) * (x1 - x0); };
    var py = function (v) { return y1 - (v + b) / (2 * b) * (y1 - y0); };

    var svg = svgEl("svg", {viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": "Earnings estimate change against share price change"});

    // band either side of the 45 degree line, where the two moves agree
    var poly = [[px(-b), py(-b + THRESH)], [px(b - THRESH), py(b)],
                [px(b), py(b - THRESH)], [px(-b + THRESH), py(-b)]];
    svg.appendChild(svgEl("polygon", {
      points: poly.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" "),
      fill: "#6b7480", opacity: 0.07}));

    [-0.5, 0.5].forEach(function (f) {
      svg.appendChild(svgEl("line", {x1: px(b * f), y1: y0, x2: px(b * f), y2: y1, stroke: "#262d38"}));
      svg.appendChild(svgEl("line", {x1: x0, y1: py(b * f), x2: x1, y2: py(b * f), stroke: "#262d38"}));
    });
    svg.appendChild(svgEl("line", {x1: cx, y1: y0, x2: cx, y2: y1, stroke: "#39424f"}));
    svg.appendChild(svgEl("line", {x1: x0, y1: cy, x2: x1, y2: cy, stroke: "#39424f"}));
    // the line where the estimate move equals the price move
    svg.appendChild(svgEl("line", {x1: px(-b), y1: py(-b), x2: px(b), y2: py(b),
                                   stroke: "#5d6675", "stroke-width": 1.2, "stroke-dasharray": "5 5"}));

    var LAB = {"font-family": "ui-sans-serif,system-ui,sans-serif", "font-size": 12.5,
               "letter-spacing": "0.11em"};
    function tag(x, y, anchor, fill, text) {
      var a = {}, k;
      for (k in LAB) a[k] = LAB[k];
      a.x = x; a.y = y; a["text-anchor"] = anchor; a.fill = fill;
      svg.appendChild(svgEl("text", a, text));
    }
    tag(x0 + 12, y0 + 20, "start", "#82a8ca", "PRICE BEHIND");
    tag(x1 - 12, y1 - 10, "end", "#c98a6a", "PRICE AHEAD");

    var TICK = {"font-family": "ui-monospace,Consolas,monospace", "font-size": 11, fill: "#5d6675"};
    [-1, -0.5, 0.5, 1].forEach(function (f) {
      var v = b * f, a = {}, k;
      for (k in TICK) a[k] = TICK[k];
      svg.appendChild(svgEl("text", Object.assign({}, a, {x: px(v), y: y1 + 18, "text-anchor": "middle"}),
                            sign(v, 0) + "%"));
      svg.appendChild(svgEl("text", Object.assign({}, a, {x: x0 - 10, y: py(v) + 4, "text-anchor": "end"}),
                            sign(v, 0) + "%"));
    });

    var AT = {"font-family": "ui-sans-serif,system-ui,sans-serif", "font-size": 12.5, fill: "#8a94a3"};
    svg.appendChild(svgEl("text", Object.assign({}, AT, {x: cx, y: H - 16, "text-anchor": "middle"}),
                          "Share price change, 90 days"));
    svg.appendChild(svgEl("text", Object.assign({}, AT, {
      transform: "translate(20," + cy + ") rotate(-90)", "text-anchor": "middle"}),
      "Earnings estimate change, 90 days"));

    rows.forEach(function (r) {
      var c = svgEl("circle", {"class": "pt", cx: px(r.price).toFixed(1), cy: py(r.rev).toFixed(1),
                               r: 5.2, fill: BANDS[r.bandkey][0], "fill-opacity": 0.85,
                               stroke: "#0f1319", "stroke-width": 1});
      c.addEventListener("mouseenter", function () {
        c.setAttribute("r", 8);
        showTip(r, svg, px(r.price), py(r.rev));
      });
      c.addEventListener("mouseleave", function () {
        c.setAttribute("r", 5.2);
        tip.style.opacity = 0;
      });
      svg.appendChild(c);
    });
    chart.appendChild(svg);
  }

  function showTip(r, svg, sx, sy) {
    clear(tip);
    var head = document.createElement("b");
    head.textContent = r.name;
    tip.appendChild(head);
    tip.appendChild(document.createTextNode("  " + r.ticker));

    var l1 = document.createElement("span");
    l1.className = "t-sub";
    l1.textContent = "Estimates " + sign(r.rev) + "%   Price " + sign(r.price) + "%";
    tip.appendChild(l1);

    var l2 = document.createElement("span");
    l2.className = "t-sub";
    l2.textContent = "Gap " + sign(r.gap) + " pp";
    tip.appendChild(l2);

    var box = svg.getBoundingClientRect();
    var fb = chart.parentNode.getBoundingClientRect();
    var scale = box.width / W;
    tip.style.opacity = 1;
    var left = box.left - fb.left + sx * scale + 14;
    var top = box.top - fb.top + sy * scale - 12;
    if (left + tip.offsetWidth > fb.width - 8) left -= tip.offsetWidth + 28;
    tip.style.left = Math.max(6, left) + "px";
    tip.style.top = Math.max(6, top) + "px";
  }

  /* ---- sortable table ---------------------------------------------------- */
  var sortKey = "gap", sortDir = -1;
  var VAL = {
    ticker: function (r) { return r.ticker; },
    name: function (r) { return r.name; },
    sector: function (r) { return r.sector; },
    rev: function (r) { return r.rev; },
    price: function (r) { return r.price; },
    gap: function (r) { return r.gap; },
    analysts: function (r) { return r.analysts == null ? -1 : r.analysts; },
    bandlabel: function (r) { return BANDS[r.bandkey][1]; }
  };

  var rowFor = {};
  Array.prototype.forEach.call(tbody.querySelectorAll("tr"), function (tr) {
    rowFor[tr.querySelector(".tk").textContent] = tr;
  });

  function order(rows) {
    var f = VAL[sortKey];
    return rows.slice().sort(function (a, b) {
      var x = f(a), y = f(b);
      if (typeof x === "string") return x.localeCompare(y) * sortDir;
      return (x - y) * sortDir;
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll("th[data-k]"), function (th) {
    th.addEventListener("click", function () {
      var k = th.getAttribute("data-k");
      if (k === sortKey) { sortDir = -sortDir; } else { sortKey = k; sortDir = -1; }
      apply();
    });
  });

  function apply() {
    var shown = DATA.filter(matches);
    draw(shown);

    var ordered = order(shown);
    var seen = {};
    ordered.forEach(function (r) {
      seen[r.ticker] = 1;
      tbody.appendChild(rowFor[r.ticker]);          // appendChild moves, so this reorders
      rowFor[r.ticker].classList.remove("hide");
    });
    Object.keys(rowFor).forEach(function (t) {
      if (!seen[t]) rowFor[t].classList.add("hide");
    });

    Array.prototype.forEach.call(document.querySelectorAll("th[data-k]"), function (th) {
      th.classList.remove("asc", "desc");
      if (th.getAttribute("data-k") === sortKey) th.classList.add(sortDir === 1 ? "asc" : "desc");
    });

    document.getElementById("count").textContent =
      (shown.length === DATA.length ? "All " + DATA.length + " names"
                                    : shown.length + " of " + DATA.length + " names") +
      ", sorted by " + sortKey + ".";
    document.getElementById("empty").style.display = shown.length ? "none" : "block";
  }

  Object.keys(els).forEach(function (k) {
    els[k].addEventListener(els[k].tagName === "SELECT" ? "change" : "input", apply);
  });
  document.getElementById("reset").addEventListener("click", function () {
    els.market.value = ""; els.sector.value = ""; els.band.value = "";
    els.gap.value = ""; els.text.value = "";
    sortKey = "gap"; sortDir = -1;
    apply();
  });
  apply();
})();
</script>
</body>
</html>
"""


def main():
    data = json.load(open("data/latest.json", encoding="utf-8"))
    rows = data["names"]
    dropped = data.get("dropped", [])

    compact = [{
        "ticker": r["ticker"], "name": r["name"], "market": r["market"],
        "sector": r["sector"], "band": mcap_band(r.get("mcap_bn")),
        "rev": r["revision_pct"], "price": r["price_chg_pct"], "gap": r["gap_pp"],
        "analysts": r.get("analysts"), "bandkey": band(r["gap_pp"]),
    } for r in rows]

    markets = sorted({r["market"] for r in rows})
    sectors = sorted({r["sector"] for r in rows})
    present = {mcap_band(r.get("mcap_bn")) for r in rows}
    sizes = [b for b in ["Under $50bn", "$50bn to $250bn", "Over $250bn", "Unknown"]
             if b in present]
    gap_opts = [BANDS[k][1] for k in ("behind", "ahead", "inline")]
    gap_select = ('<option value="">Any reading</option>'
                  + "".join(f'<option value="{k}">{BANDS[k][1]}</option>'
                            for k in ("behind", "ahead", "inline")))

    dropnote = ""
    if dropped:
        listed = ", ".join(html.escape(d["ticker"]) for d in dropped)
        dropnote = f" This week that is {listed}."

    page = (TEMPLATE
            .replace("__HEADLINE__", "Where price and estimates have moved apart.")
            .replace("__LEDE__", "Every name below, ranked by how far its earnings "
                                 "estimates and its share price have diverged over 90 days.")
            .replace("__N__", str(len(rows)))
            .replace("__DATE__", data["generated_utc"][:10])
            .replace("__MARKETS__", options(markets, "All markets"))
            .replace("__SECTORS__", options(sectors, "All sectors"))
            .replace("__BANDS__", options(sizes, "Any size"))
            .replace("__GAPS__", gap_select)
            .replace("__THRESHNUM__", str(GAP_THRESHOLD_PP))
            .replace("__THRESH__", str(int(GAP_THRESHOLD_PP)))
            .replace("__ROWS__", build_rows(rows))
            .replace("__DROPNOTE__", dropnote)
            .replace("__JSON__", json.dumps(compact, separators=(",", ":")))
            .replace("__BANDCFG__", json.dumps(BANDS)))

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    counts = {}
    for r in compact:
        counts[r["bandkey"]] = counts.get(r["bandkey"], 0) + 1
    print(f"built docs/index.html - {len(rows)} names, {len(dropped)} dropped, "
          f"{len(sectors)} sectors | " + ", ".join(f"{BANDS[k][1]}: {v}" for k, v in counts.items()))
    assert gap_opts  # options are derived, not hand-listed


if __name__ == "__main__":
    main()
