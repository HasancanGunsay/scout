"""FAZ 6.2: fiyat-kosullu degerlendirme.

    python scripts/fiyat_bandi.py             # CV + kayan (birincil kanit)
    python scripts/fiyat_bandi.py --dogrula   # + 2024 (onceden ilan edilmis)

SORU
  Model AUC'si 0,70 - ama bunun ne kadari SADECE FIYAT? Kullanici pahali
  oyunculari aramiyor. Ucuz bantta modelin fiyatin USTUNE bir sey katip
  katmadigi hic olculmemisti. Katmiyorsa "yatirima deger" siralamasi bir
  fiyat siralamasinin kopyasi olur.

NASIL OLCULUYOR
  Her fiyat bandi ICINDE, lig-ici AUC. Karsilastirilan tahminciler:
    model      tam model (oyun verisi + piyasa)
    piyasa     yalnizca piyasa (log_deger, deger_var, yas)
    basit      dakika + yas
    saf        oyun verisi, piyasa YOK
  Esli, oyuncu bazli bootstrap GA.

ONEMLI: 'piyasa' tahmincisi degerlemesi OLMAYAN oyuncuda bilgisiz kalir
(deger_var=0 icin sabit). O bantta model - piyasa farki TRIVIAL olarak
pozitif; orada anlamli kiyas model - basit ve saf - basit'tir. Rapor bunu
ayri gosterir.

SIZINTI DISIPLINI
  Birincil kanit: lig-disarida-birak CV (2022+23) ve kayan (2022->2023).
  2024 tutulan pencere BIRINCIL KANIT DEGIL; --dogrula ile yalnizca
  onceden ilan edilmis dogrulama olarak bir kez acilir. Karar, kanit
  ikisinde de ayni yonu gostermedikce kesinlestirilmez.
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
from scout.kaynaklar import db_yolu  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))

import train_model as tm  # noqa: E402
from scout.model.ranker import esli_bootstrap, fark_ga, lig_ici_auc  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = db_yolu()  # SCOUT_DB ya da data/scout.duckdb (FAZ 9.5)

PIYASA_OZ = ["log_deger", "deger_var", "age_season_end"]
BASIT_OZ = ["minutes", "minutes_agepct", "age_season_end"]

# (ad, alt sinir, ust sinir) - deger EUR; 'yok' ayri
BANTLAR = [("1 <0,5M", 0, 5e5), ("2 0,5-2M", 5e5, 2e6),
           ("3 2-5M", 2e6, 5e6), ("4 >=5M", 5e6, np.inf)]


def bant_ata(deger: pd.Series) -> pd.Series:
    """Sezon-sonu degerine gore fiyat bandi. Degerleme yoksa '0 yok'."""
    out = pd.Series("0 yok", index=deger.index, dtype=object)
    for ad, lo, hi in BANTLAR:
        m = deger.notna() & (deger >= lo) & (deger < hi)
        out[m] = ad
    return out


def ucuz_mu(bant: pd.Series, tavan: str = "3 2-5M") -> pd.Series:
    """Kullanicinin tanimi: sezon-sonu degeri <=5M veya degerleme yok."""
    return bant.isin(["0 yok", "1 <0,5M", "2 0,5-2M", tavan])


def tahmin_uret(tr: pd.DataFrame, te: pd.DataFrame, C: float = 1.0
                ) -> pd.DataFrame:
    te = te.copy()
    for ad, kol in (("model", tm.OZELLIKLER), ("piyasa", PIYASA_OZ),
                    ("basit", BASIT_OZ), ("saf", tm.OZELLIKLER_SAF)):
        _, te[ad] = tm.egit(tm._hazirla(tr, kol), tr.y.to_numpy(),
                            tm._hazirla(te, kol, ref=tr), C)
    return te


def cv_tahmin(df: pd.DataFrame) -> pd.DataFrame:
    """Lig-disarida-birak: her satir kendi ligini hic gormemis modelden."""
    d = df.copy()
    for ad, kol in (("model", tm.OZELLIKLER), ("piyasa", PIYASA_OZ),
                    ("basit", BASIT_OZ), ("saf", tm.OZELLIKLER_SAF)):
        d[ad] = tm.lolo_cv(d, kol, 1.0)
    return d.dropna(subset=["model", "piyasa", "basit", "saf"])


def bant_raporu(d: pd.DataFrame, baslik: str, B: int = 300) -> pd.DataFrame:
    d = d.copy()
    d["bant"] = bant_ata(d.deger)
    d["ucuz"] = ucuz_mu(d.bant)
    kesitler = [(b, d[d.bant == b]) for b in sorted(d.bant.unique())]
    kesitler.append(("UCUZ (<=5M veya yok)", d[d.ucuz]))
    kesitler.append(("PAHALI (>5M)", d[~d.ucuz]))
    kesitler.append(("HEPSI", d))

    print(f"\n{'=' * 84}\n{baslik}\n{'=' * 84}")
    print(f"{'bant':24s}{'n':>6s}{'olumlu%':>9s}"
          f"{'model':>8s}{'piyasa':>8s}{'basit':>8s}{'saf':>8s}"
          f"   model-piyasa        model-basit         saf-basit")
    satir = []
    for ad, g in kesitler:
        if len(g) < 60 or g.y.sum() < 15 or (1 - g.y).sum() < 15:
            print(f"{ad:24s}{len(g):6d}   (yetersiz orneklem - olculmedi)")
            continue
        auc = {k: lig_ici_auc(g, k) for k in ("model", "piyasa", "basit", "saf")}
        bs = esli_bootstrap(g, ["model", "piyasa", "basit", "saf"], B=B)

        def f(a, b):
            o, lo, hi = fark_ga(bs, a, b)
            isaret = "*" if (lo > 0 or hi < 0) else " "
            return f"{o:+.3f}[{lo:+.2f},{hi:+.2f}]{isaret}"

        print(f"{ad:24s}{len(g):6d}{100 * g.y.mean():8.1f}%"
              f"{auc['model']:8.3f}{auc['piyasa']:8.3f}{auc['basit']:8.3f}"
              f"{auc['saf']:8.3f}   {f('model', 'piyasa')}  "
              f"{f('model', 'basit')}  {f('saf', 'basit')}")
        satir.append(dict(bant=ad, n=len(g), **auc,
                          mp=fark_ga(bs, "model", "piyasa"),
                          mb=fark_ga(bs, "model", "basit"),
                          sb=fark_ga(bs, "saf", "basit")))
    print("  * = %95 GA sifiri disliyor")
    return pd.DataFrame(satir)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dogrula", action="store_true",
                    help="2024 tutulan pencereyi ONCEDEN ILAN EDILMIS "
                         "dogrulama olarak ac")
    a = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    egitim = tm.veri_yukle(con, tm.EGITIM_SEZONLARI)
    d22 = tm.veri_yukle(con, (2022,))
    d23 = tm.veri_yukle(con, (2023,))
    print(f"[in] egitim {len(egitim):,} · 2022 {len(d22):,} · 2023 {len(d23):,}")

    # 1) BIRINCIL: lig-disarida-birak CV (2022+2023)
    cv = cv_tahmin(egitim)
    bant_raporu(cv, "BIRINCIL 1/2 - LIG-DISARIDA-BIRAK CV (2022+2023)")

    # 2) BIRINCIL: kayan baslangic (2022 -> 2023)
    ky = tahmin_uret(d22, d23)
    bant_raporu(ky, "BIRINCIL 2/2 - KAYAN BASLANGIC (2022 -> 2023)")

    # 3) DOGRULAMA (onceden ilan edilmis)
    if a.dogrula:
        d24 = tm.veri_yukle(con, (2024,))
        t = tahmin_uret(egitim, d24)
        bant_raporu(t, "DOGRULAMA - TUTULAN 2024 (4. bakis, betimleyici; "
                       "model secimi YOK)")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
