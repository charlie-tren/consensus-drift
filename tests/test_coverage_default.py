"""The default coverage cut, read off the built page rather than the source.

These assert on docs/index.html because that is what ships. A test of the
constant alone would pass while the template forgot to select it, which is the
failure that matters: a no-JS reader, and every sibling site that parses #rows,
sees the markup, not the Python.
"""
import json
import pathlib
import re

import build

PAGE = pathlib.Path(__file__).resolve().parent.parent / "docs" / "index.html"


def _page():
    return PAGE.read_text(encoding="utf-8")


def _rows(html):
    m = re.search(r'<script id="rows" type="application/json">(.*?)</script>', html, re.S)
    assert m, "the page publishes no #rows block"
    return json.loads(m.group(1))


def test_the_cut_is_the_selected_option():
    # The default lives in the markup, so the page and a no-JS read agree.
    html = _page()
    sel = re.search(r'<select id="f-cov"[^>]*>(.*?)</select>', html, re.S).group(1)
    picked = re.findall(r'<option value="(\d*)" selected>', sel)
    assert picked == [str(build.MIN_ANALYSTS)]


def test_thin_is_published_for_every_row_and_matches_the_cut():
    # Crosscheck reads `thin` rather than re-deriving the threshold, so it has to
    # be present on every row and agree with the constant on every row.
    rows = _rows(_page())
    assert rows, "no rows"
    assert all("thin" in r for r in rows)
    for r in rows:
        assert r["thin"] == ((r["analysts"] or 0) < build.MIN_ANALYSTS), r["ticker"]


def test_the_cut_leaves_most_of_the_universe():
    # A guard on the guard: if Yahoo stopped reporting analyst counts, every row
    # would read thin and the default view would silently empty. Measured
    # 05/10/2026 at 99 of 1,225.
    rows = _rows(_page())
    thin = sum(r["thin"] for r in rows)
    assert thin < 0.25 * len(rows), f"{thin} of {len(rows)} rows are thin"


def test_the_staleness_check_runs_in_the_browser_not_at_build_time():
    # A banner decided at build time cannot fire: the build is what stops. The
    # check has to compare the baked date with the reader's own clock.
    html = _page()
    assert 'id="stale" hidden' in html
    assert "Date.now()" in html and "STALE_DAYS" in html
