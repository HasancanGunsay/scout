"""Kadro rol haritasi - takimin hangi rolde guclu, hangisinde bosluk (ADIM 6).

Kesif "kim iyi" diye sorar, bu modul "BIZE KIM LAZIM" diye sorar. Ligin en
iyi on liberosu, zaten iki tane on liberosu olan takim icin bir sey ifade
etmez.

TABAN NEDEN TAKIM SEVIYESINDE?
Rol skorlari zaten (lig, sezon, mevki) kohortu icinde percentile, yani ayni
lig icinde takim-takim kiyas mesru. Ama kiyas tabani OYUNCU medyani olamaz:
o medyan yedekleri de sayar ve tabani yapay olarak asagi ceker - her takim
her rolde "ortalamanin ustunde" cikar. Dogru taban, HER TAKIMIN o roldeki
EN IYISININ medyani: "ligin ortalama takiminin o roldeki en iyisi".

LIGLER ARASI KIYAS YAPILMAZ
Lig gucu duzeltmesi geriye donuk testte sonucu KOTULESTIRIYORDU (§23),
o yuzden skora uygulanmiyor. Bu modul tek lig-sezon icinde calisir.

ESIK NEDEN 12 (OLCULDU, 30 Agu 2026)
Ilk surumde 8'di ve bir OLCUM DEGIL VARSAYIMDI. Olculdu ve YETERSIZ cikti.

Yontem: ayni takim + ayni rol + AYNI OYUNCU, ardisik iki sezon (n=1.006).
Kadro degismedigi icin 'fark' degerinin sezonlar arasi oynamasi
= gercek gelisim + olcum gurultusu. Gercek gelisim >= 0 oldugundan bu bir
UST SINIR.

  |degisim| medyani            7,7 percentile
  |degisim| %68 yuzdeligi     12,1
  +-8 bandinin ictekiler orani  %51   <- yarisi disarida kaliyordu
  +-12 bandinin ictekiler orani %67

Olcut: bant, hicbir sey degismemis vakalarin ~%68'ini (1 SD esdegeri)
kapsamali. Bu 12,1 -> 12.

Ust sinir oldugu icin gercek gurultu daha kucuk olabilir; yani 12 GENIS
tarafta hata yapiyor - var olan bir boslugu kacirir, olmayan bir boslugu
uydurmaz. Bu projenin baska yerlerdeki durusuyla ayni yonde (eksik veriden
skor uretmemek gibi): uydurmaktansa susmak.

Yeniden olcmek icin: python scripts/validate_squad.py
"""

from __future__ import annotations

import pandas as pd

ESIK = 12.0


def durum(fark: float, esik: float = ESIK) -> str:
    """Farki 'guclu' / 'ortalama' / 'bosluk' olarak etiketle."""
    if pd.isna(fark):
        return "ortalama"
    if fark >= esik:
        return "guclu"
    if fark <= -esik:
        return "bosluk"
    return "ortalama"


def rol_haritasi(
    lig_skor: pd.DataFrame,
    takim: str,
    *,
    esik: float = ESIK,
) -> pd.DataFrame:
    """Bir takimin rol haritasi.

    lig_skor: TEK bir lig-sezonun (oyuncu x rol) skorlari. Dakika ve kapsam
              suzgecleri cagiran tarafta uygulanmis olmali.

    Doner: rol basina bir satir -
        role, role_name, player_name, score, age_season_end, minutes,
        lig_taban, fark, derinlik, durum
    """
    gerekli = {"team_name", "role", "role_name", "score", "player_name",
               "player_id", "minutes"}
    eksik = gerekli - set(lig_skor.columns)
    if eksik:
        raise KeyError(f"eksik sutun: {sorted(eksik)}")

    df = lig_skor[lig_skor.score.notna()]
    if df.empty or takim not in set(df.team_name):
        return pd.DataFrame()

    # ligin tabani: her takimin o roldeki en iyisinin medyani
    takim_en_iyi = df.groupby(["team_name", "role"], as_index=False).score.max()
    lig_taban = (takim_en_iyi.groupby("role", as_index=False).score.median()
                             .rename(columns={"score": "lig_taban"}))

    kadro = df[df.team_name == takim]
    if kadro.empty:
        return pd.DataFrame()

    sut = ["role", "role_name", "player_name", "score", "minutes"]
    if "age_season_end" in kadro.columns:
        sut.append("age_season_end")
    en_iyi = kadro.loc[kadro.groupby("role").score.idxmax(), sut]

    # derinlik: o rolde ligin OYUNCU medyaninin ustunde kac oyuncumuz var
    oyuncu_medyan = df.groupby("role").score.median().rename("oyuncu_medyan")
    k = kadro.join(oyuncu_medyan, on="role")
    derinlik = k[k.score > k.oyuncu_medyan].groupby("role").size().rename("derinlik")

    out = en_iyi.merge(lig_taban, on="role", how="left").join(derinlik, on="role")
    out["derinlik"] = out.derinlik.fillna(0).astype(int)
    out["fark"] = out.score - out.lig_taban
    out["durum"] = out.fark.map(lambda f: durum(f, esik))
    return out.sort_values("fark").reset_index(drop=True)


