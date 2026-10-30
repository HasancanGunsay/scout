"""FAZ 3: emsal oranini uret ve AYIRT ETME GUCUNU sina.

    python scripts/build_emsal.py                # sina + player_emsal
    python scripts/build_emsal.py --sadece-sina
    python scripts/build_emsal.py --k-taramasi

Emsal orani bir TAHMIN degil, bir TABAN ORANI - isi gerekcelendirmek.
Ama hicbir ayirt etme gucu olmayan bir oran gerekce degil, sustur. O yuzden
olculuyor: 2024 hedeflerinin emsalleri YALNIZCA 2022+2023'ten seciliyor
(gelecege bakis yok) ve lig-ici AUC hesaplaniyor.

Mesafe MODELIN ozellik uzayinda, katsayilarla agirlikli (bkz. emsal.py -
ilk surum stil uzayindaydi ve olculunce yetersiz cikti).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scout.kaynaklar import db_yolu  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))

from scout.features.emsal import (ASGARI_EMSAL, MESAFE_OZELLIKLERI,  # noqa: E402
                                  VARSAYILAN_K, cumle, emsaller,
                                  lig_taban_orani, mesafe_uzayi, ozet)
from scout.model.ranker import (esli_bootstrap, fark_ga,  # noqa: E402
                                lig_ici_auc)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = db_yolu()  # SCOUT_DB ya da data/scout.duckdb (FAZ 9.5)


def veri(con) -> pd.DataFrame:
    """train_model ile AYNI ozellik hattini kullan - mesafe orada tanimli."""
    import train_model as tm

    df = pd.concat([tm.veri_yukle(con, (2022, 2023)),
                    tm.veri_yukle(con, (2024,))], ignore_index=True)
    # 7.0: disaridan tahmin (player_tahmin); uretim modeli 2022-24'u gormus
    ek = con.sql("""SELECT player_id, league_id, season, model_olasilik
                    FROM player_tahmin""").df()
    df = df.merge(ek, on=["player_id", "league_id", "season"], how="left")
    df["lig_taban"] = lig_taban_orani(df)
    return df


def _agirliklar(tr: pd.DataFrame):
    """Modelin |katsayi| vektoru - mesafe agirligi olarak kullanilir."""
    import train_model as tm
    m, _ = tm.egit(tm._hazirla(tr, MESAFE_OZELLIKLERI), tr.y.to_numpy(),
                   tm._hazirla(tr, MESAFE_OZELLIKLERI))
    return np.abs(m[-1].coef_[0])


def oranlar(hedefler: pd.DataFrame, havuz: pd.DataFrame, w, k: int
            ) -> pd.DataFrame:
    """Her hedef icin emsal ozeti. Havuz AYRI verilebilir (sizinti kontrolu)."""
    kayit = []
    if havuz is hedefler:
        Z = mesafe_uzayi(havuz, w)
        for i, h in hedefler.iterrows():
            o = ozet(emsaller(havuz, i, Z, k=k), float(h.lig_taban))
            kayit.append({"player_id": h.player_id, "league_id": h.league_id,
                          "season": h.season, **o})
    else:
        for i, h in hedefler.iterrows():
            b = pd.concat([havuz, hedefler.loc[[i]]])
            Z = mesafe_uzayi(b, w)
            o = ozet(emsaller(b, i, Z, k=k), float(h.lig_taban))
            kayit.append({"player_id": h.player_id, "league_id": h.league_id,
                          "season": h.season, **o})
    return pd.DataFrame(kayit)


def sina(df: pd.DataFrame, w, k: int) -> pd.DataFrame:
    havuz = df[df.season.isin([2022, 2023])]
    test = df[df.season == 2024]
    e = oranlar(test, havuz, w, k)
    return test.merge(e, on=["player_id", "league_id", "season"], how="left")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sadece-sina", action="store_true")
    ap.add_argument("--k-taramasi", action="store_true")
    ap.add_argument("--k", type=int, default=VARSAYILAN_K)
    a = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    df = veri(con)
    print(f"[in]   {len(df):,} oyuncu-sezon (U23, 450+ dk)")

    w = _agirliklar(df[df.season.isin([2022, 2023])])
    ilk4 = sorted(zip(MESAFE_OZELLIKLERI, w), key=lambda t: -t[1])[:4]
    print("[w]    en agir mesafe boyutlari: "
          + ", ".join(f"{c}={v:.2f}" for c, v in ilk4))

    if a.k_taramasi:
        # ODUNLESME: buyuk k guven araligini daraltir ve daha cok "anlamli"
        # uretir - AMA ayirt etme gucu duser. O ek anlamliliklar SAHTE
        # KESINLIK olur.
        satir = []
        for k_ in (20, 40, 80, 150):
            t = sina(df, w, k_)
            y_ = t[t.yeterli.fillna(False)].dropna(subset=["oran"])
            satir.append(dict(
                k=k_, n=len(y_), auc=round(lig_ici_auc(y_, "oran"), 3),
                ga_genislik=round((y_.oran_hi - y_.oran_lo).mean(), 3),
                tabani_asan_pct=round(100 * y_.taban_ustunde.mean(), 1)))
        print("\n--- k taramasi ---")
        print(pd.DataFrame(satir).to_string(index=False))
        con.close()
        return 0

    test = sina(df, w, a.k)
    y = test[test.yeterli.fillna(False)].dropna(
        subset=["oran", "model_olasilik", "score"]).copy()
    print(f"[sina] {len(y):,}/{len(test):,} hedefte emsal grubu yeterli "
          f"(>={ASGARI_EMSAL})")

    kol = ["oran", "model_olasilik", "score"]
    print(f"\n{'=' * 68}\nAYIRT ETME GUCU (2024 · emsaller yalnizca 22+23'ten)"
          f"\n{'=' * 68}")
    for k_ in kol:
        print(f"  lig-ici AUC  {k_:16s} = {lig_ici_auc(y, k_):.3f}")
    bs = esli_bootstrap(y, kol, B=300)
    for a_, b_ in [("oran", "score"), ("oran", "model_olasilik")]:
        o, lo, hi = fark_ga(bs, a_, b_)
        print(f"  {a_} - {b_:16s} = {o:+.3f}  %95 GA [{lo:+.3f}, {hi:+.3f}]")

    print("\n  --- kalibrasyon ---")
    y["kova"] = pd.qcut(y.oran, 5, duplicates="drop")
    print(y.groupby("kova", observed=True).agg(
        n=("y", "size"), emsal_dedi=("oran", "mean"),
        gerceklesen=("y", "mean")).round(3).to_string())
    print(f"\n  GA'si ligin tabanini asan vaka: "
          f"%{100 * y.taban_ustunde.mean():.1f}")

    if not a.sadece_sina:
        print("\n[uret] tum satirlar...")
        tum = oranlar(df, df, w, a.k)
        con.close()
        con2 = duckdb.connect(str(DB))
        con2.register("tum", tum)
        con2.execute("CREATE OR REPLACE TABLE player_emsal AS SELECT * FROM tum")
        con2.close()
        n = int(tum.yeterli.sum())
        print(f"[ok]   player_emsal: {len(tum):,} satir · {n:,} oranli "
              f"(%{100 * n / len(tum):.0f})")
        for _, r in tum[tum.yeterli].head(2).iterrows():
            print("  " + cumle(r.to_dict()))
    else:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
