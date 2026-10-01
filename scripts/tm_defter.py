"""FAZ 7.5: TM ileriye donuk defteri - 2025/26 havuzu.

    python scripts/tm_defter.py --kaydet    # havuzu bugun kaydet (ekleme yalniz)
    python scripts/tm_defter.py --durum     # kac iddia, pencere ne zaman kapaniyor
    python scripts/tm_defter.py --puanla    # YALNIZ pencere kapandiysa (2027-06-15+)

Model: 'tam' (§53), 2013-2024'un TAMAMIYLA egitilir. Kalibrasyon yok:
12 sezonla egitilen modelde guncelleme kurallari ham'dan iyi degil (§54).
Ayni oyuncular icin saf / dakika+yas / piyasa olasiliklari da yazilir -
P1-P4 (PLAN §56) puanlamada bunlarla karsilastirilir.

Defter: tm_iddia_defteri (DB) + data/defter/tm_iddia_defteri.csv (git).
Puanlama icin YENI bir TM anlik goruntusu gerekir (ucretsiz, CC0):
data/raw/transfermarkt/<tarih>/ altina koy, build_tm_tarih.py calistir.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import warnings
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout.model.egitim import _hazirla, egit  # noqa: E402
from scout.model.kalibrasyon import ece  # noqa: E402
from scout.model.ranker import esli_bootstrap, fark_ga, lig_ici_auc  # noqa: E402
from scout.model.tm_defter import (DEFTER_SEZONU, MODEL_SURUMU,  # noqa: E402
                                   PENCERE_BITIS, kayit_tablosu,
                                   pencere_kapandi_mi, puanla, yeni_satirlar)
from scout.model.tm_model import VARYANTLAR, hazirla  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = ROOT / "data" / "scout.duckdb"
CSV = ROOT / "data" / "defter" / "tm_iddia_defteri.csv"
HAM = sorted((ROOT / "data" / "raw" / "transfermarkt").glob(
    "*/transfermarkt-datasets.duckdb"))[-1]


def _defter(con) -> pd.DataFrame:
    try:
        return con.sql("SELECT * FROM tm_iddia_defteri").df()
    except duckdb.CatalogException:
        return pd.DataFrame()


def tahmin_et(d: pd.DataFrame) -> pd.DataFrame:
    tr = d[(d.season >= 2013) & (d.season < DEFTER_SEZONU) & d.y.notna()]
    h = d[d.season == DEFTER_SEZONU].copy()
    assert h.kademe.isna().all(), "2025 sonucu biliniyor olmamali (pencere acik)"
    for ad in ("tam", "saf", "basit", "piyasa"):
        kol = VARYANTLAR[ad]
        _, h["model" if ad == "tam" else ad] = egit(
            _hazirla(tr, kol), tr.y.to_numpy(), _hazirla(h, kol, ref=tr))
    print(f"[egitim] {len(tr):,} satir, sezon {tr.season.min()}-{tr.season.max()}"
          f" · havuz {DEFTER_SEZONU}: {len(h):,} oyuncu-lig")
    return h


def kulup_adlari(h: pd.DataFrame) -> pd.DataFrame:
    con = duckdb.connect()
    con.execute(f"ATTACH '{HAM.as_posix()}' AS r (READ_ONLY)")
    # ham dosyada kimlik turleri tablodan tabloya farkli (§52): INT'e cevir
    k = con.sql("SELECT TRY_CAST(club_id AS INT) club_id, name kulup "
                "FROM r.clubs").df()
    g = con.sql("SELECT player_id, current_club_name guncel_kulup FROM r.players").df()
    con.close()
    return h.merge(k, on="club_id", how="left").merge(g, on="player_id", how="left")


def kaydet() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    d = hazirla(con.sql("SELECT * FROM tm_oyuncu_sezon").df())
    eski = _defter(con)
    con.close()
    h = kulup_adlari(tahmin_et(d))
    aday = kayit_tablosu(h, dt.date.today(), HAM.parent.name)
    yeni = yeni_satirlar(aday, eski)
    if yeni.empty:
        print("[kaydet] yeni iddia yok - havuz zaten defterde (ekleme yalniz)")
        return
    con = duckdb.connect(str(DB))
    con.register("yeni", yeni)
    con.execute("CREATE TABLE IF NOT EXISTS tm_iddia_defteri AS "
                "SELECT * FROM yeni WHERE 1=0")
    con.execute("INSERT INTO tm_iddia_defteri BY NAME SELECT * FROM yeni")
    hepsi = _defter(con)
    con.close()
    CSV.parent.mkdir(parents=True, exist_ok=True)
    hepsi.sort_values(["model_surumu", "comp", "pos_group", "sira_lig_mevki"]).to_csv(
        CSV, index=False, encoding="utf-8", lineterminator="\n")
    print(f"[kaydet] {len(yeni):,} iddia yazildi -> tm_iddia_defteri "
          f"(+ {CSV.relative_to(ROOT)})")
    ozet(yeni)


def ozet(d: pd.DataFrame) -> None:
    print(f"\n  havuz: {len(d):,} oyuncu · {d.comp.nunique()} lig · "
          f"ucuz (degerli, <=5M) {int(d.ucuz.sum()):,} · deger bilinmiyor {int((d.deger_var == 0).sum())}")
    print("  mevki: " + ", ".join(f"{k} {v}" for k, v in
                                  d.pos_group.value_counts().items()))
    print(f"  model olasiligi: ortalama {d.model_olasilik.mean():.3f} · "
          f"medyan {d.model_olasilik.median():.3f}")
    print(f"  pencere kapanisi: {PENCERE_BITIS} (sonuc ancak sonra, yeni TM verisiyle)")


def durum() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    d = _defter(con)
    veri_sonu = con.sql("SELECT max(sezon_bitis) FROM tm_oyuncu_sezon").fetchone()[0]
    con.close()
    if d.empty:
        print("[durum] TM defteri bos - once --kaydet")
        return
    print(f"[durum] {len(d):,} iddia · surumler {d.model_surumu.unique().tolist()} · "
          f"kayit {d.kayit_tarihi.min()}")
    kalan = (PENCERE_BITIS - dt.date.today()).days
    print(f"  pencere kapanisi {PENCERE_BITIS}: {max(kalan, 0)} gun kaldi")


def puanla_cmd() -> int:
    con = duckdb.connect(str(DB), read_only=True)
    d = _defter(con)
    s = con.sql("SELECT player_id, comp, season, kademe, pencere_tam "
                "FROM tm_oyuncu_sezon").df()
    con.close()
    if d.empty:
        print("[puanla] TM defteri bos - once --kaydet")
        return 0
    p = puanla(d, s)
    gelen = p[p.gerceklesti.notna()]
    if not len(gelen):
        print(f"[puanla] pencere ACIK - sonuc yok. Kapanis {PENCERE_BITIS}; "
              "sonra yeni TM anlik goruntusu + build_tm_tarih.py.")
        return 0
    g = gelen.assign(y=gelen.gerceklesti, league_id=gelen.comp)
    print(f"[puanla] sonucu gelen {len(g):,} / {len(p):,}")
    kol = ["model_olasilik", "saf_olasilik", "basit_olasilik", "piyasa_olasilik"]
    print("  " + " ".join(f"{k}={lig_ici_auc(g, k):.3f}" for k in kol))
    bs = esli_bootstrap(g, kol, B=1000)
    for a, b, ad in [("model_olasilik", "basit_olasilik", "P1 model - dakika+yas"),
                     ("model_olasilik", "piyasa_olasilik", "P2 model - piyasa")]:
        o, lo, hi = fark_ga(bs, a, b)
        print(f"  {ad:24s} {o:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    print(f"  P3 kalibrasyon: ECE {ece(g.model_olasilik, g.y):.3f} · sapma "
          f"{g.model_olasilik.mean() - g.y.mean():+.3f}")
    u = g[g.ucuz & (g.pos_group != "Goalkeeper")]
    for pg, x in u.groupby("pos_group"):
        print(f"  P4 {pg:11s} ucuz top-20: model {x.nlargest(20, 'model_olasilik').y.mean():.2f}"
              f" · dakika+yas {x.nlargest(20, 'basit_olasilik').y.mean():.2f} · "
              f"taban {x.y.mean():.2f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kaydet", action="store_true")
    ap.add_argument("--durum", action="store_true")
    ap.add_argument("--puanla", action="store_true")
    a = ap.parse_args()
    if a.kaydet:
        kaydet()
    if a.durum:
        durum()
    if a.puanla:
        return puanla_cmd()
    if not (a.kaydet or a.durum or a.puanla):
        durum()
    return 0


if __name__ == "__main__":
    sys.exit(main())
