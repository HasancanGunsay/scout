"""Tek dogruluk kaynagi player_tahmin testleri (FAZ 7.0)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scout.model.kalibrasyon import GLOBAL, platt_uygula
from scout.model.tahmin import (SUTUNLAR, TUR_URETIM, TUR_URETIM_KALIBRESIZ,
                                tahmin_tablosu)

KAL = {GLOBAL: [0.0, 1.0], "tam": [0.5, 1.0], "sicrama_only": [-0.6, 0.9]}


def _ranking():
    return pd.DataFrame({
        "player_id": [1, 2], "league_id": [10, 10], "season": [2024, 2024],
        "kapsam": ["tam", "sicrama_only"], "model_olasilik": [0.6, 0.2],
        "model_ham": [0.55, 0.3], "tahmin_turu": ["zaman-disi"] * 2,
        "baska": [1, 2]})


def _uretim():
    return pd.DataFrame({
        "player_id": [1, 3], "league_id": [10, 10], "season": [2024, 2025],
        "model_olasilik": [0.95, 0.4], "kapsam": ["tam", "sicrama_only"]})


def test_disaridan_tahmin_varsa_uretim_kullanilmaz():
    """2022-24'te uretim modeli sezonu GORMUS: disaridan tahmin kazanir."""
    t = tahmin_tablosu(_ranking(), _uretim(), KAL)
    r = t[(t.player_id == 1) & (t.season == 2024)].iloc[0]
    assert r.model_olasilik == pytest.approx(0.6)
    assert r.tahmin_turu == "zaman-disi"


def test_yeni_sezon_uretimden_gelir_ve_kalibre_edilir():
    t = tahmin_tablosu(_ranking(), _uretim(), KAL)
    r = t[t.player_id == 3].iloc[0]
    assert r.tahmin_turu == TUR_URETIM
    assert r.model_ham == pytest.approx(0.4)
    assert r.model_olasilik == pytest.approx(
        platt_uygula([0.4], KAL["sicrama_only"])[0])


def test_kalibrator_yoksa_ham_ve_etiketli():
    t = tahmin_tablosu(_ranking(), _uretim(), None)
    r = t[t.player_id == 3].iloc[0]
    assert r.tahmin_turu == TUR_URETIM_KALIBRESIZ
    assert r.model_olasilik == pytest.approx(0.4)


def test_sutunlar_ve_tekillik():
    t = tahmin_tablosu(_ranking(), _uretim(), KAL)
    assert list(t.columns) == SUTUNLAR
    assert not t.duplicated(["player_id", "league_id", "season"]).any()
    assert len(t) == 3


def test_uretim_yoksa_yalniz_ranking():
    t = tahmin_tablosu(_ranking())
    assert len(t) == 2 and set(t.tahmin_turu) == {"zaman-disi"}


def test_model_ham_yoksa_olasiliktan_doldurulur():
    r = _ranking().drop(columns="model_ham")
    t = tahmin_tablosu(r)
    assert np.allclose(t.model_ham, t.model_olasilik)
