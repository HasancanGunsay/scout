"""TM tarihsel modeli: ozellik hazirligi ve varyantlar (FAZ 7.2).

Ayni hedef (y = kademe >= 3), ayni egitim hatti (egitim.py), ayni olcu
(lig-ici AUC, oyuncu-kumeli esli bootstrap). Yalnizca TM verisi.

VARYANTLAR (karsilastirma sirasi PLAN §53'te ONCEDEN yazildi)
  basit       yas + dakika payi                 - en aptal makul rakip
  piyasa      yas + deger                       - piyasa
  saf         oyun verisi + savunma baglami     - piyasa YOK
  tam         saf + deger
  tam_savsiz  tam - savunma baglami             - savunma baglami ne katiyor?
  tam_mevki   tam + savunma baglami x defans    - mevkiye ozel etkilesim

METIN URETMEZ.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

YAS_SINIRI = 23.0
ASGARI_DK = 450
KOHORT = ["comp", "season", "pos_group"]
PM_SIKISTIRMA_DK = 900      # arti-eksi gurultulu: dk_pm/(dk_pm+900) ile 0'a cek

OZ_BASIT = ["yas", "dakika_payi"]
OZ_PIYASA = ["yas", "log_deger", "deger_var"]
OZ_OYUN = ["yas", "dakika_payi", "ilk11_payi", "tam_mac_payi", "yedek_payi",
           "dakika_payi_onceki", "onceki_sezon_var", "ga90_pct", "kart_90",
           "takim_ppg", "ilk_bes"]
OZ_SAVUNMA = ["pm_on_sik", "ga_on_sik"]
OZ_DEGER = ["log_deger", "deger_var"]
OZ_MEVKI_ETK = ["pm_on_sik_def", "ga_on_sik_def"]

VARYANTLAR = {
    "basit": OZ_BASIT,
    "piyasa": OZ_PIYASA,
    "saf": OZ_OYUN + OZ_SAVUNMA,
    "tam": OZ_OYUN + OZ_SAVUNMA + OZ_DEGER,
    "tam_savsiz": OZ_OYUN + OZ_DEGER,
    "tam_mevki": OZ_OYUN + OZ_SAVUNMA + OZ_DEGER + OZ_MEVKI_ETK,
}


def kohort_yuzdelik(tum: pd.DataFrame, kol: str, asgari_dk: float = 0
                    ) -> pd.Series:
    """Lig-sezon-mevki kohortunda yuzdelik (0-100), TUM yaslar arasinda.
    Yalniz ayni sezonun verisi - sonuc ya da gelecek bilgisi yok."""
    x = tum[kol].where(tum.dk >= asgari_dk)
    return x.groupby([tum[k] for k in KOHORT]).rank(pct=True) * 100


def hazirla(tum: pd.DataFrame) -> pd.DataFrame:
    """tm_oyuncu_sezon (TUM yaslar) -> modelleme satirlari (U23, >=450 dk).

    Yuzdelikler filtrelemeden ONCE tum kohortta hesaplanir.
    """
    d = tum.copy()
    d["ga90_pct"] = kohort_yuzdelik(d, "ga_90", ASGARI_DK)
    agirlik = d.dk_pm / (d.dk_pm + PM_SIKISTIRMA_DK)
    d["pm_on_sik"] = (d.pm_on_goreli * agirlik).fillna(0.0)
    d["ga_on_sik"] = (-d.ga_on_goreli * agirlik).fillna(0.0)   # buyuk = iyi
    defans = (d.pos_group == "Defender").astype(float)
    d["pm_on_sik_def"] = d.pm_on_sik * defans
    d["ga_on_sik_def"] = d.ga_on_sik * defans
    # eksik deger: 0 EUR DEGIL (§39.4) - lig-sezon medyani + deger_var
    med = d.groupby(["comp", "season"]).log_deger.transform(
        lambda s: s[d.loc[s.index, "deger_var"] == 1].median())
    d.loc[d.deger_var == 0, "log_deger"] = med[d.deger_var == 0]
    d["log_deger"] = d.log_deger.fillna(d.log_deger.median())

    d = d[(d.yas < YAS_SINIRI) & (d.dk >= ASGARI_DK) & d.pos_group.notna()]
    d = d.assign(league_id=d.comp)                 # ranker.lig_ici_auc icin
    d["y"] = np.where(d.kademe.notna(), (d.kademe >= 3).astype(float), np.nan)
    return d.reset_index(drop=True)
