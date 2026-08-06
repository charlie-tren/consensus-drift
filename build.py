"""Render data/latest.json into docs/index.html.

docs/ because GitHub Pages can serve a project site from / or /docs and nothing else.

Static HTML + a server-rendered inline SVG. No JS, no toolchain, no runtime
dependency - the chart is real markup, so it works with scripting off and the
tooltips are native <title> elements.
"""

import html
import json
import os

W, H = 940, 620                       # svg viewBox
PAD = {"l": 74, "r": 26, "t": 30, "b": 62}

QUADRANTS = {
    "unearned":   ("#c98a6a", "Price up, estimates down"),
    "earned":     ("#7fae8f", "Price up, estimates up"),
    "overlooked": ("#82a8ca", "Estimates up, price down"),
    "confirmed":  ("#6b7480", "Price down, estimates down"),
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


def build_svg(rows):
    xs = [r["price_chg_pct"] for r in rows]
    ys = [r["revision_pct"] for r in rows]
    xb, yb = nice_bound(xs), nice_bound(ys)

    x0, x1 = PAD["l"], W - PAD["r"]
    y0, y1 = PAD["t"], H - PAD["b"]
    cx = x0 + (x1 - x0) / 2
    cy = y0 + (y1 - y0) / 2

    def px(v):
        return x0 + (v + xb) / (2 * xb) * (x1 - x0)

    def py(v):
        return y1 - (v + yb) / (2 * yb) * (y1 - y0)

    p = []
    a = p.append
    a(f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
      f'role="img" aria-label="Estimate revisions against price change">')
    a('<defs><style>.gl{stroke:#262d38;stroke-width:1}</style></defs>')

    # quadrant washes - the two off-diagonals are the interesting ones, so only those get tint
    a(f'<rect x="{cx}" y="{y0}" width="{x1-cx}" height="{cy-y0}" fill="#7fae8f" opacity="0.05"/>')
    a(f'<rect x="{cx}" y="{cy}" width="{x1-cx}" height="{y1-cy}" fill="#c98a6a" opacity="0.09"/>')
    a(f'<rect x="{x0}" y="{y0}" width="{cx-x0}" height="{cy-y0}" fill="#82a8ca" opacity="0.09"/>')

    # gridlines
    for frac in (-0.5, 0.5):
        gx, gy = px(xb * frac), py(yb * frac)
        a(f'<line class="gl" x1="{gx:.1f}" y1="{y0}" x2="{gx:.1f}" y2="{y1}"/>')
        a(f'<line class="gl" x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}"/>')

    # axes through zero
    a(f'<line x1="{cx:.1f}" y1="{y0}" x2="{cx:.1f}" y2="{y1}" stroke="#5d6675" stroke-width="1.4"/>')
    a(f'<line x1="{x0}" y1="{cy:.1f}" x2="{x1}" y2="{cy:.1f}" stroke="#5d6675" stroke-width="1.4"/>')

    # quadrant labels
    lab = 'font-family="ui-sans-serif,system-ui,sans-serif" font-size="12.5" letter-spacing="0.11em"'
    a(f'<text x="{x1-10}" y="{y0+20}" text-anchor="end" fill="#7fae8f" {lab}>EARNED</text>')
    a(f'<text x="{x1-10}" y="{y1-10}" text-anchor="end" fill="#c98a6a" {lab}>UNEARNED</text>')
    a(f'<text x="{x0+10}" y="{y0+20}" fill="#82a8ca" {lab}>OVERLOOKED</text>')
    a(f'<text x="{x0+10}" y="{y1-10}" fill="#6b7480" {lab}>CONFIRMED</text>')

    # ticks
    tick = 'font-family="ui-monospace,Consolas,monospace" font-size="11" fill="#5d6675"'
    for frac in (-1, -0.5, 0.5, 1):
        v = xb * frac
        a(f'<text x="{px(v):.1f}" y="{y1+18}" text-anchor="middle" {tick}>{v:+.0f}%</text>')
        v = yb * frac
        a(f'<text x="{x0-10}" y="{py(v)+4:.1f}" text-anchor="end" {tick}>{v:+.0f}%</text>')

    # axis titles
    at = 'font-family="ui-sans-serif,system-ui,sans-serif" font-size="12.5" fill="#8a94a3"'
    a(f'<text x="{cx:.1f}" y="{H-16}" text-anchor="middle" {at}>Share price change, 90 days</text>')
    a(f'<text transform="translate(20,{cy:.1f}) rotate(-90)" text-anchor="middle" {at}>'
      f'FY2 consensus EPS revision, 90 days</text>')

    # points - label only the extremes so the middle stays readable
    # label the biggest REVISIONS - the vertical axis is what the chart is about, and
    # picking by |revision| also spreads the labels vertically so they don't collide
    named = {r["ticker"] for r in sorted(rows, key=lambda r: -abs(r["revision_pct"]))[:6]}
    for r in rows:
        colour = QUADRANTS[r["quadrant"]][0]
        X, Y = px(r["price_chg_pct"]), py(r["revision_pct"])
        tip = (f'{r["name"]} ({r["ticker"]})  -  price {r["price_chg_pct"]:+.1f}%, '
               f'estimates {r["revision_pct"]:+.1f}%')
        a(f'<g><title>{html.escape(tip)}</title>'
          f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="5.5" fill="{colour}" fill-opacity="0.85" '
          f'stroke="#0f1319" stroke-width="1"/></g>')
        if r["ticker"] in named:
            # above the dot, centred - sitting beside it collided with neighbouring points
            a(f'<text x="{X:.1f}" y="{Y-11:.1f}" text-anchor="middle" fill="#e6e9ee" '
              f'font-family="ui-sans-serif,system-ui,sans-serif" font-size="12">'
              f'{html.escape(r["ticker"])}</text>')

    a("</svg>")
    return "".join(p)


def build_rows(rows):
    out = []
    for r in rows:
        colour, _ = QUADRANTS[r["quadrant"]]
        analysts = r["analysts"] if r["analysts"] else "-"
        out.append(
            f'<tr><td class="tk">{html.escape(r["ticker"])}</td>'
            f'<td>{html.escape(r["name"])}</td>'
            f'<td class="n" style="color:{colour}">{r["revision_pct"]:+.2f}%</td>'
            f'<td class="n">{r["price_chg_pct"]:+.2f}%</td>'
            f'<td class="n muted">{analysts}</td>'
            f'<td class="q" style="color:{colour}">{r["quadrant"]}</td></tr>')
    return "\n".join(out)


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Consensus Drift - where price and estimates disagree</title>
<meta name="description" content="Sell-side EPS estimate revisions plotted against share price change over 90 days. The interesting names are the ones where the two disagree.">
<link rel="canonical" href="https://drift.charlietrenorden.com/">
<meta property="og:title" content="Consensus Drift">
<meta property="og:description" content="Estimate revisions against price change. The interesting names are where the two disagree.">
<meta property="og:url" content="https://drift.charlietrenorden.com/">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='24' fill='%231a212b'/><path d='M72.5 37 A26 26 0 1 0 72.5 63' fill='none' stroke='%2382a8ca' stroke-width='13' stroke-linecap='round'/><circle cx='50' cy='50' r='6.5' fill='%2382a8ca'/></svg>">
<style>
  *,*::before,*::after{box-sizing:border-box}
  :root{--bg:#0f1319;--raised:#171c24;--ink:#e6e9ee;--soft:#8a94a3;--faint:#5d6675;
        --rule:#262d38;--accent:#82a8ca}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:400 17px/1.65 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
       -webkit-font-smoothing:antialiased}
  .wrap{max-width:1000px;margin:0 auto;padding:2.2rem 1.5rem 5rem}
  .bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:3.4rem;gap:1rem}
  .mark{font:600 17px/1 ui-sans-serif,system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase}
  .back{font:500 14px/1 ui-sans-serif,system-ui,sans-serif;color:var(--soft);text-decoration:none;
        border:1px solid var(--rule);border-radius:999px;padding:.5rem .9rem}
  .back:hover{color:var(--ink);border-color:var(--accent)}
  h1{font-weight:400;font-size:clamp(2.1rem,5vw,3rem);line-height:1.06;letter-spacing:-.015em;margin:0 0 1rem}
  .lede{font-size:1.14rem;color:var(--soft);max-width:62ch;margin:0 0 .6rem}
  .stamp{font:500 13px/1.5 ui-monospace,Consolas,monospace;color:var(--faint);margin:1.4rem 0 0}
  figure{margin:2.6rem 0 0;background:var(--raised);border:1px solid var(--rule);border-radius:8px;padding:.6rem}
  figure svg{display:block;width:100%;height:auto}
  .key{display:flex;flex-wrap:wrap;gap:1.4rem;margin:1.4rem 0 0;
       font:500 13px/1.4 ui-sans-serif,system-ui,sans-serif;color:var(--soft)}
  .key b{font-weight:600}
  h2{font-weight:400;font-size:1.5rem;letter-spacing:-.01em;margin:3.4rem 0 .8rem}
  p{max-width:68ch;color:var(--soft)}
  table{width:100%;border-collapse:collapse;margin-top:1.2rem;
        font:400 14.5px/1.5 ui-sans-serif,system-ui,sans-serif}
  th{text-align:left;font:600 11.5px/1 ui-sans-serif,system-ui,sans-serif;letter-spacing:.13em;
     text-transform:uppercase;color:var(--faint);padding:0 .7rem .7rem;border-bottom:1px solid var(--rule)}
  td{padding:.62rem .7rem;border-bottom:1px solid var(--rule);color:var(--ink)}
  td.n{text-align:right;font-family:ui-monospace,Consolas,monospace;font-size:13.5px}
  td.tk{font-family:ui-monospace,Consolas,monospace;font-size:13px;color:var(--soft)}
  td.q{font-size:12.5px;letter-spacing:.05em}
  td.muted{color:var(--faint)}
  th.n{text-align:right}
  .foot{margin-top:3.4rem;padding-top:1.4rem;border-top:1px solid var(--rule);
        color:var(--faint);font:400 13.5px/1.65 ui-sans-serif,system-ui,sans-serif;max-width:70ch}
  .foot a{color:var(--accent)}
  code{font-family:ui-monospace,Consolas,monospace;font-size:.9em;color:var(--ink)}
  @media (max-width:640px){ .key{gap:.8rem} td,th{padding-left:.35rem;padding-right:.35rem} }
