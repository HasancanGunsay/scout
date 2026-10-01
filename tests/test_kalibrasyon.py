"""Kapsam-kosullu kalibrasyon testleri (FAZ 6.6)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scout.model.kalibrasyon import (GLOBAL, ece, grup_fit, grup_uygula,
                                     kosullu_ece, lolo_kalibre, platt_fit,
                                     platt_uygula)


def _iki_grup(n=4000, seed=0):
    """Grup A'da model kotumser, B'de iyimser (6.6'nin gercek deseni)."""
    rng = np.random.default_rng(seed)
    g = rng.choice(["tam", "sicrama_only"], n)
    p = rng.uniform(0.02, 0.98, n)
    kaydir = np.where(g == "tam", 1.0, -1.0)
    gercek = 1 / (1 + np.exp(-(np.log(p / (1 - p)) + kaydir)))
    y = (rng.uniform(size=n) < gercek).astype(int)
    lig = rng.integers(0, 12, n)
    return pd.DataFrame({"p": p, "y": y, "kapsam": g, "league_id": lig})


def test_zaten_kalibre_veride_platt_kimlige_yakin():
    rng = np.random.default_rng(1)
    p = rng.uniform(0.02, 0.98, 20000)
    y = (rng.uniform(size=p.size) < p).astype(int)
    a, b = platt_fit(p, y)
    assert a == pytest.approx(0.0, abs=0.08) and b == pytest.approx(1.0, abs=0.08)


def test_platt_monoton():
    p = np.linspace(0.01, 0.99, 50)
    q = platt_uygula(p, (0.4, 0.7))
    assert (np.diff(q) > 0).all()


def test_kosullu_ece_zit_hatalari_gizlemez():
    """Genel ECE zit yonlu grup hatalarini goturur; kosullu ECE gormeli."""
    d = _iki_grup()
    assert kosullu_ece(d.p, d.y, d.kapsam) > 2 * ece(d.p, d.y)


def test_grup_kalibrasyonu_kosullu_ece_dusurur():
    d = _iki_grup()
    par = grup_fit(d.p, d.y, d.kapsam)
    q = grup_uygula(d.p, d.kapsam, par)
    assert kosullu_ece(q, d.y, d.kapsam) < 0.5 * kosullu_ece(d.p, d.y, d.kapsam)


def test_grup_icinde_siralama_degismez():
    d = _iki_grup()
    q = grup_uygula(d.p, d.kapsam, grup_fit(d.p, d.y, d.kapsam))
    for _, s in d.assign(q=q).groupby("kapsam"):
        assert (s.sort_values("p").q.diff().dropna() >= 0).all()


def test_kucuk_grup_ve_bilinmeyen_grup_global_e_duser():
    d = _iki_grup()
    g = d.kapsam.copy()
    g.iloc[:30] = "minik"
    par = grup_fit(d.p, d.y, g)
    assert "minik" not in par and GLOBAL in par
    q = grup_uygula([0.3], ["hic_gorulmedi"], par)
    assert q[0] == pytest.approx(platt_uygula([0.3], par[GLOBAL])[0])


def test_lolo_kalibrator_kendi_ligini_gormez():
    """Bir ligin sonuclarini degistirmek o ligin kalibre tahminini
    DEGISTIRMEMELI (kalibrator yalniz diger liglerden kurulur)."""
    d = _iki_grup()
    d["y"] = d.y.astype(int)
    q1 = lolo_kalibre(d, "p", "kapsam")
    d2 = d.copy()
    m = d2.league_id == 3
    d2.loc[m, "y"] = 1 - d2.loc[m, "y"]
    q2 = lolo_kalibre(d2, "p", "kapsam")
    assert np.allclose(q1[m], q2[m])
    assert not np.allclose(q1[~m], q2[~m])


def test_lolo_hepsi_dolu_ve_olasilik():
    d = _iki_grup()
    q = lolo_kalibre(d, "p", None)
    assert q.notna().all() and ((q > 0) & (q < 1)).all()
