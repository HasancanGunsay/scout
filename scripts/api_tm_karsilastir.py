"""FAZ 7.4: API modeli vs TM modeli - ayni oyuncu-sezonlarda (2022-2024).

    python scripts/api_tm_karsilastir.py

SORU: Izlenen liglerde API'nin oyun metrikleri (rating, ikili mucadele,
pas, top kesme...) TM'nin bilmedigi bir sey biliyor mu? Ucretli veriye
gecme kararinin dayanagi bu.

KURULUM
  Nufus  : 2022-24, izlenen 9 lig (kapsam 'tam'), U23. Iki tabloda da olan
           oyuncu-sezonlar (API >=450 dk VE TM >=450 dk).
  API    : player_ranking (disaridan; 2022/23 lig-disi CV, 2024 zaman-disi),
           KALIBRASYON ONCESI (*_ham) - lig-ici AUC kalibrasyondan etkilenmez.
  TM     : ileri-zincir - sezon t, 2013..t-1 ile egitilmis modelle (§54).
  Birlesik: logit ortalamasi. PARAMETRESIZ - ayni veride agirlik ogrenmek
           iyimser olurdu.

ONCEDEN YAZILAN OKUMA
  Ana:   birlesik - TM > 0 (oyuncu-kumeli %95 GA sifirin ustunde)
         => API metrikleri TM'nin ustune bilgi katiyor.
  Ikinci: API saf - TM saf (ikisi de piyasa degeri OLMADAN): hangi oyun
          verisi daha bilgili?
  2024 API tahminleri 6. kez kullaniliyor (§50.6 sayaci); burada model
  SECIMI yok, betimleyici karsilastirma.
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

from scout.features.outcome import TM_KARSILIGI  # noqa: E402
from scout.model.egitim import _hazirla, egit  # noqa: E402
from scout.model.kalibrasyon import _logit  # noqa: E402
from scout.model.ranker import esli_bootstrap, fark_ga, lig_ici_auc  # noqa: E402
from scout.model.tm_model import VARYANTLAR, hazirla  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = ROOT / "data" / "scout.duckdb"
SEZONLAR = (2022, 2023, 2024)
B = 1000


def tm_ileri(d: pd.DataFrame) -> pd.DataFrame:
    out = []
    for t in SEZONLAR:
        tr = d[(d.season >= 2013) & (d.season < t) & d.y.notna()]
        te = d[d.season == t].copy()
        for v in ("tam", "saf", "basit", "piyasa"):
            kol = VARYANTLAR[v]
            _, te[f"tm_{v}"] = egit(_hazirla(tr, kol), tr.y.to_numpy(),
                                    _hazirla(te, kol, ref=tr))
        out.append(te)
    return pd.concat(out, ignore_index=True)


def birlestir(con) -> pd.DataFrame:
    tm = hazirla(con.sql("SELECT * FROM tm_oyuncu_sezon").df())
    tm = tm_ileri(tm)
    api = con.sql("""
        SELECT r.player_id api_id, r.league_id, r.season, r.pos_group api_pos,
               r.model_ham api_tam, r.saf_ham api_saf, r.basit api_basit,
               r.piyasa_ham api_piyasa, r.kademe, o.tm_id
        FROM player_ranking r
        JOIN player_outcome o USING (player_id, league_id, season)
        WHERE r.kapsam = 'tam' AND r.season IN (2022, 2023, 2024)""").df()
    api["comp"] = api.league_id.map(TM_KARSILIGI)
    x = api.merge(tm, left_on=["tm_id", "season", "comp"],
                  right_on=["player_id", "season", "comp"], how="inner",
                  suffixes=("", "_tm"))
    # ayni sonuc tanimi: iki tablonun kademesi ayni olmali (§52.4: %100)
    uyum = (x.kademe == x.kademe_tm).mean()
    print(f"[in] API {len(api):,} · eslesen {len(x):,} · kademe uyumu %{100 * uyum:.2f}")
    x["y"] = (x.kademe >= 3).astype(int)
    x["birlesik"] = (_logit(x.api_tam) + _logit(x.tm_tam)) / 2
    x["birlesik_saf"] = (_logit(x.api_saf) + _logit(x.tm_saf)) / 2
    x["player_id"] = x.tm_id                  # bootstrap kumesi
    return x


KOL = ["api_tam", "tm_tam", "birlesik", "api_saf", "tm_saf", "birlesik_saf",
       "api_basit", "tm_basit", "api_piyasa", "tm_piyasa"]
CIFT = [("birlesik", "tm_tam"), ("birlesik", "api_tam"), ("api_tam", "tm_tam"),
        ("api_saf", "tm_saf"), ("birlesik_saf", "tm_saf"),
        ("tm_tam", "tm_basit"), ("api_tam", "api_basit")]


def rapor(x: pd.DataFrame, baslik: str, ciftler=CIFT, b: int = B) -> None:
    if len(x) < 150 or x.y.sum() < 30 or (1 - x.y).sum() < 30:
        print(f"\n[{baslik}] n={len(x)} - yetersiz")
        return
    print(f"\n--- {baslik} (n={len(x):,}, olumlu %{100 * x.y.mean():.1f}) ---")
    print("  " + " ".join(f"{k}={lig_ici_auc(x, k):.3f}" for k in KOL))
    bs = esli_bootstrap(x, KOL, B=b)
    for a, c in ciftler:
        o, lo, hi = fark_ga(bs, a, c)
        print(f"  {a:>13s} - {c:<10s} {o:+.3f} [{lo:+.3f}, {hi:+.3f}]"
              + ("*" if lo > 0 or hi < 0 else ""))


def main() -> int:
    con = duckdb.connect(str(DB), read_only=True)
    x = birlestir(con)
    con.close()
    rapor(x, "HEPSI 2022-24, izlenen 9 lig")
    for s in SEZONLAR:
        rapor(x[x.season == s], f"sezon {s}", [("birlesik", "tm_tam"),
                                                ("api_tam", "tm_tam")], 400)
    for pg in ("Defender", "Midfielder", "Attacker"):
        rapor(x[x.pos_group == pg], f"mevki {pg}",
              [("birlesik", "tm_tam"), ("api_tam", "tm_tam"),
               ("api_saf", "tm_saf")], 400)
    print("\n--- ince mevki (AUC; aralik icin n kucuk) ---")
    for m, g in x.groupby("ince_mevki"):
        if len(g) >= 100 and 20 <= g.y.sum() <= len(g) - 20:
            print(f"  {m:20s} n={len(g):4d} api_tam={lig_ici_auc(g, 'api_tam'):.3f} "
                  f"tm_tam={lig_ici_auc(g, 'tm_tam'):.3f} "
                  f"birlesik={lig_ici_auc(g, 'birlesik'):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
