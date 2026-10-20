"""Sitenin masaüstü ve mobil tam sayfa görüntüsü (kontrol için, scratchpad'e)."""
import sys
from playwright.sync_api import sync_playwright
OUT = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    for ad, w in [("desk", 1280), ("mob", 390)]:
        s = b.new_page(viewport={"width": w, "height": 900})
        s.goto("http://localhost:8600/", wait_until="networkidle")
        s.wait_for_timeout(800)
        sw = s.evaluate("document.documentElement.scrollWidth")
        print(ad, "scrollWidth", sw, "viewport", w)
        s.screenshot(path=f"{OUT}/site_{ad}.png", full_page=True)
    b.close()
