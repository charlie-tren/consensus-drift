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
    return (current - prior) / abs(prior) * 100.0


def quadrant(price_chg, revision):
    """Where a name sits. The off-diagonals are the interesting ones."""
    if price_chg is None or revision is None:
        return None
    if price_chg >= 0 and revision >= 0:
        return "earned"        # price up, estimates up - agreement
    if price_chg >= 0 and revision < 0:
        return "unearned"      # price up on FALLING estimates - re-rating without support
    if price_chg < 0 and revision >= 0:
        return "overlooked"    # estimates up, price hasn't followed
    return "confirmed"         # both down - agreement


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
    })
    row["quadrant"] = quadrant(row["price_chg_pct"], row["revision_pct"])
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
        "names": sorted(kept, key=lambda r: r["revision_pct"]),
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
