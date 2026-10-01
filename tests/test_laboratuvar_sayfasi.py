"""Laboratuvar SAYFASINI calistiran testler (1 Eki 2026, metrik aileleri).

Kullanici istegi: bir metrige bakarken iliskili metrikler de gorunsun.
Sinanan: her kategori acilir, ailenin tum metrikleri tabloda, siralanan
metrik ilk sirada, ham kolon adi (pass_accuracy gibi) arayuze SIZMIYOR.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAYFA = ROOT / "app" / "views" / "Laboratuvar.py"
DB = ROOT / "data" / "scout.duckdb"
SNAP = ROOT / "data" / "scout_ui_snapshot.duckdb"
sys.path.insert(0, str(ROOT / "app"))

import _metrikler as MK  # noqa: E402

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

veri_var = pytest.mark.skipif(not (DB.exists() or SNAP.exists()),
                              reason="veritabani yok")


def test_katalog_adlari_tekil_ve_turkce_metin_app_tarafinda():
    adlar = [m.ad for m in MK.TUMU.values()]
    assert len(adlar) == len(set(adlar)), "ayni Turkce ad iki metrikte"
    assert len(MK.TUMU) == sum(len(v) for v in MK.AILELER.values()), \
        "bir metrik iki ailede"


@veri_var
def test_katalogdaki_her_metrik_veride_var():
    import duckdb
    con = duckdb.connect(str(DB if DB.exists() else SNAP), read_only=True)
    try:
        kol = {r[0] for r in con.sql("DESCRIBE player_features").fetchall()}
    finally:
        con.close()
    eksik = [k for k in MK.TUMU if k not in kol]
    assert not eksik, f"katalogda var, veride yok: {eksik}"


def _at() -> AppTest:
    at = AppTest.from_file(str(SAYFA), default_timeout=180)
    at.run()
    return at


@veri_var
@pytest.mark.parametrize("aile", list(MK.AILELER))
def test_her_kategori_iliskili_metriklerle_acilir(aile):
    at = _at()
    assert not at.exception
    [s for s in at.selectbox if s.label == "Kategori"][0].set_value(aile).run()
    assert not at.exception, [str(e) for e in at.exception]
    if not at.dataframe:                      # filtreye uyan yoksa bos durum
        return
    kol = list(at.dataframe[0].value.columns)
    beklenen = [m.ad for m in MK.AILELER[aile]]
    assert all(b in kol for b in beklenen), (aile, kol)
    assert kol[7] == beklenen[0], "siralanan metrik kimlik sutunlarindan hemen sonra"
    sizinti = [k for k in kol if k in MK.TUMU]
    assert not sizinti, f"ham kolon adi arayuzde: {sizinti}"


@veri_var
def test_pas_kategorisinde_api_yuzde_degil_uyarisi():
    at = _at()
    [s for s in at.selectbox if s.label == "Kategori"][0].set_value(
        "Pas ve oyun kurma").run()
    assert any("yüzde değil" in i.value for i in at.info)
