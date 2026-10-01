"""player_sonra veri butunlugu testleri (FAZ 6.4).

DB yoksa ya da kilitliyse atlanir.
"""
from __future__ import annotations

from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")
ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "scout.duckdb"


@pytest.fixture(scope="module")
def con():
    if not DB.exists():
        pytest.skip("veritabani yok")
    try:
        c = duckdb.connect(str(DB), read_only=True)
        c.sql("SELECT 1 FROM player_sonra LIMIT 1")
    except Exception:
        pytest.skip("player_sonra yok ya da DB kilitli")
    yield c
    c.close()


def test_ga90_yalniz_yeterli_dakikada(con):
    """ga90 kosullu: <450 dk oynayanda NaN olmali (seçilim etkisi)."""
    n = con.sql("SELECT count(*) FROM player_sonra WHERE ga90 IS NOT NULL "
                "AND (dk_lig IS NULL OR dk_lig < 450)").fetchone()[0]
    assert n == 0


def test_kayit_yok_sifir_degil(con):
    """'Hic maci yok' NULL kalmali: izlenmeyen ligde oynayan 0 mac oynamis
    DEGILDIR. Bu ayrim kaybolursa dusuk gorunurluk oyunculari 'oynamadi'
    sayilir (§38.4)."""
    n = con.sql("SELECT count(*) FROM player_sonra WHERE mac_lig IS NULL"
                ).fetchone()[0]
    assert n > 1000


def test_deger_oran_yalniz_iki_degerleme_varsa(con):
    n = con.sql("SELECT count(*) FROM player_sonra WHERE deger_oran IS NOT NULL "
                "AND (deger_bas IS NULL OR deger_son IS NULL OR deger_bas<=0)"
                ).fetchone()[0]
    assert n == 0


def test_deger_degisim_tutarli(con):
    n = con.sql("SELECT count(*) FROM player_sonra WHERE deger_degisim IS NOT NULL "
                "AND abs(deger_degisim-(deger_son-deger_bas))>1").fetchone()[0]
    assert n == 0


def test_transfer_tablosu_tek_kaynak_degil(con):
    """tm_transfers EKSIK (kulup degistirenlerin %9'u kayitli). 'transfer_var'
    sutunu geri gelirse yanlis bilgi verir - yoklugu kilitli."""
    kol = [r[0] for r in con.sql("DESCRIBE player_sonra").fetchall()]
    assert "transfer_var" not in kol
    assert "kulup_degisti" in kol and "bilinen_bedel" in kol


def test_pencere_tam_sansur_isareti(con):
    """gozlem_ay < 12 ise pencere_tam False olmali."""
    n = con.sql("SELECT count(*) FROM player_sonra WHERE pencere_tam "
                "AND gozlem_ay < 12").fetchone()[0]
    assert n == 0
