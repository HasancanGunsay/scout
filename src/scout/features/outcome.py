"""Gercek sonuc: skorladigimiz oyuncuya SONRADAN ne oldu (FAZ 1).

NEDEN VAR
Simdiye kadarki butun dogrulama geriye donuk testti - 2022'den 2023/24'u
tahmin et, ayni veri havuzu icinde. Transfermarkt CC0 veri setinin
`appearances` tablosu 2026-05'e kadar mac bazinda dakika/gol veriyor;
yani API'nin ucretsiz planda vermedigi 2025/26 sonuclari elimizde.
Bu, modelin gelistirilmesinde hic kullanilmamis GERCEK bir pencere.

OLCULEN SEY NE DEGIL
TM 31 birinci ligi ve Avrupa kupalarini izliyor. Bir oyuncunun TM'de kaydi
YOKSA bu "basarisiz oldu" demek DEGIL - Kolombiya'da gayet iyi oynuyor ama
izlenmiyor olabilir. Olculen sey:

    "izlenen bir birinci lige sicradi ve orada yer edindi mi"

Wonderkid avi icin dogru hedef bu, ama cumleyi boyle kurmak zorundayiz.

=========================================================================
TUZAK: TM'NIN SEZON ETIKETI TAKVIM YILI LIGLERINDE BIR YIL KAYIK
=========================================================================
Olculdu (30 Agu 2026), TM games tablosundan:

    BRA1 season=2024  ->  maclar 2025-03-29 .. 2025-12-07   (takvim 2025!)
    ARG1 season=2024  ->  maclar 2025-01-24 .. 2025-05-04
    SE1  season=2024  ->  maclar 2025-03-29 .. 2025-11-09
    ES1  season=2024  ->  maclar 2024-08-15 .. 2025-05-25   (bizimkiyle ayni)

Bizim API sezonumuzda Brezilya 2024 = takvim 2024. Yani TM'nin `season`
alanini dogrudan kullanmak Brezilya/Arjantin/Iskandinavya icin BIR YIL
kaydirirdi ve bunu kimse fark etmezdi - sonuc tablosu makul gorunurdu.

COZUM: sezon etiketi HIC kullanilmiyor. Her sey TARIHE dayaniyor.
Sonuc penceresi, skorlanan sezonun bitis TARIHINDEN itibaren 12 ve 24 aylik
iki dilim. Takvim uzlasimi ne olursa olsun calisir.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

# Takvim yili ligleri: sezon S, S yilinin aralik ayinda biter.
# Empirik olarak dogrulandi (yukaridaki tablo): Brezilya 7 Ara, Isvec 9 Kas,
# Norvec 30 Kas. 15 Aralik guvenli bir ust sinir - bir sonraki sezon en
# erken mart sonunda basliyor.
TAKVIM_YILI_ULKELERI = {
    "Argentina", "Brazil", "Colombia", "Ecuador", "Finland", "Norway", "Sweden",
}

# Sonbahar-ilkbahar ligleri: sezon S, S+1 yilinin mayisinda biter.
# Gozlenen en gec bitis 25 Mayis; 15 Haziran guvenli ust sinir.
SONBAHAR_BITIS = (6, 15)
TAKVIM_BITIS = (12, 15)

# =========================================================================
# TUZAK 2: competitions TABLOSU 31 BIRINCI LIG DIYOR, VERI 14'UNDE VAR
# =========================================================================
# Olculdu (30 Agu 2026): tm_competitions 31 tane type='domestic_league'
# listeliyor ve tm_games bunlarin maclarini iceriyor. AMA appearances
# tablosunda yalnizca 14'unun OYUNCU kaydi var:
#
#   BRA1 (Brezilya Serie A)  -> 557 mac,  0 appearance
#   ARG1 (Arjantin)          -> 418 mac,  0 appearance
#   SE1  (Allsvenskan)       -> 329 mac,  0 appearance
#   NO1  (Eliteserien)       -> 329 mac,  0 appearance
#
# Bunlari "izleniyor" saymak felaket olurdu: Brezilya Serie A'da kalmaya
# devam eden oyuncu "iz yok" (kademe 0) cikardi ve model "Brezilya Serie A
# oyunculari basarisiz oluyor" diye ogrenirdi. Olculdu: bu ligler yanlislikla
# izleniyor sayilinca ortalama kademeleri 0,22-0,34 cikiyordu - Ligue 2'nin
# (0,75) bile altinda, ki futbolen sacma.
#
# Veikkausliiga'nin 17 metrigi hic yayinlanmadigi halde 1.301 sahte skor
# uretmesiyle (§21) ayni sinif hata: EKSIK VERIYI SIFIR SAYMAK.
#
# COZUM: izlenen lig listesi SABIT DEGIL, appearances tablosundan
# TURETILIYOR (izlenen_ligler fonksiyonu).

# Bizim lig -> TM birinci lig karsiligi. Yalnizca TM'nin GERCEKTEN oyuncu
# kaydi tuttugu ligler; ikinci ligler ve kayit tutulmayan ulkeler None.
TM_KARSILIGI = {
    39:  "GB1",    # Premier League
    78:  "L1",     # Bundesliga
    135: "IT1",    # Italya Serie A
    140: "ES1",    # La Liga
    61:  "FR1",    # Ligue 1
    88:  "NL1",    # Eredivisie
    144: "BE1",    # Jupiler Pro League
    119: "DK1",    # Danimarka Superliga
    94:  "PO1",    # Primeira Liga
    # --- asagidakiler TM'de birinci lig olarak GORUNUYOR ama oyuncu kaydi
    #     YOK; izlenmiyor sayilmalari zorunlu (yukaridaki nota bak) ---
    71:  None,     # Brezilya Serie A  (BRA1 - 0 appearance)
    128: None,     # Liga Profesional Argentina (ARG1 - 0 appearance)
    113: None,     # Allsvenskan (SE1 - 0 appearance)
    103: None,     # Eliteserien (NO1 - 0 appearance)
    # --- ikinci ligler ve izlenmeyen ulkeler ---
    145: None, 72: None, 239: None, 242: None, 244: None,
    62: None, 80: None, 136: None, 89: None, 95: None, 114: None,
}

# Sonucun bu lig icin ne anlama geldigi.
#   "tam"          mensei izlenen bir lig - KALMAK da gorunur, sicramak da
#   "sicrama_only" mensei izlenmiyor - YALNIZCA 14 lige sicrayan gorunur.
#                  kademe 0 "basarisiz" DEMEK DEGIL.
KAPSAM_TAM = "tam"
KAPSAM_SICRAMA = "sicrama_only"

# Guney Amerika ve Iskandinavya icin ozellikle onemli: Brezilya Serie B'den
# Brezilya Serie A'ya cikmak gercek bir siçramadir ama BIZ GOREMEYIZ.
# Bu liglerin taban oranlari bu yuzden dusuk gorunur; lig ICINDE
# karsilastirma (in-league AUC, §31) bu yuzden zorunlu.


def izlenen_ligler(appearances: "pd.DataFrame", competitions: "pd.DataFrame",
                   *, asgari_satir: int = 5000) -> set[str]:
    """appearances'ta GERCEKTEN veri olan birinci ligler.

    Sabit liste tutmuyoruz: veri seti guncellendiginde yeni lig eklenebilir
    ya da bir lig dusebilir. Esik 5.000 satir - bir lig-sezon bile bunun
    ustunde; altinda kalan bir sey varsa kismi/bozuk kayittir.
    """
    birinci = set(competitions.loc[
        competitions["type"] == "domestic_league", "competition_id"])
    sayim = appearances.groupby("competition_id").size()
    return {k for k, v in sayim.items() if k in birinci and v >= asgari_satir}


def kapsam(league_id: int) -> str:
    """Bu ligden gelen oyuncunun sonucu ne kadar gorunur?"""
    return KAPSAM_TAM if TM_KARSILIGI.get(league_id) else KAPSAM_SICRAMA


ILK_BES = {"ES1", "GB1", "IT1", "L1", "FR1"}

# Kademe esikleri (tek bir 12 aylik dilimde, birinci lig dakikasi)
ESIK_GORUNDU = 1
ESIK_ROTASYON = 450
ESIK_YER_EDINDI = 900


def sezon_bitis(country: str, season: int) -> dt.date:
    """Skorlanan sezonun bitis tarihi. Sonuc penceresi buradan baslar."""
    if country in TAKVIM_YILI_ULKELERI:
        ay, gun = TAKVIM_BITIS
        return dt.date(int(season), ay, gun)
    ay, gun = SONBAHAR_BITIS
    return dt.date(int(season) + 1, ay, gun)


def kademe(lig_dakika: float, ilk_bes: bool) -> int:
    """Tek bir 12 aylik dilimin kademesi.

    0  TM'de birinci lig izi yok
    1  gorundu ama <450 dk
    2  450-899 dk (rotasyon)
    3  >=900 dk (yer edindi)
    4  >=900 dk ve ilk-5 ligde
    """
    if pd.isna(lig_dakika) or lig_dakika < ESIK_GORUNDU:
        return 0
    if lig_dakika < ESIK_ROTASYON:
        return 1
    if lig_dakika < ESIK_YER_EDINDI:
        return 2
    return 4 if ilk_bes else 3


KADEME_ADI = {
    0: "iz yok",
    1: "gorundu (<450 dk)",
    2: "rotasyon (450-899 dk)",
    3: "yer edindi (>=900 dk)",
    4: "ilk-5 ligde yer edindi",
}


# =========================================================================
# SANSURLEME (censoring) - 30 Agu 2026'da yakalandi
# =========================================================================
# Ilk surumde sonuc "iki dilimin en iyisi" (max(y1, y2)) olarak taniminmisti.
# Bu SANSURLU ve SANSURSUZ satirlari karistiriyordu:
#
#   veri sonu 2026-06-28
#   Hollanda 2022 -> sezon bitisi 2023-06-15 -> 36,4 ay gozlenebilir (y1+y2 tam)
#   Hollanda 2024 -> sezon bitisi 2025-06-15 -> 12,4 ay gozlenebilir (yalniz y1)
#
# Yani 2022 satirlarina IKI sans, 2024 satirlarina BIR sans veriliyordu.
# Egitilen model bundan "eski sezonlar daha basarili" diye ogrenirdi ve bu
# tamamen bir olcum artefakti olurdu. Sonuc tablosu makul gorunurdu.
#
# COZUM: birincil sonuc 12 AYLIK dilim - her sezon icin tam ve kiyaslanabilir.
# 24 aylik sonuc yalnizca penceresi tamamlanmis satirlarda uretilir, aksi
# halde NULL. Karistirmak imkansiz hale getirildi.

PENCERE_AY = 12


def gozlem_ay(bitis: dt.date, veri_sonu: dt.date) -> float:
    """Sezon bitisinden veri sonuna kac ay var."""
    return (veri_sonu - bitis).days / 30.44


def pencere_tam(bitis: dt.date, veri_sonu: dt.date, ay: int = PENCERE_AY) -> bool:
    """O dilim gercekten gozlenebildi mi?"""
    return gozlem_ay(bitis, veri_sonu) >= ay
