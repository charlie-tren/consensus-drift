"""Regenerate universe.json from index constituents.

Read from Wikipedia. Run this when you want to refresh the membership; fetch.py
only ever reads the resulting universe.json.

Wikipedia returns 403 to the default urllib user agent, so one is set explicitly.

MARKET IS DERIVED FROM THE EXCHANGE SUFFIX, NOT FROM THE INDEX. That matters once
more than one index feeds the same country: EURO STOXX 50 alone spans eight
exchanges, and its German members have to land in the same bucket as the DAX ones
or the filter reads as though Germany appears twice. Deriving from the suffix also
means a name picked up by two indices dedupes to one market by construction.
"""

import io
import json
import re
import urllib.request

import pandas as pd

UA = "Mozilla/5.0 (consensus-drift; https://charlietrenorden.com/consensus-drift/)"

# Exchange suffix -> the label shown in the market filter. Country first, exchange
# in brackets, because the country is what a reader is actually filtering on.
MARKETS = {
    "":     "United States (NYSE & Nasdaq)",
    ".AX":  "Australia (ASX)",
    ".L":   "United Kingdom (LSE)",
    ".TO":  "Canada (TSX)",
    ".DE":  "Germany (XETRA)",
    ".PA":  "France (Euronext Paris)",
    ".AS":  "Netherlands (Euronext Amsterdam)",
    ".BR":  "Belgium (Euronext Brussels)",
    ".MC":  "Spain (BME)",
    ".MI":  "Italy (Borsa Italiana)",
    ".SW":  "Switzerland (SIX)",
    ".ST":  "Sweden (Nasdaq Stockholm)",
    ".HE":  "Finland (Nasdaq Helsinki)",
    ".CO":  "Denmark (Nasdaq Copenhagen)",
    ".OL":  "Norway (Oslo Bors)",
    ".IR":  "Ireland (Euronext Dublin)",
    ".VI":  "Austria (Wiener Borse)",
    ".LS":  "Portugal (Euronext Lisbon)",
    ".HK":  "Hong Kong (HKEX)",
    ".NS":  "India (NSE)",
    ".NZ":  "New Zealand (NZX)",
    ".SI":  "Singapore (SGX)",
}

