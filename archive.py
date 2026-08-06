"""Append this run's snapshot to the long-run history.

The point of the project is the revision PATH, and Yahoo only exposes 90 days of
it. Everything older than that is gone the moment it rolls off. So every weekly
run appends its full snapshot here, and after a year there is a genuine panel:
~650 names x 52 observations, with estimates, price and the gap for each.

Stored as CSV rather than a binary database on purpose - it diffs in git, needs no
driver, and pandas / DuckDB / Excel all read it directly:

    import pandas as pd
    h = pd.read_csv("data/history.csv", parse_dates=["asof"])
    h.pivot_table(index="asof", columns="ticker", values="gap_pp")

Idempotent: re-running on the same date replaces that date's rows rather than
duplicating them, so a re-run after a failed fetch is safe.
"""

import csv
import json
import os

HISTORY = "data/history.csv"
FIELDS = ["asof", "ticker", "name", "market", "sector", "mcap_bn",
          "eps_now", "eps_prior", "revision_pct",
          "price_now", "price_prior", "price_chg_pct", "gap_pp", "analysts"]


def load_existing(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    data = json.load(open("data/latest.json", encoding="utf-8"))
    asof = data["generated_utc"][:10]

    rows = [{
        "asof": asof,
        "ticker": r["ticker"], "name": r["name"], "market": r["market"],
        "sector": r.get("sector", ""), "mcap_bn": r.get("mcap_bn", ""),
        "eps_now": r["eps_now"], "eps_prior": r["eps_prior"],
        "revision_pct": r["revision_pct"],
        "price_now": r["price_now"], "price_prior": r["price_prior"],
        "price_chg_pct": r["price_chg_pct"], "gap_pp": r["gap_pp"],
        "analysts": r.get("analysts") or "",
    } for r in data["names"]]

    kept = [r for r in load_existing(HISTORY) if r.get("asof") != asof]
    replaced = len(load_existing(HISTORY)) - len(kept)

    os.makedirs("data", exist_ok=True)
    with open(HISTORY, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(kept)
        w.writerows(rows)

    dates = sorted({r["asof"] for r in kept} | {asof})
    print(f"history.csv: +{len(rows)} rows for {asof}"
          + (f" (replaced {replaced} existing rows for that date)" if replaced else "")
          + f" | {len(kept) + len(rows)} rows total across {len(dates)} snapshots"
          + (f", {dates[0]} to {dates[-1]}" if len(dates) > 1 else ""))


if __name__ == "__main__":
    main()
