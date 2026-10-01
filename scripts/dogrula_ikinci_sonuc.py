"""FAZ 6.2b: TM'nin kor oldugu grubu KENDI VERIMIZDEN dogrula.

    python scripts/dogrula_ikinci_sonuc.py

Model TM sonucu (kademe>=3) ile egitildi. Burada hedef BAMBASKA bir sonuc:
kendi verimizde orijinden daha ust seviyedeki bir ligde >=450 dk (outcome2.py).
Model bu sonucu hic gormedi -> bagimsiz dogrulama.

Tahminler lig-disarida-birak CV'den (2022+2023) - her satir kendi ligini
hic gormemis modelden. 2024 orijinleri gozlenemez (2025 kapali) ve DISLANIR.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import fiyat_bandi as fb  # noqa: E402
import train_model as tm  # noqa: E402
from scout.features.outcome2 import ust_gecis, yon_dengesi  # noqa: E402
from scout.model.ranker import esli_bootstrap, fark_ga, lig_ici_auc  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = ROOT / "data" / "scout.duckdb"
TM_KOR_LIGLER = {128, 71, 239, 242, 244, 103, 113}   # oyuncu bazinda TM kaydi yok


def kesit_raporu(d: pd.DataFrame, ad_kol: str = "y2", B: int = 300) -> None:
    d = d.copy()
    d["y"] = d[ad_kol]
    print(f"{'kesit':34s}{'n':>6s}{'olumlu':>8s}{'taban%':>8s}"
          f"{'model':>8s}{'piyasa':>8s}{'basit':>8s}{'saf':>8s}"
          f"   model-basit          saf-basit           model-piyasa")
    kes = [
        ("HEPSI (T2-T4 orijin)", d),
        ("  deger VAR", d[d.deger_var == 1]),
        ("  deger YOK  <- TM kor grubu", d[d.deger_var == 0]),
        ("  kapsam sicrama_only", d[d.kapsam == "sicrama_only"]),
        ("  TM kor ligler (ARG/BRA/COL/...)", d[d.league_id.isin(TM_KOR_LIGLER)]),
        ("  ucuz (<=5M veya yok)", d[d.ucuz]),
    ]
    for ad, g in kes:
        if len(g) < 80 or g.y.sum() < 15 or (1 - g.y).sum() < 15:
            print(f"{ad:34s}{len(g):6d}{int(g.y.sum()):8d}   (yetersiz orneklem)")
            continue
        auc = {k: lig_ici_auc(g, k) for k in ("model", "piyasa", "basit", "saf")}
        bs = esli_bootstrap(g, ["model", "piyasa", "basit", "saf"], B=B)

        def f(a, b):
            o, lo, hi = fark_ga(bs, a, b)
            return f"{o:+.3f}[{lo:+.2f},{hi:+.2f}]" + (
                "*" if (lo > 0 or hi < 0) else " ")

        print(f"{ad:34s}{len(g):6d}{int(g.y.sum()):8d}{100 * g.y.mean():7.1f}%"
              f"{auc['model']:8.3f}{auc['piyasa']:8.3f}{auc['basit']:8.3f}"
              f"{auc['saf']:8.3f}   {f('model', 'basit')} {f('saf', 'basit')} "
              f"{f('model', 'piyasa')}")
    print("  * = %95 GA sifiri disliyor")


def main() -> int:
    con = duckdb.connect(str(DB), read_only=True)
    egitim = tm.veri_yukle(con, tm.EGITIM_SEZONLARI)
    havuz = con.sql("""SELECT player_id, league_id, season, country, minutes
                       FROM player_features""").df()
    tum_orijin = con.sql("""SELECT player_id, league_id, season, country,
                                   age_season_end
                            FROM player_features WHERE minutes>=450""").df()
    con.close()

    # ---- 1) SEVIYE tanimini VERIYLE sina ---------------------------------
    print("=" * 84)
    print("1) SEVIYE TANIMI SINAMASI - yon dengesi (yukari gecis orani)")
    print("=" * 84)
    for ad, o in (("tum yaslar", tum_orijin),
                  ("U23", tum_orijin[tum_orijin.age_season_end < 23])):
        r = yon_dengesi(o[["player_id", "league_id", "season", "country"]],
                        havuz)
        print(f"  {ad:11s} yukari {r['yukari']:5d} · asagi {r['asagi']:5d} · "
              f"ayni seviye {r['ayni']:5d} · yukari orani "
              f"%{100 * r['yukari_orani']:.0f}")
    print("  (tanim dogruysa genc orijinlerde yukari orani belirgin > %50)")

    # ---- 2) sonuc + tahminler --------------------------------------------
    o = ust_gecis(egitim[["player_id", "league_id", "season", "country"]],
                  havuz)
    d = cv_ekle(egitim)
    d = d.merge(o[["player_id", "league_id", "season", "o_seviye",
                   "gozlenebilir", "y2", "hedef_lig", "herhangi_sonraki"]],
                on=["player_id", "league_id", "season"], how="left")
    d["bant"] = fb.bant_ata(d.deger)
    d["ucuz"] = fb.ucuz_mu(d.bant)

    print(f"\n[in] egitim havuzu {len(d):,} · gozlenebilir "
          f"{int(d.gozlenebilir.sum()):,} · T1 orijin (yukari cikamaz) "
          f"{int((d.o_seviye == 1).sum()):,}")
    ok = d[d.gozlenebilir & (d.o_seviye >= 2)]
    print(f"[in] degerlendirilebilir (gozlenebilir, T2-T4 orijin): {len(ok):,}"
          f" · y2 olumlu {int(ok.y2.sum()):,} (%{100 * ok.y2.mean():.1f})")

    # ---- 3) iki sonucun uyumu --------------------------------------------
    gor = ok[ok.kapsam == "tam"]
    print(f"\n2) IKI SONUCUN UYUMU (izlenen ligler; her ikisi de gorunur)")
    if len(gor) > 50:
        print(f"   corr(y_TM, y2) = {np.corrcoef(gor.y, gor.y2)[0, 1]:+.3f} "
              f"(n={len(gor)})")

    print(f"\n{'=' * 84}\n3) MODELIN IKINCI SONUCU ONGORMESI (lig-ici AUC) - "
          f"bagimsiz dogrulama\n{'=' * 84}")
    kesit_raporu(ok)
    return 0


def cv_ekle(egitim: pd.DataFrame) -> pd.DataFrame:
    return fb.cv_tahmin(egitim)


if __name__ == "__main__":
    sys.exit(main())