</style>
</head>
<body>
<div class="wrap">
  <div class="bar">
    <span class="mark">Consensus Drift</span>
    <a class="back" href="https://charlietrenorden.com/">Other projects &#8599;</a>
  </div>

  <h1>Where price and estimates disagree.</h1>
  <p class="lede">Sell-side earnings estimates move in trends, not jumps. Plotting the
  <em>revision path</em> against what the share price did over the same window puts every
  name in one of four boxes - and the two off-diagonal boxes are the ones worth a
  second look.</p>
  <p class="stamp">__STAMP__</p>

  <figure>__SVG__</figure>

  <div class="key">
    <span><b style="color:#c98a6a">Unearned</b> &middot; price up, estimates down</span>
    <span><b style="color:#82a8ca">Overlooked</b> &middot; estimates up, price down</span>
    <span><b style="color:#7fae8f">Earned</b> &middot; both up</span>
    <span><b style="color:#6b7480">Confirmed</b> &middot; both down</span>
  </div>

  <h2>Every name</h2>
  <table>
    <thead><tr><th>Ticker</th><th>Name</th><th class="n">EPS revision</th>
    <th class="n">Price</th><th class="n">Analysts</th><th>Quadrant</th></tr></thead>
    <tbody>
__ROWS__
    </tbody>
  </table>

  <h2>How this is built</h2>
  <p>For each name the FY2 (next full year) consensus EPS is taken as it stands today and
  as it stood 90 days ago, and the change between the two is the revision. That is the
  number on the vertical axis. The horizontal axis is the share price change over the same
  90 days. Both come from Yahoo Finance, which publishes the estimate at several points in
  the past - so this reads the revision path directly rather than reconstructing it
  from stored history.</p>
  <p>A revision is divided by the <em>absolute</em> prior estimate, so a loss-making name
  moving from -1.00 to -0.50 registers as an upgrade rather than a downgrade.
  Where Yahoo has no prior estimate it returns <code>0.0</code> rather than an empty value;
  those names are dropped rather than plotted as an infinite revision. __DROPNOTE__</p>
  <p>Estimates are opinions with a poor forecasting record, and a revision says only that
  analysts changed their minds - not that they were right. Nothing here is a view,
  a recommendation, or advice.</p>

  <p class="foot">Built by <a href="https://charlietrenorden.com/">Charlie Trenorden</a>.
  Data from Yahoo Finance, refreshed weekly. General information only, not advice, and not
  affiliated with Yahoo.</p>
</div>
</body>
</html>
"""


def main():
    data = json.load(open("data/latest.json", encoding="utf-8"))
    rows = data["names"]
    dropped = data.get("dropped", [])

    stamp = (f'{len(rows)} names  |  90-day window  |  '
             f'updated {data["generated_utc"][:10]}  |  source: Yahoo Finance')

    if dropped:
        listed = ", ".join(html.escape(d["ticker"]) for d in dropped)
        dropnote = (f"Dropped this run: {listed} - "
                    f"{len(dropped)} of {len(rows) + len(dropped)} tracked.")
    else:
        dropnote = "No names were dropped this run."

    page = (TEMPLATE
            .replace("__STAMP__", html.escape(stamp))
            .replace("__SVG__", build_svg(rows))
            .replace("__ROWS__", build_rows(rows))
            .replace("__DROPNOTE__", dropnote))

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    print(f"built docs/index.html - {len(rows)} plotted, {len(dropped)} disclosed as dropped")


if __name__ == "__main__":
    main()
