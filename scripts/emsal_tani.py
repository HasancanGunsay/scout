"""FAZ 3 TANI: emsal orani neden zayif? Dort mesafe tanimini kiyasla.

    python scripts/emsal_tani.py

SORU
  Emsal orani lig-ici AUC 0,576 verdi ve vakalarin yalnizca %10'unda ligin
  taban oranindan ayirt edilebildi. Neden?

SUPHE
  Mesafe 12 boyutlu: 10'u STIL (CLR), 2'si seviye. Yani agirligin %83'u
  "nasil oynuyor" boyutunda. Oysa modelin en guclu degiskenleri
  deger_var (+1,44), log_deger (+0,88), minutes (+0,41) - piyasa degeri
  emsal eslestirmesine HIC girmiyor.

  Yani "benzer OYNAYANLARI" buluyoruz, "benzer DURUMDA olanlari" degil.

Kiyaslanan tanimlar:
  A  stil + seviye              (mevcut)
  B  model olasiligi komsulugu  (en yakin p degerleri)
  C  model ozellik uzayi, katsayiyla agirlikli
  D  stil + seviye + piyasa degeri

Sizinti disiplini: hedefler 2024, emsal havuzu YALNIZCA 2022+2023, model
2022+2023 ile egitilmis.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from scout.features.emsal import ASGARI_EMSAL, wilson  # noqa: E402
from scout.features.similarity import stil_vektorleri  # noqa: E402
from scout.model.ranker import lig_ici_auc  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = ROOT / "data" / "scout.duckdb"
K = 40
YAS_BANDI = 1.5
TABAN_BANDI = 0.10

MODEL_OZ = ["score", "score_age", "age_season_end", "minutes", "minutes_pct",
            "minutes_agepct", "rating_pct", "starts_pct", "log_deger",
            "deger_var"]


def _z(x):
    sd = x.std(axis=0)
    sd[sd < 1e-9] = 1.0
    return (x - x.mean(axis=0)) / sd


def veri(con) -> pd.DataFrame:
    import train_model as tm
    df = pd.concat([tm.veri_yukle(con, (2022, 2023)),
                    tm.veri_yukle(con, (2024,))], ignore_index=True)
    stil = con.sql("SELECT * FROM player_features").df()
    sk = [c for c in stil.columns if c.endswith("_p90_sh")]
    df = df.merge(stil[["player_id", "league_id", "season"] + sk],
                  on=["player_id", "league_id", "season"], how="left")
    pg = con.sql("""SELECT player_id, league_id, season, pos_group
                    FROM player_features""").df()
    df = df.merge(pg, on=["player_id", "league_id", "season"], how="left",
                  suffixes=("", "_x"))
    df["lig_taban"] = df.groupby(["league_id", "season"]).y.transform("mean")
    return df


def _model_egit(tr: pd.DataFrame):
    import train_model as tm
    return tm.egit(tm._hazirla(tr, MODEL_OZ), tr.y.to_numpy(),
                   tm._hazirla(tr, MODEL_OZ))[0]


def mesafe_uzayi(alt: pd.DataFrame, tanim: str, m=None) -> np.ndarray:
    """Emsal mesafesinin hesaplanacagi standartlastirilmis uzay."""
    import train_model as tm

    if tanim == "A_stil_seviye":
        X, _, idx = stil_vektorleri(alt)
        S = alt.loc[idx, ["score", "minutes_agepct"]].astype(float)
        return np.hstack([_z(X), _z(S.to_numpy())]), idx

    if tanim == "D_stil_seviye_deger":
        X, _, idx = stil_vektorleri(alt)
        S = alt.loc[idx, ["score", "minutes_agepct", "log_deger",
                          "deger_var"]].astype(float)
        return np.hstack([_z(X), _z(S.to_numpy())]), idx

    if tanim == "B_model_olasiligi":
        p = m.predict_proba(tm._hazirla(alt, MODEL_OZ))[:, 1]
        return _z(p.reshape(-1, 1)), alt.index

    if tanim == "C_model_uzayi":
        X = tm._hazirla(alt, MODEL_OZ)
        Xs = m[0].transform(X)               # StandardScaler
        w = np.abs(m[-1].coef_[0])
        return Xs * w, alt.index

    raise ValueError(tanim)


def calistir(df: pd.DataFrame, tanim: str, m=None) -> pd.DataFrame:
    havuz = df[df.season.isin([2022, 2023])]
    hedef = df[df.season == 2024]
    kayit = []
    for i, h in hedef.iterrows():
        uygun = havuz[
            (havuz.player_id != h.player_id)
            & (havuz.pos_group == h.pos_group)
            & (havuz.kapsam == h.kapsam)
            & ((havuz.age_season_end - h.age_season_end).abs() <= YAS_BANDI)
            & ((havuz.lig_taban - h.lig_taban).abs() <= TABAN_BANDI)]
        if len(uygun) < ASGARI_EMSAL:
            continue
        alt = pd.concat([uygun, hedef.loc[[i]]])
        Z, idx = mesafe_uzayi(alt, tanim, m)
        # stil vektoru eksik metrikte satir dusuruyor - hedef dustuyse atla
        if i not in list(idx) or len(idx) < ASGARI_EMSAL + 1:
            continue
        alt2 = alt.loc[idx]
        konum = list(idx).index(i)
        d = np.linalg.norm(Z - Z[konum], axis=1)
        alt2 = alt2.assign(uz=d)
        alt2 = alt2[alt2.index != i].nsmallest(K, "uz")
        olumlu = int(alt2.y.sum())
        lo, hi = wilson(olumlu, len(alt2))
        kayit.append(dict(player_id=h.player_id, league_id=h.league_id,
                          season=h.season, y=h.y, lig_taban=h.lig_taban,
                          oran=olumlu / len(alt2), lo=lo, hi=hi,
                          ustunde=lo > h.lig_taban))
    return pd.DataFrame(kayit)


def main() -> int:
    con = duckdb.connect(str(DB), read_only=True)
    df = veri(con)
    con.close()
    print(f"[in] {len(df):,} satir · 2024 hedef {int((df.season == 2024).sum()):,}")

    m = _model_egit(df[df.season.isin([2022, 2023])])

    satir = []
    for tanim in ("A_stil_seviye", "D_stil_seviye_deger",
                  "C_model_uzayi", "B_model_olasiligi"):
        r = calistir(df, tanim, m)
        if r.empty:
            continue
        # kalibrasyon hatasi: |dedigi - gerceklesen| kova ortalamasi
        r["kova"] = pd.qcut(r.oran, 5, duplicates="drop")
        kal = r.groupby("kova", observed=True).agg(
            dedi=("oran", "mean"), oldu=("y", "mean"), n=("y", "size"))
        kal_hata = float((kal.dedi - kal.oldu).abs().mul(kal.n).sum() / kal.n.sum())
        satir.append(dict(
            tanim=tanim, n=len(r),
            auc=round(lig_ici_auc(r, "oran"), 3),
            kalibrasyon_hatasi=round(kal_hata, 4),
            ga_genislik=round((r.hi - r.lo).mean(), 3),
            tabani_asan_pct=round(100 * r.ustunde.mean(), 1)))
    print("\n" + "=" * 74)
    print("EMSAL MESAFE TANIMLARI (2024 hedef · havuz 2022+2023)")
    print("=" * 74)
    print(pd.DataFrame(satir).to_string(index=False))
    print("\nauc          : ayirt etme gucu (model 0,706 · mevcut skor 0,608)")
    print("kal_hatasi   : |dedigi - gerceklesen|, kucuk iyi")
    print("tabani_asan  : GA'si ligin tabanini asan vaka orani")
    return 0


if __name__ == "__main__":
    sys.exit(main())
