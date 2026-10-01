"""Mevki siralamasi mantigi: filtre, siralama, ozet (FAZ 6.5).

METIN URETMEZ - kod dondurur; Turkce cumleleri arayuz kurar (§35.6, §41.4).

KULLANICININ TESTI
Kullanici tarihsel bir sezonu secer, mevki + fiyat tavani belirler, listenin
en ustunu inceler ve "gercekte ne oldu"ya bakar. Bu modul o listenin OZETINI
de uretir: listedeki oyuncularin kacinin gercekten yer edindigi, havuzun
tabaniyla ve GUVEN ARALIGIYLA birlikte. Aralik olmadan oran vermek, bu
projenin aylarca yaptigi hatadir (§31).

NE OLCMUYOR
Ozet yalnizca TM sonucuna (yer edindi) dayanir. Rating yok; deger artisi
kanitlanmadi (§48.9). 'dogrulanmamis' guvenli satirlarda sonuc kismen kordur.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scout.features.emsal import wilson

OLCUTLER = {                         # hepsi kapsam-kalibre (6.6); *_ham = oncesi
    "model": "model_olasilik",        # tam model (oyun verisi + piyasa)
    "piyasa_ustu": "piyasa_ustu",     # model - piyasa (yalniz degerlemesi VARSA)
    "saf": "saf",                     # yalniz oyun verisi, piyasa YOK
}
GUVENLER = ["iyi", "zayif", "dogrulanmamis", "dusuk"]
MEVKILER = ["Defender", "Midfielder", "Attacker", "Goalkeeper"]

ASGARI_OZET_N = 30          # bunun altinda oran YORUMLANMAZ (kucuk kohort kurali)

# ozet uyari kodlari
UYARI_KUCUK_N = "kucuk_n"
UYARI_DOGRULANMAMIS = "dogrulanmamis_agirlikli"
UYARI_KALECI = "kaleci"
UYARI_ZAYIF = "zayif_agirlikli"
UYARI_IZLENEN = "izlenen_agirlikli"

# Karisik (iki kapsamli) havuzda listenin bu kadari izlenen liglerdense uyar.
# Kalibrasyon (6.6) sonrasi izlenen ligler kalibre olasilikta ustte: sonucu
# GORUNUR olan one cikiyor; dusuk gorunurlukteki gizli yetenek geri itiliyor.
IZLENEN_ESIGI = 0.75


def filtrele(df: pd.DataFrame, *, sezon: int | None = None,
             mevkiler: list[str] | None = None, kapsam: str | None = None,
             fiyat_tavani: float | None = None, degersiz_dahil: bool = True,
             guvenler: list[str] | None = None, yas_max: float | None = None,
             min_dakika: float = 0) -> pd.DataFrame:
    """Kullanicinin filtreleri. fiyat_tavani EUR cinsinden.

    Degerlemesi OLMAYAN oyuncu 'ucuz' sayilir mi? Kullanici karar verir
    (degersiz_dahil): eksik deger 0 EUR DEGILDIR (§39.4, §45); bu yuzden
    tavan karsilastirmasina sokulmaz, ayri bir secenektir.
    """
    m = pd.Series(True, index=df.index)
    if sezon is not None:
        m &= df.season == sezon
    if mevkiler:
        m &= df.pos_group.isin(mevkiler)
    if kapsam in ("tam", "sicrama_only"):
        m &= df.kapsam == kapsam
    if fiyat_tavani is not None:
        var = df.deger.notna()
        m &= (var & (df.deger <= fiyat_tavani)) | (~var & degersiz_dahil)
    if guvenler:
        m &= df.guven.isin(guvenler)
    if yas_max is not None:
        m &= df.age_season_end <= yas_max
    if min_dakika:
        m &= df.minutes >= min_dakika
    return df[m]


def sirala(df: pd.DataFrame, olcut: str = "model", n: int = 20) -> pd.DataFrame:
    """Olcute gore ilk n. Olcut NaN olan satirlar SIRALANMAZ (dislanir).

    'piyasa_ustu' yalnizca degerlemesi olanlarda tanimli; digerlerini sona
    itmek yerine listeden cikarmak dogru: onlar icin 'piyasa altinda
    fiyatlanma' TANIMSIZ (§45.4).
    """
    kol = OLCUTLER[olcut]
    x = df.dropna(subset=[kol])
    return x.sort_values(kol, ascending=False).head(n)


def yer_edindi(df: pd.DataFrame) -> pd.Series:
    """kademe>=3; kademe bilinmiyorsa NaN (0 DEGIL)."""
    return (df.kademe >= 3).astype(float).where(df.kademe.notna())


def ozet(top: pd.DataFrame, havuz: pd.DataFrame) -> dict:
    """Listenin ozeti: gercekte yer edinen oran, tabanla ve GA ile.

    top   : gosterilen liste
    havuz : ayni filtrelerin uygulandigi TUM oyuncular (top dahil)
    """
    y_top = yer_edindi(top).dropna()
    y_hav = yer_edindi(havuz).dropna()
    n = len(y_top)
    o = {
        "n": n,
        "havuz_n": len(y_hav),
        "yeterli": n >= ASGARI_OZET_N,
        "uyarilar": [],
    }
    if len(y_hav):
        o["taban"] = float(y_hav.mean())
    if n:
        olumlu = int(y_top.sum())
        lo, hi = wilson(olumlu, n)
        o.update(olumlu=olumlu, oran=olumlu / n, oran_lo=lo, oran_hi=hi)
        if "taban" in o:
            o["ga_tabani_asiyor"] = bool(lo > o["taban"])
    if n < ASGARI_OZET_N:
        o["uyarilar"].append(UYARI_KUCUK_N)

    if len(top):
        pay = top.guven.value_counts(normalize=True)
        if pay.get("dogrulanmamis", 0) >= 0.5:
            o["uyarilar"].append(UYARI_DOGRULANMAMIS)
        if pay.get("zayif", 0) >= 0.5:
            o["uyarilar"].append(UYARI_ZAYIF)
        if (top.pos_group == "Goalkeeper").mean() >= 0.5:
            o["uyarilar"].append(UYARI_KALECI)
        if "kapsam" in top.columns and havuz.kapsam.nunique() > 1:
            pay_tam = float((top.kapsam == "tam").mean())
            o["izlenen_payi"] = pay_tam
            if pay_tam >= IZLENEN_ESIGI:
                o["uyarilar"].append(UYARI_IZLENEN)
        o["guven_dagilimi"] = {k: int(v) for k, v in
                               top.guven.value_counts().items()}

    # sonra-sutunlari (yalniz gozlenenlerde)
    for kol in ("dk_lig", "ilk11_lig", "ga90"):
        if kol in top.columns:
            s = pd.to_numeric(top[kol], errors="coerce").dropna()
            o[f"{kol}_ort"] = float(s.mean()) if len(s) else None
            o[f"{kol}_n"] = int(len(s))
    return o


def sonra_metni_kodu(r: pd.Series) -> str:
    """'Sonra' sutununun durum kodu - izlenmeyen ligde 'iz yok' BASARISIZLIK
    degildir (§38.4)."""
    if pd.isna(r.get("kademe")):
        return "bilinmiyor"
    k = int(r["kademe"])
    if k >= 3:
        return "yer_edindi"
    if k == 2:
        return "rotasyon"
    if k == 1:
        return "gorundu"
    return "iz_yok_gorunmez" if r.get("kapsam") == "sicrama_only" else "iz_yok"
