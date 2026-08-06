# Consensus Drift

Sell-side EPS estimate revisions plotted against share price change, so the names
where the two disagree stand out.

**Live:** https://charlietrenorden.com/consensus-drift/

Served as a GitHub Pages PROJECT site. Because the user site `charlie-tren.github.io`
carries the custom domain, project sites inherit it as `<domain>/<repo>/` - so this
needed no subdomain and no DNS record of its own.

Estimates move in trends rather than jumps, so the interesting picture is the
*revision path*, not the level - and specifically the two off-diagonal quadrants:

| Quadrant | Meaning |
|---|---|
| **Unearned** | price up, estimates down - re-rating without support |
| **Overlooked** | estimates up, price hasn't followed |
| Earned | both up, they agree |
| Confirmed | both down, they agree |

## Running it

```bash
pip install -r requirements.txt
python fetch.py      # -> data/latest.json   (~20s for 40 names)
python build.py      # -> docs/index.html
python -m pytest tests -q
python -m http.server 8000 -d docs
```

`universe.json` is the only input. Edit it to change what's tracked; every name
costs about half a second on refresh.

## How it works

- **Source is Yahoo Finance via `yfinance`.** No key, no Bloomberg - Bloomberg is
  work-licensed and cannot feed a public site.
- `Ticker.eps_trend` publishes the FY2 (`+1y`) consensus EPS **as it stood
  current / 7d / 30d / 60d / 90d ago**. That is the revision path, straight out of
  the box, so this needs no stored history of its own. The 90-day column is what
  gets plotted.
- Price change comes from the same 90-day window, taken from daily closes.
- The chart is a **server-rendered inline SVG** - no JS, no charting library, no
  toolchain. Tooltips are native `<title>` elements, so it works with scripting off.

## Two things that will bite

1. **Yahoo returns `0.0` for a missing prior estimate, not null.** A name with no
   90-day-ago figure computes as an infinite revision and swamps the chart.
   `revision_pct()` treats zero on either side as missing, and dropped names are
   listed on the page rather than silently disappearing. Live example: CBA.AX and
   GMG.AX both came back `90daysAgo = 0.000` on 06/08/2026.
2. **Divide by the absolute prior estimate.** For a loss-maker, -1.00 -> -0.50 is
   an upgrade; dividing by the raw negative base flips the sign and reports it as a
   downgrade. Both cases are covered in `tests/test_calc.py`.

## Deployment

GitHub Pages serves `main` / `docs`. `.github/workflows/refresh.yml` re-runs the
fetch and build weekly and commits the result - no deploy secrets, because Pages
reads the committed output directly.

Repo is public, so Actions minutes are free.
