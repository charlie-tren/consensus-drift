"""Render docs/og-card-source.html to docs/og-card.png: 1200x630 CSS px drawn natively at 2x.

    python tools/make_card.py
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

DOCS = Path(__file__).resolve().parent.parent / "docs"
OUT = DOCS / "og-card.png"

with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=2)
    pg.goto((DOCS / "og-card-source.html").as_uri())
    pg.screenshot(path=str(OUT))
    b.close()

size = OUT.stat().st_size
assert size < 300_000, f"{OUT.name} is {size} bytes; WhatsApp drops thumbnails over 300KB"
print(f"{OUT.name} {size} bytes")
