"""Kaynak katmani + kisi kaydi (GELISTIRME FAZ 9.4).

    python scripts/build_kisi.py

Uretir: kaynak_kimlik, kaynak_mac_katilim, kaynak_oyuncu_sezon, kaynak_deger,
kaynak_sozlesme (standart tablolar, scout.sources) ve kisi_kaynak, kisi
(scout.resolve.kisi). EKLEMELI: mevcut tablolari degistirmez, mevcut hesaplar
bunlari okumaz. Zincirde build_links'ten sonra (eslesme player_links'ten).
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scout.kaynaklar import db_yolu  # noqa: E402
from scout.resolve import kisi as KS  # noqa: E402
from scout.sources.adaptorler import varsayilan_kaynaklar  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = db_yolu()  # SCOUT_DB ya da data/scout.duckdb (FAZ 9.5)


def main() -> int:
    kaynaklar = varsayilan_kaynaklar()
    con = duckdb.connect(str(DB))
    sayilar = KS.kur(con, kaynaklar)
    for t, n in sayilar.items():
        print(f"  {t:22s} {n:>10,}")
    print(KS.ozet(con).to_string(index=False))
    sorun = [d for d in KS.denetim(con) if not d[1]]
    for ad, _, detay in KS.denetim(con):
        print(f"  [{'ok' if (ad, False, detay) not in sorun else 'KALDI'}] {ad} - {detay}")
    con.close()
    return 1 if sorun else 0


if __name__ == "__main__":
    sys.exit(main())
