"""Oyuncu SAYFASINI gercekten calistiran testler (FAZ 4 -> 8.4).

8.4'te "Oyuncu profili" ve "Scout dosyasi" tek sayfada birlesti (sekmeler).
Testler eski Scout dosyasi testlerinin devami.

NEDEN VAR: Kadro Analizi sayfasi iki kez yalnizca tarayicida acildigi icin
kirik bulundu, birim testlerin hepsi yesilken (§34.6). Bu dosya sayfayi
bastan sona calistirir. Ozellikle sinanan:
  - dusuk gorunurluklu ligde RISK BAYRAKLARI yaniyor mu
  - Turkce metin src/ yerine arayuzden mi geliyor (ASCII sizintisi yok)
  - model iddiasi OLMAYAN oyuncu-sezon da acilir (profil + benzerler)
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAYFA = ROOT / "app" / "views" / "Oyuncu.py"
DB = ROOT / "data" / "scout.duckdb"
SNAP = ROOT / "data" / "scout_ui_snapshot.duckdb"

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (DB.exists() or SNAP.exists()),
    reason="veritabani yok - sayfa testi atlaniyor",
)


def _sorgu(q):
    import duckdb
    con = duckdb.connect(str(DB if DB.exists() else SNAP), read_only=True)
    try:
        return con.sql(q).fetchall()
    finally:
        con.close()


def _at(anahtar=None, timeout: int = 240) -> AppTest:
    at = AppTest.from_file(str(SAYFA), default_timeout=timeout)
    if anahtar:
        pid, lid, sez = anahtar
        at.query_params.update({"pid": str(pid), "lid": str(lid),
                                "sezon": str(sez)})
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _metin(at) -> str:
    return " ".join(str(m.value) for m in at.markdown)


def test_iddia_ve_bolumler_var():
    at = _at()
    for bolum in ("Kanıt", "Bağlam", "Yörünge", "Emsal", "Riskler",
                  "Ne izlemelisin"):
        assert bolum in _metin(at), f"bölüm eksik: {bolum}"
    assert "yaşında" in " ".join(str(i.value) for i in at.info), "iddia kutusu"
    assert len(at.get("download_button")) >= 1, "dosya disa aktarimi"
    assert {t.label for t in at.tabs} >= {"Scout dosyası", "Profil",
                                          "Benzer oyuncular"}


def test_dusuk_gorunurlukte_sonuc_uyarisi_yanar():
    """En onemli uyari: kademe 0 'basarisiz' demek DEGIL (§38.4)."""
    (k,) = _sorgu("""SELECT player_id, league_id, season FROM player_ranking
                     WHERE kapsam = 'sicrama_only'
                     ORDER BY model_olasilik DESC LIMIT 1""")
    at = _at(k)
    assert "Sonuç kısmen görünmez" in _metin(at)


def test_turkce_metin_ascii_sizintisi_yok():
    at = _at()
    hepsi = _metin(at) + " ".join(str(i.value) for i in at.info)
    for sizinti in ("yasinda", "olasiligini", "gorunmez -", "orneklem -"):
        assert sizinti not in hepsi, f"ASCII metin sizmis: {sizinti}"


def test_farkli_oyuncularda_cokmuyor():
    for k in _sorgu("""SELECT player_id, league_id, season FROM player_ranking
                       ORDER BY model_olasilik DESC LIMIT 4 OFFSET 10"""):
        _at(k)


def test_iddiasi_olmayan_oyuncu_da_acilir():
    """23 yas ustu: model iddiasi yok ama profil ve benzerler calisir."""
    (k,) = _sorgu("""SELECT player_id, league_id, season FROM player_features
                     WHERE age_season_end > 27 AND minutes > 2000 LIMIT 1""")
    at = _at(k)
    assert any("model iddiası yok" in str(m.value) for m in at.markdown)
    assert any("Metrik profili" in str(m.value) for m in at.markdown)


def test_olasilik_tek_kaynaktan_disaridan_tahmin():
    """7.0: sayfa, Havuz/Mevki Siralamasi ile AYNI olasiligi gostermeli -
    player_tahmin'deki disaridan tahmin; uretim modelinin orneklem ici
    olasiligi DEGIL. Varsayilan oyuncu: en yeni sezonun en yukseği."""
    at = _at()
    goster = [m.value for m in at.metric if m.label == "Model olasılığı"][0]
    ((beklenen,),) = _sorgu("""
        SELECT max(t.model_olasilik) FROM player_tahmin t
        JOIN player_outcome o USING (player_id, league_id, season)
        WHERE t.season = (SELECT max(season) FROM player_tahmin)""")
    assert goster == f"%{100 * beklenen:.0f}"


def test_parametreyle_oyuncuyu_secer():
    """Havuz / Takip / Kesif ?pid=&lid=&sezon= ile gelir."""
    ((pid, lid, sez, ad),) = _sorgu("""
        SELECT player_id, league_id, season, player_name FROM player_ranking
        WHERE season = 2023 ORDER BY model_olasilik LIMIT 1 OFFSET 40""")
    at = _at((pid, lid, sez))
    sec = [s for s in at.selectbox if s.label == "Oyuncu ara"][0].value
    assert sec.startswith(ad + " — ") and f"{sez})" in sec, sec
