"""Ucretsiz plan hangi sezonlara eriyor? - 1 ISTEK maliyetli sonda.

NEDEN GEREKLI: 26 Tem 2026'da olculdu ve API acikca soyledi:
    "Free plans do not have access to this season, try from 2022 to 2024."
Bu bir PLAN penceresi. Pencereler zamanla kayabilir - takvim ilerledikce
2025 acilmis olabilir. Bunu varsaymak yerine SINAMAK gerekiyor ve
maliyeti sezon basina tek istek.

Neden onemli: sistem su an en iyi ihtimalle 2024/25 sezonunu goruyor,
yani "su an patlayan cocuk kim" sorusunu cevaplayamiyor. 2025 acilirsa
sistemin kullanim degeri niteliksel olarak degisir.

    python scripts/probe_season_access.py            # 2025 ve 2026 dener
    python scripts/probe_season_access.py --sezon 2025
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout.ingest.apifootball import ApiFootball  # noqa: E402

SONUC = ROOT / "data" / "raw" / "season_access.json"
TAZELIK_GUN = 30   # sonucu bu kadar gun sonra yeniden sina

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Brezilya Serie A - takvim ligi, kadrosu kucuk, tek sayfa yeter
TEST_LIG = 71
TEST_TAKIM = 127        # Flamengo


def dene(api: ApiFootball, sezon: int) -> bool:
    print(f"\n--- sezon {sezon} deneniyor (1 istek) ---")
    try:
        r = api.get("players", {"league": TEST_LIG, "team": TEST_TAKIM,
                                "season": sezon, "page": 1}, force=True)
    except Exception as e:                       # noqa: BLE001
        print(f"  HATA: {type(e).__name__}: {e}")
        return False

    hatalar = r.get("errors") or {}
    if hatalar:
        print(f"  REDDEDILDI: {hatalar}")
        return False

    n = len(r.get("response") or [])
    print(f"  ERISILEBILIR - {n} oyuncu dondu")
    if n:
        st = (r["response"][0].get("statistics") or [{}])[0]
        dk = (st.get("games") or {}).get("minutes")
        print(f"  ornek: {r['response'][0]['player'].get('name')} - {dk} dakika")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sezon", type=int, action="append",
                    help="denenecek sezon (birden fazla verilebilir)")
    ap.add_argument("--gunluk", action="store_true",
                    help="gunluk zincir modu: sonuc tazeyse hic istek harcama")
    a = ap.parse_args()

    # Gunluk modda sonuc tazeyse hicbir sey yapma - her gun 2 istek yakmayalim.
    if a.gunluk and SONUC.exists():
        try:
            onceki = json.loads(SONUC.read_text(encoding="utf-8"))
            yas = (dt.date.today() - dt.date.fromisoformat(onceki["tarih"])).days
            if yas < TAZELIK_GUN:
                print(f"[sezon] son sinama {yas} gun once: {onceki['acik']} "
                      f"- tekrar denenmiyor")
                return 0
        except Exception:
            pass
    sezonlar = a.sezon or [2025, 2026]

    api = ApiFootball()
    print(f"[kota]  bugun {api.used_today}/{api.daily_limit}, kalan {api.remaining}")
    if api.remaining < len(sezonlar):
        print(f"Kota yetersiz ({len(sezonlar)} istek gerekiyor). "
              "Kota 00:00 UTC'de (yerel 03:00) sifirlanir.")
        return 1

    acik = [s for s in sezonlar if dene(api, s)]
    print("\n" + "=" * 60)
    if acik:
        print(f"ACIK SEZONLAR: {acik}")
        print("config/leagues.yaml icindeki 'seasons' listesine eklenebilir.")
    else:
        print("Yeni sezon acilmamis - pencere hala 2022-2024.")

    # Sonucu yaz - --gunluk tazelik kontrolu buna bakiyor.
    # 30 Agu 2026: bu satirlar EKSIKTI. 30 Eki 2026: eklenmislerdi ama
    # `return 0`'in ARKASINDAYDILAR, hic calismiyorlardi - dosya 30 Agu'da
    # elle yazilmis haliyle kaldi, 29 Eyl'den beri gunluk zincir her gun
    # 2 istek yakti. Simdi return'den once; test_probe_season_access sinar.
    sonuc_yaz(sezonlar, acik)
    return 0


def sonuc_yaz(sezonlar: list[int], acik: list[int], yol: Path | None = None) -> None:
    yol = yol or SONUC        # cagri aninda okunur (test SONUC'u degistirebilsin)
    yol.write_text(
        json.dumps({"tarih": dt.date.today().isoformat(),
                    "denenen": sezonlar, "acik": acik},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"[yazildi] {yol.name}")


if __name__ == "__main__":
    sys.exit(main())
