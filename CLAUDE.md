# Consensus Drift - notes for whoever edits this next

## The page does not work on mobile yet

Measured 07/08/2026 at a 375px viewport: `document.documentElement.scrollWidth` is
**615px**, so the whole body pans sideways instead of the table scrolling inside
itself. The cause is the results table - 591px of minimum content with no
`overflow-x` wrapper. Also at that width the wordmark wraps onto two lines and
crowds the "Other Projects" back-link, the five filter dropdowns land at ragged
widths rather than a grid, and the chart's axis labels are unreadable.

**If you are touching the page CSS in `build.py`, fix this while you are in there.**

Verify it the way it was found, not by eye:

```python
# 375px viewport, then:
assert page.evaluate("document.documentElement.scrollWidth") <= 375
```

A table scrolling inside a wrapper passes. A body that pans does not.

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
