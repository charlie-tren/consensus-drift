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

- [x] **More markets. DONE 07/08/2026** - Hong Kong, India, New Zealand, Singapore and the
      seven European completers (DAX, CAC 40, SMI, AEX, IBEX 35, FTSE MIB, OMX Stockholm 30)
      are in. Universe 912 -> 1,309 names across 17 markets. The market labels changed with
      it: markets are now derived from the EXCHANGE SUFFIX rather than the index a name
      arrived through, and read "Country (Exchange)". That was forced rather than cosmetic -
      EURO STOXX 50 alone spans eight exchanges, so an "EU" bucket sitting next to a
      "Germany" one would have listed Germany twice.
      STILL OPEN below: Japan, and the deliberately-skipped small-cap indices.

- [ ] **~~More markets.~~ Survey kept for the two indices NOT taken.** Every candidate below
      was checked 07/08/2026 against
      BOTH Wikipedia (does a constituent table exist) and Yahoo (does `eps_trend` return a
      usable 90-day revision, sampled 8 names each). New-name counts are net of the
      existing 912, so the European ones are already net of the EURO STOXX overlap.

      | Index | New names | Yahoo usable (of 8) |
      |---|---|---|
      | S&P 600 SmallCap | 603 | 8 |
      | FTSE 250 | 250 | 6 |
      | S&P/TSX Composite | 160 | - (CA already 95%) |
      | Hang Seng | 85 | 8 |
      | NIFTY 50 | 50 | 5 |
      | S&P/NZX 50 | 50 | 8 |
      | FTSE MIB | 35 | 8 |
      | IBEX 35 | 31 | 8 |
      | OMX Stockholm 30 | 30 | 8 |
      | Straits Times | 30 | 7 |
      | CAC 40 | 25 | 6 |
      | DAX | 23 | 7 |
      | SMI | 20 | 6 |
      | AEX | 19 | 8 |

      EVERYTHING IN THAT TABLE IS NOW IN except the three at the top. What is left:

      - **S&P 600 SmallCap (603) and FTSE 250 (250) - deliberately not taken.** They would
        add ~850 thinly-covered small caps where the "consensus" is two or three desks,
        which is the noisiest end of the page and exactly what the analyst-coverage filter
        exists to screen out. They would also roughly double the fetch. Revisit only if the
        page ever wants a small-cap view of its own rather than more rows in this one.
      - **S&P/TSX Composite (160)** - straightforward if Canadian breadth is ever wanted;
        TSX 60 currently covers the large caps only.

      NIFTY 50 went in despite being the weakest of the set on the sample (5 of 8 names
      with a usable revision, against 7-8 for everything else). Worth checking the India
      drop rate on the first live run - if it is much worse than the ~8% average, the
      50 names are buying little.

- [ ] **Japan is the one real gap, and it is a SOURCE problem, not a data problem.**
      Yahoo returned a usable 90-day revision for 8 of 8 sampled Tokyo names
      (7203.T, 6758.T, 9984.T, 8306.T, 6501.T, 4063.T, 9432.T, 8058.T), so the estimates
      are there. What is missing is a constituent list: the Nikkei 225 Wikipedia page's
      only large table is 113 rows of annual index levels, not members, and there is no
      TOPIX 100 page. Guessing 4-digit codes would invent tickers. Needs a different
      source before Japan can go on.

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

- [x] **Yahoo's FY2 prior can be a different BASIS, not a stale number. FIXED 07/08/2026.**
      The original suspicion (HON showing a prior of 23.00 against a current 10.01) was
      right that the number was wrong, but wrong about the shape - it is not a stale
      prior, it is a discontinuity. Reading all five points Yahoo publishes made it
      obvious:
        HON     23.00 -> 22.96 -> 9.38 -> 9.78 -> 10.01   one -59% step MID-path
        IFT.NZ   0.13 -> 0.42  -> 0.28 -> 0.33 -> 0.33    the BASE is the outlier
        FLEX     4.11 -> 6.95  -> 6.95 -> 6.92 -> 7.11    one +69% step at the base
      All three were in the top ten moves on the page and IFT.NZ was the top row.
      `path_break()` in fetch.py now drops a path containing a single step that both
      exceeds 40% and accounts for 80%+ of all movement in the quarter, plus a separate
      check for a base more than 2x or 0.5x the next point (the mid-path test has nothing
      to dominate when the break is at the very start). Tuned against real downgrades of
      comparable size that MUST survive - 360.AX -55.6%, KMD.NZ -59.5%, EXO.AS -54.9% -
      and all nine cases are in tests/test_calc.py.
      Costs nothing extra: `eps_trend` already returned all five points.

- [x] **Market caps were in the listing currency. FIXED 07/08/2026.** Found while adding
      the cap column: Yahoo reports `marketCap` in the LISTING currency, so Reliance came
      back as 18,066 (INR bn), Tencent 4,288 (HKD bn) and AstraZeneca's Stockholm line
      2,361 (SEK bn) - all sorting above Nvidia. This silently broke the pre-existing
      "Any size" band filter too, and got much worse the moment 12 more currencies were
      added. fetch.py now converts to USD once per run (~10 pairs for 1,300 names).
      `currency` is "GBp" for London because prices quote in pence, but marketCap is in
      whole pounds - so pence-quoted currencies map to their major unit rather than being
      divided by 100.

- [ ] **SNDK reports an FY2 EPS of 258 against a prior of 172.** Noticed 07/08/2026 while
      checking the largest surviving revisions. The +49.9% may well be right - both ends
      sit on the same basis, so the percentage is internally consistent and `path_break`
      correctly leaves it alone - but SanDisk does not earn USD 258 a share, so the LEVEL
      is wrong (a share-count or units artefact). It does not affect this page, which only
      ever reads percentage changes, but it would matter to any future view that shows a
      level. Worth a scan for absurd absolute EPS values if a level ever goes on screen.

- [ ] **The weekly fetch now takes about 40 minutes, up from 25.** 1,309 names at roughly
      1.8s each. Free - the repo is public, so Actions minutes are not billed - and well
      inside the 6-hour job ceiling, but it is the number that moves if more markets go on.
      S&P 600 and FTSE 250 would roughly double it again.

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
