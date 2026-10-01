"""FAZ 7.2: TM tarihsel modeli - gelistirme ve TEK ACILISLI muhurlu test.

    python scripts/tm_model.py --gelistir     # yalniz 2013-2017
    python scripts/tm_model.py --test         # 2018-2021 muhrunu AC (bir kez)

GELISTIRME (2013-2017): lig-disarida-birak CV + kayan baslangic
(2013-15 -> 2016-17). Iki karar burada, ONCEDEN yazili kurallarla verilir:
  K1 savunma baglami: tam - tam_savsiz, DEFANS alt grubunda iki
     dogrulamada da > 0 ve genelde anlamli negatif DEGILSE tutulur.
  K2 mevki etkilesimi: tam_mevki ancak tam'i iki dogrulamada da GA sifiri
     dislayarak yenerse benimsenir (projenin mevcut varyant kurali).

TEST (2018-2021): secilen model 2013-2017'nin tamamiyla egitilir, 2018-2021
bir kez tahmin edilir. Hipotezler PLAN §53'te, test ACILMADAN once yazildi
ve commit edildi. Acilis data/tm_tarih/muhur_acilis.json'a kaydedilir;
dosya varken --test calismaz (sonuclar reports/ altinda).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import warnings
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout.features.tm_tarih import GELISTIRME, MUHURLU_TEST  # noqa: E402
from scout.model.egitim import _hazirla, egit, lolo_cv  # noqa: E402
from scout.model.kalibrasyon import ece  # noqa: E402
from scout.model.ranker import esli_bootstrap, fark_ga, lig_ici_auc  # noqa: E402
from scout.model.tm_model import OZ_DEGER, VARYANTLAR, hazirla  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = ROOT / "data" / "scout.duckdb"
MUHUR = ROOT / "data" / "tm_tarih" / "muhur_acilis.json"
RAPOR = ROOT / "reports" / "tm_muhurlu_test_2018_2021.txt"
C = 1.0
B_GEL, B_TEST = 400, 1000
COVID = {2019: "2019/20 (COVID, ara verildi)", 2020: "2020/21 (seyircisiz)"}
UCUZ_TAVAN = 5e6


def yukle() -> pd.DataFrame:
    con = duckdb.connect(str(DB), read_only=True)
    tum = con.sql("SELECT * FROM tm_oyuncu_sezon").df()
    con.close()
    return hazirla(tum)


def _f(bs, a, b) -> str:
    o, lo, hi = fark_ga(bs, a, b)
    return f"{o:+.3f} [{lo:+.3f}, {hi:+.3f}]" + ("*" if lo > 0 or hi < 0 else " ")


def degerlendir(d: pd.DataFrame, kolonlar: list[str], ciftler, B: int,
                baslik: str) -> dict:
    """AUC tablosu + esli fark GA'lari. Doner: {cift: (o, lo, hi)}."""
    print(f"\n--- {baslik} (n={len(d):,}, olumlu %{100 * d.y.mean():.1f}) ---")
    print("  " + "  ".join(f"{k}={lig_ici_auc(d, k):.3f}" for k in kolonlar))
    bs = esli_bootstrap(d, kolonlar, B=B)
    sonuc = {}
    for a, b in ciftler:
        sonuc[(a, b)] = fark_ga(bs, a, b)
        print(f"  {a:>11s} - {b:<11s} {_f(bs, a, b)}")
    return sonuc


# ---------------------------------------------------------------- gelistirme
def gelistir(d: pd.DataFrame) -> dict:
    dev = d[d.season.isin(GELISTIRME) & d.y.notna()].reset_index(drop=True)
    assert not dev.season.isin(MUHURLU_TEST).any()
    print(f"[gelistirme] {len(dev):,} satir, sezonlar {sorted(dev.season.unique())}")

    lolo = dev.copy()
    for v, kol in VARYANTLAR.items():
        lolo[v] = lolo_cv(lolo, kol, C)
    lolo = lolo.dropna(subset=list(VARYANTLAR))

    tr = dev[dev.season <= 2015]
    kay = dev[dev.season >= 2016].copy()
    for v, kol in VARYANTLAR.items():
        _, kay[v] = egit(_hazirla(tr, kol), tr.y.to_numpy(),
                         _hazirla(kay, kol, ref=tr), C)

    ciftler = [("tam", "basit"), ("tam", "piyasa"), ("saf", "piyasa"),
               ("saf", "basit"), ("tam", "tam_savsiz"), ("tam_mevki", "tam")]
    kol = list(VARYANTLAR)
    r = {}
    for ad, x in (("LOLO", lolo), ("KAYAN", kay)):
        r[ad] = degerlendir(x, kol, ciftler, B_GEL, f"{ad} - HEPSI")
        r[ad + "_def"] = degerlendir(x[x.pos_group == "Defender"], kol,
                                     [("tam", "tam_savsiz"), ("tam", "basit")],
                                     B_GEL, f"{ad} - DEFANS")

    print(f"\n{'=' * 80}\nMEVKI MEVKI (LOLO, gelistirme) - lig-ici AUC\n{'=' * 80}")
    print(f"{'mevki':20s}{'n':>6s}" + "".join(f"{k:>11s}" for k in kol))
    for m, g in lolo.groupby("ince_mevki"):
        if len(g) >= 150:
            print(f"{m:20s}{len(g):6d}" + "".join(
                f"{lig_ici_auc(g, k):11.3f}" for k in kol))

    # ---- onceden yazili kararlar
    k1 = (r["LOLO_def"][("tam", "tam_savsiz")][0] > 0
          and r["KAYAN_def"][("tam", "tam_savsiz")][0] > 0
          and r["LOLO"][("tam", "tam_savsiz")][2] > 0
          and r["KAYAN"][("tam", "tam_savsiz")][2] > 0)
    k2 = (r["LOLO"][("tam_mevki", "tam")][1] > 0
          and r["KAYAN"][("tam_mevki", "tam")][1] > 0)
    final = ("tam_mevki" if k2 else "tam") if k1 else "tam_savsiz"
    print(f"\n{'=' * 80}\nKARARLAR\n{'=' * 80}")
    print(f"  K1 savunma baglami tutulsun mu : {k1}")
    print(f"  K2 mevki etkilesimi            : {k2}")
    print(f"  >>> SECILEN MODEL: {final}")
    return {"final": final, "k1": k1, "k2": k2}