def yas_profili(kadro: pd.DataFrame) -> pd.DataFrame:
    """Dakika agirlikli yas bandi dagilimi.

    Kadro yenileme ihtiyacini oyuncu SAYISI degil oynanan DAKIKA gosterir:
    on yedek genc olabilir ama sahada 33 yasindakiler varsa kadro yaslidir.
    """
    sinirlar = [0, 21, 24, 28, 31, 99]
    etiketler = ["U21", "21-23", "24-27", "28-30", "31+"]

    d = kadro.drop_duplicates("player_id")[["age_season_end", "minutes"]].copy()
    d = d.apply(pd.to_numeric, errors="coerce").dropna()
    if d.empty:
        return pd.DataFrame(columns=["bant", "dakika", "oyuncu", "pay"])

    d["bant"] = pd.cut(d.age_season_end, bins=sinirlar, labels=etiketler,
                       right=False)
    ozet = (d.groupby("bant", observed=False)
             .agg(dakika=("minutes", "sum"), oyuncu=("minutes", "size"))
             .reset_index())
    toplam = ozet.dakika.sum()
    ozet["pay"] = 100 * ozet.dakika / toplam if toplam else 0.0
    return ozet

# --------------------------------------------------- yedek benzerligi (olculdu)
# "Stil benzerligi yedek bulmaya yarar" iddiasi ilk surumde DOGRULANMAMISTI.
# Olculdu (30 Agu 2026, scripts/validate_squad.py):
#
#   Sonuc degiskeni KULUPLERIN KENDI DAVRANISI: bir rolun en iyisi takimdan
#   ayrildiginda, yerine gelen oyuncu ligdeki rastgele bir ayni-mevki
#   oyuncusundan daha mi benzer stilde?
#
#   n = 2.510 degisim
#   gelenin yuzdelik sirasi 0,406  %95 GA [0,394 , 0,417]   (0,50 = rastgele)
#   -> Kulupler GERCEKTEN benzerini ariyor. Genel olarak ANLAMLI.
#
# AMA MEVKIYE GORE CARPICI BICIMDE DEGISIYOR - ve kalecide TERSINE DONUYOR:
GECMIS_YEDEK_BENZERLIGI = {
    "Defender":   (+0.654, +0.596, +0.710, 608),
    "Midfielder": (+0.140, +0.083, +0.204, 710),
    "Attacker":   (+0.061, +0.017, +0.106, 1055),
    "Goalkeeper": (-0.170, -0.276, -0.070, 137),
}
# (ortalama fark, GA alt, GA ust, n) - pozitif = gelen rastgeleden BENZER.
#
# KALECI UYARISI: -0,170, GA tamami negatif. Kulupler kaleci degistirirken
# rastgeleden DAHA FARKLI stilde birini aliyor. Sebebi muhtemelen kaleci
# "stil" vektorunun (pas/mudahale hacimleri) kalecilikte anlamli bir sey
# olcmemesi. Arayuz kalecide aciktan uyariyor - sessizce yanlis yol
# gostermektense hicbir sey soylememek yeglenir.


def yedek_benzerligi_notu(pos_group: str):
    """(seviye, ort, lo, hi, n) - arayuzun mevkiye gore gosterecegi bulgu.

    seviye: 'guclu' | 'zayif' | 'ters' | 'bilinmiyor'

    Metin URETMEZ: src/ ASCII ve dilden bagimsiz kaliyor, kullaniciya
    gorunen Turkce cumleyi arayuz kuruyor (app/views/Kadro_Analizi.py).
    Ilk surumde metni burada uretmistim ve sayfada Turkce arayuzun
    ortasinda ASCII bir cumle olarak goruldu.
    """
    kayit = GECMIS_YEDEK_BENZERLIGI.get(pos_group)
    if kayit is None:
        return "bilinmiyor", None, None, None, 0
    ort, lo, hi, n = kayit
    if hi < 0:
        return "ters", ort, lo, hi, n
    if ort >= 0.30:
        return "guclu", ort, lo, hi, n
    return "zayif", ort, lo, hi, n
