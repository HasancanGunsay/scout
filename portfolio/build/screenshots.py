"""Scout arayüzünün ekran görüntüleri (portfolyo sitesi için).

Önkoşul: Streamlit 8501'de çalışıyor (.claude/launch.json "scout").
    .venv/Scripts/python.exe portfolio/build/screenshots.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

CIKTI = Path(__file__).resolve().parents[1] / "assets" / "img"
TABAN = "http://localhost:8501"
SAYFALAR = {
    "pool.png": "/?oyuncu=926993-PO1-2025",
    "position-ranking.png": "/Mevki_Siralamasi",
    "ledger.png": "/Hesap_Defteri",
}


def main():
    CIKTI.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        tarayici = p.chromium.launch(channel="msedge")
        sayfa = tarayici.new_page(viewport={"width": 1440, "height": 900},
                                  device_scale_factor=1.5)
        for ad, yol in SAYFALAR.items():
            sayfa.goto(TABAN + yol, wait_until="networkidle")
            sayfa.wait_for_selector('[data-testid="stMainBlockContainer"]', timeout=60_000)
            # Streamlit çalışma göstergesi kaybolana kadar bekle
            sayfa.wait_for_function(
                "() => !document.querySelector('[data-testid=\"stStatusWidget\"]')",
                timeout=90_000)
            sayfa.wait_for_timeout(2500)
            sayfa.screenshot(path=str(CIKTI / ad))
            print("yazildi", ad)
            if ad == "pool.png":
                # oyuncu kartı: başlığı ekranın üstüne getir
                sayfa.locator(".oy-bas").first.scroll_into_view_if_needed()
                sayfa.evaluate("""() => {
                    const e = document.querySelector('.oy-bas');
                    const s = document.querySelector('[data-testid="stMain"]') || window;
                    const y = e.getBoundingClientRect().top - 40;
                    (s.scrollBy ? s : window).scrollBy(0, y);
                }""")
                sayfa.wait_for_timeout(800)
                sayfa.screenshot(path=str(CIKTI / "player-card.png"))
                print("yazildi player-card.png")
        tarayici.close()


if __name__ == "__main__":
    main()
