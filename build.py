"""Render data/latest.json into docs/index.html.

docs/ because GitHub Pages serves a project site from / or /docs and nothing else.

The chart is drawn client-side: hover-to-identify and the market / sector / size
filters both need it, and the axis rescales to whatever is on screen so a filtered
selection never sits squashed in the corner of a fixed frame. The table is
server-rendered HTML, so with scripting off you still get every number.

The client builds the SVG with createElementNS and the tooltip with textContent -
no innerHTML anywhere, so company names from Yahoo can never be parsed as markup.
"""

import html
import json
import os

QUADRANTS = {
    "unearned":   "#c98a6a",
    "earned":     "#7fae8f",
    "overlooked": "#82a8ca",
    "confirmed":  "#6b7480",
}
QUAD_LABEL = {
    "unearned": "Unearned", "earned": "Earned",
    "overlooked": "Overlooked", "confirmed": "Confirmed",
}


def nice_bound(vals, floor=5.0):
    """Symmetric axis bound, rounded out to something readable."""
    # pad the DATA, then apply the floor - padding the floor itself made an empty
    # universe round up to the next step (caught by tests/test_calc.py)
    m = max((abs(v) for v in vals), default=0.0) * 1.12
    m = max(m, floor)
    for step in (5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100):
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
        colour = QUADRANTS[r["quadrant"]]
        out.append(
            f'<tr><td class="tk">{html.escape(r["ticker"])}</td>'
            f'<td>{html.escape(r["name"])}</td>'
            f'<td class="sec">{html.escape(r["sector"])}</td>'
            f'<td class="n" style="color:{colour}">{r["revision_pct"]:+.2f}%</td>'
            f'<td class="n">{r["price_chg_pct"]:+.2f}%</td>'
            f'<td class="n muted">{r["analysts"] or "-"}</td>'
            f'<td class="q" style="color:{colour}">{QUAD_LABEL[r["quadrant"]]}</td></tr>')
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
<title>__TITLE__</title>
<meta name="description" content="Analyst earnings estimates plotted against share price. The interesting names are where the two disagree.">
<link rel="canonical" href="https://charlietrenorden.com/consensus-drift/">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="Analyst estimates against share price. The interesting names are where the two disagree.">
<meta property="og:url" content="https://charlietrenorden.com/consensus-drift/">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='24' fill='%231a212b'/><path d='M72.5 37 A26 26 0 1 0 72.5 63' fill='none' stroke='%2382a8ca' stroke-width='13' stroke-linecap='round'/><circle cx='50' cy='50' r='6.5' fill='%2382a8ca'/></svg>">
<style>
  *,*::before,*::after{box-sizing:border-box}
  :root{--bg:#0f1319;--raised:#171c24;--ink:#e6e9ee;--soft:#8a94a3;--faint:#5d6675;
        --rule:#262d38;--accent:#82a8ca}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:400 17px/1.65 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
       -webkit-font-smoothing:antialiased}
  .wrap{max-width:1040px;margin:0 auto;padding:2.2rem 1.5rem 5rem}

  .bar{display:flex;align-items:center;justify-content:space-between;gap:1rem;margin-bottom:3rem}
  /* navigation, not a title - kept lighter than the page's own name */
  .home{font:500 13px/1 ui-sans-serif,system-ui,sans-serif;letter-spacing:.1em;
        text-transform:uppercase;color:var(--soft);text-decoration:none;
        display:inline-flex;align-items:center;gap:.5rem;transition:color .2s}
  .home:hover{color:var(--accent)}
  .home .back{color:var(--accent);font-size:14px}

  h1{font-weight:400;font-size:clamp(2.7rem,7.4vw,4.4rem);line-height:1.02;
     letter-spacing:-.02em;margin:0 0 1.1rem;max-width:14ch}
  .lede{font-size:1.16rem;color:var(--soft);max-width:52ch;margin:0}

  .meta-row{display:flex;flex-wrap:wrap;gap:.5rem;margin:1.9rem 0 0}
  .chip{font:500 12px/1 ui-sans-serif,system-ui,sans-serif;letter-spacing:.04em;
        color:var(--soft);background:var(--raised);border:1px solid var(--rule);
        border-radius:999px;padding:.52rem .8rem}
  .chip b{color:var(--ink);font-weight:600}

  .controls{display:flex;flex-wrap:wrap;gap:.6rem;margin:2.4rem 0 1rem;align-items:center}
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

  h2{font-weight:400;font-size:1.55rem;letter-spacing:-.01em;margin:3.6rem 0 .4rem}
  .sub{color:var(--faint);font:400 14px/1.5 ui-sans-serif,system-ui,sans-serif;margin:0 0 .4rem}
  p{max-width:66ch;color:var(--soft)}

  table{width:100%;border-collapse:collapse;margin-top:1rem;
        font:400 14.5px/1.5 ui-sans-serif,system-ui,sans-serif}
  th{text-align:left;font:600 11.5px/1 ui-sans-serif,system-ui,sans-serif;letter-spacing:.13em;
     text-transform:uppercase;color:var(--faint);padding:0 .7rem .7rem;
     border-bottom:1px solid var(--rule)}
  td{padding:.62rem .7rem;border-bottom:1px solid var(--rule);color:var(--ink)}
  td.n{text-align:right;font-family:ui-monospace,Consolas,monospace;font-size:13.5px}
  td.tk{font-family:ui-monospace,Consolas,monospace;font-size:13px;color:var(--soft)}
  td.sec{color:var(--soft);font-size:13.5px}
  td.q{font-size:13px}
  td.muted{color:var(--faint)}
  th.n{text-align:right}
  tr.hide{display:none}
  #empty{display:none;color:var(--faint);padding:1.3rem .2rem;
         font:400 14px/1.5 ui-sans-serif,system-ui,sans-serif}

  .foot{margin-top:3.6rem;padding-top:1.3rem;border-top:1px solid var(--rule);
        color:var(--faint);font:400 13px/1.7 ui-sans-serif,system-ui,sans-serif;max-width:70ch}
  .foot a{color:var(--accent)}
  @media (max-width:640px){ td,th{padding-left:.35rem;padding-right:.35rem}
    td.sec,th:nth-child(3){display:none} }
