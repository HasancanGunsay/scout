"""Metrik kataloğu — aileler, Türkçe adlar, biçim ve yön.

Kullanıcı isteği (1 Eki 2026): bir metriğe bakarken onu bağlamına oturtan
İLİŞKİLİ metrikler de görünsün — pas /90'a bakarken toplam pası, ikili
kazanma yüzdesine bakarken kaç ikiliye girdiğini görebilmek gibi. Bir oran
hacmi olmadan yanıltır: 3 ikilinin 3'ünü kazanmak %100'dür.

/90 sütunları güvenilirlik düzeltmeli (_sh): az dakikada şişen uç değerler
ligin ortalamasına doğru çekilmiştir (§11).

API'NİN "passes.accuracy" ALANI YÜZDE DEĞİL (1 Eki 2026'da ölçüldü):
pas hacmini izliyor (90 dk başına pasla korelasyon 0,66); düzenli
oynayanlarda kabaca maç başına isabetli pas SAYISI. Dunk 2022: 90 dk'da 89
pas, değer 80. Gerçek pas isabeti yüzdesi ücretsiz API'de yok.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Metrik:
    kol: str
    ad: str
    bicim: str = "%.2f"          # streamlit NumberColumn formatı
    yuzde: bool = False          # 0-1 değeri yüzde olarak gösterilir
    dusuk_iyi: bool = False      # sıralama varsayılanı artan
    aciklama: str = ""


_SH = "Güvenilirlik düzeltmeli: az dakikada şişen uç değerler ligin ortalamasına çekildi."

AILELER: dict[str, list[Metrik]] = {
    "Pas ve oyun kurma": [
        Metrik("passes_p90_sh", "Pas /90", "%.1f", aciklama=_SH),
        Metrik("passes", "Toplam pas", "%d"),
        Metrik("pass_accuracy", "İsabetli pas/maç (API)", "%d",
               aciklama="YÜZDE DEĞİL. API bu alanda yaklaşık maç başına "
                        "isabetli pas sayısı veriyor; pas hacmiyle birlikte "
                        "artar. Gerçek isabet yüzdesi için Sofascore."),
        Metrik("key_passes_p90_sh", "Kilit pas /90", "%.2f", aciklama=_SH),
        Metrik("key_passes", "Toplam kilit pas", "%d"),
        Metrik("assists", "Asist", "%d"),
    ],
    "Gol ve şut": [
        Metrik("np_ga_p90_sh", "Gol+asist /90 (pen.siz)", "%.2f", aciklama=_SH),
        Metrik("np_goals_p90_sh", "Gol /90 (pen.siz)", "%.2f", aciklama=_SH),
        Metrik("goals", "Gol", "%d"),
        Metrik("shots_p90_sh", "Şut /90", "%.2f", aciklama=_SH),
        Metrik("shots", "Toplam şut", "%d"),
        Metrik("shot_accuracy", "İsabetli şut %", "%.0f%%", yuzde=True,
               aciklama="İsabetli şut / toplam şut."),
        Metrik("goals_per_shot", "Gol / şut", "%.2f"),
    ],
    "Çalım ve top taşıma": [
        Metrik("dribbles_won_p90_sh", "Başarılı çalım /90", "%.2f", aciklama=_SH),
        Metrik("dribbles_p90_sh", "Çalım denemesi /90", "%.2f", aciklama=_SH),
        Metrik("dribble_pct", "Çalım başarısı %", "%.0f%%", yuzde=True),
        Metrik("dribbles_won", "Toplam başarılı çalım", "%d"),
        Metrik("fouls_drawn_p90_sh", "Kazanılan faul /90", "%.2f", aciklama=_SH),
    ],
    "İkili mücadele": [
        Metrik("duels_won_p90_sh", "Kazanılan ikili /90", "%.2f", aciklama=_SH),
        Metrik("duel_win_pct", "İkili kazanma %", "%.0f%%", yuzde=True),
        Metrik("duels_p90_sh", "İkili /90", "%.2f", aciklama=_SH),
        Metrik("duels", "Toplam ikili", "%d"),
        Metrik("duels_won", "Kazanılan ikili", "%d"),
    ],
    "Savunma": [
        Metrik("def_actions_padj_p90_sh", "Savunma aksiyonu /90 (düz.)", "%.2f",
               aciklama="Top kapma + pas arası + blok; takımın topa sahip "
                        "olma payına göre düzeltilmiş (§32) ve güvenilirlik "
                        "düzeltmeli."),
        Metrik("tackles_padj_p90_sh", "Top kapma /90 (düz.)", "%.2f",
               aciklama="Topa sahip olma payına göre düzeltilmiş."),
        Metrik("interceptions_padj_p90_sh", "Pas arası /90 (düz.)", "%.2f",
               aciklama="Topa sahip olma payına göre düzeltilmiş."),
        Metrik("blocks_p90_sh", "Blok /90", "%.2f", aciklama=_SH),
        Metrik("tackles", "Toplam top kapma", "%d"),
        Metrik("interceptions", "Toplam pas arası", "%d"),
        Metrik("dribbled_past", "Çalımlandığı", "%d", dusuk_iyi=True),
    ],
    "Disiplin": [
        Metrik("fouls_made_p90_sh", "Yapılan faul /90", "%.2f", dusuk_iyi=True,
               aciklama=_SH),
        Metrik("cards_p90_sh", "Kart /90", "%.2f", dusuk_iyi=True, aciklama=_SH),
        Metrik("yellow", "Sarı kart", "%d", dusuk_iyi=True),
        Metrik("red", "Kırmızı kart", "%d", dusuk_iyi=True),
        Metrik("fouls_drawn", "Kazanılan faul", "%d"),
    ],
    "Kaleci": [
        Metrik("saves_p90_sh", "Kurtarış /90", "%.2f", aciklama=_SH),
        Metrik("goals_conceded_p90_sh", "Yenen gol /90", "%.2f", dusuk_iyi=True,
               aciklama=_SH),
        Metrik("saves", "Toplam kurtarış", "%d"),
        Metrik("goals_conceded", "Yenen gol", "%d", dusuk_iyi=True),
    ],
    "Süre ve reyting": [
        Metrik("rating", "API reytingi", "%.2f"),
        Metrik("rating_pct", "Reyting yüzdeliği", "%.0f",
               aciklama="Lig-sezon-mevki kohortundaki yüzdelik (0-100)."),
        Metrik("minutes", "Dakika", "%d"),
        Metrik("starts_pct", "İlk 11 oranı %", "%.0f%%", yuzde=True),
        Metrik("apps", "Maç", "%d"),
        Metrik("starts", "İlk 11", "%d"),
        Metrik("sub_in", "Yedekten giriş", "%d"),
    ],
}

TUMU: dict[str, Metrik] = {m.kol: m for ms in AILELER.values() for m in ms}

MEVKI_ADI = {"Goalkeeper": "Kaleci", "Defender": "Defans",
             "Midfielder": "Orta saha", "Attacker": "Forvet",
             "Unknown": "Bilinmiyor"}


def ad(kol: str) -> str:
    """Bilinen metrikte Türkçe ad, değilse kolon adı (SQL sekmesi için)."""
    m = TUMU.get(kol)
    return m.ad if m else kol


def aile_bul(kol: str) -> str | None:
    for aile, ms in AILELER.items():
        if any(m.kol == kol for m in ms):
            return aile
    return None
