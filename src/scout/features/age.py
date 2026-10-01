"""Yas duzeltmesi - §1.3.

PROBLEM: 19 yasinda Ligue 2'de ortalama bir sezon, 26 yasinda ayni sezondan
COK daha degerlidir. Ham skor bunu goremez ve sistemin listesi 27 yasindaki
olgun oyuncularla dolar - oysa sen wonderkid ariyorsun.

IKI FARKLI CIKTI URETILIR:

  1. SIMDIKI SKOR    - oyuncu su anda ne kadar iyi (yas duzeltmesi YOK)
  2. POTANSIYEL SKOR - yasina gore ne kadar iyi (yas duzeltmeli)

19'luk bir cocuk 1'de dusuk, 2'de cok yuksek cikabilir. Scout ikisini de
gormeli: biri "bugun bana yardim eder mi", digeri "3 yil sonra ne olur".

IKI YONTEM (ikisi de uretilir, biri digerini dogrular):

  A) EGRI YONTEMI  - yas ~ performans egrisi fit edilir, oyuncunun kendi
     yasindaki beklentiden ne kadar SAPTIGI olculur. Surekli, puruzsuz.
  B) YAS BANDI     - oyuncu sadece kendi yas grubuyla kiyaslanir.
     Kaba ama saglam; az veriyle bile calisir.

UYARI: A yontemi anlamli bir egri icin genis veri ister. Su an elimizde
2 lig var; egri fit edilir ama veri biriktikce yeniden fit edilmeli.
`fit_quality` alani kac oyuncuyla fit edildigini soyler.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Wonderkid avi icin yas bantlari
AGE_BANDS = [(0, 19, "U19"), (19, 21, "U21"), (21, 23, "U23"), (23, 27, "23-26"),
             (27, 31, "27-30"), (31, 99, "31+")]


def add_age_band(df: pd.DataFrame, age_col: str = "age_season_end") -> pd.DataFrame:
    out = df.copy()
    age = pd.to_numeric(out[age_col], errors="coerce")
    band = pd.Series(pd.NA, index=out.index, dtype="string")
    for lo, hi, label in AGE_BANDS:
        band = band.mask(age.notna() & (age >= lo) & (age < hi), label)
    out["age_band"] = band
    return out


class AgeCurve:
    """Yas ~ performans egrisi (kubik polinom, lig sabit etkili).

    Lig sabit etkisi sart: Serie A ve Serie B'nin performans seviyeleri
    farkli, bunu kontrol etmezsek egri lig kompozisyonunu yansitir.
    """

    def __init__(self, degree: int = 3) -> None:
        self.degree = degree
        self.coef_: np.ndarray | None = None
        self.league_means_: dict = {}
        self.grand_mean_: float = np.nan
        self.n_fit_: int = 0
        self.age_min_: float = np.nan
        self.age_max_: float = np.nan
        # Tani: egri gercekten bilgi tasiyor mu?
        self.curve_range_: float = np.nan   # egrinin yas boyunca oynadigi aralik
        self.resid_sd_: float = np.nan      # kalan gurultunun std'si
        self.n_seasons_: int = 0
        self.peak_age_: float = np.nan          # egrinin tepe yaptigi yas
        self.decline_after_peak_: float = np.nan  # tepeden sona dusus miktari

    @property
    def informative(self) -> bool:
        """Egri kullanilabilir mi?

        Dort sart:
          - egrinin yas boyunca gezdigi aralik, gurultunun en az %25'i kadar
          - EN AZ IKI SEZON verisi
          - TEPE NOKTASI futbolca makul bir yasta (23-32)
          - tepeden sonra ANLAMLI bir dusus olmali

        Son iki sart 11 Agustos 2026'da eklendi, cunku ilk iki sart yeterli
        degilmis (§19). 2022 verisi gelince n_seasons_ 2 oldu ve egri
        "aktiflesti"; ama fit edilen egri 16 yasinda 6.767'den 38 yasinda
        6.965'e MONOTON ARTIYORDU - hic tepe yapmadan.

        Sorun su: iki sezonluk veriyi HAVUZLAYIP fit etmek boylamsal yapmaz,
        fit hala KESITSELDIR. Dolayisiyla 'iki sezon' sarti tasarlandigi isi
        gormuyordu. 35 yasinda hala oynayanlar secilmis bir azinliktir ve
        egri onlarin iyiligini yasa mal eder.

        Monoton artan bir yas egrisi hayatta kalma yanliliginin IMZASIDIR.
        Gercek futbolcu egrisi 26-28 civarinda tepe yapar ve 30'dan sonra
        duser. Sekli boyle degilse egri veriye degil yanliliga uymus demektir.
        """
        if self.coef_ is None or not np.isfinite(self.curve_range_):
            return False
        if self.n_seasons_ < 2:
            return False
        if self.curve_range_ < 0.25 * self.resid_sd_:
            return False
        if not np.isfinite(self.peak_age_):
            return False
        if not (23.0 <= self.peak_age_ <= 32.0):
            return False
        # tepeden sonra en az aralik kadarinin %15'i kadar dusus bekliyoruz;
        # aksi halde 'tepe' yalnizca degerlendirme araliginin ucu demektir
        return self.decline_after_peak_ >= 0.15 * self.curve_range_

    def fit(
        self,
        df: pd.DataFrame,
        metric: str,
        *,
        age_col: str = "age_season_end",
        league_col: str = "league_id",
        weight_col: str = "nineties",
        min_weight: float = 5.0,
    ) -> "AgeCurve":
        d = df[[metric, age_col, league_col, weight_col]].dropna()
        d = d[d[weight_col] >= min_weight]
        if len(d) < 40:
            self.n_fit_ = len(d)
            return self  # veri yetersiz - egri fit edilmez

        # 1) Lig etkisini cikar (her ligi kendi ortalamasina gore merkezle)
        self.grand_mean_ = float(np.average(d[metric], weights=d[weight_col]))
        self.league_means_ = {}
        centered = d[metric].copy()
        for lg, g in d.groupby(league_col):
            m = float(np.average(g[metric], weights=g[weight_col]))
            self.league_means_[lg] = m
            centered.loc[g.index] = g[metric] - m

        # 2) Kalan sinyale yas polinomu fit et, dakikaya gore agirlikli
        age = d[age_col].to_numpy(float)
        self.age_min_, self.age_max_ = float(age.min()), float(age.max())
        X = np.vander(age, self.degree + 1, increasing=True)
        w = d[weight_col].to_numpy(float)
        WX = X * w[:, None]
        self.coef_ = np.linalg.lstsq(WX.T @ X, WX.T @ centered.to_numpy(float), rcond=None)[0]
        self.n_fit_ = len(d)
        self.n_seasons_ = int(df["season"].nunique()) if "season" in df.columns else 1

        # Tani olcumleri
        fitted = X @ self.coef_
        self.resid_sd_ = float(np.std(centered.to_numpy(float) - fitted))
        tbl = self.curve_table(0.5)
        self.curve_range_ = float(tbl["expected"].max() - tbl["expected"].min())

        # Sekil tanisi: tepe nerede ve tepeden sonra dusuyor mu? (§19)
        i = int(tbl["expected"].idxmax())
        self.peak_age_ = float(tbl.loc[i, "age"])
        sonrasi = tbl[tbl["age"] > self.peak_age_]["expected"]
        self.decline_after_peak_ = (
            float(tbl.loc[i, "expected"] - sonrasi.min()) if len(sonrasi) else 0.0
        )
        return self

    def expected(self, age: pd.Series, league: pd.Series | None = None) -> pd.Series:
        """Verilen yas (ve lig) icin beklenen performans."""
        a = pd.to_numeric(age, errors="coerce")
        if self.coef_ is None:
            return pd.Series(np.nan, index=a.index, dtype=float)
        # Egriyi fit araligina kirp - disari ekstrapolasyon guvenilmez
        a_cl = a.clip(self.age_min_, self.age_max_)
        X = np.vander(a_cl.fillna(self.age_min_).to_numpy(float),
                      self.degree + 1, increasing=True)
        base = pd.Series(X @ self.coef_, index=a.index)
        if league is not None:
            base = base + league.map(self.league_means_).astype(float)
        else:
            base = base + self.grand_mean_
        return base.where(a.notna())

    def curve_table(self, step: float = 1.0) -> pd.DataFrame:
        """Egrinin yas-yas degerleri - grafikte gostermek ve denetlemek icin."""
        if self.coef_ is None:
            return pd.DataFrame(columns=["age", "expected"])
        ages = np.arange(np.floor(self.age_min_), np.ceil(self.age_max_) + step, step)
        X = np.vander(ages, self.degree + 1, increasing=True)
        return pd.DataFrame({"age": ages, "expected": X @ self.coef_ + self.grand_mean_})


def age_adjusted(
    df: pd.DataFrame,
    metric: str,
    curve: AgeCurve,
    *,
    age_col: str = "age_season_end",
    league_col: str = "league_id",
) -> pd.Series:
    """Oyuncunun kendi yasindaki beklentiden SAPMASI.

    Pozitif = yasitlarindan iyi. Wonderkid sinyali budur.
    """
    exp = curve.expected(df[age_col], df[league_col])
    return df[metric] - exp
