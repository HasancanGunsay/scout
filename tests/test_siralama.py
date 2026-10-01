"""Mevki siralamasi mantigi testleri (FAZ 6.5)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scout.model.siralama import (ASGARI_OZET_N, UYARI_DOGRULANMAMIS,
                                  UYARI_IZLENEN, UYARI_KALECI, UYARI_KUCUK_N,
                                  filtrele,
                                  ozet, sirala, sonra_metni_kodu, yer_edindi)


def _df(n=200, seed=1):
    rng = np.random.default_rng(seed)
    d = pd.DataFrame({
        "player_id": np.arange(n),
        "season": rng.choice([2022, 2023, 2024], n),
        "pos_group": rng.choice(["Defender", "Midfielder", "Attacker",
                                 "Goalkeeper"], n),
        "kapsam": rng.choice(["tam", "sicrama_only"], n),
        "deger": rng.choice([np.nan, 1e5, 1e6, 3e6, 8e6, 2e7], n),
        "guven": rng.choice(["iyi", "zayif", "dogrulanmamis", "dusuk"], n),
        "age_season_end": rng.uniform(17, 23, n),
        "minutes": rng.integers(450, 3000, n),
        "model_olasilik": rng.uniform(0, 1, n),
        "piyasa_ustu": rng.uniform(-0.3, 0.3, n),
        "saf": rng.uniform(0, 1, n),
        "kademe": rng.integers(0, 5, n).astype(float),
    })
    d.loc[d.deger.isna(), "piyasa_ustu"] = np.nan     # tanimsiz
    return d


# ---------------------------------------------------------- filtreler
def test_sezon_ve_mevki_filtresi():
    d = _df()
    f = filtrele(d, sezon=2024, mevkiler=["Defender", "Attacker"])
    assert (f.season == 2024).all()
    assert set(f.pos_group) <= {"Defender", "Attacker"}


def test_fiyat_tavani_degersizi_ayri_secenek():
    """Eksik deger 0 EUR DEGIL (§39.4): tavana sokulmaz, ayri secenek."""
    d = _df()
    dahil = filtrele(d, fiyat_tavani=5e6, degersiz_dahil=True)
    haric = filtrele(d, fiyat_tavani=5e6, degersiz_dahil=False)
    assert haric.deger.notna().all() and (haric.deger <= 5e6).all()
    assert len(dahil) > len(haric)
    assert dahil.deger.isna().sum() > 0


def test_tavan_sinirda_dahil():
    d = pd.DataFrame({"deger": [5e6, 5e6 + 1], "season": 2024})
    assert len(filtrele(d, fiyat_tavani=5e6, degersiz_dahil=False)) == 1


def test_guven_ve_yas_ve_dakika_filtresi():
    d = _df()
    f = filtrele(d, guvenler=["iyi"], yas_max=20.0, min_dakika=1000)
    assert (f.guven == "iyi").all() and (f.age_season_end <= 20).all()
    assert (f.minutes >= 1000).all()


def test_filtre_kapsam():
    d = _df()
    assert (filtrele(d, kapsam="tam").kapsam == "tam").all()
    assert len(filtrele(d, kapsam="hepsi")) == len(d)     # taninmayan = filtre yok


# ----------------------------------------------------------- siralama
def test_siralama_azalan_ve_n():
    d = _df()
    t = sirala(d, "model", 15)
    assert len(t) == 15
    assert (t.model_olasilik.diff().dropna() <= 0).all()


def test_piyasa_ustu_tanimsizlari_listeden_cikarir():
    """Degerlemesi olmayanda 'piyasa altinda fiyatlanma' TANIMSIZ (§45.4);
    sona itmek yerine listeden cikar."""
    d = _df()
    t = sirala(d, "piyasa_ustu", 50)
    assert t.piyasa_ustu.notna().all()
    assert t.deger.notna().all()


def test_saf_olcut_piyasadan_bagimsiz():
    d = _df()
    t = sirala(d, "saf", 10)
    assert (t.saf.diff().dropna() <= 0).all()


# -------------------------------------------------------------- ozet
def test_yer_edindi_kademe_3_ve_ustu_nan_sifir_degil():
    s = yer_edindi(pd.DataFrame({"kademe": [0, 2, 3, 4, np.nan]}))
    assert list(s.dropna()) == [0.0, 0.0, 1.0, 1.0]
    assert np.isnan(s.iloc[4])


def test_ozet_ga_ve_taban():
    d = _df(400, seed=3)
    d["kademe"] = 0.0
    top = d.head(40).copy()
    top["kademe"] = [3.0] * 20 + [0.0] * 20
    o = ozet(top, pd.concat([top, d.iloc[40:]]))
    assert o["olumlu"] == 20 and o["oran"] == pytest.approx(0.5)
    assert o["oran_lo"] < 0.5 < o["oran_hi"]
    assert o["ga_tabani_asiyor"] is True            # taban ~%5


def test_ozet_kucuk_grupta_uyari():
    d = _df()
    o = ozet(d.head(ASGARI_OZET_N - 1), d)
    assert UYARI_KUCUK_N in o["uyarilar"] and o["yeterli"] is False


def test_ozet_kucuk_grupta_bile_gaaraligi_gosterilir():
    """Az orneklemde oran yorumlanmaz ama belirsizlik (GA) hep uretilir."""
    o = ozet(_df().head(10), _df())
    assert "oran_lo" in o and "oran_hi" in o


def test_ozet_dogrulanmamis_agirlikli_uyarisi():
    d = _df()
    top = d.head(40).copy()
    top["guven"] = "dogrulanmamis"
    assert UYARI_DOGRULANMAMIS in ozet(top, d)["uyarilar"]


def test_ozet_kaleci_uyarisi():
    d = _df()
    top = d.head(40).copy()
    top["pos_group"] = "Goalkeeper"
    assert UYARI_KALECI in ozet(top, d)["uyarilar"]


def test_ozet_karma_listede_izlenen_agirlikli_uyarisi():
    """6.6: karma havuzda liste izlenen liglerle dolarsa uyar; tek kapsamli
    havuzda (kullanici zaten secmis) uyarma."""
    d = _df()
    top = d.head(40).copy()
    top["kapsam"] = "tam"
    o = ozet(top, d)
    assert UYARI_IZLENEN in o["uyarilar"] and o["izlenen_payi"] == 1.0
    assert UYARI_IZLENEN not in ozet(top, d[d.kapsam == "tam"])["uyarilar"]
    top["kapsam"] = ["tam", "sicrama_only"] * 20
    assert UYARI_IZLENEN not in ozet(top, d)["uyarilar"]


def test_ozet_sonra_ortalamalari_yalniz_gozlenenlerden():
    d = _df()
    top = d.head(4).copy()
    top["dk_lig"] = [1000.0, np.nan, np.nan, 500.0]
    o = ozet(top, d)
    assert o["dk_lig_ort"] == pytest.approx(750.0)
    assert o["dk_lig_n"] == 2


def test_ozet_bos_listede_cokmez():
    o = ozet(_df().iloc[:0], _df())
    assert o["n"] == 0 and UYARI_KUCUK_N in o["uyarilar"]


# ----------------------------------------------------- sonra durum kodu
def test_iz_yok_gorunmez_dusuk_gorunurlukte():
    """Kademe 0 izlenmeyen ligden geliyorsa 'basarisiz' DEGIL (§38.4)."""
    r = pd.Series({"kademe": 0, "kapsam": "sicrama_only"})
    assert sonra_metni_kodu(r) == "iz_yok_gorunmez"
    assert sonra_metni_kodu(pd.Series({"kademe": 0, "kapsam": "tam"})) == "iz_yok"


def test_sonra_kodlari_ascii():
    for k in (0, 1, 2, 3, 4):
        kod = sonra_metni_kodu(pd.Series({"kademe": k, "kapsam": "tam"}))
        assert kod.isascii() and " " not in kod
    assert sonra_metni_kodu(pd.Series({"kademe": np.nan})) == "bilinmiyor"
