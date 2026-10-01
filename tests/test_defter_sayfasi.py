"""Hesap Defteri SAYFASINI gercekten calistiran testler (FAZ 5).

Ozellikle sinanan: sayfa retrospektif bolumu SICIL diye sunmuyor mu?
Bu ayrimin arayuzde kaybolmasi, geriye donuk testi basari iddiasi gibi
gostermek olurdu (§31'de bir kez yapildi).
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAYFA = ROOT / "app" / "views" / "Hesap_Defteri.py"
DB = ROOT / "data" / "scout.duckdb"
SNAP = ROOT / "data" / "scout_ui_snapshot.duckdb"

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (DB.exists() or SNAP.exists()),
    reason="veritabani yok - sayfa testi atlaniyor",
)


def _at(timeout: int = 180) -> AppTest:
    at = AppTest.from_file(str(SAYFA), default_timeout=timeout)
    at.run()
    return at


def test_sayfa_hatasiz_acilir():
    at = _at()
    assert not at.exception, [str(e) for e in at.exception]


def test_iki_bolum_de_var():
    at = _at()
    assert not at.exception
    metin = " ".join(str(m.value) for m in at.markdown)
    assert "İleriye dönük" in metin
    assert "Geçmişe dönük" in metin


def test_retrospektif_sicil_diye_sunulmuyor():
    """EN KRITIK: geriye donuk sonuc 'basari' gibi gosterilmemeli."""
    at = _at()
    assert not at.exception
    uyari = " ".join(str(w.value) for w in at.warning)
    assert "sicil DEĞİL" in uyari, "en onemli cekince gorunmuyor"
    assert "nerede yanıldığını" in uyari


def test_bos_ileriye_donuk_bolum_aciklaniyor():
    """Bos bolum 'bir sey calismiyor' gibi gorunmemeli - neden bos oldugu
    yazmali."""
    at = _at()
    assert not at.exception
    bilgi = " ".join(str(i.value) for i in at.info)
    if bilgi:
        assert "normal" in bilgi.lower()


def test_kalibrasyon_grafigi_cizilir():
    at = _at()
    assert not at.exception
    assert len(at.get("plotly_chart")) >= 1
