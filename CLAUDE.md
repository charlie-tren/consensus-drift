# Consensus Drift - notes for whoever edits this next

## Mobile: fixed, and how to keep it fixed

Fixed 07/08/2026 (commit b59423b). The page used to be 615px wide at a 375px
viewport, so the body panned sideways. The table now scrolls inside an
`overflow-x` wrapper, the masthead stacks below 560px, the filters are a grid
rather than ragged flex, and the chart's type scales with its container.

**The chart is one viewBox scaled to fit**, so every font size, radius and pad in
viewBox units shrinks with the container - at 375px the 11-unit ticks rendered at
about 4px. `typeScale()` returns K, and the type and gutters are multiplied by it.
K is 1 at desktop width, which reproduces the original constants exactly. If you
add anything textual to the chart, multiply its size by K or it will be unreadable
on a phone.

**Verify by measuring, not by looking.** At 375 / 768 / 1280:

```python
assert page.evaluate("document.documentElement.scrollWidth") <= viewport_width
```

plus a check that no `<text>` in the chart falls outside the SVG's own rect. That
second check found two defects the screenshot did not show: the widest x tick ran
past the frame once the type grew, and the rotated y-axis title sat flush against
the edge.

## Two traps this project has already fallen into

**Classify on the delta, not the sign of each axis.** The first version used four
quadrants and put NVDA (estimates +14.8%, price +3.8%) in the same box as a name
whose price had run 43% on a 1.4% upgrade. Opposite situations. Any new
classifier needs a test where the two inputs agree in direction but not in
magnitude - `tests/test_calc.py` has it.

**Yahoo's sentinels bite at scale, not at 40 names.** `0.0` means "missing", not
zero, and a near-zero prior produces nonsense (WBD: a `-0.001` prior gave a
+7116% "revision" that set the axis by itself). `MIN_BASE_EPS` floors it. Divide
by the *absolute* prior so a narrowing loss reads as an upgrade. Run `fetch.py`
over the full universe and read the output before believing a green test suite.

**A single step is not a revision.** Yahoo returns the estimate at five points and
only the two ends were read until 07/08/2026, so a change of BASIS - a fiscal-year
roll, a restatement, a spin-off - passed as a 90-day revision. HON reported 23.00
-> 10.01 on one -59% step with a calm quarter either side; IFT.NZ was the top row
of the page on a 0.13 base that the very next point contradicted at 0.42.
`path_break()` in `fetch.py` reads the whole path. If you touch its thresholds, the
tests hold both the artefacts that must drop and real downgrades of comparable size
that must survive (360.AX -55.6%) - the second half is the one that matters.

**Market cap comes back in the LISTING currency.** Reliance as 18,066 (INR bn) and
Tencent as 4,288 (HKD bn) both sort above Nvidia. `fetch.py` converts to USD once
per run. London reports `currency` as "GBp" because prices quote in pence, but
marketCap is in whole pounds - do not divide it by 100.

**A partial run is worse than a failed one, so it must not be allowed to publish.**
Yahoo rate-limits a serial sweep of ~1,300 names. On 09/08/2026 the run published
511 names and dropped 798, of which **750 were "Too Many Requests"** rather than real
data gaps - and it exited 0, so the site quietly showed a chart and band counts drawn
from under 40% of the universe with nothing on the page saying so. It went unnoticed
for two days because a thin chart looks exactly like a complete one.

`fetch.py` now slows down (`REQUEST_GAP`), retries throttled names with escalating
waits (`RETRY_WAITS` - a rate limit is temporary, unlike a real gap), and **refuses to
publish** above `MAX_RATE_LIMIT_SHARE`. Two details worth keeping if you touch it:

- **The guard runs BEFORE the write.** It used to write `latest.json` and then check,
  so "refusing to publish an empty chart" was false - it had already published, and a
  thin run overwrote a good one. Leaving the old file in place means the site shows
  last week's complete data rather than this week's third.
- **`is_rate_limit()` matches on class name and message, not an imported symbol.**
  `YFRateLimitError` has moved module between yfinance versions, and an ImportError
  would switch the guard off without failing anything. `tests/test_calc.py` holds both
  halves: a rate limit must be caught, and a genuine data gap must NOT be, or a
  legitimately thin universe blocks publication for the wrong reason.

**Never write the same user-visible string in two places.** The size-band labels
lived both in `mcap_band()` and in a hardcoded ordering list. Relabelling them
"US$" in one place left the ordering matching nothing, and the size filter rendered
EMPTY on the page - with a clean build and a green test suite, because nothing
compared the two. `MCAP_BANDS` is now the single source and a test fails if a label
`mcap_band` can return is not in it. The general form: when you change a literal,
**grep for the OLD string, not the new one** - the duplicate you are looking for is
by definition the one that still says the old thing.

## Every displayed dimension should be filterable

Charlie asked for this three times in a row on 07/08/2026 - market, reading, market
cap - so treat it as the standing convention rather than three requests: **if a
column is on screen, it gets a filter, not just a sort.** Text columns take a
substring box, fixed vocabularies take a select, numbers take a minimum. The top
control row and the in-table filter row are allowed to overlap (sector and market
have both) and they AND together.

That also gives you a free correctness check worth using: two independent controls
over the same quantity must agree. `c-mcap >= 250` and the "Over US$250bn" band both
return 58 names; if they ever disagree, one of them is wrong.
