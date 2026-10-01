"""Transfermarkt tarihsel veri (FAZ 7.1): 2012-2025, yalniz TM.

NEDEN
API ucretsiz plani yalnizca 2022-2024'u veriyor ve 2024 held-out'u bes
bakisla tukendi. Ham TM dosyasinda hic kullanilmamis 2012-2021 (10 sezon)
ve 2025/26 var. Bu modul, o donemi mevcut sistemle AYNI sonuc tanimiyla
(outcome.py: 12 ay, kademe) kullanilabilir hale getirir.

SINIR (kullaniciya hep soylenmeli)
TM yalnizca 14 birinci ligde oyuncu kaydi tutuyor. Dusuk gorunurluklu
ligler (projenin asil hedefi) bu donemde YOK. Bu veriyle dogrulanan sey:
izlenen liglerdeki genc oyuncular icin TM verisinin ne soyledigi ve
kalibrasyonun zaman icinde nasil kaydigi.

SAVUNMA ICIN (kullanicinin sorusu, 1 Eki 2026)
TM'nin olay verisi gol/asist/kart odakli - savunmaya kor. Bu yuzden
mevkiden bagimsiz baglam uretilir: oyuncu sahadayken takimin attigi/yedigi
gol (arti-eksi), takim gucu, ilk 11 ve 90 dakika istikrari. Mevki, oyuncunun
BUGUNKU mevkisi degil, o sezon ilk 11'de en cok oynadigi mevkidir
(game_lineups) - stoper / sol bek / sag bek / on libero ayrimi buradan.

MUHUR (7.2 icin ONCEDEN, sonuclara bakilmadan konuldu)
  2012          yalniz 'onceki sezon' bilgisi (kadro verisi yok)
  2013-2017     GELISTIRME - ozellik, model ve kural secimi burada
  2018-2021     MUHURLU TEST - TEK ACILIS; 7.1'de sonuclarina bakilmaz
  2022-2024     API donemi - 7.4 karsilastirmasi (API modeliyle ayni yillar)
  2025          ileriye donuk (sonuc penceresi acik) - 7.5 defteri
"""

from __future__ import annotations

YALNIZ_GECMIS = (2012,)
GELISTIRME = tuple(range(2013, 2018))
MUHURLU_TEST = tuple(range(2018, 2022))
API_DONEMI = (2022, 2023, 2024)
ILERIYE_DONUK = (2025,)

BOLUM = {
    **{s: "yalniz_gecmis" for s in YALNIZ_GECMIS},
    **{s: "gelistirme" for s in GELISTIRME},
    **{s: "muhurlu_test" for s in MUHURLU_TEST},
    **{s: "api_donemi" for s in API_DONEMI},
    **{s: "ileriye_donuk" for s in ILERIYE_DONUK},
}


def bolum(sezon: int) -> str | None:
    return BOLUM.get(int(sezon))


# game_lineups.position -> (ince mevki, kaba grup). Kaba grup API'nin
# dortlusuyle ayni adlar: modeller ve sayfalar ayni sozlugu kullanir.
INCE_MEVKI = {
    "Goalkeeper": ("Kaleci", "Goalkeeper"),
    "Centre-Back": ("Stoper", "Defender"),
    "Sweeper": ("Stoper", "Defender"),
    "Left-Back": ("Sol bek", "Defender"),
    "Right-Back": ("Sag bek", "Defender"),
    "Defender": ("Defans (belirsiz)", "Defender"),
    "Defensive Midfield": ("On libero", "Midfielder"),
    "Central Midfield": ("Merkez orta saha", "Midfielder"),
    "Attacking Midfield": ("10 numara", "Midfielder"),
    "Left Midfield": ("Sol orta saha", "Midfielder"),
    "Right Midfield": ("Sag orta saha", "Midfielder"),
    "Midfield": ("Orta saha (belirsiz)", "Midfielder"),
    "midfield": ("Orta saha (belirsiz)", "Midfielder"),
    "Left Winger": ("Sol kanat", "Attacker"),
    "Right Winger": ("Sag kanat", "Attacker"),
    "Centre-Forward": ("Santrfor", "Attacker"),
    "Second Striker": ("Ikinci forvet", "Attacker"),
    "Attack": ("Forvet (belirsiz)", "Attacker"),
}
# players.position (oyuncunun GUNCEL kaba mevkisi) - yalniz kadro verisi
# yoksa yedek olarak
KABA_YEDEK = {"Goalkeeper": "Goalkeeper", "Defender": "Defender",
              "Midfield": "Midfielder", "Attack": "Attacker"}


def mevki(lineup_pos: str | None, guncel_pos: str | None) -> tuple[str | None, str | None, str]:
    """(ince, kaba, kaynak). kaynak: 'kadro' (o sezonun ilk 11'i) | 'guncel'
    (oyuncunun BUGUNKU mevkisi - tarihsel olarak yanlis olabilir) | 'yok'."""
    if lineup_pos and lineup_pos in INCE_MEVKI:
        ince, kaba = INCE_MEVKI[lineup_pos]
        return ince, kaba, "kadro"
    if guncel_pos in KABA_YEDEK:
        return None, KABA_YEDEK[guncel_pos], "guncel"
    return None, None, "yok"


SAHADA_YOK = 999     # oyundan cikmadi: uzatmalar dahil sonuna kadar sahada


def sahada_mi(gol_dakika: float, giris: float, cikis: float) -> bool:
    """Gol oyuncu sahadayken mi oldu? Aralik (giris, cikis]: giris dakikasindaki
    gol oyuncu girmeden, cikis dakikasindaki gol cikmadan once sayilir."""
    return giris < max(gol_dakika, 1) <= cikis
