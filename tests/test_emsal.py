"""Emsal orani testleri (FAZ 3).

EN KRITIK IKI SEY:

1) Emsal grubu KAPSAM ve LIG TABANI bakimindan homojen olmali. Karisirsa
   oran anlamini yitirir - 'tam' kapsamli liglerde taban %57,
   'sicrama_only'de %12; ikisini ayni gruba koymak ligin kendisini
   yetenek sanmaktir.

2) Mesafe MODEL UZAYINDA ve katsayiyla AGIRLIKLI olmali. Ilk surum stil
   uzayindaydi (agirligin %83'u "nasil oynuyor") ve olculunce AUC 0,560
   cikti; model uzayinda 0,662. Agirliksiz esit mesafe de yetmez -
   model deger_var'a 1,44, starts_pct'e 0,05 veriyor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scout.features.emsal import (ASGARI_EMSAL, MESAFE_OZELLIKLERI, cumle,
                                  emsaller, lig_taban_orani, mesafe_uzayi,
                                  ozet, wilson)


def _havuz(n=200, seed=1, kapsam="sicrama_only", taban=0.10,
           pg="Midfielder", pid_ofset=0):
    rng = np.random.default_rng(seed)
    d = pd.DataFrame({
        "player_id": np.arange(n) + pid_ofset,
        "league_id": 1 if kapsam == "sicrama_only" else 2,
        "season": 2022,
        "pos_group": pg,
        "kapsam": kapsam,
        "age_season_end": rng.uniform(19, 22, n),
        "lig_taban": taban,
        "y": rng.binomial(1, taban, n),
    })
    # DIKKAT: age_season_end MESAFE_OZELLIKLERI icinde de var - onu
    # ezmemeliyiz, yoksa yas bandi filtresi hicbir seyi eslestirmez.
    for c in MESAFE_OZELLIKLERI:
        if c not in d.columns:
            d[c] = rng.uniform(0, 100, n)
    return d


def _Z(df, w=None):
    return mesafe_uzayi(df, w)


# ------------------------------------------------------------- mesafe
def test_mesafe_uzayi_standartlastirir():
    d = _havuz(100, seed=1)
    Z = mesafe_uzayi(d)
    assert Z.shape == (100, len(MESAFE_OZELLIKLERI))
    assert np.allclose(Z.mean(axis=0), 0, atol=1e-9)
    assert np.allclose(Z.std(axis=0), 1, atol=1e-9)


def test_mesafe_uzayi_agirlik_uygular():
    """Agirliksiz mesafe, modelin onem farkini siler."""
    d = _havuz(100, seed=2)
    w = np.zeros(len(MESAFE_OZELLIKLERI))
    w[0] = 1.0                                  # yalnizca ilk boyut sayilsin
    Z = mesafe_uzayi(d, w)
    assert np.allclose(Z[:, 1:], 0)
    assert not np.allclose(Z[:, 0], 0)


def test_mesafe_uzayi_eksik_sutuna_dayanikli():
    d = _havuz(60, seed=3).drop(columns=["log_deger", "deger_var"])
    Z = mesafe_uzayi(d)
    assert Z.shape[1] == len(MESAFE_OZELLIKLERI) - 2
    assert np.isfinite(Z).all()


def test_mesafe_uzayi_tamamen_bos_sutunda_cokmez():
    d = _havuz(60, seed=4)
    d["log_deger"] = np.nan
    Z = mesafe_uzayi(d)
    assert np.isfinite(Z).all()


# -------------------------------------------------------- emsal secimi
def test_emsal_ayni_kapsamdan_secilir():
    a = _havuz(150, seed=5, kapsam="sicrama_only", taban=0.10)
    b = _havuz(150, seed=6, kapsam="tam", taban=0.60, pid_ofset=10000)
    h = pd.concat([a, b], ignore_index=True)
    e = emsaller(h, h.index[0], _Z(h), k=40)
    assert not e.empty
    assert (e.kapsam == "sicrama_only").all(), "kapsam karismis"


def test_emsal_benzer_lig_tabanindan_secilir():
    a = _havuz(150, seed=7, taban=0.10)
    b = _havuz(150, seed=8, taban=0.45, pid_ofset=10000)
    b["league_id"] = 3
    h = pd.concat([a, b], ignore_index=True)
    e = emsaller(h, h.index[0], _Z(h), k=40)
    assert (e.lig_taban - 0.10).abs().max() <= 0.10


def test_emsal_ayni_mevkiden_secilir():
    a = _havuz(150, seed=9, pg="Midfielder")
    b = _havuz(150, seed=10, pg="Attacker", pid_ofset=10000)
    h = pd.concat([a, b], ignore_index=True)
    e = emsaller(h, h.index[0], _Z(h), k=40)
    assert (e.pos_group == "Midfielder").all()


def test_ayni_oyuncunun_baska_sezonu_emsal_olamaz():
    h = _havuz(120, seed=11)
    ikinci = h.iloc[[0]].copy()
    ikinci["season"] = 2023
    h = pd.concat([h, ikinci], ignore_index=True)
    e = emsaller(h, h.index[0], _Z(h), k=40)
    assert (e.player_id != h.iloc[0].player_id).all()


def test_yas_bandi_uygulanir():
    h = _havuz(200, seed=12)
    h.loc[h.index[0], "age_season_end"] = 20.0
    e = emsaller(h, h.index[0], _Z(h), k=40, yas_bandi=0.5)
    assert (e.age_season_end - 20.0).abs().max() <= 0.5


def test_havuz_kucukse_bos_doner():
    h = _havuz(20, seed=13)
    assert emsaller(h, h.index[0], _Z(h), k=40).empty


def test_en_yakinlar_gercekten_en_yakin():
    h = _havuz(120, seed=14)
    Z = _Z(h)
    e = emsaller(h, h.index[0], Z, k=10)
    d = np.linalg.norm(Z - Z[0], axis=1)
    # secilenlerin uzakligi, secilmeyen uygun adaylarin en kucugunden buyuk olmasin
    assert e.uzaklik.max() <= np.sort(d[1:])[10] + 1e-9


# --------------------------------------------------------------- ozet
def test_ozet_kucuk_grupta_oran_uretmez():
    """Kucuk kohortta percentile uretmeme kuralinin (§21) aynisi."""
    o = ozet(_havuz(ASGARI_EMSAL - 1, seed=15), 0.10)
    assert o["yeterli"] is False
    assert o["oran"] is None and o["olumlu"] is None


def test_ozet_kaldirac_hesabi():
    e = _havuz(40, seed=16)
    e["y"] = [1] * 10 + [0] * 30
    o = ozet(e, 0.10)
    assert o["oran"] == pytest.approx(0.25)
    assert o["kaldirac"] == pytest.approx(2.5)


def test_ozet_sifir_tabanda_kaldirac_yok():
    assert ozet(_havuz(40, seed=17), 0.0)["kaldirac"] is None


# ------------------------------------------------------ belirsizlik
def test_wilson_bilinen_deger():
    lo, hi = wilson(6, 40)
    assert lo == pytest.approx(0.071, abs=0.005)
    assert hi == pytest.approx(0.291, abs=0.005)


def test_wilson_sifir_olumluda_ust_sinir_sifir_degil():
    """0/40 gormek '%0' demek DEGIL - ust sinir %9.

    Kalibrasyonda en dusuk kova 0,018 dedi ama gerceklesen 0,062 cikti.
    Nokta tahmini iyimser; GA bunu kurtariyor. Cumle her zaman GA gosterir.
    """
    lo, hi = wilson(0, 40)
    assert lo == 0.0
    assert 0.05 < hi < 0.12


def test_wilson_n_buyudukce_daralir():
    assert (wilson(60, 400)[1] - wilson(60, 400)[0]) < \
           (wilson(6, 40)[1] - wilson(6, 40)[0])


def test_taban_ustunde_bayragi_GA_ile_karar_verir():
    """Kaldiracin kendisi yaniltici: taban %3'te %15 bulmak 5 kat gorunur
    ama n=40'ta bu fark gurultuden ayirt edilemeyebilir."""
    e = _havuz(40, seed=18)
    e["y"] = [1] * 6 + [0] * 34            # %15, GA %7-%29
    assert ozet(e, 0.03)["taban_ustunde"] is True
    assert ozet(e, 0.12)["taban_ustunde"] is False


def test_cumle_belirsizligi_her_zaman_gosterir():
    e = _havuz(40, seed=19)
    e["y"] = [1] * 6 + [0] * 34
    s = cumle(ozet(e, 0.12))
    assert "GA" in s and "KAPSIYOR" in s
    assert "6.0" not in s and "40.0" not in s


def test_cumle_yetersiz_grupta_uyarir():
    s = cumle(ozet(_havuz(10, seed=20), 0.1))
    assert "yetersiz" in s and str(ASGARI_EMSAL) in s


# --------------------------------------------------------- lig tabani
def test_lig_taban_orani_grup_bazinda():
    d = pd.DataFrame({"league_id": [1, 1, 2, 2], "season": 2022,
                      "y": [1, 0, 1, 1]})
    assert list(lig_taban_orani(d)) == [0.5, 0.5, 1.0, 1.0]
