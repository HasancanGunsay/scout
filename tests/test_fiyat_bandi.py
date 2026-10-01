"""Fiyat bandi mantigi testleri (FAZ 6.2)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fiyat_bandi import bant_ata, ucuz_mu  # noqa: E402


def test_bant_sinirlari():
    d = pd.Series([np.nan, 0, 499_999, 500_000, 1_999_999, 2_000_000,
                   4_999_999, 5_000_000, 50e6])
    assert list(bant_ata(d)) == ["0 yok", "1 <0,5M", "1 <0,5M", "2 0,5-2M",
                                 "2 0,5-2M", "3 2-5M", "3 2-5M", "4 >=5M",
                                 "4 >=5M"]


def test_degerleme_yok_sifir_degil():
    """Eksik deger '0 EUR' (ucuz) sanilmamali: ayri bantta durur.

    Ayni sinif hata iki kez yasandi (Veikkausliiga 0 metrik, §21; piyasa
    degeri log1p(0), §39.4) - bu ayrim kilitli.
    """
    assert bant_ata(pd.Series([np.nan]))[0] == "0 yok"
    assert bant_ata(pd.Series([0.0]))[0] == "1 <0,5M"


def test_ucuz_tanimi_kullanicinin_tanimi():
    b = bant_ata(pd.Series([np.nan, 1e5, 1e6, 3e6, 8e6]))
    assert list(ucuz_mu(b)) == [True, True, True, True, False]
