"""Mevcut iki kaynagin adaptorleri: API-Football ve Transfermarkt (FAZ 9.4).

Ikisi de analitik veritabanindaki MEVCUT tablolardan okur (player_season,
tm_*); ham veriye yeniden gitmez. Yani bu adaptorler mevcut hattin ciktisini
standart sekle cevirir, hattin kendisini degistirmez.
"""
from __future__ import annotations

from scout.kaynaklar import tm_db_yolu
from scout.resolve.matcher import KABUL


class ApiFootballKaynak:
    """API-Football ucretsiz plan (2022-24). Mac bazinda veri YOK: yalniz sezon."""

    ad = "api"
    surum = "api-football-free-2022-2024"
    omurga = False

    def eslesme_sql(self) -> str:
        """Kisi kaydina baglama: YALNIZ kabul edilmis eslesme (A/B/manuel, §60).
        Kabul disi aday (aday_tm_id) baglanmaz - o oyuncu 'api:<id>' kalir."""
        kabul = ", ".join(f"'{k}'" for k in KABUL)
        return f"""
            SELECT CAST(player_id AS VARCHAR) AS kaynak_id,
                   'tm:' || CAST(CAST(tm_id AS BIGINT) AS VARCHAR) AS kisi_id,
                   confidence AS guven, 'eslesme' AS yontem
            FROM player_links
            WHERE confidence IN ({kabul}) AND tm_id IS NOT NULL"""

    def sql(self, tablo: str) -> str | None:
        s = f"'{self.surum}'"
        if tablo == "kaynak_kimlik":
            # Oyuncu birden cok lig-sezonda gorunur: kimlik icin en son kayit.
            return f"""
                SELECT 'api' AS kaynak, CAST(player_id AS VARCHAR) AS kaynak_id,
                       {s} AS kaynak_surum,
                       arg_max(coalesce(nullif(trim(coalesce(firstname,'') || ' ' ||
                               coalesce(lastname,'')), ''), player_name), season) AS ad,
                       arg_max(CAST(birth_date AS DATE), season) AS dogum_tarihi,
                       arg_max(nationality, season) AS uyruk,
                       arg_max(height_cm, season) AS boy_cm,
                       CAST(NULL AS VARCHAR) AS ayak,
                       arg_max(position, season) AS mevki
                FROM player_season GROUP BY player_id"""
        if tablo == "kaynak_oyuncu_sezon":
            return f"""
                SELECT 'api', CAST(player_id AS VARCHAR), {s},
                       CAST(league_id AS VARCHAR), season, CAST(team_id AS VARCHAR),
                       apps, starts, minutes, goals, assists
                FROM player_season"""
        return None


class TransfermarktKaynak:
    """Transfermarkt acik veri seti (CC0), config/kaynaklar.yaml'daki surum."""

    ad = "tm"
    omurga = True          # kisi kaydinin omurgasi: her TM oyuncusu bir kisi

    def eslesme_sql(self) -> None:
        return None

    def __init__(self, surum: str | None = None):
        self.surum = surum or f"transfermarkt-{tm_db_yolu().parent.name}"

    def sql(self, tablo: str) -> str | None:
        s = f"'{self.surum}'"
        if tablo == "kaynak_kimlik":
            return f"""
                SELECT 'tm', CAST(player_id AS VARCHAR), {s}, name,
                       CAST(date_of_birth AS DATE), country_of_citizenship,
                       height_in_cm, foot, coalesce(sub_position, position)
                FROM tm_players"""
        if tablo == "kaynak_mac_katilim":
            return f"""
                SELECT 'tm', CAST(player_id AS VARCHAR), {s}, CAST(game_id AS VARCHAR),
                       date, competition_id, CAST(player_club_id AS VARCHAR),
                       minutes_played, goals, assists, yellow_cards, red_cards
                FROM tm_appearances"""
        if tablo == "kaynak_oyuncu_sezon":
            return f"""
                SELECT 'tm', CAST(player_id AS VARCHAR), {s}, comp, season,
                       CAST(club_id AS VARCHAR), mac, ilk11, dk, gol, asist
                FROM tm_oyuncu_sezon"""
        if tablo == "kaynak_deger":
            return f"""
                SELECT 'tm', CAST(player_id AS VARCHAR), {s}, date, market_value_in_eur
                FROM tm_player_valuations"""
        if tablo == "kaynak_sozlesme":
            return f"""
                SELECT 'tm', CAST(player_id AS VARCHAR), {s}, current_club_name,
                       CAST(contract_expiration_date AS DATE)
                FROM tm_players WHERE contract_expiration_date IS NOT NULL"""
        return None


def varsayilan_kaynaklar() -> list:
    return [ApiFootballKaynak(), TransfermarktKaynak()]