</style>
</head>
<body>
<div class="wrap">
  <div class="bar">
    <a class="home" href="https://charlietrenorden.com/"><span class="back">&larr;</span>Other projects</a>
  </div>

  <h1>__HEADLINE__</h1>
  <p class="lede">__LEDE__</p>

  <div class="meta-row">
    <span class="chip"><b>__N__</b> names</span>
    <span class="chip">90-day window</span>
    <span class="chip">Updated <b>__DATE__</b></span>
    <span class="chip">Yahoo Finance</span>
  </div>

  <div class="controls">
    <select id="f-market" aria-label="Market">__MARKETS__</select>
    <select id="f-sector" aria-label="Sector">__SECTORS__</select>
    <select id="f-band" aria-label="Company size">__BANDS__</select>
    <input type="search" id="f-text" placeholder="Search name or ticker" aria-label="Search">
    <button class="reset" id="reset" type="button">Reset</button>
  </div>

  <figure>
    <div id="chart"></div>
    <div id="tip"></div>
  </figure>

  <div class="key">
    <span><b style="color:#c98a6a">Unearned</b> &middot; Price up, estimates down</span>
    <span><b style="color:#82a8ca">Overlooked</b> &middot; Estimates up, price down</span>
    <span><b style="color:#7fae8f">Earned</b> &middot; Both up</span>
    <span><b style="color:#6b7480">Confirmed</b> &middot; Both down</span>
  </div>

  <h2>The Full List</h2>
  <p class="sub" id="count"></p>
  <table>
    <thead><tr><th>Ticker</th><th>Name</th><th>Sector</th><th class="n">EPS Revision</th>
    <th class="n">Price</th><th class="n">Analysts</th><th>Quadrant</th></tr></thead>
    <tbody id="tbody">
__ROWS__
    </tbody>
  </table>
  <p id="empty">Nothing matches those filters.</p>

  <h2>How It Works</h2>
  <p>Analysts publish an earnings forecast for each company and quietly revise it as the
  year goes on. This compares where that forecast sits now against where it sat three
  months ago, and puts it beside what the share price did over the same stretch.</p>
  <p>Both numbers come from Yahoo Finance. __DROPNOTE__</p>

  <p class="foot">Built by <a href="https://charlietrenorden.com/">Charlie Trenorden</a>.
  Refreshed weekly. Not advice.</p>
</div>

