"""Scout Dosyasi SAYFASINI gercekten calistiran testler (FAZ 4).

NEDEN VAR: Kadro Analizi sayfasi iki kez yalnizca tarayicida acildigi icin
kirik bulundu, birim testlerin hepsi yesilken (§34.6). Modul dogruydu,
sayfa yanlisti. Bu dosya sayfayi bastan sona calistirir.

Ayrica bu sayfada ozellikle sinanan iki sey:
  - dusuk gorunurluklu ligde RISK BAYRAKLARI yaniyor mu
  - Turkce metin src/ yerine arayuzden mi geliyor (ASCII sizintisi yok)
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAYFA = ROOT / "app" / "views" / "Scout_Dosyasi.py"
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


def test_iddia_ve_bolumler_var():
    at = _at()
    assert not at.exception
    metin = " ".join(str(m.value) for m in at.markdown)
    for bolum in ("Kanıt", "Bağlam", "Yörünge", "Emsal", "Riskler",
                  "Ne izlemelisin"):
        assert bolum in metin, f"bölüm eksik: {bolum}"


def test_iddia_kutusu_dolu():
    at = _at()
    assert not at.exception
    assert at.info, "iddia kutusu yok"
    assert "yaşında" in " ".join(str(i.value) for i in at.info)


def test_dusuk_gorunurlukte_sonuc_uyarisi_yanar():
    """En onemli uyari: kademe 0 'basarisiz' demek DEGIL (§38.4).

    Dusuk gorunurluklu ligde bu bayrak HER ZAMAN yanmali.
    """
    at = _at()
    assert not at.exception
    at.radio[0].set_value("Düşük görünürlük").run()
    assert not at.exception, [str(e) for e in at.exception]
    metin = " ".join(str(m.value) for m in at.markdown)
    assert "Sonuç kısmen görünmez" in metin


def test_turkce_metin_ascii_sizintisi_yok():
    """src/ metin uretmiyor - sayfada 'yasinda' gibi ASCII Turkce olmamali."""
    at = _at()
    assert not at.exception
    hepsi = " ".join(str(m.value) for m in at.markdown) + \
            " ".join(str(i.value) for i in at.info)
    for sizinti in ("yasinda", "olasiligini", "gorunmez -", "orneklem -"):
        assert sizinti not in hepsi, f"ASCII metin sizmis: {sizinti}"


def test_disa_aktarim_dugmesi_var():
    """Dosya sahaya telefonla gidilecek - markdown cikisi sart."""
    at = _at()
    assert not at.exception
    assert len(at.get("download_button")) >= 1


def test_oyuncu_degistirince_cokmuyor():
    at = _at()
    assert not at.exception
    adlar = list(at.selectbox[-1].options)[:4]
    assert adlar
    for ad in adlar:
        at2 = _at()
        at2.selectbox[-1].select(ad).run()
        assert not at2.exception, f"{ad}: {[str(e) for e in at2.exception]}"


def test_olasilik_tek_kaynaktan_disaridan_tahmin():
    """7.0: dosya, Mevki Siralamasi ile AYNI olasiligi gostermeli - yani
    player_tahmin'deki disaridan tahmini; sezonu egitimde gormus uretim
    modelinin (player_model_score) orneklem ici olasiligini DEGIL."""
    import duckdb
    at = _at()
    assert not at.exception
    goster = [m.value for m in at.metric if m.label == "Model olasılığı"][0]
    con = duckdb.connect(str(DB if DB.exists() else SNAP), read_only=True)
    try:
        beklenen = con.sql("""
            SELECT max(t.model_olasilik) FROM player_tahmin t
            JOIN player_outcome o USING (player_id, league_id, season)
            WHERE t.season = (SELECT max(season) FROM player_tahmin)
        """).fetchone()[0]
    finally:
        con.close()
    assert goster == f"%{100 * beklenen:.0f}"
