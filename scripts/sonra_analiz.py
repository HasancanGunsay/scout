"""FAZ 6.4b: "top-K sonradan daha mi iyi yapti?" - esleştirilmis kontrol.

    python scripts/sonra_analiz.py            # K=20
    python scripts/sonra_analiz.py --k 50

Tedavi : her (sezon, mevki) icin UCUZ bantta model_olasilik'a gore top-K
         (tahminler DISARIDAN - player_ranking, bkz. build_ranking.py)
Kontrol: ayni sezon + mevki + kapsam + deger_var; en yakin 5 oyuncu
         (yas, log dakika, log deger). Tedavi disindaki ucuz oyunculardan.

SONUCLAR (TM tabanli, sonra 12 ay; RATING YOK):
  yer        birinci ligde yer edindi (kademe>=3)
  dk_lig     birinci lig dakikasi  (izlenen ligde oynamadiysa 0)
  ilk11_lig  birinci lig ilk 11 sayisi
  ga90       (gol+asist)/90  - yalniz >=450 dk oynayanlar (kosullu!)
  deger_lo   ln(deger_son / deger_bas)  - iki degerleme de varsa

ONEMLI: eslestirme dakikayi SABITLER. Yani "top-K daha cok oynadi" bulgusu
dakika farkindan gelemez - bu muhafazakar bir testtir.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout.model.kontrol import eslestir, fark_tablosu, kume_bootstrap  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = ROOT / "data" / "scout.duckdb"
SONUCLAR = ["yer", "dk_lig", "ilk11_lig", "ga90", "deger_lo"]
ACIKLAMA = {
    "yer": "yer edindi (birinci lig, >=900 dk)",
    "dk_lig": "birinci lig dakikasi",
    "ilk11_lig": "birinci lig ilk 11 sayisi",
    "ga90": "gol+asist/90 (>=450 dk oynayanlar)",
    "deger_lo": "deger degisimi ln(son/bas)",
}


def veri_yukle(con) -> pd.DataFrame:
    d = con.sql("""
        SELECT r.*, s.mac_lig, s.dk_lig, s.ilk11_lig, s.ga90, s.deger_bas,
               s.deger_son, s.kulup_degisti, s.pencere_tam
        FROM player_ranking r
        JOIN player_sonra s USING (player_id, league_id, season)
        WHERE r.ucuz AND s.pencere_tam""").df()
    d["yer"] = (d.kademe >= 3).astype(float)
    d["dk_lig"] = d.dk_lig.fillna(0.0)
    d["ilk11_lig"] = d.ilk11_lig.fillna(0.0)
    ok = (d.deger_bas > 0) & (d.deger_son > 0)
    d["deger_lo"] = np.where(ok, np.log(d.deger_son / d.deger_bas), np.nan)
    d["log_dk"] = np.log(d.minutes.clip(lower=1))
    d["log_deger"] = np.log1p(d.deger.fillna(0))
    return d.reset_index(drop=True)


def tedavi_sec(d: pd.DataFrame, k: int) -> pd.Series:
    """Her (sezon, mevki) icin ucuz bantta model top-K isareti."""
    isaret = pd.Series(False, index=d.index)
    for _, g in d.groupby(["season", "pos_group"]):
        if len(g) >= 3 * k:
            isaret[g.nlargest(k, "model_olasilik").index] = True
    return isaret


def analiz(d: pd.DataFrame, k: int, ad: str, filtre: pd.Series) -> None:
    ted = d[d.tedavi & filtre]
    hav = d[~d.tedavi & filtre]
    if len(ted) < 30:
        print(f"\n[{ad}] tedavi n={len(ted)} - yetersiz")
        return
    e = eslestir(ted, hav, sayisal=["age_season_end", "log_dk", "log_deger"],
                 kesin=["season", "pos_group", "kapsam", "deger_var"], k=5)
    f = fark_tablosu(ted, hav, e, SONUCLAR)
    print(f"\n{'-' * 92}\n{ad}  ·  tedavi {len(ted)} (eslesen {len(e)}) · "
          f"benzersiz oyuncu {ted.player_id.nunique()}\n{'-' * 92}")
    print(f"{'sonuc':38s}{'tedavi ort':>12s}{'fark':>10s}   %95 GA (oyuncu-kume)      n")
    for s in SONUCLAR:
        o, lo, hi, n = kume_bootstrap(f, s)
        tort = ted.loc[list(e), s].mean()
        isr = "*" if (n >= 10 and (lo > 0 or hi < 0)) else " "
        if np.isnan(o):
            print(f"{ACIKLAMA[s]:38s}{tort:12.3f}   (yetersiz orneklem, n={n})")
        else:
            print(f"{ACIKLAMA[s]:38s}{tort:12.3f}{o:+10.3f}   "
                  f"[{lo:+.3f}, {hi:+.3f}]{isr}   {n}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--sezon", type=int, nargs="*", default=None,
                    help="yalniz bu sezonlar (or. --sezon 2024: temiz zaman-disi)")
    a = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    d = veri_yukle(con)
    con.close()
    if a.sezon:
        d = d[d.season.isin(a.sezon)].reset_index(drop=True)
        print(f"[in] yalniz sezon {a.sezon}")
    d["tedavi"] = tedavi_sec(d, a.k)
    print(f"[in] ucuz, pencere tam: {len(d):,} · tedavi (top-{a.k}/sezon/mevki) "
          f"{int(d.tedavi.sum())}")

    hepsi = pd.Series(True, index=d.index)
    analiz(d, a.k, "HEPSI (mevki+sezon top-K, ucuz)", hepsi)
    analiz(d, a.k, "KAPSAM tam  (sonuc gorunur)", d.kapsam == "tam")
    analiz(d, a.k, "KAPSAM sicrama_only (sonuc KISMEN gorunur)",
           d.kapsam == "sicrama_only")
    for pg in ["Defender", "Midfielder", "Attacker", "Goalkeeper"]:
        analiz(d, a.k, f"MEVKI {pg}", d.pos_group == pg)
    print("\n  * = %95 GA sifiri disliyor. RATING yok (§43.4).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