# ---------------------------------------------------------------- test
def _ucuz_top20(t: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    u = t[(t.deger_var == 0) | (t.deger <= UCUZ_TAVAN)]
    s = []
    for (sez, pg), g in u.groupby(["season", "pos_group"]):
        if len(g) < 60 or pg == "Goalkeeper":
            continue
        s.append(dict(sezon=sez, mevki=pg, n=len(g), taban=g.y.mean(),
                      model=g.nlargest(20, a).y.mean(),
                      basit=g.nlargest(20, b).y.mean()))
    return pd.DataFrame(s)


def test(d: pd.DataFrame, final: str) -> None:
    if MUHUR.exists():
        print(f"[test] MUHUR ZATEN ACILDI ({json.loads(MUHUR.read_text())['tarih']}). "
              f"Ikinci acilis yok - sonuclar: {RAPOR.relative_to(ROOT)}")
        sys.exit(2)
    dev = d[d.season.isin(GELISTIRME) & d.y.notna()]
    t = d[d.season.isin(MUHURLU_TEST) & d.y.notna()].copy()
    saf_final = [c for c in VARYANTLAR[final] if c not in OZ_DEGER]
    modeller = {"model": VARYANTLAR[final], "saf": saf_final,
                "basit": VARYANTLAR["basit"], "piyasa": VARYANTLAR["piyasa"],
                "tam_savsiz": VARYANTLAR["tam_savsiz"]}
    for ad, kol in modeller.items():
        _, t[ad] = egit(_hazirla(dev, kol), dev.y.to_numpy(),
                        _hazirla(t, kol, ref=dev), C)
    MUHUR.parent.mkdir(parents=True, exist_ok=True)
    MUHUR.write_text(json.dumps({"tarih": dt.datetime.now().isoformat(
        timespec="seconds"), "final": final, "n": len(t)}), encoding="utf-8")

    kol = list(modeller)
    print(f"\n{'=' * 80}\nMUHURLU TEST 2018-2021 - TEK ACILIS · secilen: {final}"
          f"\n{'=' * 80}")
    ciftler = [("model", "basit"), ("model", "piyasa"), ("saf", "piyasa"),
               ("saf", "basit")]
    if final != "tam_savsiz":
        ciftler.append(("model", "tam_savsiz"))
    degerlendir(t, kol, ciftler, B_TEST, "H1-H3 HEPSI")
    if final != "tam_savsiz":
        degerlendir(t[t.pos_group == "Defender"], kol,
                    [("model", "tam_savsiz"), ("model", "basit")], B_TEST,
                    "H4 DEFANS")

    print(f"\n--- SEZON SEZON (COVID isaretli) ---")
    for s, g in t.groupby("season"):
        print(f"  {s} {COVID.get(s, ''):30s} n={len(g):4d} olumlu %{100*g.y.mean():4.1f} "
              f"model={lig_ici_auc(g, 'model'):.3f} basit={lig_ici_auc(g, 'basit'):.3f} "
              f"piyasa={lig_ici_auc(g, 'piyasa'):.3f} · ECE={ece(g.model, g.y):.3f} "
              f"sapma={g.model.mean() - g.y.mean():+.3f}")

    print(f"\n--- MEVKI MEVKI (model - basit) ---")
    for m, g in t.groupby("ince_mevki"):
        if len(g) < 120 or g.y.sum() < 25:
            continue
        bs = esli_bootstrap(g, ["model", "basit", "piyasa"], B=400)
        print(f"  {m:20s} n={len(g):4d} model={lig_ici_auc(g, 'model'):.3f} "
              f"basit={lig_ici_auc(g, 'basit'):.3f} piyasa={lig_ici_auc(g, 'piyasa'):.3f}"
              f"  model-basit {_f(bs, 'model', 'basit')}")

    u = _ucuz_top20(t, "model", "basit")
    print(f"\n--- H5 UCUZ BANT (<=5M ya da degersiz) TOP-20 ISABETI ---")
    print(u.round(3).to_string(index=False))
    print(f"  ortalama: model {u.model.mean():.3f} · basit {u.basit.mean():.3f} · "
          f"taban {u.taban.mean():.3f} · model kazandi {int((u.model > u.basit).sum())}"
          f"/{len(u)} (berabere {int((u.model == u.basit).sum())})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gelistir", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--final", choices=list(VARYANTLAR),
                    help="--test icin secilen model (gelistirme karari)")
    a = ap.parse_args()
    d = yukle()
    if a.gelistir:
        gelistir(d)
    if a.test:
        if not a.final:
            print("--test icin --final (gelistirmede secilen) gerekli")
            return 1
        test(d, a.final)
    return 0


if __name__ == "__main__":
    sys.exit(main())
