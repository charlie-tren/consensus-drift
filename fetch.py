"""Pull the estimate revision path and price change for the tracked universe.

Writes data/latest.json. Reads universe.json and nothing else.

The whole point of this project is the REVISION PATH, not the estimate level, so
what we want from Yahoo is `eps_trend`: the FY2 (+1y) consensus EPS as it stood
current / 7d / 30d / 60d / 90d ago. Yahoo publishes that directly, which is why
this needs no stored history of our own.
"""

import json
import math
import sys
import time
from datetime import datetime, timezone

import yfinance as yf

WINDOW_LABEL = "90daysAgo"   # the revision window we plot
PRICE_DAYS = 90

# Yahoo rate-limits a ~1,300-name serial sweep, and the failure is SILENT in the worst
# way: each name drops individually, the run exits 0, and a chart built from a third of
# the universe looks exactly like a complete one. The 09/08/2026 run published 511 names
# and dropped 798, of which 750 were "Too Many Requests" - not real data gaps. Every band
# count on the page was drawn from under half the intended universe with nothing saying so.
#
# Three defences, in the order they matter:
#   1. SLOW DOWN so it mostly does not happen (REQUEST_GAP).
#   2. RETRY what still trips, with escalating waits - a rate limit is temporary by
#      definition, so a name lost to one is recoverable, unlike a real data gap.
#   3. REFUSE TO PUBLISH if too much is still missing. A silent partial is worse than a
#      missed run, because a missed run is visible and a thin chart is not.
REQUEST_GAP = 0.4            # seconds between names on the main sweep
RETRY_WAITS = (15, 45, 120)  # escalating pauses before each retry sweep
MAX_RATE_LIMIT_SHARE = 0.05  # above this share still missing, do not publish at all

# A percentage change computed off a near-zero base is noise, not information.
# At 40 names this never showed up; at 665 it did - WBD came back with a prior
# estimate of -0.001 and a "revision" of +7116%, which would set the axis on its
# own and squash every real name into the middle. Anything below this floor is
# dropped and disclosed rather than plotted.
MIN_BASE_EPS = 0.10

# Yahoo publishes the estimate at five points - 90d / 60d / 30d / 7d / current - and
# until 07/08/2026 only the two ends were read. That let a DISCONTINUITY in the path
# pass as a revision. Two shapes were found in the live data, both in the top ten
# moves on the page:
#
#   HON   23.00 -> 22.96 -> 9.38 -> 9.78 -> 10.01   one -59% step mid-path, calm either
#                                                   side; reported as a -56.5% "cut"
#   IFT.NZ 0.13 -> 0.42  -> 0.28 -> 0.33 -> 0.33    the BASE is the outlier; reported
#                                                   as +150%, the top row of the page
#   FLEX   4.11 -> 6.95  -> 6.95 -> 6.92 -> 7.11    same shape at the base, +72.9%
#
# A consensus is a mean over many desks, so it moves progressively. A single step that
# swamps the rest of the quarter is a change of BASIS - a fiscal-year roll, a
# restatement, a spin-off - not analysts changing their minds, and the percentage
# across it is not a revision. Two independent checks, because the break can sit
# anywhere in the path:
#
#   1. DOMINANT STEP - the largest step is big AND accounts for nearly all of the
#      total movement in the path. Catches a break anywhere, including mid-path.
#   2. BASE OUTLIER - the base itself is more than double or less than half the next
#      point. Catches the case where the break is at the 90-day end, where there is
#      no "before" to compare against and check 1 has nothing to dominate.
#
# Deliberately tuned to leave progressive moves alone: 360.AX fell 2.11 -> 1.53 ->
# 1.26 -> 0.94 over the quarter, a real -55.6% downgrade, and passes both.
PATH_LABELS = ["90daysAgo", "60daysAgo", "30daysAgo", "7daysAgo", "current"]
STEP_BIG = 1.40        # a step of more than +/-40% is a candidate break
STEP_DOMINANT = 0.80   # ...and is a break if it is 80%+ of all movement in the path
BASE_OUTLIER = 2.00    # the base may not be 2x or 0.5x the next point along

