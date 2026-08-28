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

# The price-target view was removed on 07/08/2026 after measuring it. Implied upside
# is (target - price) / price, so with targets slow to move a rising price compresses
# upside by arithmetic: corr(upside, 90d price change) = -0.537 across 838 names, with
# mean upside falling monotonically across all ten price-change deciles (+31.8% to
# +4.0%). The earnings view has corr = -0.090, i.e. genuinely independent axes, which
# is why its gap carries information and the target one did not.
#
# fetch.py still stores target_price every week. Once data/history.csv spans 90 days
# (~13 runs from 07/08/2026) a real target CHANGE becomes available for every name, and
# that belongs on the same footing as the earnings view - diagonal, gap and all.
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


# One list, used BOTH to label a row and to order the dropdown. These were two
# separate copies of the same four strings until 07/08/2026, when relabelling them
# US$ in one place silently emptied the size filter on the live page - the build
# printed no error and the tests were green, because nothing compares the two.
MCAP_BANDS = ["Under US$50bn", "US$50bn to US$250bn", "Over US$250bn", "Unknown"]


def mcap_band(bn):
    if bn is None:
        return MCAP_BANDS[3]
    if bn < 50:
        return MCAP_BANDS[0]
    if bn < 250:
        return MCAP_BANDS[1]
    return MCAP_BANDS[2]


def country_of(market):
    """"Australia (ASX)" -> "Australia".

    The full label is 30 characters at its longest, which is far too wide for a
    table cell, so the cell carries the country and the full label rides along in
    a title attribute. The column FILTER still matches the whole string, so both
    "Australia" and "ASX" find the same rows.
    """
    return market.split(" (")[0]


def fmt_mcap(bn):
    """Market cap in billions, at a precision that stays readable across three
    orders of magnitude - 4,120 down to 0.6."""
    if bn is None:
        return "-"
    if bn >= 100:
        return f"{bn:,.0f}"
    if bn >= 10:
        return f"{bn:.0f}"
    return f"{bn:.1f}"


def _fmt(v, suffix=""):
    return "-" if v is None else f"{v:+.1f}{suffix}"


