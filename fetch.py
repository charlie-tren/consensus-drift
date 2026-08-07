"""Pull the estimate revision path and price change for the tracked universe.

Writes data/latest.json. Reads universe.json and nothing else.

The whole point of this project is the REVISION PATH, not the estimate level, so
what we want from Yahoo is `eps_trend`: the FY2 (+1y) consensus EPS as it stood
current / 7d / 30d / 60d / 90d ago. Yahoo publishes that directly, which is why
this needs no stored history of our own.
"""

import json
import sys
from datetime import datetime, timezone

import yfinance as yf

WINDOW_LABEL = "90daysAgo"   # the revision window we plot
PRICE_DAYS = 90

# A percentage change computed off a near-zero base is noise, not information.
# At 40 names this never showed up; at 665 it did - WBD came back with a prior
# estimate of -0.001 and a "revision" of +7116%, which would set the axis on its
# own and squash every real name into the middle. Anything below this floor is
# dropped and disclosed rather than plotted.
MIN_BASE_EPS = 0.10


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
    return (current - prior) / abs(prior) * 100.0


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
    try:
        info = t.info or {}
        sector, industry = info.get("sector"), info.get("industry")
        mcap = info.get("marketCap")
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
        "mcap_bn": round(mcap / 1e9, 1) if mcap else None,
        # target price is a LEVEL, not a history - Yahoo publishes no 90-day-ago target,
        # so the second view can only show implied upside, never a target revision
        "target_price": round(target, 2) if target else None,
        "target_upside_pct": (round((target - last) / last * 100.0, 2)
                              if target and last else None),
        "target_analysts": int(n_opinions) if n_opinions else None,
    })
    row["gap_pp"] = round(gap_pp(row["price_chg_pct"], row["revision_pct"]), 2)
    return row


def main():
    universe = json.load(open("universe.json", encoding="utf-8"))["names"]
    kept, dropped = [], []
    for i, entry in enumerate(universe, 1):
        try:
            row = fetch_one(entry)
        except Exception as exc:                      # noqa: BLE001 - one bad name must not kill the run
            row = {**entry, "dropped": f"error: {type(exc).__name__}: {exc}"[:120]}
        (dropped if "dropped" in row else kept).append(row)
        print(f"  [{i:>2}/{len(universe)}] {entry['ticker']:<8} "
              + (f"DROPPED - {row['dropped']}" if "dropped" in row
                 else f"rev {row['revision_pct']:+6.2f}%  price {row['price_chg_pct']:+6.2f}%"))

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
    if not kept:
        print("ERROR: nothing usable - refusing to publish an empty chart")
        sys.exit(1)


if __name__ == "__main__":
    main()