<script id="rows" type="application/json">__JSON__</script>
<script>
(function () {
  var DATA = JSON.parse(document.getElementById("rows").textContent);
  var COL = __COLOURS__;
  var LABEL = __QLABELS__;
  var NS = "http://www.w3.org/2000/svg";
  var W = 940, H = 600, PAD = {l: 74, r: 26, t: 30, b: 62};

  var chart = document.getElementById("chart");
  var tip = document.getElementById("tip");
  var els = {
    market: document.getElementById("f-market"),
    sector: document.getElementById("f-sector"),
    band:   document.getElementById("f-band"),
    text:   document.getElementById("f-text")
  };

  /* every node is built with createElementNS / textContent - nothing is ever parsed
     as markup, so a company name from Yahoo cannot become an element */
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
    var steps = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100];
    for (i = 0; i < steps.length; i++) if (m <= steps[i]) return steps[i];
    return Math.ceil(m / 25) * 25;
  }

  function sign(v) { return (v > 0 ? "+" : "") + v.toFixed(1) + "%"; }

  function matches(r) {
    if (els.market.value && r.market !== els.market.value) return false;
    if (els.sector.value && r.sector !== els.sector.value) return false;
    if (els.band.value && r.band !== els.band.value) return false;
    var q = els.text.value.trim().toLowerCase();
    if (q && (r.ticker + " " + r.name + " " + r.sector).toLowerCase().indexOf(q) < 0) return false;
    return true;
  }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  function draw(rows) {
    clear(chart);
    if (!rows.length) return;

    var xb = bound(rows.map(function (r) { return r.price; }));
    var yb = bound(rows.map(function (r) { return r.rev; }));
    var x0 = PAD.l, x1 = W - PAD.r, y0 = PAD.t, y1 = H - PAD.b;
    var cx = x0 + (x1 - x0) / 2, cy = y0 + (y1 - y0) / 2;
    var px = function (v) { return x0 + (v + xb) / (2 * xb) * (x1 - x0); };
    var py = function (v) { return y1 - (v + yb) / (2 * yb) * (y1 - y0); };

    var svg = svgEl("svg", {
      viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": "Earnings estimate change against share price change"
    });

    [[cx, y0, x1 - cx, cy - y0, "#7fae8f", 0.05],
     [cx, cy, x1 - cx, y1 - cy, "#c98a6a", 0.09],
     [x0, y0, cx - x0, cy - y0, "#82a8ca", 0.09]].forEach(function (q) {
      svg.appendChild(svgEl("rect", {x: q[0], y: q[1], width: q[2], height: q[3],
                                     fill: q[4], opacity: q[5]}));
    });

    [-0.5, 0.5].forEach(function (f) {
      svg.appendChild(svgEl("line", {x1: px(xb * f), y1: y0, x2: px(xb * f), y2: y1, stroke: "#262d38"}));
      svg.appendChild(svgEl("line", {x1: x0, y1: py(yb * f), x2: x1, y2: py(yb * f), stroke: "#262d38"}));
    });
    svg.appendChild(svgEl("line", {x1: cx, y1: y0, x2: cx, y2: y1, stroke: "#5d6675", "stroke-width": 1.4}));
    svg.appendChild(svgEl("line", {x1: x0, y1: cy, x2: x1, y2: cy, stroke: "#5d6675", "stroke-width": 1.4}));

    var LAB = {"font-family": "ui-sans-serif,system-ui,sans-serif", "font-size": 12.5,
               "letter-spacing": "0.11em"};
    function corner(x, y, anchor, fill, text) {
      var a = {}, k;
      for (k in LAB) a[k] = LAB[k];
      a.x = x; a.y = y; a["text-anchor"] = anchor; a.fill = fill;
      svg.appendChild(svgEl("text", a, text));
    }
    corner(x1 - 10, y0 + 20, "end", "#7fae8f", "EARNED");
    corner(x1 - 10, y1 - 10, "end", "#c98a6a", "UNEARNED");
    corner(x0 + 10, y0 + 20, "start", "#82a8ca", "OVERLOOKED");
    corner(x0 + 10, y1 - 10, "start", "#6b7480", "CONFIRMED");

    var TICK = {"font-family": "ui-monospace,Consolas,monospace", "font-size": 11, fill: "#5d6675"};
    [-1, -0.5, 0.5, 1].forEach(function (f) {
      var v = xb * f, a = {}, k;
      for (k in TICK) a[k] = TICK[k];
      svg.appendChild(svgEl("text", Object.assign({}, a, {x: px(v), y: y1 + 18, "text-anchor": "middle"}),
                            (v > 0 ? "+" : "") + v.toFixed(0) + "%"));
      v = yb * f;
      svg.appendChild(svgEl("text", Object.assign({}, a, {x: x0 - 10, y: py(v) + 4, "text-anchor": "end"}),
                            (v > 0 ? "+" : "") + v.toFixed(0) + "%"));
    });

    var AT = {"font-family": "ui-sans-serif,system-ui,sans-serif", "font-size": 12.5, fill: "#8a94a3"};
    svg.appendChild(svgEl("text", Object.assign({}, AT, {x: cx, y: H - 16, "text-anchor": "middle"}),
                          "Share price change, 90 days"));
    svg.appendChild(svgEl("text", Object.assign({}, AT, {
      transform: "translate(20," + cy + ") rotate(-90)", "text-anchor": "middle"}),
      "Earnings estimate change, 90 days"));

    rows.forEach(function (r) {
      var c = svgEl("circle", {"class": "pt", cx: px(r.price).toFixed(1), cy: py(r.rev).toFixed(1),
                               r: 5.5, fill: COL[r.quadrant], "fill-opacity": 0.85,
                               stroke: "#0f1319", "stroke-width": 1});
      c.addEventListener("mouseenter", function () {
        c.setAttribute("r", 8);
        showTip(r, svg, px(r.price), py(r.rev));
      });
      c.addEventListener("mouseleave", function () {
        c.setAttribute("r", 5.5);
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
    tip.appendChild(document.createTextNode(" " + r.ticker));

    var l1 = document.createElement("span");
    l1.className = "t-sub";
    l1.textContent = "Estimates " + sign(r.rev) + "  ·  Price " + sign(r.price);
    tip.appendChild(l1);

    var l2 = document.createElement("span");
    l2.className = "t-sub";
    l2.textContent = LABEL[r.quadrant] + "  ·  " + r.sector;
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

  function apply() {
    var shown = DATA.filter(matches);
    draw(shown);
    var keep = {};
    shown.forEach(function (r) { keep[r.ticker] = 1; });
    Array.prototype.forEach.call(document.querySelectorAll("#tbody tr"), function (tr) {
      tr.classList.toggle("hide", !keep[tr.querySelector(".tk").textContent]);
    });
    document.getElementById("count").textContent =
      shown.length === DATA.length
        ? "All " + DATA.length + " names, biggest downgrades first."
        : shown.length + " of " + DATA.length + " names.";
    document.getElementById("empty").style.display = shown.length ? "none" : "block";
  }

  Object.keys(els).forEach(function (k) {
    els[k].addEventListener(els[k].tagName === "SELECT" ? "change" : "input", apply);
  });
  document.getElementById("reset").addEventListener("click", function () {
    els.market.value = ""; els.sector.value = ""; els.band.value = ""; els.text.value = "";
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
        "rev": r["revision_pct"], "price": r["price_chg_pct"],
        "quadrant": r["quadrant"],
    } for r in rows]

    markets = sorted({r["market"] for r in rows})
    sectors = sorted({r["sector"] for r in rows})
    present = {mcap_band(r.get("mcap_bn")) for r in rows}
    bands = [b for b in ["Under $50bn", "$50bn to $250bn", "Over $250bn", "Unknown"]
             if b in present]

    dropnote = ""
    if dropped:
        listed = ", ".join(html.escape(d["ticker"]) for d in dropped)
        dropnote = ("A name is left out when Yahoo has no comparable figure from three "
                    f"months back, which this week means {listed}.")

    page = (TEMPLATE
            .replace("__TITLE__", "Consensus Drift")
            .replace("__HEADLINE__", "Where price and estimates disagree.")
            .replace("__LEDE__", "Analysts move their earnings forecasts slowly. When the "
                                 "share price has gone the other way, the gap is worth a look.")
            .replace("__N__", str(len(rows)))
            .replace("__DATE__", data["generated_utc"][:10])
            .replace("__MARKETS__", options(markets, "All markets"))
            .replace("__SECTORS__", options(sectors, "All sectors"))
            .replace("__BANDS__", options(bands, "Any size"))
            .replace("__ROWS__", build_rows(rows))
            .replace("__DROPNOTE__", dropnote)
            .replace("__JSON__", json.dumps(compact, separators=(",", ":")))
            .replace("__COLOURS__", json.dumps(QUADRANTS))
            .replace("__QLABELS__", json.dumps(QUAD_LABEL))
            )

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    print(f"built docs/index.html - {len(rows)} plotted, {len(dropped)} dropped, "
          f"{len(sectors)} sectors, {len(markets)} markets, {len(bands)} size bands")


if __name__ == "__main__":
    main()