# Yahoo reports marketCap in the LISTING currency, so across 17 markets the raw number
# is not comparable and a "$bn" size filter on it is simply wrong: Reliance came back
# as 18,066 (INR bn), Tencent 4,288 (HKD bn) and AstraZeneca's Stockholm line 2,361
# (SEK bn), all of which sort above Nvidia. Converted to USD once per run - about ten
# FX pairs for the whole universe, so the cost is a rounding error on 1,300 names.
#
# `currency` is GBp for London (prices quote in pence) but marketCap is still in whole
# pounds, so pence-quoted currencies map to their major unit rather than being scaled.
MAJOR_UNIT = {"GBP": "GBP", "GBp": "GBP", "ZAc": "ZAR", "ILA": "ILS"}
_fx = {"USD": 1.0}


def usd_rate(ccy):
    """Units of USD per 1 unit of ccy, or None if Yahoo has no pair for it.

    Cached for the life of the run - the alternative is 1,300 lookups of the same
    ten pairs.
    """
    if not ccy:
        return None
    ccy = MAJOR_UNIT.get(ccy, ccy).upper()
    if ccy in _fx:
        return _fx[ccy]
    rate = None
    try:
        hist = yf.Ticker(f"{ccy}USD=X").history(period="5d", interval="1d")
        closes = hist["Close"].dropna() if hist is not None and not hist.empty else []
        if len(closes):
            rate = float(closes.iloc[-1])
    except Exception:
        pass
    _fx[ccy] = rate
    print(f"  FX {ccy}USD = {rate}")
    return rate


