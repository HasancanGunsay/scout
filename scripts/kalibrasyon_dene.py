"""FAZ 6.6: kapsam-kosullu kalibrasyon denemesi.

    python scripts/kalibrasyon_dene.py              # yalniz 2022+2023 lig-disi CV
    python scripts/kalibrasyon_dene.py --dogrula    # + 2024 teyidi (held-out BAKIS)

Girdi: player_ranking (disaridan tahminler). Kalibrator de disaridan kurulur:
her lig icin YALNIZ diger liglerin tahmin+sonucuyla (lolo_kalibre).

VARYANTLAR
  ham      kalibrasyonsuz
  global   tek Platt
  kapsam   Platt, kapsam basina (tam / sicrama_only)
  kd       Platt, kapsam x deger_var basina

KARAR KURALI (calistirmadan ONCE yazildi):
  Bir varyant benimsenir ancak ve ancak 2022+2023 lig-disi CV'de
   (1) genel ECE ham'dan dusuk ve lig-kumeli bootstrap %95 GA sifiri disliyor,
   (2) Brier ham'dan kotu DEGIL (fark GA ust siniri <= 0),
   (3) iki kapsamin hicbirinde ECE kotulesmiyor (nokta tahmini).
  Birden fazla gecerse en BASIT olan (global < kapsam < kd); karmasik olan
  ancak basitten Brier'de GA sifiri dislayarak iyiyse secilir.
  2024 yalnizca teyittir; karari degistirmez, kaydedilir.

KURAL DUZELTMESI (ilk calistirmadan SONRA - acikca kayitli, PLAN §50):
  (1)'deki GENEL ECE bu soruna kor: izlenen liglerde model kotumser,
  dusuk gorunurlukte iyimser; ayni olasilik kovasinda iki hata birbirini
  goturuyor (genel ECE 0,014 iken kapsam-ici ECE'ler 0,089 / 0,063).
  Planin hedefi (§43, 6.6) KAPSAM-KOSULLU kalibrasyon hatasiydi. (1) su
  olcuyle degistirildi: 'kosullu ECE' = kapsam-ici ECE'lerin n-agirlikli
  ortalamasi. Sonradan duzeltme oldugu icin 2024 teyidi ZORUNLU sayildi:
  2024'te de kosullu ECE ve Brier iyilesmiyorsa benimsenmez.
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

from scout.model.kalibrasyon import (brier, ece, grup_fit, grup_uygula,  # noqa: E402
                                     kosullu_ece, lolo_kalibre, logloss)
from scout.model.ranker import _auc  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = db_yolu()  # SCOUT_DB ya da data/scout.duckdb (FAZ 9.5)
VARYANT = {"ham": None, "global": "__yok__", "kapsam": "kapsam", "kd": "kd"}
SIRA = ["ham", "global", "kapsam", "kd"]


def veri(con) -> pd.DataFrame:
    d = con.sql("SELECT * FROM player_ranking WHERE kademe IS NOT NULL").df()
    d["y"] = (d.kademe >= 3).astype(int)
    if "model_ham" in d.columns:          # tablo 6.6 sonrasi: kalibre DEGIL, ham
        d["model_olasilik"] = d.model_ham
    d["kd"] = d.kapsam + "_" + d.deger_var.astype(int).astype(str)
    d["__yok__"] = "hepsi"
    return d.reset_index(drop=True)


def kalibre_lolo(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["p_ham"] = d.model_olasilik
    for v in SIRA[1:]:
        d[f"p_{v}"] = lolo_kalibre(d, "model_olasilik", VARYANT[v])
    return d


def kalibre_zaman(egit: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    t = test.copy()
    t["p_ham"] = t.model_olasilik
    for v in SIRA[1:]:
        g = VARYANT[v]
        par = grup_fit(egit.model_olasilik, egit.y, egit[g].astype(str))
        t[f"p_{v}"] = grup_uygula(t.model_olasilik, t[g].astype(str), par)
    return t


def ust_sapma(d: pd.DataFrame, kol: str, n: int = 50) -> pd.DataFrame:
    """Defterin olcusu (§42.3): sezon x kapsam basina ilk n - ne dedi/ne oldu."""
    top = (d.sort_values("p_ham", ascending=False)
            .groupby(["season", "kapsam"]).head(n))
    return top.groupby("kapsam").apply(
        lambda g: pd.Series({"n": len(g), "dedi": g[kol].mean(),
                             "oldu": g.y.mean(),
                             "sapma": g[kol].mean() - g.y.mean()}))


def ucuz_top20(d: pd.DataFrame, kol: str) -> float:
    """Karisik (iki kapsam) ucuz havuzda sezon x mevki top-20 isabeti."""
    u = d[d.ucuz]
    h = [g.nlargest(20, kol).y.mean() for _, g in u.groupby(["season", "pos_group"])
         if len(g) >= 60]
    return float(np.mean(h))


def metrikler(d: pd.DataFrame, v: str) -> dict:
    p = d[f"p_{v}"]
    o = {"ece": ece(p, d.y), "ece_k": kosullu_ece(p, d.y, d.kapsam),
         "brier": brier(p, d.y), "logloss": logloss(p, d.y),
         "auc_havuz": _auc(d.y.to_numpy(), p.to_numpy()),
         "top20_ucuz": ucuz_top20(d, f"p_{v}")}
    for k, g in d.groupby("kapsam"):
        o[f"ece_{k}"] = ece(g[f"p_{v}"], g.y)
        o[f"sapma_{k}"] = float(g[f"p_{v}"].mean() - g.y.mean())
    return o


def _ece_k(s, kol):
    return kosullu_ece(s[kol], s.y, s.kapsam)


def _brier(s, kol):
    return brier(s[kol], s.y)


def lig_bootstrap(d: pd.DataFrame, a: str, b: str, fn, B: int = 1000,
                  seed: int = 7) -> tuple[float, float, float]:
    """fn(s, p_a) - fn(s, p_b); ligler yeniden orneklenir (lig = kume)."""
    rng = np.random.default_rng(seed)
    ligler = d.league_id.unique()
    gruplar = {l: g for l, g in d.groupby("league_id")}
    nokta = fn(d, f"p_{a}") - fn(d, f"p_{b}")
    fark = []
    for _ in range(B):
        s = pd.concat([gruplar[l] for l in rng.choice(ligler, len(ligler))])
        fark.append(fn(s, f"p_{a}") - fn(s, f"p_{b}"))
    lo, hi = np.percentile(fark, [2.5, 97.5])
    return float(nokta), float(lo), float(hi)


def rapor(d: pd.DataFrame, baslik: str, bootstrap: bool = True) -> dict:
    print(f"\n{'=' * 96}\n{baslik}  (n={len(d):,}, olumlu={int(d.y.sum())}, "
          f"lig={d.league_id.nunique()})\n{'=' * 96}")
    print(f"{'varyant':9s}{'ECE kos':>8s}{'ECE gen':>8s}{'Brier':>8s}{'logloss':>9s}{'AUC havuz':>10s}"
          f"{'top20 ucuz':>11s}{'ECE tam':>9s}{'ECE sic':>9s}"
          f"{'sapma tam':>11s}{'sapma sic':>11s}")
    m = {}
    for v in SIRA:
        m[v] = metrikler(d, v)
        r = m[v]
        print(f"{v:9s}{r['ece_k']:8.4f}{r['ece']:8.4f}{r['brier']:8.4f}{r['logloss']:9.4f}"
              f"{r['auc_havuz']:10.4f}{r['top20_ucuz']:11.3f}{r['ece_tam']:9.4f}"
              f"{r['ece_sicrama_only']:9.4f}{r['sapma_tam']:+11.4f}"
              f"{r['sapma_sicrama_only']:+11.4f}")
    if bootstrap:
        print("\n  fark (varyant - ham), lig-kumeli bootstrap %95 GA:")
        for v in SIRA[1:]:
            e = lig_bootstrap(d, v, "ham", _ece_k)
            b = lig_bootstrap(d, v, "ham", _brier)
            m[v]["ece_fark"], m[v]["brier_fark"] = e, b
            print(f"  {v:8s} kosullu ECE {e[0]:+.4f} [{e[1]:+.4f}, {e[2]:+.4f}]"
                  f"{'*' if e[2] < 0 or e[1] > 0 else ' '}   "
                  f"Brier {b[0]:+.4f} [{b[1]:+.4f}, {b[2]:+.4f}]"
                  f"{'*' if b[2] < 0 or b[1] > 0 else ' '}")
        e = lig_bootstrap(d, "kd", "kapsam", _brier)
        print(f"  kd-kapsam Brier {e[0]:+.4f} [{e[1]:+.4f}, {e[2]:+.4f}]")
        m["kd"]["brier_kd_kapsam"] = e
    print("\n  ust dilim (defter olcusu: sezon x kapsam basina ilk 50):")
    for v in SIRA:
        s = ust_sapma(d, f"p_{v}")
        print(f"  {v:8s} " + " | ".join(
            f"{k}: dedi {r.dedi:.3f} oldu {r.oldu:.3f} sapma {r.sapma:+.3f}"
            for k, r in s.iterrows()))
    return m


def karar(m: dict) -> str:
    gecen = []
    for v in SIRA[1:]:
        r, h = m[v], m["ham"]
        k1 = r["ece_fark"][2] < 0
        k2 = r["brier_fark"][2] <= 0
        k3 = (r["ece_tam"] <= h["ece_tam"]
              and r["ece_sicrama_only"] <= h["ece_sicrama_only"])
        print(f"  {v:8s} (1) kosullu ECE GA<0: {k1}  (2) Brier kotu degil: {k2}  "
              f"(3) iki kapsamda ECE kotulesmiyor: {k3}")
        if k1 and k2 and k3:
            gecen.append(v)
    if not gecen:
        return "ham"
    secim = gecen[0]
    if "kd" in gecen and secim != "kd" and m["kd"]["brier_kd_kapsam"][2] < 0:
        secim = "kd"
    return secim


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dogrula", action="store_true",
                    help="2024 teyidi (held-out'a bir bakis daha - kaydedilir)")
    a = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    d = veri(con)
    con.close()
    cv = d[d.tahmin_turu == "lig-disi CV"].reset_index(drop=True)
    cv = kalibre_lolo(cv)
    m = rapor(cv, "2022+2023 LIG-DISI CV (kalibrator de lig-disi)")
    print(f"\n{'-' * 96}\nKARAR KURALI")
    secim = karar(m)
    print(f"\n  >>> SECIM: {secim}")

    if a.dogrula:
        t = d[d.tahmin_turu == "zaman-disi"].reset_index(drop=True)
        t = kalibre_zaman(cv, t)
        mt = rapor(t, "2024 ZAMAN-DISI TEYIT (kalibrator 2022+2023 CV'den)")
        if secim != "ham":
            e, b = mt[secim]["ece_fark"], mt[secim]["brier_fark"]
            ok = e[2] < 0 and b[2] <= 0
            print(f"\n  >>> 2024 TEYIT ({secim}): {'GECTI' if ok else 'GECMEDI - benimsenmez'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
