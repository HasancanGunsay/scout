"""Mevki Siralamasi SAYFASINI gercekten calistiran testler (FAZ 6.5).

Kadro Analizi ve Scout Dosyasi sayfalari birim testler yesilken sayfada
kirik cikti (§34.6, §41.5). Bu dosya sayfayi baştan sona calistirir.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAYFA = ROOT / "app" / "views" / "Mevki_Siralamasi.py"
DB = ROOT / "data" / "scout.duckdb"
SNAP = ROOT / "data" / "scout_ui_snapshot.duckdb"

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (DB.exists() or SNAP.exists()), reason="veritabani yok")


def _at() -> AppTest:
    at = AppTest.from_file(str(SAYFA), default_timeout=180)
    at.run()
    return at


def test_sayfa_hatasiz_acilir():
    at = _at()
    assert not at.exception, [str(e) for e in at.exception]


def test_dort_mevki_sekmesi():
    at = _at()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Defans", "Orta saha", "Forvet", "Kaleci"]


def test_iki_temel_uyari_gorunur():
    """Rating yok + 'yatirima deger' = sahada deger uretir (deger artisi degil)."""
    at = _at()
    assert not at.exception
    metin = " ".join(str(i.value) for i in at.info) + " " + \
            " ".join(str(w.value) for w in at.warning)
    assert "Rating verisi yok" in metin
    assert "değeri artar" in metin          # 'demek degildir' cekincesi


def test_tablo_ve_indirme_var():
    at = _at()
    assert not at.exception
    assert len(at.dataframe) >= 1
    assert len(at.get("download_button")) >= 1


def test_kaleci_uyarisi_yanar():
    at = _at()
    assert not at.exception
    uyari = " ".join(str(w.value) for w in at.warning)
    assert "Kaleci" in uyari and "Düşük güven" in uyari


def test_farkli_sezon_ve_olcutlerde_cokmuyor():
    at = _at()
    assert not at.exception
    for sezon in list(at.selectbox[0].options):
        at2 = _at()
        at2.selectbox[0].select(sezon).run()
        assert not at2.exception, f"{sezon}: {[str(e) for e in at2.exception]}"
    for olcut in ("piyasa_ustu", "saf", "model"):
        at3 = _at()
        at3.radio[0].set_value(olcut).run()
        assert not at3.exception, f"{olcut}: {[str(e) for e in at3.exception]}"


def test_asiri_siki_filtrede_cokmuyor():
    """Bos liste yolu: fiyat tavani 0,25M, degersiz haric, yalniz 'iyi' guven."""
    at = _at()
    assert not at.exception
    at.slider[1].set_value(0.25)
    at.checkbox[0].set_value(False)
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
