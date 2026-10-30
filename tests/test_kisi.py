"""Kaynak katmani ve kisi kaydi (FAZ 9.4) - kucuk sentetik veritabaniyla."""
import duckdb
import pytest

from scout import sources as S
from scout.resolve import kisi as KS
from scout.sources.adaptorler import ApiFootballKaynak, TransfermarktKaynak


@pytest.fixture
def con():
    c = duckdb.connect()
    c.execute("""CREATE TABLE tm_players AS SELECT * FROM (VALUES
        (10, 'Ali Veli', DATE '2004-01-01', 'Türkiye', 180, 'right', 'Centre-Back',
         'Position', 'Ornek SK', DATE '2027-06-30'),
        (11, 'John Doe', DATE '2003-05-05', 'England', 175, 'left', 'Left-Back',
         'Position', 'X FC', NULL),
        (12, 'Tek Kisi', DATE '2002-02-02', 'Ghana', 190, 'right', NULL,
         'Attack', 'Y FC', NULL)
        ) t(player_id, name, date_of_birth, country_of_citizenship, height_in_cm, foot,
            sub_position, position, current_club_name, contract_expiration_date)""")
    c.execute("""CREATE TABLE player_season AS SELECT * FROM (VALUES
        (100, 'A. Veli', 'Ali', 'Veli', TIMESTAMP '2004-01-01', 'Turkey', 180.0, 1, 2023, 7,
         10.0, 8.0, 800.0, 1.0, 0.0, 'Defender'),
        (100, 'A. Veli', 'Ali', 'Veli', TIMESTAMP '2004-01-01', 'Turkey', 181.0, 1, 2024, 7,
         20.0, 18.0, 1600.0, 2.0, 1.0, 'Defender'),
        (200, 'J. Doe', 'John', 'Doe', TIMESTAMP '2003-05-05', 'England', 175.0, 2, 2024, 8,
         5.0, 2.0, 300.0, 0.0, 0.0, 'Defender'),
        (300, 'Z. Yok', 'Zed', 'Yok', TIMESTAMP '2005-03-03', 'Chile', 170.0, 3, 2024, 9,
         12.0, 10.0, 900.0, 3.0, 2.0, 'Attacker')
        ) t(player_id, player_name, firstname, lastname, birth_date, nationality, height_cm,
            league_id, season, team_id, apps, starts, minutes, goals, assists, position)""")
    # 100 -> A (kabul), 200 -> C (belirsiz: tm_id bos, aday ayri), 300 -> eslesme yok
    c.execute("""CREATE TABLE player_links AS SELECT * FROM (VALUES
        (100, 10.0, NULL, 'A'), (200, NULL, 11.0, 'C'), (300, NULL, NULL, 'D')
        ) t(player_id, tm_id, aday_tm_id, confidence)""")
    c.execute("""CREATE TABLE tm_appearances AS SELECT * FROM (VALUES
        (10, 5000, 1, DATE '2026-03-01', 'TR1', 90, 0, 1, 0, 0)
        ) t(player_id, game_id, player_club_id, date, competition_id, minutes_played,
            goals, assists, yellow_cards, red_cards)""")
    c.execute("""CREATE TABLE tm_oyuncu_sezon AS SELECT * FROM (VALUES
        (10, 'TR1', 2025, 1, 30, 28.0, 2500.0, 2.0, 1.0)
        ) t(player_id, comp, season, club_id, mac, ilk11, dk, gol, asist)""")
    c.execute("""CREATE TABLE tm_player_valuations AS SELECT * FROM (VALUES
        (10, DATE '2026-02-01', 500000)) t(player_id, date, market_value_in_eur)""")
    yield c
    c.close()


def _kaynaklar(*ek):
    return [ApiFootballKaynak(), TransfermarktKaynak(surum="transfermarkt-test"), *ek]


def test_kurallar_mevcut_sistemle_ayni(con):
    KS.kur(con, _kaynaklar())
    k = dict(con.execute("SELECT kaynak || ':' || kaynak_id, kisi_id FROM kisi_kaynak").fetchall())
    assert k["api:100"] == "tm:10"           # kabul edilmis eslesme -> TM kisisi
    assert k["api:200"] == "api:200"         # C: aday var ama BAGLANMAZ (§60)
    assert k["api:300"] == "api:300"         # eslesmesiz -> kendi kisisi
    assert k["tm:11"] == "tm:11"             # omurga: her TM kimligi bir kisi
    assert all(ok for _, ok, _ in KS.denetim(con))


