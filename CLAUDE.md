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
