"""Ikinci sonuc degiskeni: KENDI VERIMIZDEN "ust lige gecis" (FAZ 6.2b).

NEDEN
Birinci sonuc degiskeni (outcome.py) Transfermarkt'a dayaniyor ve TM'nin
oyuncu bazinda izlemedigi liglerde KOR: "degerleme yok" grubunda 895
oyuncudan 12 olumlu (%1,3), 28 lig-sezonun 22'sinde sifir olumlu (§45.3).
Kolombiya/Arjantin/Ekvador/Iskandinavya'da bir oyuncu kendi ulkesinde ust
lige ciksa bile TM tarafinda "iz yok" gorunur.

Bu modul ayni oyuncunun SONRAKI SEZON satirini kendi API verimizden
(player_features) arar: 24 ligimizden birinde, orijinden DAHA UST bir
seviyede >=450 dk oynadi mi?

TUZAKLAR (hepsi 6.1'deki sansur dersinden)
1) SANSUR: sonraki-sezon penceresi TUM orijinler icin ayni uzunlukta olmali.
   Sabit pencere: sezon bitisinden (90 gun, 400 gun]. 2024 orijinleri
   gozlenemez (2025 API'de kapali) ve DISLANIR - sifir sayilmaz.
2) TAKVIM: sezon ETIKETI kullanilmiyor; tarih kullaniliyor (outcome.py'deki
   TM tuzagiyla ayni sebep). Brezilya 2022 -> Portekiz 2022/23 ayni etiketli
   sezon, ama tarihce SONRA.
3) SEVIYE: lig seviyesi elle tanimli (asagida) ve VERIYLE SINANIYOR - orijinden
   farkli seviyeye gecenlerin kacta kaci yukari? Yon dengesizse tanim yanlis.

NE OLCMUYOR
Gorulmeyen ligler (Turkiye, Rusya, MLS...) icin gecis GORUNMEZ; 24 ligimizin
disina gidenler "gecis yok" gorunur. TM gorunurlugunun ayna gorunumu: iki
sonuc birbirinin kor noktasini kismen kapatiyor, hicbiri tam degil.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from scout.features.outcome import sezon_bitis

# 1 = en ust. Elle tanimli, agirlikli olarak KABA (4 kademe) tutuldu ki
# tek tek lig siralamasi tartismasi sonucu tasimasin. Yon dengesi ile
# sinaniyor (yon_dengesi).
SEVIYE = {
    # T1 - ilk-5
    39: 1, 140: 1, 135: 1, 78: 1, 61: 1,
    # T2 - guclu ikinci grup
    94: 2, 88: 2, 144: 2, 71: 2, 128: 2,
    # T3
    119: 3, 103: 3, 113: 3, 72: 3, 62: 3, 136: 3, 239: 3,
    # T4
    80: 4, 89: 4, 145: 4, 95: 4, 114: 4, 242: 4, 244: 4,
}

PENCERE_ALT_GUN = 90      # ayni sezon (kis transferi) sayilmasin
PENCERE_UST_GUN = 400     # ~13 ay - TM sonucunun 12 ayina esdeger
ASGARI_DAKIKA = 450
GOZLEM_GUN = 360          # orijinden bu kadar sonrasi veride var mi


def seviye(lig_id: int) -> int | None:
    return SEVIYE.get(int(lig_id))


def ust_gecis(orijin: pd.DataFrame, havuz: pd.DataFrame,
              veri_sonu: dt.date | None = None) -> pd.DataFrame:
    """Her orijin satiri icin ust lige gecis sonucu.

    orijin: player_id, league_id, season, country
    havuz : player_id, league_id, season, country, minutes  (sonraki
            sezon adaylari - tum oyuncu-lig-sezonlar)
    Doner: orijin + [bitis, o_seviye, gozlenebilir, y2, hedef_lig,
                     hedef_dk, herhangi_sonraki]
      gozlenebilir=False -> penceresi veriyle KAPANMAMIS (sifir DEGIL, disla)
    """
    o = orijin.copy()
    o["bitis"] = [pd.Timestamp(sezon_bitis(c, s))
                  for c, s in zip(o.country, o.season)]
    o["o_seviye"] = o.league_id.map(seviye)

    h = havuz.copy()
    h["h_bitis"] = [pd.Timestamp(sezon_bitis(c, s))
                    for c, s in zip(h.country, h.season)]
    h["h_seviye"] = h.league_id.map(seviye)

    if veri_sonu is None:
        vs = h.h_bitis.max()
    else:
        vs = pd.Timestamp(veri_sonu)
    o["gozlenebilir"] = (vs - o.bitis).dt.days >= GOZLEM_GUN

    m = o[["player_id", "league_id", "season", "bitis", "o_seviye"]].merge(
        h[["player_id", "league_id", "season", "h_bitis", "h_seviye",
           "minutes"]].rename(columns={"league_id": "h_lig",
                                       "season": "h_sezon"}),
        on="player_id", how="left")
    fark = (m.h_bitis - m.bitis).dt.days
    m = m[(fark > PENCERE_ALT_GUN) & (fark <= PENCERE_UST_GUN)]
    m = m[m.minutes >= ASGARI_DAKIKA]

    anahtar = ["player_id", "league_id", "season"]
    yukari = m[m.h_seviye < m.o_seviye]
    y = (yukari.sort_values("h_seviye").drop_duplicates(anahtar)
         [anahtar + ["h_lig", "minutes"]]
         .rename(columns={"h_lig": "hedef_lig", "minutes": "hedef_dk"}))
    o = o.merge(y, on=anahtar, how="left")
    o["y2"] = o.hedef_lig.notna().astype(int)

    var = m.drop_duplicates(anahtar)[anahtar].assign(herhangi_sonraki=True)
    o = o.merge(var, on=anahtar, how="left")
    o["herhangi_sonraki"] = o.herhangi_sonraki.fillna(False).astype(bool)
    return o


def yon_dengesi(orijin: pd.DataFrame, havuz: pd.DataFrame) -> dict:
    """SEVIYE tanimini VERIYLE sina.

    Farkli seviyedeki bir lige gecenlerin kacta kaci yukari? Tanim dogruysa
    yukari gecis belirgin cogunlukta olmali (genc yetenekler yukari gider);
    yon dengeliyse ya da asagi baskinsa seviye siralamasi yanlis.
    """
    o = ust_gecis(orijin, havuz)
    o = o[o.gozlenebilir]
    # tum gecisler (yukari + asagi) icin ayni pencere
    h = havuz.copy()
    h["h_bitis"] = [pd.Timestamp(sezon_bitis(c, s))
                    for c, s in zip(h.country, h.season)]
    h["h_seviye"] = h.league_id.map(seviye)
    m = o[["player_id", "league_id", "season", "bitis", "o_seviye"]].merge(
        h[["player_id", "h_bitis", "h_seviye", "minutes"]],
        on="player_id", how="inner")
    fark = (m.h_bitis - m.bitis).dt.days
    m = m[(fark > PENCERE_ALT_GUN) & (fark <= PENCERE_UST_GUN)
          & (m.minutes >= ASGARI_DAKIKA)]
    m = m.dropna(subset=["o_seviye", "h_seviye"])
    yukari = int((m.h_seviye < m.o_seviye).sum())
    asagi = int((m.h_seviye > m.o_seviye).sum())
    ayni = int((m.h_seviye == m.o_seviye).sum())
    return {"yukari": yukari, "asagi": asagi, "ayni": ayni,
            "yukari_orani": yukari / max(yukari + asagi, 1)}