def test_kisi_nitelikleri_omurgadan(con):
    KS.kur(con, _kaynaklar())
    ad, kaynaklar = con.execute(
        "SELECT ad, kaynaklar FROM kisi WHERE kisi_id = 'tm:10'").fetchone()
    assert ad == "Ali Veli" and kaynaklar == "api,tm"     # TM adi oncelikli
    assert con.execute("SELECT count(*) FROM kisi").fetchone()[0] == 5   # 3 tm + 2 api


def test_api_kimligi_en_son_sezondan(con):
    KS.kur(con, _kaynaklar())
    assert con.execute("SELECT boy_cm FROM kaynak_kimlik WHERE kaynak='api' AND "
                       "kaynak_id='100'").fetchone()[0] == 181.0


def test_standart_tablolar_sema_ile(con):
    sayilar = KS.kur(con, _kaynaklar())
    for t in S.SEMA:
        kol = [r[0] for r in con.execute(f"DESCRIBE {t}").fetchall()]
        assert kol == S.sutunlar(t), t
    assert sayilar["kaynak_mac_katilim"] == 1        # API mac verisi vermez
    assert sayilar["kaynak_oyuncu_sezon"] == 5       # 4 API + 1 TM


class _SahteTff:
    """Yeni kaynak = bir adaptor + eslesme kurali (GELISTIRME 9.4 kabul kriteri)."""
    ad, surum, omurga = "tff", "tff-test", False

    def eslesme_sql(self):
        return """SELECT kaynak_id, kisi_id, 'ad+dogum' AS guven, 'eslesme' AS yontem
                  FROM (VALUES ('T1', 'tm:10')) t(kaynak_id, kisi_id)"""

    def sql(self, tablo):
        if tablo == "kaynak_kimlik":
            return """SELECT * FROM (VALUES
                ('tff', 'T1', 'tff-test', 'ALİ VELİ', DATE '2004-01-01', 'TR', NULL, NULL, 'D'),
                ('tff', 'T2', 'tff-test', 'YENİ GENÇ', DATE '2007-07-07', 'TR', NULL, NULL, 'F'))"""
        if tablo == "kaynak_mac_katilim":
            return """SELECT * FROM (VALUES ('tff', 'T1', 'tff-test', 'M1', DATE '2026-10-04',
                       'TR2', '20', 90.0, 0.0, 0.0, 0.0, 0.0))"""
        return None


def test_yeni_kaynak_tek_adaptorle_eklenir(con):
    KS.kur(con, _kaynaklar(_SahteTff()))
    k = dict(con.execute("SELECT kaynak || ':' || kaynak_id, kisi_id FROM kisi_kaynak").fetchall())
    assert k["tff:T1"] == "tm:10"            # eslesen -> ayni kisi (3 kaynakli)
    assert k["tff:T2"] == "tff:T2"           # eslesmeyen -> yeni kisi
    assert con.execute("SELECT kaynaklar FROM kisi WHERE kisi_id='tm:10'").fetchone()[0] \
        == "api,tff,tm"
    # bu sezonun maci artik kisi uzerinden okunabilir
    dk = con.execute("""SELECT sum(m.dakika) FROM kaynak_mac_katilim m
                        JOIN kisi_kaynak k USING (kaynak, kaynak_id)
                        WHERE k.kisi_id = 'tm:10' AND m.tarih >= DATE '2026-07-01'""").fetchone()[0]
    assert dk == 90.0
    assert all(ok for _, ok, _ in KS.denetim(con))


def test_iki_tm_kimligini_birlestiren_kural_yakalanir(con):
    KS.kur(con, _kaynaklar())
    # elle bozulma: ikinci bir TM kimligini tm:10'a bagla
    con.execute("UPDATE kisi_kaynak SET kisi_id = 'tm:10' WHERE kaynak = 'tm' AND kaynak_id = '11'")
    sonuc = {ad: ok for ad, ok, _ in KS.denetim(con)}
    assert sonuc["kisi kaydi: iki TM kimligi ayni kisiye baglanmamis"] is False