def build_rows(rows):
    out = []
    for r in rows:
        colour, label = BANDS[band(r["gap_pp"])]
        out.append(
            f'<tr><td class="tk">{html.escape(r["ticker"])}</td>'
            f'<td class="nm" title="{html.escape(r["name"])}">'
            f'<span>{html.escape(r["name"])}</span></td>'
            f'<td class="sec">{html.escape(r["sector"])}</td>'
            f'<td class="mkt" title="{html.escape(r["market"])}">'
            f'{html.escape(country_of(r["market"]))}</td>'
            f'<td class="n">{r["revision_pct"]:+.1f}%</td>'
            f'<td class="n">{r["price_chg_pct"]:+.1f}%</td>'
            f'<td class="n" style="color:{colour}"><b>{r["gap_pp"]:+.1f}</b></td>'
            f'<td class="n mc">{fmt_mcap(r.get("mcap_bn"))}</td>'
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
<meta name="description" content="Analyst earnings estimates plotted against what the share price actually did, across __NMKT__ equity markets.">
<link rel="canonical" href="https://charlietrenorden.com/consensus-drift/">
<meta property="og:title" content="Consensus Drift">
<meta property="og:description" content="Analyst earnings estimates plotted against what the share price actually did, across __NMKT__ equity markets.">
<meta property="og:image" content="https://charlietrenorden.com/assets/og-card.png">
<meta property="og:image:width" content="2400">
<meta property="og:image:height" content="1260">
<meta property="og:image:alt" content="Consensus Drift - where price and earnings estimates have moved apart">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://charlietrenorden.com/assets/og-card.png">
<meta property="og:url" content="https://charlietrenorden.com/consensus-drift/">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="icon" href="favicon-192.png" type="image/png" sizes="192x192">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<style>
  *,*::before,*::after{box-sizing:border-box}
  :root{--bg:#0f1319;--raised:#171c24;--ink:#e6e9ee;--soft:#8a94a3;--faint:#5d6675;
        --rule:#262d38;--accent:#82a8ca}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:400 17px/1.65 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
       -webkit-font-smoothing:antialiased}
  .wrap{max-width:1060px;margin:0 auto;padding:2.2rem 1.5rem 5rem}

  /* Wordmark hard left, back-link hard right, and nothing in between: two items
     under space-between is the whole layout. The previous version was a
     three-column bar meant to centre the wordmark, with an empty .bar-pad on the
     right to balance the link on the left - but .mark had no `order` and so sorted
     ahead of both, which put the wordmark in the LEFT column centred within it and
     left the pad as 152px of dead space holding the link in off the right edge.
     DOM order now matches reading order, so no `order` is needed at all. */
  .bar{display:flex;align-items:baseline;justify-content:space-between;
       gap:1rem;margin-bottom:2.6rem}
  .mark{font:300 30px/1 ui-sans-serif,system-ui,sans-serif;letter-spacing:.30em;
        text-transform:uppercase;color:var(--ink)}
  /* navigation, not a title - kept lighter than the page's own name */
  .home{font:500 13px/1 ui-sans-serif,system-ui,sans-serif;letter-spacing:.1em;
        text-transform:uppercase;color:var(--soft);text-decoration:none;
        white-space:nowrap;
        display:inline-flex;align-items:center;gap:.5rem;transition:color .2s}
  .home:hover{color:var(--accent)}
  .home .back{color:var(--accent);font-size:14px}
  @media (max-width:720px){ .mark{font-size:18px;letter-spacing:.2em} }
  /* below this the wordmark wrapped to two lines and crowded the back-link,
     because both were sharing one row */
  @media (max-width:560px){
     The back-link sits top RIGHT on every project page, and `space-between`
     only delivers that while it SHARES a line with something. Once the
     header wraps or stacks on a phone the link gets a line of its own and
     falls back to the left, which is how three sites ended up on the
     opposite side from the other seventeen. A wrapped element needs a new
     alignment, not the old one.
    .bar{flex-direction:column;align-items:stretch;gap:.5rem}
    .bar .home{align-self:flex-end}
    .mark{font-size:20px}
  }

  h1{font-weight:400;font-size:clamp(1.7rem,3vw,2.15rem);line-height:1.1;
     letter-spacing:-.015em;margin:0 0 1.05rem;max-width:26ch}
  .lede{font-size:1.05rem;line-height:1.6;color:var(--soft);max-width:60ch;margin:0}

  /* these three were boxed pills, which put a third row of bordered widgets
     directly above the five selects and made the whole header read as chrome.
     Plain text, one line, dot-separated - the numbers still stand out. */
  .meta-row{font:400 12.5px/1.5 ui-sans-serif,system-ui,sans-serif;letter-spacing:.02em;
            color:var(--faint);margin:1.7rem 0 0}
  .meta-row b{color:var(--soft);font-weight:600}
  .meta-row span+span::before{content:"·";margin:0 .55rem;color:var(--rule)}

  .controls{display:flex;flex-wrap:wrap;gap:.6rem;margin:1.25rem 0 1.5rem;align-items:center}
  /* a flex wrap left the five selects at ragged widths, 1-2 per row; a grid
     lines them up */
  @media (max-width:560px){
    .controls{display:grid;grid-template-columns:1fr 1fr;gap:.5rem}
    .controls select,.controls input{width:100%;min-width:0}
    /* the fifth select leaves an empty cell beside it - put Reset there rather than
       stranding it alone on a row of its own */
    .controls #f-text{grid-column:1 / -1;order:1}
  }
  select,input[type=search]{font:500 13px/1 ui-sans-serif,system-ui,sans-serif;color:var(--ink);
        background:var(--raised);border:1px solid var(--rule);border-radius:7px;
        padding:.55rem .65rem;min-width:8.4rem}
  /* a select sizes itself to its LONGEST option, so "Communication Services" was
     making the sector box half as wide again as the rest and pushing the search
     field onto a second row of boxes. Cap it - native selects truncate cleanly. */
  .controls select{max-width:8.9rem}
  /* the market labels are "Country (Exchange)" and run to ~30 characters, so this
     one needs more room than the rest or the closed state truncates mid-word */
  .controls #f-market{max-width:16rem}
  .controls #f-text{flex:1 1 8rem;min-width:8rem;max-width:14rem}
  /* Reset is dead chrome while nothing is filtered - only show it once it does
     something. Kept in the DOM (not display:none in JS) so the row doesn't jump. */
  .reset[hidden]{display:none}
  /* the two caps above are a desktop single-row fix and must not survive into the
     mobile grid, where the cells set their own widths */
  @media (max-width:560px){
    .controls select{max-width:none}
    .controls #f-text{max-width:none;flex:none}
  }
  select:focus,input:focus{outline:2px solid var(--accent);outline-offset:1px}
  /* lives on the meta line, not in the control row: at these label lengths
     ("United States (NYSE & Nasdaq)") the five selects and the search field
     already fill the row, and Reset was wrapping to a line of its own */
  .reset{background:none;border:0;color:var(--faint);cursor:pointer;
         font:inherit;padding:0;margin-left:.9rem;text-decoration:underline;
         text-underline-offset:3px}
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
  .key[hidden]{display:none}   /* display:flex above beats the hidden attribute */

  h2{font-weight:400;font-size:1.5rem;letter-spacing:-.01em;margin:3.4rem 0 .4rem}
  .sub{color:var(--faint);font:400 14px/1.5 ui-sans-serif,system-ui,sans-serif;margin:0 0 .4rem}
  p{max-width:70ch;color:var(--soft)}
  .method{font-size:14.5px;line-height:1.62;color:var(--soft);max-width:72ch}

  /* Without this the 591px min-content table made the BODY 615px wide at a
     375px viewport, so the whole page panned sideways instead of the table
     scrolling. Verify with document.documentElement.scrollWidth <= innerWidth. */
  .tablewrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
  table{width:100%;border-collapse:collapse;margin-top:1rem;
        font:400 14.5px/1.5 ui-sans-serif,system-ui,sans-serif}
  th{text-align:left;font:600 11.5px/1.3 ui-sans-serif,system-ui,sans-serif;letter-spacing:.11em;
     text-transform:uppercase;color:var(--faint);padding:0 .45rem .55rem;
     border-bottom:1px solid var(--rule);cursor:pointer;user-select:none;white-space:nowrap}
  th:hover{color:var(--soft)}
  th .ar{opacity:0;margin-left:.25rem}
  th.asc .ar,th.desc .ar{opacity:1;color:var(--accent)}
  th.desc .ar{display:inline-block;transform:rotate(180deg)}
  td{padding:.55rem .45rem;border-bottom:1px solid var(--rule);color:var(--ink);
     height:2.5rem}
  td.n{text-align:right;font-family:ui-monospace,Consolas,monospace;font-size:13px}
  td.tk{font-family:ui-monospace,Consolas,monospace;font-size:12.5px;color:var(--soft)}
  td.sec,td.mkt{color:var(--soft);font-size:13.5px}
  td.mkt{white-space:nowrap}
  tr.filters select{width:100%;min-width:0;font:400 12.5px/1 ui-sans-serif,system-ui,sans-serif;
        background:var(--bg);border:1px solid var(--rule);border-radius:5px;padding:.3rem .35rem}
  td.q{font-size:13px;white-space:nowrap}
  td.muted{color:var(--faint)}
  th.n{text-align:right}
  tr.hide{display:none}
  tr.filters td{padding:.42rem .45rem;border-bottom:1px solid var(--rule)}
  tr.filters input{width:100%;min-width:0;font:400 12.5px/1 ui-sans-serif,system-ui,sans-serif;
        color:var(--ink);background:#10141b;border:1px solid var(--rule);border-radius:5px;
        padding:.4rem .45rem}
  tr.filters input::placeholder{color:#4a525f}
  #empty{display:none;color:var(--faint);padding:1.3rem .2rem;
         font:400 14px/1.5 ui-sans-serif,system-ui,sans-serif}

  .pager{display:flex;align-items:center;gap:1rem;margin-top:1.1rem;
         flex-wrap:wrap}
  .pager.top{margin:1.4rem 0 0}
  .pager{
         font:500 13px/1 ui-sans-serif,system-ui,sans-serif;color:var(--soft)}
  .pager button{background:var(--raised);border:1px solid var(--rule);border-radius:7px;
        color:var(--ink);padding:.55rem .85rem;cursor:pointer;
        font:500 13px/1 ui-sans-serif,system-ui,sans-serif}
  .pager button:hover:enabled{border-color:var(--accent)}
  .pager button:disabled{color:var(--faint);cursor:default;opacity:.5}
  .foot{margin-top:3.4rem;padding-top:1.3rem;border-top:1px solid var(--rule);
        color:var(--faint);font:400 13px/1.7 ui-sans-serif,system-ui,sans-serif;max-width:70ch}
  .foot a{color:var(--accent)}
  /* Drop a column at each width where the remaining ones stop fitting, so the
     table never needs its horizontal scrollbar. The thresholds are the measured
     min-content widths plus the 48px the page takes either side: all ten
     columns 976px, without Cap 864, without Sector 755, without Market 643. */
  @media (max-width:1023px){ td.mc,th.mc-h{display:none} }
  @media (max-width:911px){ td.sec,th.sec-h{display:none} }
  @media (max-width:802px){ td.mkt,th.mkt-h{display:none} }
  @media (max-width:700px){ td,th{padding-left:.3rem;padding-right:.3rem} }
  /* Name is the one column that cannot be dropped - a table of bare tickers is not
     readable - but it is also the only one that can be arbitrarily long, and
     "Semiconductor Manufacturing International Corporation" wrapped to FOUR lines at
     390px. Its row was then four times the height of its neighbours, which breaks the
     scan down the Gap column that the whole table exists for. One line and an
     ellipsis below the breakpoint; the full name rides along in the title, the same
     way the market cell already carries its full label. */
  @media (max-width:640px){
    td.nm span{display:block;overflow:hidden;text-overflow:ellipsis;
               white-space:nowrap;max-width:8.5rem}
  }
</style>
<!-- Cloudflare Web Analytics. Single braces: this page template is a plain
     string with __TOKEN__-style placeholders, NOT an f-string, so doubling them
     leaves literal {{ }} in the output. Verified in docs/index.html. -->
<script>/* Analytics, gated. Two kinds of visitor are not an audience and never load it: anyone who has opted out with ?nostats=1, and automation, since navigator.webdriver is the one signal true for Playwright, Puppeteer and Selenium alike. Inline and dependency-free on purpose - served from the Worker, a bad deploy there would stop analytics on every site. See site-stats/beacon. */(function(){try{var X="ct.nostats",C="ct_nostats",D=";path=/;domain=.charlietrenorden.com",q=location.search,out=false;if(q.indexOf("nostats=1")>-1){try{localStorage.setItem(X,"1")}catch(e){}document.cookie=C+"=1"+D+";max-age=63072000;samesite=lax";}if(q.indexOf("nostats=0")>-1){try{localStorage.removeItem(X)}catch(e){}document.cookie=C+"="+D+";max-age=0";}try{out=!!localStorage.getItem(X)}catch(e){}if(!out)out=document.cookie.indexOf(C+"=1")>-1;if(out||navigator.webdriver)return;var d=document,s;s=d.createElement("script");s.defer=true;s.src="https://static.cloudflareinsights.com/beacon.min.js";s.setAttribute("data-cf-beacon",'{"token": "32b821209b5441a08df42ccf61c9e6c2"}');d.head.appendChild(s);s=d.createElement("script");s.defer=true;s.src="https://beacon.charlietrenorden.com/b.js";d.head.appendChild(s);}catch(e){}})();</script>
</head>
<body>
<div class="wrap">
  <div class="bar">
    <span class="mark">Consensus Drift</span>
    <a class="home" href="https://charlietrenorden.com/"><span class="back">&larr;</span>&nbsp;Other projects</a>
  </div>

  <h1>__HEADLINE__</h1>
  <p class="lede">__LEDE__</p>

  <div class="meta-row">
    <span><b>__N__</b> names</span>
    <span>90-day window</span>
    <span>updated <b>__DATE__</b></span>
    <button class="reset" id="reset" type="button" hidden>Clear filters</button>
  </div>

  <div class="controls">
    <select id="f-market" aria-label="Market">__MARKETS__</select>
    <select id="f-sector" aria-label="Sector">__SECTORS__</select>
    <select id="f-band" aria-label="Company size">__BANDS__</select>
    <select id="f-gap" aria-label="Gap">__GAPS__</select>
    <select id="f-cov" aria-label="Analyst coverage">__COVER__</select>
    <input type="search" id="f-text" placeholder="Name or ticker" aria-label="Search by name or ticker">
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

  <p class="sub" id="count" hidden></p>
  <div class="pager top" id="pager-top">
    <button type="button" data-nav="prev">&larr; Previous</button>
    <span data-info></span>
    <button type="button" data-nav="next">Next &rarr;</button>
  </div>
  <div class="tablewrap">
  <table>
    <thead><tr>
      <th data-k="ticker">Ticker<span class="ar">&#9650;</span></th>
      <th data-k="name">Name<span class="ar">&#9650;</span></th>
      <th data-k="sector" class="sec-h">Sector<span class="ar">&#9650;</span></th>
      <th data-k="market" class="mkt-h">Market<span class="ar">&#9650;</span></th>
      <th data-k="rev" class="n">Estimates<span class="ar">&#9650;</span></th>
      <th data-k="price" class="n">Price<span class="ar">&#9650;</span></th>
      <th data-k="gap" class="n">Gap (pp)<span class="ar">&#9650;</span></th>
      <th data-k="mcap" class="n mc-h">Cap (US$bn)<span class="ar">&#9650;</span></th>
      <th data-k="analysts" class="n">Analysts<span class="ar">&#9650;</span></th>
      <th data-k="bandlabel">Reading<span class="ar">&#9650;</span></th>
    </tr>
    <tr class="filters">
      <td><input id="c-ticker" type="search" placeholder="filter" aria-label="Filter ticker"></td>
      <td><input id="c-name" type="search" placeholder="filter" aria-label="Filter name"></td>
      <td class="sec"><input id="c-sector" type="search" placeholder="filter" aria-label="Filter sector"></td>
      <td class="mkt"><input id="c-market" type="search" placeholder="filter" aria-label="Filter market - matches country or exchange"></td>
      <td class="n"><input id="c-rev" type="text" inputmode="decimal" placeholder="min |%|" aria-label="Minimum absolute estimate change"></td>
      <td class="n"><input id="c-price" type="text" inputmode="decimal" placeholder="min |%|" aria-label="Minimum absolute price change"></td>
      <td class="n"><input id="c-gap" type="text" inputmode="decimal" placeholder="min |pp|" aria-label="Minimum absolute gap"></td>
      <td class="n mc"><input id="c-mcap" type="text" inputmode="decimal" placeholder="min US$bn" aria-label="Minimum market cap in US$ billions"></td>
      <td class="n"><input id="c-analysts" type="text" inputmode="numeric" placeholder="min" aria-label="Minimum analysts"></td>
      <td><select id="c-band" aria-label="Filter reading">__READINGS__</select></td>
    </tr></thead>
    <tbody id="tbody">
__ROWS__
    </tbody>
  </table>
  </div>
  <p id="empty">Nothing matches those filters.</p>
  <div class="pager" id="pager-bottom">
    <button type="button" data-nav="prev">&larr; Previous</button>
    <span data-info></span>
    <button type="button" data-nav="next">Next &rarr;</button>
  </div>

  <h2>Method</h2>
  <p class="method">Sell-side analysts publish consensus earnings forecasts for the coming
  financial year and revise them as the year progresses. The vertical axis shows the 90-day
  change for these estimates. The horizontal axis shows total share price movement over the
  same period.</p>
  <p class="method">Estimate and price data sourced from Yahoo Finance.__DROPNOTE__ Names
  whose moves fall outside the plotted range are shown as hollow markers on the chart.
  Market capitalisations are converted to US dollars at the latest spot rate.</p>

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
  var W = 940, H = 640, PAD = {l: 74, r: 26, t: 46, b: 78};

  // The chart is one viewBox scaled to fit its container, so on a phone an
  // 11-unit tick label renders at about 4px. K grows the type in viewBox units
  // to hold the RENDERED size roughly steady, and the padding grows with it so
  // the bigger labels still fit their gutters. K is 1 at desktop width, which
  // reproduces the original constants exactly.
  // The captions need real estate rather than a particular type size, so this is
  // decided on the width itself. Expressed in K it moved silently the one time K was
  // retuned, and 768px went from clean to two overlapping labels.
  function roomForCaptions() {
    return (chart.clientWidth || W) >= 620;
  }

  function typeScale() {
    var w = chart.clientWidth || W;
    // 900, not 700: at 700 an 11-unit tick still reached the reader at about 8px on
    // a 320px phone, which is under the floor for anything a reader has to read.
    // Measured against the rendered height, not the declared size - in a scaled
    // viewBox the declared size tells you nothing.
    return Math.min(3.0, Math.max(1, 900 / w));
  }

  var chart = document.getElementById("chart");
  var tip = document.getElementById("tip");
  var tbody = document.getElementById("tbody");
  var els = {
    market: document.getElementById("f-market"),
    sector: document.getElementById("f-sector"),
    band:   document.getElementById("f-band"),
    gap:    document.getElementById("f-gap"),
    cov:    document.getElementById("f-cov"),
    text:   document.getElementById("f-text")
  };
  // per-column filters in the table head: substring on the text columns, minimum
  // absolute value on the numeric ones
  var cols = {
    ticker: document.getElementById("c-ticker"),
    name: document.getElementById("c-name"),
    sector: document.getElementById("c-sector"),
    market: document.getElementById("c-market"),
    bandlabel: document.getElementById("c-band"),
    rev: document.getElementById("c-rev"),
    price: document.getElementById("c-price"),
    gap: document.getElementById("c-gap"),
    mcap: document.getElementById("c-mcap"),
    analysts: document.getElementById("c-analysts")
  };

  // Narrowing the window hides a column and its filter control with it, so a
  // value typed while wide would go on filtering with nothing on screen to undo
  // it. Ignore those rather than clear them - widen again and they come back.
  // Read once per apply, not once per row.
  var colLive = {};
  function readColLive() {
    for (var k in cols) {
      if (Object.prototype.hasOwnProperty.call(cols, k)) {
        colLive[k] = cols[k].offsetParent !== null;
      }
    }
  }

  function colMatch(r) {
    var t;
    for (var k in cols) {
      if (!Object.prototype.hasOwnProperty.call(cols, k)) continue;
      if (colLive[k] === false) continue;
      var v = cols[k].value.trim();
      if (!v) continue;
      if (k === "bandlabel") {
        // a select of the three fixed readings, so exact match, not substring
        if (BANDS[r.bandkey][1] !== v) return false;
      } else if (k === "ticker" || k === "name" || k === "sector" || k === "market") {
        if (String(r[k]).toLowerCase().indexOf(v.toLowerCase()) < 0) return false;
      } else {
        var min = parseFloat(v);
        if (isNaN(min)) continue;
        // analysts and mcap are LEVELS, so a missing one must fail a minimum
        // rather than pass it; the rest are magnitudes of a change.
        if (k === "analysts" || k === "mcap") t = r[k] == null ? -1 : r[k];
        else t = Math.abs(r[k]);
        if (t < min) return false;
      }
    }
    return true;
  }

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

  function yOf(r)    { return r.rev; }
  function bandOf(r) { return r.bandkey; }

  // Match from the START of the ticker or of a word in the name or sector, never from
  // the middle. This box was a plain substring search until 28/08/2026, which meant
  // "AMD" also returned Camden Property Trust and "ON" returned every name containing
  // Constellation, Regeneron or Capstone. It matters more now that Shortfall and DCF
  // Studio hand a company over through it by ?q=: an exact ticker must land on one row.
  // Same rule as Shortfall's lookup, deliberately - one behaviour across the estate.
  function named(r, q) {
    if (r.ticker.toLowerCase().indexOf(q) === 0) return true;
    var words = (r.name + " " + r.sector).toLowerCase().split(/[^a-z0-9.]+/);
    for (var i = 0; i < words.length; i++) {
      if (words[i].indexOf(q) === 0) return true;
    }
    return false;
  }

  function matches(r) {
    if (els.market.value && r.market !== els.market.value) return false;
    if (els.sector.value && r.sector !== els.sector.value) return false;
    if (els.band.value && r.band !== els.band.value) return false;
    if (els.gap.value && r.bandkey !== els.gap.value) return false;
    if (els.cov.value && (r.analysts == null || r.analysts < +els.cov.value)) return false;
    var q = els.text.value.trim().toLowerCase();
    if (q && !named(r, q)) return false;
    return colMatch(r);
  }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  function draw(rows) {
    clear(chart);
    if (!rows.length) return;

    // scale to the 98th percentile, not the maximum: a handful of names whose
    // estimates flipped from profit to loss run to several hundred percent and would
    // squash everything else into the middle. Outliers are pinned to the frame edge
    // and drawn hollow so they read as off-scale rather than as real positions.
    var all = rows.map(function (r) { return Math.abs(r.price); })
                  .concat(rows.map(function (r) { return Math.abs(yOf(r)); }))
                  .sort(function (a, c) { return a - c; });
    var b = bound([all[Math.floor(all.length * 0.98)] || 5]);

    // Bringing an off-scale name into frame by clamping each axis separately CHANGED
    // its gap, so a blue dot could land inside the grey band and contradict its own
    // colour (Liontown: price -55.7 clamped to -50 while estimates stayed -40.7, so a
    // +15pp gap displayed as +9.3pp). The gap is constant along the 45 degree line, so
    // slide the point down that diagonal instead - position moves, gap does not.
    function place(x, y) {
      var t = 0;
      if (Math.max(x, y) > b) t = Math.max(x, y) - b;
      else if (Math.min(x, y) < -b) t = Math.min(x, y) + b;
      var nx = x - t, ny = y - t;
      // a gap wider than the whole frame cannot be shown faithfully; corner it
      return [Math.max(-b, Math.min(b, nx)), Math.max(-b, Math.min(b, ny))];
    }
    var K = typeScale();
    PAD = {l: 30 + 44 * K, r: 12 + 14 * K, t: 26 + 20 * K, b: 40 + 38 * K};
    var x0 = PAD.l, x1 = W - PAD.r, y0 = PAD.t, y1 = H - PAD.b;
    var cx = x0 + (x1 - x0) / 2, cy = y0 + (y1 - y0) / 2;
    var px = function (v) { return x0 + (v + b) / (2 * b) * (x1 - x0); };
    var py = function (v) { return y1 - (v + b) / (2 * b) * (y1 - y0); };

    var svg = svgEl("svg", {viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": "Earnings estimate change against share price change"});

    // band either side of the 45 degree line, where the two moves agree.
    // Drawn well beyond the frame and clipped to the plot, so it runs edge to edge
    // instead of stopping short in the corners.
    var defs = svgEl("defs", {});
    var clip = svgEl("clipPath", {id: "plot"});
    clip.appendChild(svgEl("rect", {x: x0, y: y0, width: x1 - x0, height: y1 - y0}));
    defs.appendChild(clip);
    svg.appendChild(defs);

    var E = b * 3;                                   // far outside the visible range
    var poly = [[px(-E), py(-E + THRESH)], [px(E), py(E + THRESH)],
                [px(E), py(E - THRESH)], [px(-E), py(-E - THRESH)]];
    svg.appendChild(svgEl("polygon", {
      points: poly.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" "),
      fill: "#6b7480", opacity: 0.07, "clip-path": "url(#plot)"}));

    [-0.5, 0.5].forEach(function (f) {
      svg.appendChild(svgEl("line", {x1: px(b * f), y1: y0, x2: px(b * f), y2: y1, stroke: "#262d38"}));
      svg.appendChild(svgEl("line", {x1: x0, y1: py(b * f), x2: x1, y2: py(b * f), stroke: "#262d38"}));
    });
    svg.appendChild(svgEl("line", {x1: cx, y1: y0, x2: cx, y2: y1, stroke: "#39424f"}));
    svg.appendChild(svgEl("line", {x1: x0, y1: cy, x2: x1, y2: cy, stroke: "#39424f"}));
    // the line where the estimate move equals the price move
    svg.appendChild(svgEl("line", {x1: x0, y1: y1, x2: x1, y2: y0,
                                   stroke: "#5d6675", "stroke-width": 1.2, "stroke-dasharray": "5 5"}));

    var LAB = {"font-family": "ui-sans-serif,system-ui,sans-serif", "font-size": 12.5 * K,
               "letter-spacing": "0.11em"};
    function tag(x, y, anchor, fill, text) {
      var a = {}, k;
      for (k in LAB) a[k] = LAB[k];
      a.x = x; a.y = y; a["text-anchor"] = anchor; a.fill = fill;
      svg.appendChild(svgEl("text", a, text));
    }
    // above and below the frame, not inside it - they were colliding with the data
      // Both captions come off once the type has grown past about half again. There
      // is no room for them in a fixed 940-unit frame at that size - pushed clear of
      // the tick labels they land on the axis title instead - and nothing is lost,
      // because the page prints both of them in full sentences directly underneath
      // the chart. A label that does not fit is deleted, not shuffled.
      if (roomForCaptions()) {
        tag(x0, y0 - 6 - 6 * K, "start", "#82a8ca", "PRICE BEHIND");
        tag(x1, y1 + 8 + 31 * K, "end", "#c98a6a", "PRICE AHEAD");
      }


    var TICK = {"font-family": "ui-monospace,Consolas,monospace", "font-size": 11 * K, fill: "#5d6675"};
    [-1, -0.5, 0.5, 1].forEach(function (f) {
      var v = b * f, a = {}, k;
      for (k in TICK) a[k] = TICK[k];
      svg.appendChild(svgEl("text", Object.assign({}, a, {x: px(v), y: y1 + 8 + 10 * K,
                            "text-anchor": f === -1 ? "start" : f === 1 ? "end" : "middle"}),
                            sign(v, 0) + "%"));
      // The bottom-left corner carries the same number twice, once per axis, and
      // once the type grows they overprint: "-50%" over "-50%". The x axis keeps it,
      // because that is the axis a reader is scanning along.
      {
        svg.appendChild(svgEl("text", Object.assign({}, a, {x: x0 - 4 - 6 * K, y: py(v) + 4 * K, "text-anchor": "end"}),
                              sign(v, 0) + "%"));
      }
    });

    var AT = {"font-family": "ui-sans-serif,system-ui,sans-serif", "font-size": 12.5 * K, fill: "#8a94a3"};
    svg.appendChild(svgEl("text", Object.assign({}, AT, {x: cx, y: H - 6 - 10 * K, "text-anchor": "middle"}),
                          "Share price change, 90 days"));
    svg.appendChild(svgEl("text", Object.assign({}, AT, {
      transform: "translate(" + (10 + 14 * K) + "," + cy + ") rotate(-90)", "text-anchor": "middle"}),
      "Earnings estimate change, 90 days"));

    var drawn = [];
    rows.forEach(function (r) {
      var off = Math.abs(r.price) > b || Math.abs(yOf(r)) > b;
      var pos = place(r.price, yOf(r));
      var c = svgEl("circle", {"class": "pt", cx: px(pos[0]).toFixed(1),
                               cy: py(pos[1]).toFixed(1),
                               r: (5.2 * Math.max(1, K * 0.72)).toFixed(2),
                               fill: off ? "none" : BANDS[bandOf(r)][0],
                               "fill-opacity": 0.85,
                               stroke: off ? BANDS[bandOf(r)][0] : "#0f1319",
                               "stroke-width": off ? 1.6 : 1});
      c.__row = r; c.__x = px(pos[0]); c.__y = py(pos[1]);
      svg.appendChild(c);
      drawn.push(c);
    });

    // One handler for the whole plot, resolving to the nearest point. Per-circle
    // mouseenter handed the tooltip back and forth between overlapping neighbours on
    // every pixel of movement, which is what made it strobe.
    var current = null;
    svg.addEventListener("mousemove", function (ev) {
      var box = svg.getBoundingClientRect();
      var scale = W / box.width;
      var mx = (ev.clientX - box.left) * scale, my = (ev.clientY - box.top) * scale;
      var best = null, bestD = 14 * 14;            // only within a sensible radius
      for (var i = 0; i < drawn.length; i++) {
        var dx = drawn[i].__x - mx, dy = drawn[i].__y - my, d = dx * dx + dy * dy;
        if (d < bestD) { bestD = d; best = drawn[i]; }
      }
      if (best === current) return;                // nothing changed - leave it alone
      if (current) current.setAttribute("r", 5.2);
      current = best;
      if (!best) { tip.style.opacity = 0; return; }
      best.setAttribute("r", 8);
      showTip(best.__row, svg, best.__x, best.__y);
    });
    svg.addEventListener("mouseleave", function () {
      if (current) current.setAttribute("r", 5.2);
      current = null;
      tip.style.opacity = 0;
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
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var left = box.left - fb.left + sx * scale + 14;
    var top = box.top - fb.top + sy * scale - 12;
    // flip rather than let it hang off the edge, then keep it off the corner captions
    if (left + w > fb.width - 8) left -= w + 28;
    if (top + h > fb.height - 8) top -= h - 10;
    tip.style.left = Math.max(6, Math.min(left, fb.width - w - 6)) + "px";
    tip.style.top = Math.max(6, top) + "px";
  }

  /* ---- sortable table ---------------------------------------------------- */
  var sortKey = "gap", sortDir = -1;
  var PAGE = 50, page = 0;
  var VAL = {
    ticker: function (r) { return r.ticker; },
    name: function (r) { return r.name; },
    sector: function (r) { return r.sector; },
    market: function (r) { return r.market; },
    rev: function (r) { return r.rev; },
    price: function (r) { return r.price; },
    gap: function (r) { return r.gap; },
    analysts: function (r) { return r.analysts == null ? -1 : r.analysts; },
    mcap: function (r) { return r.mcap == null ? -1 : r.mcap; },
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
      page = 0;
      apply();
    });
  });

  function apply() {
    readColLive();
    var shown = DATA.filter(matches);
    draw(shown);

    var ordered = order(shown);
    var pages = Math.max(1, Math.ceil(ordered.length / PAGE));
    if (page >= pages) page = pages - 1;
    var slice = ordered.slice(page * PAGE, page * PAGE + PAGE);

    var seen = {};
    slice.forEach(function (r) {
      seen[r.ticker] = 1;
      tbody.appendChild(rowFor[r.ticker]);          // appendChild moves, so this reorders
      rowFor[r.ticker].classList.remove("hide");
    });
    Object.keys(rowFor).forEach(function (t) {
      if (!seen[t]) rowFor[t].classList.add("hide");
    });

    var label = ordered.length ? "Page " + (page + 1) + " of " + pages : "";
    Array.prototype.forEach.call(document.querySelectorAll("[data-info]"), function (el) {
      el.textContent = label;
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-nav]"), function (btn) {
      btn.disabled = btn.getAttribute("data-nav") === "prev" ? page === 0 : page >= pages - 1;
    });
    Array.prototype.forEach.call(document.querySelectorAll(".pager"), function (el) {
      el.style.display = ordered.length > PAGE ? "flex" : "none";
    });

    Array.prototype.forEach.call(document.querySelectorAll("th[data-k]"), function (th) {
      th.classList.remove("asc", "desc");
      if (th.getAttribute("data-k") === sortKey) th.classList.add(sortDir === 1 ? "asc" : "desc");
    });

    document.getElementById("count").textContent =
      (shown.length === DATA.length ? "All " + DATA.length + " names"
                                    : shown.length + " of " + DATA.length + " names") +
      ", sorted by " + sortKey + ", " + PAGE + " a page.";
    document.getElementById("empty").style.display = shown.length ? "none" : "block";

    // Reset only earns its place in the row once a filter is actually on.
    var any = Object.keys(els).some(function (k) { return els[k].value !== ""; }) ||
              Object.keys(cols).some(function (k) { return cols[k].value !== ""; });
    document.getElementById("reset").hidden = !any;
  }

  function reset0() { page = 0; writeQuery(); apply(); }

  // ?q= is how Shortfall and DCF Studio hand a company over. It fills the SAME search
  // box a reader would have typed into, rather than a hidden filter, so the list is
  // never narrowed by something invisible. An empty box removes the parameter instead
  // of writing q=, so the default state never lands in a shared URL.
  function readQuery() {
    try {
      var q = new URLSearchParams(window.location.search).get("q");
      if (q) els.text.value = q;
    } catch (e) { /* no URLSearchParams, no handoff - the page still works */ }
  }

  function writeQuery() {
    try {
      var u = new URL(window.location.href);
      var v = els.text.value.trim();
      if (v) u.searchParams.set("q", v);
      else u.searchParams.delete("q");
      history.replaceState(null, "", u);
    } catch (e) { /* a file:// page has no origin to replace against */ }
  }

  Object.keys(els).forEach(function (k) {
    els[k].addEventListener(els[k].tagName === "SELECT" ? "change" : "input", reset0);
  });
  Object.keys(cols).forEach(function (k) {
    cols[k].addEventListener(cols[k].tagName === "SELECT" ? "change" : "input", reset0);
  });
  Array.prototype.forEach.call(document.querySelectorAll("[data-nav]"), function (btn) {
    btn.addEventListener("click", function () {
      var dir = btn.getAttribute("data-nav");
      if (dir === "prev" && page > 0) page--;
      else if (dir === "next") page++;
      apply();
      document.getElementById("pager-top").scrollIntoView({block: "start", behavior: "smooth"});
    });
  });
  document.getElementById("reset").addEventListener("click", function () {
    els.market.value = ""; els.sector.value = ""; els.band.value = "";
    els.gap.value = ""; els.cov.value = ""; els.text.value = "";
    Object.keys(cols).forEach(function (k) { cols[k].value = ""; });
    sortKey = "gap"; sortDir = -1; page = 0;
    writeQuery();
    apply();
  });
  // The type scale depends on the rendered width, so a rotation or a window
  // resize has to redraw - otherwise a phone turned landscape keeps the
  // oversized labels it was given in portrait.
  var rz;
  window.addEventListener("resize", function () {
    clearTimeout(rz);
    rz = setTimeout(apply, 180);
  });

  readQuery();
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
        "mcap": r.get("mcap_bn"),
        "rev": r["revision_pct"], "price": r["price_chg_pct"], "gap": r["gap_pp"],
        "analysts": r.get("analysts"), "bandkey": band(r["gap_pp"]),
    } for r in rows]

    markets = sorted({r["market"] for r in rows})
    sectors = sorted({r["sector"] for r in rows})
    present = {mcap_band(r.get("mcap_bn")) for r in rows}
    sizes = [b for b in MCAP_BANDS if b in present]
    gap_opts = [BANDS[k][1] for k in ("behind", "ahead", "inline")]
    gap_select = ('<option value="">Any reading</option>'
                  + "".join(f'<option value="{k}">{BANDS[k][1]}</option>'
                            for k in ("behind", "ahead", "inline")))
    # thin coverage means the "consensus" is one or two desks, which is worth filtering out
    cover_select = ('<option value="">Any coverage</option>'
                    + "".join(f'<option value="{n}">{n}+ analysts</option>'
                              for n in (5, 10, 15, 20, 30)))

    dropnote = ""
    if dropped:
        dropnote = (f" Of the {len(rows) + len(dropped)} names in the universe, "
                    f"{len(dropped)} are excluded this week where estimate history is "
                    f"absent, too sparse for a percentage change to be meaningful, or "
                    f"jumps in a single step - a change of reporting basis rather than "
                    f"a revision.")

    page = (TEMPLATE
            .replace("__HEADLINE__", "Where price and earnings estimates have moved apart.")
            .replace("__LEDE__", "The 90-day change in each company's consensus earnings "
                                 "forecast, plotted against its share price over the same period.")
            .replace("__READINGS__",
                     '<option value="">any</option>'
                     + "".join(f'<option value="{lbl}">{lbl}</option>'
                               for _, lbl in BANDS.values()))
            .replace("__NMKT__", str(len(markets)))
            .replace("__N__", str(len(rows)))
            .replace("__DATE__", data["generated_utc"][:10])
            .replace("__MARKETS__", options(markets, "All markets"))
            .replace("__SECTORS__", options(sectors, "All sectors"))
            .replace("__BANDS__", options(sizes, "Any size"))
            .replace("__GAPS__", gap_select)
            .replace("__COVER__", cover_select)
            .replace("__THRESHNUM__", str(GAP_THRESHOLD_PP))
            .replace("__THRESH__", str(int(GAP_THRESHOLD_PP)))
            .replace("__ROWS__", build_rows(rows))
            .replace("__DROPNOTE__", dropnote)
            .replace("__JSON__", json.dumps(compact, separators=(",", ":")))
            .replace("__BANDCFG__", json.dumps(BANDS))
            )

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
