"""TM tarihsel modeli ozellik hazirligi testleri (FAZ 7.2)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scout.model.tm_model import (OZ_DEGER, OZ_SAVUNMA, VARYANTLAR, hazirla,
                                  kohort_yuzdelik)


def _tum(n=40, seed=0):
    rng = np.random.default_rng(seed)
    d = pd.DataFrame({
        "player_id": np.arange(n), "comp": "GB1", "season": 2015,
        "pos_group": ["Defender"] * (n // 2) + ["Attacker"] * (n - n // 2),
        "yas": np.r_[np.full(n // 2, 20.0), np.full(n - n // 2, 28.0)],
        "dk": rng.integers(500, 3000, n).astype(float),
        "dk_pm": 1800.0, "ga_90": rng.uniform(0, 1, n),
        "pm_on_goreli": 0.5, "ga_on_goreli": -0.4,
        "deger": rng.uniform(1e5, 1e7, n), "deger_var": 1,
        "kademe": rng.integers(0, 5, n).astype(float),
    })
    d["log_deger"] = np.log1p(d.deger)
    return d


def test_yuzdelik_tum_yaslar_ve_mevki_icinde():
    """Kohort lig-sezon-MEVKI; yasli oyuncular da kohortta (filtreden once)."""
    d = _tum()
    p = kohort_yuzdelik(d, "ga_90")
    for _, g in d.assign(p=p).groupby("pos_group"):
        assert g.p.max() == pytest.approx(100.0)


def test_u23_ve_dakika_filtresi_yuzdelikten_sonra():
    d = _tum()
    h = hazirla(d)
    assert (h.yas < 23).all() and (h.dk >= 450).all()
    assert set(h.pos_group) == {"Defender"}          # yaslilar disarida


def test_eksik_deger_sifir_degil_medyan():
    d = _tum()
    d.loc[0, ["deger", "deger_var"]] = [np.nan, 0]
    d.loc[0, "log_deger"] = 0.0                      # tablodaki log1p(0)
    h = hazirla(d)
    r = h[h.player_id == 0].iloc[0]
    assert r.log_deger > 10 and r.deger_var == 0


def test_arti_eksi_sikistirma_ve_yon():
    h = hazirla(_tum())
    assert np.allclose(h.pm_on_sik, 0.5 * 1800 / 2700)
    assert (h.ga_on_sik > 0).all()                   # az gol yemek = pozitif


def test_mevki_etkilesimi_yalniz_defansta():
    d = _tum()
    d["yas"] = 20.0
    h = hazirla(d)
    assert (h.loc[h.pos_group == "Attacker", "pm_on_sik_def"] == 0).all()
    assert (h.loc[h.pos_group == "Defender", "pm_on_sik_def"] != 0).all()


def test_acik_pencere_hedefi_nan():
    d = _tum()
    d.loc[:5, "kademe"] = np.nan
    h = hazirla(d)
    assert h.y.isna().sum() == h.kademe.isna().sum() > 0


def test_varyant_ayrimlari():
    assert not set(OZ_DEGER) & set(VARYANTLAR["saf"])
    assert not set(OZ_SAVUNMA) & set(VARYANTLAR["tam_savsiz"])
    assert set(VARYANTLAR["tam"]) - set(VARYANTLAR["tam_savsiz"]) == set(OZ_SAVUNMA)
