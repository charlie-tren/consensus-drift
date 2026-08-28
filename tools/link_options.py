"""Render the cross-site link affordance on the REAL Consensus Drift table.

    python tools/link_options.py

Charlie settled the shape on Shortfall: a footer line reading "Also on", with an
unavailable target OMITTED rather than greyed. A card has a footer. A table row does
not, so the shape does not port and the placement has to be chosen again here.

Two things this sheet exists to show:

- Consensus Drift covers 1,309 names against Shortfall's 652, so only about half of
  these rows can carry a Shortfall link at all. Every variant is therefore shot over
  EIGHT consecutive rows, deliberately including Canada, Spain and Hong Kong, so the
  raggedness of omitting a link is visible rather than argued about.
- The rows are inert today. Nothing here is a tweak to an existing interaction; the
  expanding variant is new behaviour on a table that has none.

Real Shortfall tickers are read from that repo, so "has a Shortfall page" is the
truth rather than a guess.

Throwaway tooling for one decision. Delete it once the shape is settled.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "docs" / "index.html").as_uri()
SHORTFALL = ROOT.parent / "shortfall" / "docs" / "data.js"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "tools" / "link_options.png")
ROWS = 8


def shortfall_tickers() -> list[str]:
    raw = io.open(SHORTFALL, encoding="utf-8").read()
    d = json.loads(re.search(r"=\s*(\{.*\})\s*;?\s*$", raw, re.S).group(1))
    return sorted(r["ticker"] for r in d["names"])


CSS = """
.xl { font-family: ui-monospace, Consolas, monospace; font-size: 11.5px; }
.xl a { color: var(--link, #82a8ca); text-decoration: none;
        border-bottom: 1px solid rgba(130,168,202,.35); }
.xl .sep { color: var(--soft); padding: 0 .45em; }
.xl .lead { color: var(--soft); padding-right: .5em; }
td.xcell { white-space: nowrap; }
tr.xopen > td { border-bottom: 0 !important; }
tr.xdetail > td { padding: 2px 0 12px 0; }
.xmark { display: inline-flex; align-items: center; justify-content: center;
         width: 20px; height: 18px; margin-right: 5px; border-radius: 3px;
         font-family: ui-monospace, Consolas, monospace; font-size: 9.5px;
         color: #82a8ca; border: 1px solid rgba(130,168,202,.4); }
"""

HELPERS = """
const HAS = new Set(%s);
const rows = Array.prototype.slice.call(
  document.querySelectorAll('#tbody tr:not(.hide)'), 0, %d);
const tick = (tr) => tr.querySelector('.tk').textContent.trim();
const mk = (tag, cls, text, parent) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text) n.textContent = text;
  if (parent) parent.appendChild(n);
  return n;
};
// Charlie's choice on Shortfall: an unavailable target is OMITTED, not greyed. So a
// row outside Shortfall's universe carries one link, not two.
const targets = (tr) => {
  const t = ['DCF Studio'];
  if (HAS.has(tick(tr))) t.unshift('Shortfall');
  return t;
};
const run = (host, lead, labels) => {
  const s = mk('span', 'xl', '', host);
  if (lead) mk('span', 'lead', lead, s);
  labels.forEach((label, i) => {
    if (i) mk('span', 'sep', '\\u00b7', s);
    const a = mk('a', '', label, s); a.href = '#';
  });
  return s;
};
const head = () => document.querySelector('thead tr');
// The table lives in a horizontal scroll container. A screenshot cannot show what is
// scrolled out of it, so an added column simply vanished from the first two sheets.
// Releasing the overflow lets the table lay out at its true width - which is also how
// we learn whether an eleventh column FITS.
const wrap = document.querySelector('table').parentElement;
wrap.style.overflow = 'visible';
"""

VARIANTS = [
    ("Today", "no change - the rows are inert, nothing is clickable", ""),

    ("A  An eleventh column",
     "'Also on' as its own column, at the right of ten existing ones",
     """mk('th', '', 'Also on', head());
        rows.forEach((tr) => run(mk('td', 'xcell', '', tr), '', targets(tr)));"""),

    ("B  The row expands",
     "the direct translation of the card footer - shown open on row 1",
     """mk('th', '', '', head());
        rows.forEach((tr) => {
          const c = mk('td', 'xcell', '', tr);
          mk('span', '', '\\u25be', c).style.color = 'var(--soft)';
        });
        const tr = rows[0];
        tr.classList.add('xopen');
        const d = document.createElement('tr');
        d.className = 'xdetail';
        const td = mk('td', '', '', d);
        td.colSpan = 11;
        run(td, 'Also on', targets(tr));
        tr.parentNode.insertBefore(d, tr.nextSibling);"""),

    ("C  The existing cells become the links",
     "ticker goes to DCF Studio, name goes to Shortfall - no new column",
     """rows.forEach((tr) => {
          const cells = tr.querySelectorAll('td');
          const link = (cell) => {
            const a = mk('a', '', cell.textContent, null);
            a.href = '#'; a.style.color = 'inherit';
            a.style.borderBottom = '1px solid rgba(130,168,202,.4)';
            a.style.textDecoration = 'none';
            cell.textContent = ''; cell.appendChild(a);
          };
          link(cells[0]);
          if (HAS.has(tick(tr))) link(cells[1]);
        });"""),

    ("D  A trailing column of marks",
     "no words - needs each site to have a recognisable mark first",
     """mk('th', '', '', head());
        rows.forEach((tr) => {
          const c = mk('td', 'xcell', '', tr);
          if (HAS.has(tick(tr))) mk('span', 'xmark', 'SF', c).title = 'Shortfall';
          mk('span', 'xmark', 'DS', c).title = 'DCF Studio';
        });"""),
]


def font(size):
    for name in ("seguisb.ttf", "segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> int:
    have = json.dumps(shortfall_tickers())
    shots = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for title, note, js in VARIANTS:
            pg = b.new_page(viewport={"width": 1560, "height": 1400},
                            device_scale_factor=2, color_scheme="dark")
            pg.goto(PAGE)
            pg.wait_for_selector("#tbody tr:not(.hide)", state="visible", timeout=30000)
            pg.add_style_tag(content=CSS)
            if js:
                pg.evaluate("() => {" + (HELPERS % (have, ROWS)) + js + "}")
            # The table sits in a horizontal scroll container, so an ADDED column
            # overflows it rather than widening it. Framing on the thead row therefore
            # cut the new column off - measure the table itself.
            top = pg.query_selector("thead tr").bounding_box()
            tbl = pg.query_selector("table").bounding_box()
            top["width"] = max(top["width"], tbl["width"])
            last = pg.query_selector_all("#tbody tr:not(.hide)")[ROWS]
            bot = last.bounding_box()
            pad = 12
            shots.append((title, note, pg.screenshot(full_page=True, clip={
                "x": top["x"] - pad, "y": top["y"] - pad,
                "width": top["width"] + pad * 2,
                "height": bot["y"] - top["y"] + pad * 2,
            })))
            pg.close()
        b.close()

    tiles = [Image.open(io.BytesIO(s)) for _, _, s in shots]
    w = max(t.width for t in tiles)
    head_h, gap = 74, 26
    sheet = Image.new("RGB", (w + 48, sum(t.height + head_h + gap for t in tiles) + 24),
                      "#0d0f12")
    d = ImageDraw.Draw(sheet)
    y = 12
    for (title, note, _), t in zip(shots, tiles):
        d.text((24, y + 8), title, fill="#e8e6e1", font=font(28))
        d.text((24, y + 44), note, fill="#8b8f97", font=font(20))
        sheet.paste(t, (24, y + head_h))
        y += t.height + head_h + gap
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT)
    print(f"{OUT}  {sheet.width}x{sheet.height}  {len(tiles)} variants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
