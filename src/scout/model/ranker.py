"""FAZ 2: denetlenmis siralama modeli.

HEDEF
    kademe >= 3  ("izlenen bir birinci ligde yer edindi", >=900 dk)
    Tanim ve sinirlar: src/scout/features/outcome.py, PLAN §38.

NEDEN LOJISTIK REGRESYON, NEDEN AGAC DEGIL
  1) n kucuk. U23 + 450 dk + skoru olan: egitimde 3.205 satir, olumlu
     sinif ~%12-57 (kapsama gore). Agac ensemble'i bu boyutta ezberler.
  2) SCOUT DOSYASI KATSAYILARA DAYANACAK (FAZ 4). "Bu oyuncu neden one
     cikti" sorusunun cevabi okunabilir olmali. Aciklanamayan bir skor
     saha gozlemine yon veremez.

DEGERLENDIRME NEDEN LIG ICINDE
  Taban oranlar lig ve kapsam turune gore ucuruma benziyor:
      kapsam 'tam'          -> %57 yer edinir (zaten izlenen ligdeler)
      kapsam 'sicrama_only' -> %12 sicrar
  Havuzlanmis AUC bu farki "model iyi ayirt ediyor" diye okur; oysa model
  yalnizca ligi tanimis olur. §31'de kurulan lig-ici AUC zorunlu.

SIZINTI DISIPLINI
  Egitim 2022+2023, test 2024. Test penceresi model secilene kadar HIC
  acilmaz. Egitim icinde lig-disarida-birak (leave-one-league-out) CV.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

RNG = np.random.default_rng(20260830)

HEDEF_KADEME = 3


def hedef(kademe: pd.Series) -> pd.Series:
    """Ikili hedef: izlenen bir ligde yer edindi mi."""
    return (kademe >= HEDEF_KADEME).astype(int)


# ------------------------------------------------------------- lig ici AUC
def _auc(y: np.ndarray, s: np.ndarray) -> float:
    """Basit ROC AUC (Mann-Whitney U). Beraberlikler 0,5 sayilir."""
    y = np.asarray(y)
    s = np.asarray(s, float)
    ok = np.isfinite(s)
    y, s = y[ok], s[ok]
    n1, n0 = int(y.sum()), int((1 - y).sum())
    if n1 == 0 or n0 == 0:
        return np.nan
    sira = pd.Series(s).rank().to_numpy()
    return (sira[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def lig_ici_auc(df: pd.DataFrame, skor: str, hedef_kol: str = "y") -> float:
    """Her (lig, sezon) icinde AUC, olumlu ornek sayisiyla agirlikli.

    Agirlik olumlu ornek sayisi: 3 olumlu ornekli bir lig-sezonun AUC'si
    100 olumlu ornekli bir digeriyle esit sayilmamali.
    """
    pay = agirlik = 0.0
    for _, g in df.groupby(["league_id", "season"]):
        a = _auc(g[hedef_kol].to_numpy(), g[skor].to_numpy())
        if np.isnan(a):
            continue
        w = float(g[hedef_kol].sum())
        pay += a * w
        agirlik += w
    return pay / agirlik if agirlik else np.nan


def esli_bootstrap(df: pd.DataFrame, kolonlar: list[str], hedef_kol: str = "y",
                   B: int = 400) -> pd.DataFrame:
    """OYUNCU bazinda esli bootstrap: her yeniden ornekte TUM kolonlar.

    Esli olmasi sart - ayni orneklem uzerinde karsilastirilan iki yontem
    korelasyonlu; bagimsiz bootstrap fark varyansini sisirir ve gercek
    farklari 'anlamsiz' gosterir (29 Agu denetiminde tam bu hata
    yapilmisti, §31).

    Oyuncu bazinda olmasi sart - ayni oyuncu birden cok sezonda
    gorunuyor; satirlari bagimsiz saymak guven araligini yapay daraltir.
    """
    gruplar = df.groupby("player_id").indices
    oyuncular = np.array(list(gruplar.keys()))
    kayit = []
    for _ in range(B):
        sec = RNG.choice(oyuncular, len(oyuncular), replace=True)
        s = df.iloc[np.concatenate([gruplar[o] for o in sec])]
        kayit.append({k: lig_ici_auc(s, k, hedef_kol) for k in kolonlar})
    return pd.DataFrame(kayit)


def fark_ga(bs: pd.DataFrame, a: str, b: str) -> tuple[float, float, float]:
    """a - b farkinin ortalamasi ve %95 guven araligi."""
    d = (bs[a] - bs[b]).dropna()
    if len(d) < 10:
        return np.nan, np.nan, np.nan
    return float(d.mean()), float(d.quantile(0.025)), float(d.quantile(0.975))
