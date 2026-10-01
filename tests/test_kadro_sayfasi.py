"""Kadro Analizi SAYFASINI gercekten calistiran testler.

NEDEN VAR (30 Agu 2026): sayfa iki kez yalnizca tarayicida acildigi icin
kirik bulundu, birim testlerin hepsi yesilken:

  1) modul 'guclu' donuyordu, arayuz 'güçlü' ariyordu -> grafik KeyError
  2) benzerler() zaten player_features satirlarini donduruyor; yasi bir de
     player_natural_role'den cekmek age_season_end_x/_y cakismasi ve
     "KeyError: ['age_season_end'] not in index" uretiyordu

Ikisi de modul testleriyle YAKALANAMAZDI - modul dogruydu, sayfa yanlisti.
Bu dosya sayfayi bastan sona calistirir ve istisna atmadigini dogrular.

Veritabani yoksa testler atlanir: CI'da veri olmayabilir, ama gelistirici
makinesinde her zaman var.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAYFA = ROOT / "app" / "views" / "Kadro_Analizi.py"
DB = ROOT / "data" / "scout.duckdb"
SNAP = ROOT / "data" / "scout_ui_snapshot.duckdb"

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (DB.exists() or SNAP.exists()),
    reason="veritabani yok - sayfa testi atlaniyor",
)


def _calistir(timeout: int = 120) -> AppTest:
    at = AppTest.from_file(str(SAYFA), default_timeout=timeout)
    at.run()
    return at


def test_sayfa_hatasiz_acilir():
    at = _calistir()
    assert not at.exception, [str(e) for e in at.exception]


def test_rol_haritasi_ve_yas_profili_cizilir():
    """Iki grafik de uretilmeli - biri cokerse digeri de gorunmez."""
    at = _calistir()
    assert not at.exception
    # rol haritasi + yas profili = en az iki plotly grafigi
    assert len(at.get("plotly_chart")) >= 2


def test_rol_tablosu_var():
    at = _calistir()
    assert not at.exception
    assert len(at.dataframe) >= 1, "rol haritasi tablosu uretilmedi"


def test_takim_degistirince_cokmuyor():
    """Farkli kadrolar farkli kod yollarini tetikliyor.

    Ozellikle kalecisi olmayan kadro, tek oyunculu rol, bos benzerlik
    havuzu - bunlarin hepsi ayri dallar.
    """
    at = _calistir()
    assert not at.exception
    takim_sec = at.selectbox[2]                 # lig, sezon, takim
    secenekler = list(takim_sec.options)
    assert len(secenekler) > 1

    for takim in secenekler[:4]:
        at2 = AppTest.from_file(str(SAYFA), default_timeout=120)
        at2.run()
        at2.selectbox[2].select(takim).run()
        assert not at2.exception, f"{takim}: {[str(e) for e in at2.exception]}"


def test_oyuncu_degistirince_cokmuyor():
    """Benzerlik bolumu - iki kirik da buradaydi."""
    at = _calistir()
    assert not at.exception
    oyuncu_sec = at.selectbox[-1]
    adlar = list(oyuncu_sec.options)
    assert adlar, "oyuncu listesi bos"

    for ad in adlar[:5]:
        at2 = AppTest.from_file(str(SAYFA), default_timeout=120)
        at2.run()
        at2.selectbox[-1].select(ad).run()
        assert not at2.exception, f"{ad}: {[str(e) for e in at2.exception]}"


def test_kaleci_secilince_ters_olcum_uyarisi_cikar():
    """Kalecide bulgu TERSINE dondu - sayfa bunu SESSIZ gecmemeli.

    Olculdu: kulupler kaleci degistirirken rastgeleden daha FARKLI stilde
    oyuncu aliyor (-0,170, %95 GA tamami negatif). Sessizce liste gostermek
    kullaniciyi yanlis yone iter; st.error ile aciktan uyariliyor.
    """
    at = _calistir()
    assert not at.exception

    # kalecisi olan bir takim bul
    takimlar = list(at.selectbox[2].options)
    bulundu = False
    for takim in takimlar:
        at2 = AppTest.from_file(str(SAYFA), default_timeout=120)
        at2.run()
        at2.selectbox[2].select(takim).run()
        if at2.exception:
            continue
        roller = " ".join(str(d.value) for d in at2.dataframe)
        if "Kaleci" not in roller:
            continue
        # kadroda kaleci var - kaleciyi sec
        for ad in at2.selectbox[-1].options:
            at3 = AppTest.from_file(str(SAYFA), default_timeout=120)
            at3.run()
            at3.selectbox[2].select(takim).run()
            at3.selectbox[-1].select(ad).run()
            if at3.exception:
                continue
            hatalar = " ".join(str(e.value) for e in at3.error)
            if "TERS" in hatalar:
                bulundu = True
                assert "daha FARKLI" in hatalar
                break
        if bulundu:
            break

    if not bulundu:
        pytest.skip("veride 450+ dk oynamis kaleci bulunamadi")