# (label, url, ticker column, name column, suffix)
#
# suffix None means the Wikipedia ticker column ALREADY carries the exchange, which
# is true of every continental European table - EURO STOXX spans several exchanges
# and the single-country ones are written ADS.DE, MC.PA, ITX.MC in the source.
#
# NOT INCLUDED: Nikkei 225. Yahoo has the estimates - 8 of 8 sampled Tokyo names
# returned a usable 90-day revision - but the Wikipedia page carries no constituent
# table (its only large table is 113 rows of annual index levels), and guessing
# 4-digit codes would invent tickers. Japan needs a different source, not a suffix.
#
# NOT INCLUDED: S&P 600 and FTSE 250. They would add ~850 names, but they are small
# caps whose "consensus" is two or three desks - the noisiest names on the page, and
# what the analyst-coverage filter already exists to screen out.
SOURCES = [
    ("S&P 500",       "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "Symbol", "Security", ""),
    ("S&P/ASX 200",   "https://en.wikipedia.org/wiki/S%26P/ASX_200", "Code", "Company", ".AX"),
    ("FTSE 100",      "https://en.wikipedia.org/wiki/FTSE_100_Index", "Ticker", "Company", ".L"),
    ("EURO STOXX 50", "https://en.wikipedia.org/wiki/EURO_STOXX_50", "Ticker", "Name", None),
    ("S&P/TSX 60",    "https://en.wikipedia.org/wiki/S%26P/TSX_60", "Symbol", "Company", ".TO"),
    ("DAX",           "https://en.wikipedia.org/wiki/DAX", "Ticker", "Company", None),
    ("CAC 40",        "https://en.wikipedia.org/wiki/CAC_40", "Ticker", "Company", None),
    # SMI is the exception among the European tables - its Ticker column is bare
    # ("NESN", not "NESN.SW"), so it needs the suffix adding like the others do.
    ("SMI",           "https://en.wikipedia.org/wiki/Swiss_Market_Index", "Ticker", "Name", ".SW"),
    ("AEX",           "https://en.wikipedia.org/wiki/AEX_index", "Ticker", "Company", None),
    ("IBEX 35",       "https://en.wikipedia.org/wiki/IBEX_35", "Ticker", "Company", None),
    ("FTSE MIB",      "https://en.wikipedia.org/wiki/FTSE_MIB", "Ticker", "Company", None),
    ("OMX Sthlm 30",  "https://en.wikipedia.org/wiki/OMX_Stockholm_30", "Ticker", "Company", None),
    ("Hang Seng",     "https://en.wikipedia.org/wiki/Hang_Seng_Index", "Ticker", "Name", ".HK"),
    ("NIFTY 50",      "https://en.wikipedia.org/wiki/NIFTY_50", "Symbol", "Company name", ".NS"),
    ("S&P/NZX 50",    "https://en.wikipedia.org/wiki/S%26P/NZX_50_Index", "Ticker symbol", "Company", ".NZ"),
    ("Straits Times", "https://en.wikipedia.org/wiki/Straits_Times_Index", "Stock symbol", "Company", ".SI"),
]

# Hong Kong and Singapore write their codes with the exchange in front of them
# ("SEHK: 5", "SGX: A17U"); nobody else does.
EXCHANGE_PREFIX = re.compile(r"^\s*(SEHK|SGX|HKEX)\s*:?\s*", re.I)

BARE = "<bare code from a suffix-None source>"


def grab(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def to_ticker(code, suffix):
    """Wikipedia's code -> the symbol Yahoo answers to, or None if unusable."""
    code = EXCHANGE_PREFIX.sub("", str(code).replace("\xa0", " ")).strip().upper()
    if not code or code == "NAN":
        return None
    if suffix is None:
        # suffix None is a claim that the source column carries its own exchange. A
        # bare code here means that claim is wrong, and it would otherwise be filed
        # silently as a US listing - which is exactly what SMI did on the first run,
        # putting all 19 Swiss names into the NYSE bucket. Refuse it loudly instead.
        return code if "." in code else BARE
    if suffix == "":
        return code.replace(".", "-")        # Yahoo wants a dash for US share classes
    if suffix == ".HK":
        # Hong Kong codes are numeric and Yahoo wants them padded: 5 -> 0005.HK
        code = code.zfill(4) if code.isdigit() else code
        return code + suffix
    return code.replace(".", "-") + suffix


def market_of(ticker):
    suffix = "." + ticker.rsplit(".", 1)[-1] if "." in ticker else ""
    return MARKETS.get(suffix)


def main():
    names, seen = [], set()
    unknown, bare = set(), []
    for label, url, code_col, name_col, suffix in SOURCES:
        tables = pd.read_html(io.StringIO(grab(url)))
        table = max((t for t in tables
                     if any(code_col == str(c) for c in t.columns) and len(t) >= 15),
                    key=len, default=None)
        if table is None:
            print(f"  {label}: NO TABLE FOUND - skipped")
            continue
        added = 0
        for _, row in table.iterrows():
            ticker = to_ticker(row[code_col], suffix)
            if ticker is BARE:
                bare.append(f"{label}: {row[code_col]}")
                continue
            if ticker is None or ticker in seen:
                continue
            market = market_of(ticker)
            if market is None:                # an exchange with no label is a bug, not a name
                unknown.add(ticker)
                continue
            seen.add(ticker)
            names.append({"ticker": ticker,
                          "name": str(row[name_col]).replace("\xa0", " ").strip(),
                          "market": market})
            added += 1
        print(f"  {label:15s} {len(table):4d} rows -> {added:4d} new")

    if bare:
        print("\nSKIPPED - bare codes from a source declared as carrying its own "
              f"exchange (fix its suffix): {bare}")
    if unknown:
        print(f"\nSKIPPED - no MARKETS entry for their exchange: {sorted(unknown)}")

    doc = {"_comment": "Generated by build_universe.py. Market is derived from the "
                       "exchange suffix, not from the index a name arrived through. "
                       "fetch.py reads this and nothing else.",
           "names": names}
    with io.open("universe.json", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")

    by_market = {}
    for n in names:
        by_market[n["market"]] = by_market.get(n["market"], 0) + 1
    print(f"\nuniverse.json: {len(names)} names across {len(by_market)} markets")
    for m, c in sorted(by_market.items(), key=lambda kv: -kv[1]):
        print(f"  {c:4d}  {m}")


if __name__ == "__main__":
    main()