def _num(x):
    """Yahoo hands back numpy scalars, None, and NaN interchangeably."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v != v else v          # NaN check


def revision_pct(current, prior):
    """Percentage change in the consensus estimate over the window.

    Yahoo uses 0.0 as its MISSING sentinel rather than null, so a name with no
    prior estimate comes back as 0.000 and would compute as an infinite revision
    that swamps the chart. Treat 0 on either side as missing, not as a real
    estimate. (Observed live on CBA.AX and GMG.AX, 06/08/2026.)

    Sign of the base matters too: for a loss-making name a move from -1.00 to
    -0.50 is an UPGRADE, so divide by the absolute value.
    """
    if current is None or prior is None:
        return None
    if current == 0 or prior == 0:
        return None
    if abs(prior) < MIN_BASE_EPS:
        return None
    # A sign flip is not a percentage change on any comparable scale. ECHO went from
    # -0.114 to +15.64 - a loss becoming a profit - and reported +13,816%, which sorted
    # to the top of the page. IFT.AX and DOC are the mirror image, profit to loss. All
    # three are real events worth knowing about, but the percentage is not commensurate
    # with a +10% revision, so they are dropped and disclosed rather than plotted.
    # Every name above 100% in the 07/08/2026 run was a sign flip; none below it was.
    if (current > 0) != (prior > 0):
        return None
    return (current - prior) / abs(prior) * 100.0


def path_break(values):
    """Describe the discontinuity in an estimate path, or None if it reads cleanly.

    `values` is oldest-first. Anything missing, zero, or sign-flipped makes the
    ratios meaningless, so those paths are passed through untouched - the existing
    guards in revision_pct already handle the two ends, and a gap in the middle is
    not evidence of a break.
    """
    clean = [v for v in values if v is not None and v != 0]
    if len(clean) < 3 or len({v > 0 for v in clean}) > 1:
        return None

    steps = [math.log(abs(clean[i + 1] / clean[i])) for i in range(len(clean) - 1)]
    total = sum(abs(s) for s in steps)
    biggest = max(steps, key=abs)

    if (abs(biggest) > math.log(STEP_BIG)
            and total > 0 and abs(biggest) / total >= STEP_DOMINANT):
        i = steps.index(biggest)
        return (f"one {math.exp(biggest) - 1:+.0%} step accounts for "
                f"{abs(biggest) / total:.0%} of the whole path "
                f"({clean[i]:.4g} -> {clean[i + 1]:.4g})")

    if abs(steps[0]) > math.log(BASE_OUTLIER):
        return (f"the 90-day base is out of line with the rest of the path "
                f"({clean[0]:.4g} -> {clean[1]:.4g}, {math.exp(steps[0]) - 1:+.0%})")

    return None


def gap_pp(price_chg, revision):
    """How far the estimate move ran ahead of (or behind) the price move.

    Classifying by the SIGN of each axis was wrong. It put NVDA in the same box as
    a name whose price had run 40% on a 1% upgrade, because both were simply
    "up and up" - when in fact NVDA's estimates rose 14.8% against a 3.8% price
    move, which is the opposite situation. What matters is the DELTA between the
    two, so that is what gets measured. Positive means estimates outran price.
    """
    if price_chg is None or revision is None:
        return None
    return revision - price_chg


def fetch_one(entry):
    ticker = entry["ticker"]
    row = {"ticker": ticker, "name": entry["name"], "market": entry["market"]}
    t = yf.Ticker(ticker)

    trend = t.eps_trend
    if trend is None or "+1y" not in getattr(trend, "index", []):
        row["dropped"] = "no eps_trend from Yahoo"
        return row

    r = trend.loc["+1y"]
    cur, prior = _num(r.get("current")), _num(r.get(WINDOW_LABEL))
    rev = revision_pct(cur, prior)
    if rev is None:
        row["dropped"] = "no usable prior estimate (Yahoo returns 0.0 for missing)"
        row["eps_now"], row["eps_prior"] = cur, prior
        return row

    # The two ends can both look sane while the path between them contains a change
    # of basis rather than a revision - see PATH_LABELS above.
    path = [_num(r.get(lbl)) for lbl in PATH_LABELS]
    broken = path_break(path)
    if broken is not None:
        row["dropped"] = f"estimate path is discontinuous - {broken}"
        row["eps_now"], row["eps_prior"] = cur, prior
        row["eps_path"] = path
        return row

    hist = t.history(period="6mo", interval="1d")
    if hist is None or hist.empty:
        row["dropped"] = "no price history"
        return row
    closes = hist["Close"].dropna()
    if len(closes) < 2:
        row["dropped"] = "insufficient price history"
        return row
    last = float(closes.iloc[-1])
    cutoff = closes.index[-1] - __import__("pandas").Timedelta(days=PRICE_DAYS)
    earlier = closes[closes.index <= cutoff]
    if earlier.empty:
        row["dropped"] = "price history shorter than the revision window"
        return row
    then = float(earlier.iloc[-1])
    if then == 0:
        row["dropped"] = "zero prior price"
        return row

    # sector / industry / market cap drive the on-page filters
    sector = industry = None
    mcap = target = n_opinions = None
    ccy = None
    try:
        info = t.info or {}
        sector, industry = info.get("sector"), info.get("industry")
        mcap = info.get("marketCap")
        ccy = info.get("currency")
        target = _num(info.get("targetMeanPrice"))
        n_opinions = _num(info.get("numberOfAnalystOpinions"))
    except Exception:
        pass

    est = t.earnings_estimate
    analysts = None
    try:
        if est is not None and "+1y" in getattr(est, "index", []):
            analysts = _num(est.loc["+1y"].get("numberOfAnalysts"))
    except Exception:
        pass

    row.update({
        "eps_now": round(cur, 4),
        "eps_prior": round(prior, 4),
        "revision_pct": round(rev, 2),
        "price_now": round(last, 2),
        "price_prior": round(then, 2),
        "price_chg_pct": round((last - then) / then * 100.0, 2),
        "analysts": int(analysts) if analysts else None,
        "sector": sector or "Unclassified",
        "industry": industry or "Unclassified",
        # local-currency cap kept for audit; the USD one is what the page filters on
        "mcap_local_bn": round(mcap / 1e9, 1) if mcap else None,
        "mcap_ccy": ccy,
        "mcap_bn": (round(mcap * usd_rate(ccy) / 1e9, 1)
                    if mcap and usd_rate(ccy) else None),
        # target price is a LEVEL, not a history - Yahoo publishes no 90-day-ago target,
        # so the second view can only show implied upside, never a target revision
        "target_price": round(target, 2) if target else None,
        "target_upside_pct": (round((target - last) / last * 100.0, 2)
                              if target and last else None),
        "target_analysts": int(n_opinions) if n_opinions else None,
    })
    row["gap_pp"] = round(gap_pp(row["price_chg_pct"], row["revision_pct"]), 2)
    return row


def is_rate_limit(exc):
    """True if this exception is Yahoo throttling us rather than a bad name.

    Matched on the class NAME and the message, not on an imported symbol:
    `YFRateLimitError` has moved module between yfinance versions, and an
    ImportError here would turn the guard off silently - which is the exact
    failure mode this whole block exists to prevent.
    """
    return ("ratelimit" in type(exc).__name__.lower()
            or "too many requests" in str(exc).lower())


def attempt(entry):
    """Fetch one name. Returns (row, rate_limited)."""
    try:
        return fetch_one(entry), False
    except Exception as exc:                          # noqa: BLE001 - one bad name must not kill the run
        return ({**entry, "dropped": f"error: {type(exc).__name__}: {exc}"[:120]},
                is_rate_limit(exc))


def main():
    universe = json.load(open("universe.json", encoding="utf-8"))["names"]
    total = len(universe)
    kept, dropped, throttled = [], [], []

    for i, entry in enumerate(universe, 1):
        row, limited = attempt(entry)
        if limited:
            throttled.append(entry)
            print(f"  [{i:>2}/{total}] {entry['ticker']:<8} RATE LIMITED - queued for retry")
        else:
            (dropped if "dropped" in row else kept).append(row)
            print(f"  [{i:>2}/{total}] {entry['ticker']:<8} "
                  + (f"DROPPED - {row['dropped']}" if "dropped" in row
                     else f"rev {row['revision_pct']:+6.2f}%  price {row['price_chg_pct']:+6.2f}%"))
        time.sleep(REQUEST_GAP)

    # A rate limit is temporary, so a name lost to one is recoverable - unlike a real
    # data gap. Sweep the throttled names again with escalating waits.
    for wait in RETRY_WAITS:
        if not throttled:
            break
        print(f"\n{len(throttled)} name(s) rate limited - waiting {wait}s, then retrying")
        time.sleep(wait)
        still = []
        for entry in throttled:
            row, limited = attempt(entry)
            if limited:
                still.append(entry)
            else:
                (dropped if "dropped" in row else kept).append(row)
                print(f"  RECOVERED {entry['ticker']}")
            time.sleep(REQUEST_GAP)
        throttled = still

    for entry in throttled:
        dropped.append({**entry, "dropped":
                        f"error: still rate limited after {len(RETRY_WAITS)} retries"})

    # GUARD BEFORE THE WRITE, not after. The old order wrote latest.json and *then*
    # checked, so "refusing to publish an empty chart" was not true - it had already
    # published, and a thin run overwrote a good one. Leaving the previous file in place
    # means the site keeps showing last week's complete data instead of this week's third.
    share = len(throttled) / total if total else 0
    if share > MAX_RATE_LIMIT_SHARE:
        print(f"\nERROR: {len(throttled)}/{total} ({share:.1%}) still rate limited after "
              f"retries - over the {MAX_RATE_LIMIT_SHARE:.0%} ceiling")
        print("Refusing to publish a partial universe - data/latest.json left untouched")
        sys.exit(1)
    if not kept:
        print("\nERROR: nothing usable - refusing to publish an empty chart")
        sys.exit(1)

    out = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_days": PRICE_DAYS,
        "source": "Yahoo Finance via yfinance",
        "names": sorted(kept, key=lambda r: r["gap_pp"], reverse=True),
        "dropped": dropped,
    }
    with open("data/latest.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")

    print(f"\n{len(kept)} names kept, {len(dropped)} dropped -> data/latest.json")


if __name__ == "__main__":
    main()
