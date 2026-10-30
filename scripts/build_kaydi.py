"""Atomik build kapisi (FAZ 9.5) - daily_run.ps1 cagirir.

    python scripts/build_kaydi.py hazirla
        canli veritabaninin kopyasini olusturur (data/scout.build.duckdb);
        zincir SCOUT_DB=<kopya> ile ona yazar.
    python scripts/build_kaydi.py kapat --zincir ok|basarisiz [--kirilan ADIM]
        --once data/raw/denetim_canli.json --sonra data/raw/denetim_build.json
        karar verir, uygular, data/raw/build_kaydi.csv'ye yazar.
        Cikis 0 = kopya canliya gecti, 1 = canli degismedi.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scout import build_kaydi as BK  # noqa: E402
from scout.kaynaklar import CANLI_DB, tm_db_yolu  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KOPYA = CANLI_DB.with_name("scout.build.duckdb")
DURUM = ROOT / "data" / "raw" / "build_durum.json"
KAYIT = ROOT / "data" / "raw" / "build_kaydi.csv"


def main() -> int:
    ap = argparse.ArgumentParser()
    alt = ap.add_subparsers(dest="komut", required=True)
    alt.add_parser("hazirla")
    k = alt.add_parser("kapat")
    k.add_argument("--zincir", choices=["ok", "basarisiz"], required=True)
    k.add_argument("--kirilan", default="")
    k.add_argument("--once")
    k.add_argument("--sonra")
    a = ap.parse_args()

    if a.komut == "hazirla":
        simdi = dt.datetime.now()
        BK.hazirla(CANLI_DB, KOPYA)
        DURUM.write_text(json.dumps({"build_id": simdi.strftime("%Y%m%d-%H%M%S"),
                                     "baslangic": simdi.isoformat(timespec="seconds")}),
                         encoding="utf-8")
        print(KOPYA)
        return 0

    d = json.loads(DURUM.read_text(encoding="utf-8")) if DURUM.exists() else {}
    once, sonra = BK.ozet_oku(a.once and Path(a.once)), BK.ozet_oku(a.sonra and Path(a.sonra))
    karar = BK.karar(a.zincir == "ok", once, sonra)
    BK.uygula(karar, CANLI_DB, KOPYA)
    BK.kayit_yaz(KAYIT, BK.satir(d.get("build_id", "?"), d.get("baslangic", ""),
                                 a.zincir == "ok", a.kirilan, tm_db_yolu().parent.name,
                                 once, sonra, karar))
    print(f"[build] {'GECIS' if karar.gecis else 'CANLI DEGISMEDI'}: {karar.neden}"
          + (f" -> {karar.yeni_kaldi}" if karar.yeni_kaldi else ""))
    return 0 if karar.gecis else 1


if __name__ == "__main__":
    sys.exit(main())
