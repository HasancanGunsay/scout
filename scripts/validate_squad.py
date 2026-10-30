"""Kadro analizinin iki DOGRULANMAMIS varsayimini sina (PLAN §34.2, §34.5).

Sayfa iki sey iddia ediyordu ve ikisi de olculmemisti:

  A) "+-8 percentile ici fark gurultudur"
     Temkinli bir varsayimdi, kalibre edilmemisti. Burada gurultuye UST
     SINIR olculuyor: ayni takim, ayni rol, ayni oyuncu iki ardisik sezonda
     en iyiyse, 'fark' degerinin sezonlar arasi oynamasi gercek degisim +
     gurultu. Gercek degisim >= 0 oldugu icin bu bir UST SINIR.

  B) "stil benzerligi yedek bulmaya yarar"
     Sonuc degiskeni yok deyip gecmistim. Var: KULUPLERIN KENDI DAVRANISI.
     Bir rolun en iyisi takimdan ayrildiginda yerine gelen oyuncu, ligdeki
     rastgele bir ayni-mevki oyuncusundan daha mi benzer stilde?
     Kulupler benzerini ariyorsa arac kuluplerin yaptigi isi olcuyor
     demektir; aramiyorsa aracin ongordugu sey kimsenin yapmadigi seydir.

Calistirma:
    python scripts/validate_squad.py
    python scripts/validate_squad.py --min-minutes 600
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

from scout.features.similarity import stil_vektorleri  # noqa: E402
from scout.features.squad import rol_haritasi  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = db_yolu()  # SCOUT_DB ya da data/scout.duckdb (FAZ 9.5)
SNAP = ROOT / "data" / "scout_ui_snapshot.duckdb"
RNG = np.random.default_rng(20260830)
B = 2000


def _baglan():
    """Streamlit acikken ana dosya kilitli olabiliyor - kopyaya dus."""
    for yol in (DB, SNAP):
        try:
            return duckdb.connect(str(yol), read_only=True)
        except duckdb.IOException:
            continue
    raise SystemExit("veritabani acilamadi")


def _ga(x, B=B):
    """Yuzde 95 bootstrap guven araligi."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 3:
        return np.nan, np.nan
    ort = RNG.choice(x, (B, len(x)), replace=True).mean(axis=1)
    return float(np.percentile(ort, 2.5)), float(np.percentile(ort, 97.5))


# ===================================================================== A
def gurultu_ust_siniri(scores: pd.DataFrame, min_dk: int) -> pd.DataFrame:
    """Ayni takim + ayni rol + AYNI OYUNCU, ardisik iki sezon.

    Oyuncu sabit tutuluyor cunku amac 'fark' olcusunun kendi oynakligini
    gormek - kadro degisimini degil. Kalan degisim yine de gercek gelisim
    iceriyor, o yuzden sonuc bir UST SINIR.
    """
    kayit = []
    for lig in scores.league_id.unique():
        sez = sorted(scores.loc[scores.league_id == lig, "season"].unique())
        for s0, s1 in zip(sez, sez[1:]):
            if s1 - s0 != 1:
                continue
            h = {}
            for s in (s0, s1):
                d = scores[(scores.league_id == lig) & (scores.season == s)
                           & (scores.minutes >= min_dk) & scores.score.notna()]
                if d.empty:
                    continue
                for t in d.team_name.dropna().unique():
                    m = rol_haritasi(d, t)
                    if len(m):
                        m = m.assign(team_name=t, season=s)
                        h[(t, s)] = m
            ortak = {t for (t, s) in h if s == s0} & {t for (t, s) in h if s == s1}
            for t in ortak:
                a = h[(t, s0)].set_index("role")
                b = h[(t, s1)].set_index("role")
                for r in a.index.intersection(b.index):
                    if a.loc[r, "player_name"] != b.loc[r, "player_name"]:
                        continue                      # oyuncu degismis - dislaniyor
                    kayit.append(dict(lig=lig, takim=t, rol=r,
                                      s0=s0, s1=s1,
                                      fark0=a.loc[r, "fark"],
                                      fark1=b.loc[r, "fark"]))
    return pd.DataFrame(kayit)


