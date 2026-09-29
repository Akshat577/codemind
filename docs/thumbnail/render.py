"""Render the YouTube thumbnail (1280x720 PNG).

    pip install playwright && playwright install chromium
    python docs/thumbnail/render.py                  # -> docs/thumbnail/thumbnail.png
    python docs/thumbnail/render.py --photo me.png   # -> docs/thumbnail/thumbnail-photo.png

For the photo version use a portrait with a plain or removed background
(e.g. remove.bg); it is placed on the right side.
"""

import argparse
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent

ap = argparse.ArgumentParser()
ap.add_argument("--photo", help="path to your photo (PNG with transparent background works best)")
args = ap.parse_args()

url = (HERE / "thumbnail.html").as_uri()
out = HERE / "thumbnail.png"
if args.photo:
    url += "?photo=" + quote(Path(args.photo).resolve().as_uri(), safe="")
    out = HERE / "thumbnail-photo.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.goto(url)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    page.screenshot(path=str(out))
    browser.close()
print(f"saved {out}")
