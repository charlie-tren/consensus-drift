# Consensus Drift - TODO

Open items. The site is live at https://charlietrenorden.com/consensus-drift/ and the
weekly refresh runs itself, so none of this is blocking.

- [ ] **Bring back the second view as a target CHANGE, not a level. Earliest early
      November 2026** (~13 weekly runs from 07/08/2026, when `target_price` started being
      archived).
      WHY THE FIRST ATTEMPT WAS PULLED: a price-target view shipped and was removed the
      same day after being measured. Implied upside is `(target - price) / price`, so with
      targets slow to move a rising price compresses upside by arithmetic:
        corr(implied upside, 90d price change) = **-0.537**  (n = 838)
        corr(estimate change, 90d price change) = -0.090
      and mean upside fell monotonically across all ten price-change deciles, +31.8% to
      +4.0%, with no reversals. The view was largely re-plotting the horizontal axis
      against itself. The earnings view has near-independent axes, which is exactly why
      its gap carries information.
      WHAT REPLACES IT: `data/history.csv` records `target_price` weekly. Once it spans 90
      days there is a genuine target CHANGE for every name, which sits on the same footing
      as the earnings view - diagonal, gap logic and all. Check the correlation again
      before shipping it; if target change also correlates hard with price change, it is
      the same trap wearing a different hat.
      REJECTED SHORTCUT: `Ticker.upgrades_downgrades` reconstructs a 90-day mean target
      change today (VLO +15.4%, NVDA +10.9%, AAPL +7.9%) but is US-only - `BHP.AX` and
      `SHEL.L` both 404 - so it would cover 489 of 839 names and silently drop every
      non-US market.

- [ ] **Use the rest of what Yahoo publishes - a ratings view.** Probed 06/08/2026: the
      project uses ONE of several consensus fields, and the others come free in the same
      fetch. Charlie's point that started it: "obv earnings isn't everything" - a stock can
      be re-rated with no change in forecast earnings.
        - `Ticker.recommendations` - the buy/hold/sell distribution at 0m/-1m/-2m/-3m. A
          RATINGS revision path, structurally identical to the EPS one already used, and it
          does not depend on earnings at all. VLO: 3/7/8/1/1 now vs 3/7/7/2/1 three months
          back. **This is the strongest candidate**, because it is a genuine 90-day CHANGE
          rather than a level, so the gap logic and the diagonal transfer unaltered.
        - `info.recommendationMean` (1 = strong buy, 5 = strong sell). VLO 2.3. A level, so
          it carries the same mechanical risk the price-target view died of - correlate it
          against price change before building anything on it.
        - `Ticker.upgrades_downgrades` - 479 firm actions for VLO alone, with old and new
          targets. Richest, most work, and **US-only** (BHP.AX, SHEL.L 404).
      Before shipping any of these: check the correlation against 90-day price change. The
      price-target view looked reasonable and turned out to be an arithmetic identity.
      MOVED here 07/08/2026 from the hub TODO, where it did not belong.

- [ ] **More markets, if wanted.** `build_universe.py` takes a list of Wikipedia
      constituent pages, so FTSE 250, S&P MidCap 400 or the DAX are a few lines each.
      Nikkei 225 needs a different source - its Wikipedia page carries no constituent
      table, and guessing 4-digit codes would invent tickers. Note fetch time scales
      linearly: 912 names is about 25 minutes.

- [ ] **Watch the weekly run for a few weeks.** The cron has never fired unattended - it
      was armed on 06/08/2026 and every run so far has been manual. Confirm it commits
      `data/latest.json`, `data/history.csv` and `docs/index.html` and that the page date
      chip moves.

- [ ] **A Consensus Drift-specific OG card.** The page currently borrows the site-wide
      `og-card.png`, so a shared link shows Charlie's name rather than the chart. A
      project card (the scatter, the title, the domain) would sell the link far better.
      Source pattern to copy: `assets/og-card-source.html` in the hub repo - an HTML file
      rendered at 2400x1260 and screenshotted. Verify afterwards through
      linkedin.com/post-inspector/, which is also what caught the missing image.

## Notes worth keeping

Three data traps, all found by looking at real output rather than by a test:

1. **Yahoo returns `0.0` for a missing prior estimate, not null** - computes as an
   infinite revision.
2. **A near-zero base makes the percentage meaningless** - WBD reported +7,116% off a
   prior of -0.001 and set the chart axis by itself. Only visible once the universe passed
   ~650 names.
3. **A sign flip is not a percentage** - ECHO went -0.114 to +15.64, a loss becoming a
   profit, and reported **+13,816%**, sorting straight to the top of the page. Every name
   above 100% in that run was a sign flip and none below it was. Found by hovering a dot
   while checking something else; 27 unit tests and eleven browser checks were all green
   at the time.

The lesson each time: the tests pass on the logic, and the defect is in the data.