# ===================================================================== B
def _stil_uzakliklari(feats_lig: pd.DataFrame):
    """Lig havuzunda standartlastirilmis CLR uzakligi icin (Z, index)."""
    X, _, idx = stil_vektorleri(feats_lig)
    if len(idx) < 10:
        return None, None
    sd = X.std(axis=0)
    sd[sd < 1e-9] = 1.0
    return X / sd, list(idx)


def yerine_gelen_benzerligi(scores, feats, min_dk: int) -> pd.DataFrame:
    """Ayrilan oyuncunun yerine gelen, rastgele birinden daha mi benzer?

    Karsilastirma AYNI mevki grubu icinde yapiliyor - stoperle forveti
    kiyaslamak zaten anlamsiz, oradan gelecek fark bilgi tasimaz.
    """
    kayit = []
    for lig in scores.league_id.unique():
        sez = sorted(scores.loc[scores.league_id == lig, "season"].unique())
        for s0, s1 in zip(sez, sez[1:]):
            if s1 - s0 != 1:
                continue
            d0 = scores[(scores.league_id == lig) & (scores.season == s0)
                        & (scores.minutes >= min_dk) & scores.score.notna()]
            d1 = scores[(scores.league_id == lig) & (scores.season == s1)
                        & (scores.minutes >= min_dk) & scores.score.notna()]
            if d0.empty or d1.empty:
                continue

            # stil havuzu: iki sezon birlikte, tek olcekte
            fl = feats[(feats.league_id == lig) & (feats.season.isin([s0, s1]))]
            Z, idx = _stil_uzakliklari(fl)
            if Z is None:
                continue
            konum = {k: i for i, k in enumerate(idx)}
            anahtar = fl.loc[idx, ["player_id", "season", "pos_group"]] \
                        .reset_index(drop=True)
            anahtar["satir"] = range(len(anahtar))
            arama = {(int(r.player_id), int(r.season)): r.satir
                     for r in anahtar.itertuples()}
            mevki = {(int(r.player_id), int(r.season)): r.pos_group
                     for r in anahtar.itertuples()}
            s1_satir = anahtar[anahtar.season == s1]

            ortak = set(d0.team_name.dropna()) & set(d1.team_name.dropna())
            for t in ortak:
                kadro1 = set(d1.loc[d1.team_name == t, "player_id"])
                a0 = d0[d0.team_name == t]
                a1 = d1[d1.team_name == t]
                for rol in set(a0.role) & set(a1.role):
                    g0 = a0[a0.role == rol]
                    g1 = a1[a1.role == rol]
                    eski = g0.loc[g0.score.idxmax()]
                    if int(eski.player_id) in kadro1:
                        continue                      # ayrilmamis
                    yeni = g1.loc[g1.score.idxmax()]

                    k_eski = (int(eski.player_id), s0)
                    k_yeni = (int(yeni.player_id), s1)
                    if k_eski not in arama or k_yeni not in arama:
                        continue
                    pg = mevki[k_eski]
                    if mevki[k_yeni] != pg:
                        continue

                    i, j = arama[k_eski], arama[k_yeni]
                    u_yeni = float(np.linalg.norm(Z[i] - Z[j]))

                    # taban: ayni mevkideki TUM s1 oyunculari (kendisi haric)
                    aday = s1_satir[(s1_satir.player_id != yeni.player_id)]
                    aday_satir = [arama[(int(p), s1)] for p in aday.player_id
                                  if mevki.get((int(p), s1)) == pg]
                    if len(aday_satir) < 10:
                        continue
                    u_taban = np.linalg.norm(Z[aday_satir] - Z[i], axis=1)

                    kayit.append(dict(
                        lig=lig, takim=t, rol=rol, s0=s0, s1=s1,
                        ayrilan=eski.player_name, gelen=yeni.player_name,
                        pos_group=pg,
                        uzaklik_gelen=u_yeni,
                        uzaklik_taban=float(np.median(u_taban)),
                        yuzdelik=float((u_taban < u_yeni).mean()),
                    ))
    return pd.DataFrame(kayit)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-minutes", type=int, default=450)
    a = ap.parse_args()

    con = _baglan()
    scores = con.sql("""
        SELECT player_id, player_name, team_name, league_id, season, role,
               role_name, score, minutes, age_season_end
        FROM player_scores WHERE score IS NOT NULL
    """).df()
    feats = con.sql("SELECT * FROM player_features").df()
    con.close()

    print(f"[in] {len(scores):,} skor satiri, esik {a.min_minutes} dk\n")

    # ---------------------------------------------------------------- A
    print("=" * 66)
    print("A) 'fark' ne kadar oynak?  (esik +-8 dogru mu)")
    print("=" * 66)
    g = gurultu_ust_siniri(scores, a.min_minutes)
    if len(g) < 30:
        print(f"yetersiz gozlem ({len(g)}) - sinanamadi\n")
    else:
        d = g.fark1 - g.fark0
        # tek gozlemin oynakligi: iki bagimsiz olcumun farkinin SD'si / sqrt(2)
        sd = float(d.std(ddof=1) / np.sqrt(2))
        lo, hi = _ga(np.abs(d))
        print(f"n = {len(g):,} (ayni takim + ayni rol + AYNI oyuncu, ardisik sezon)")
        print(f"sezonlar arasi degisimin SD'si : {d.std(ddof=1):.2f}")
        print(f"tek olcumun oynakligi (UST SINIR): {sd:.2f} percentile")
        print(f"|degisim| ortalamasi           : {np.abs(d).mean():.2f} "
              f"%95 GA [{lo:.2f}, {hi:.2f}]")
        print(f"|degisim| <= 8 olan oran       : %{100 * (np.abs(d) <= 8).mean():.0f}")
        print(f"|degisim| <= {2*sd:.0f} olan oran      : "
              f"%{100 * (np.abs(d) <= 2 * sd).mean():.0f}")
        print(f"\nONERI: esik ~{2 * sd:.0f} (tek olcumun 2 SD'si). "
              f"Mevcut 8 {'YETERSIZ' if 2 * sd > 9 else 'MAKUL'}.\n")

    # ---------------------------------------------------------------- B
    print("=" * 66)
    print("B) Kulupler ayrilanin yerine BENZER stilde oyuncu mu aliyor?")
    print("=" * 66)
    y = yerine_gelen_benzerligi(scores, feats, a.min_minutes)
    if len(y) < 30:
        print(f"yetersiz gozlem ({len(y)}) - sinanamadi\n")
    else:
        fark = y.uzaklik_taban - y.uzaklik_gelen      # + = gelen daha benzer
        lo, hi = _ga(fark)
        ylo, yhi = _ga(y.yuzdelik)
        print(f"n = {len(y):,} degisim (rolun en iyisi ayrilmis, yerine gelen var)")
        print(f"gelenin uzakligi        : {y.uzaklik_gelen.mean():.3f}")
        print(f"rastgele ayni-mevki     : {y.uzaklik_taban.mean():.3f}")
        print(f"FARK (+ = gelen benzer) : {fark.mean():+.3f} "
              f"%95 GA [{lo:+.3f}, {hi:+.3f}]")
        print(f"gelenin yuzdelik sirasi : {y.yuzdelik.mean():.3f} "
              f"%95 GA [{ylo:.3f}, {yhi:.3f}]   (0,50 = rastgele)")
        anlamli = (lo > 0) or (hi < 0)
        print(f"\nHUKUM: {'ANLAMLI' if anlamli else 'AYIRT EDILEMIYOR'} - "
              + ("kulupler benzer stil ariyor."
                 if anlamli and fark.mean() > 0 else
                 "kulupler benzer stil ARAMIYOR."
                 if anlamli else
                 "stil benzerligi kuluplerin davranisini ongormuyor."))
        print("\n--- mevki grubuna gore ---")
        for pg, alt in y.groupby("pos_group"):
            if len(alt) < 15:
                continue
            f = alt.uzaklik_taban - alt.uzaklik_gelen
            l, h = _ga(f)
            print(f"  {pg:12s} n={len(alt):4d}  fark {f.mean():+.3f} "
                  f"[{l:+.3f}, {h:+.3f}]")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
