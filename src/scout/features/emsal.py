"""Emsal orani: "bu profildeki oyuncular ne oldu?" (FAZ 3)

Profesyonel scout'un asil sordugu soru "kac puan aldi" degil:

    "Bu profildeki 40 oyuncudan 9'u izlenen bir birinci ligde yer edindi:
     %23 (%95 GA %12-%38). Ligin taban orani %12."

Bu bir TAHMIN DEGIL, bir TABAN ORANI. Model bir olasilik uretir ve kullanici
ona guvenmek zorunda kalir; emsal orani sayilabilir, ADI OLAN bir gecmis
gosterir. Scout dosyasinda (FAZ 4) ikisi yan yana durur.

=========================================================================
MESAFE: MODELIN OZELLIK UZAYI  (ILK SURUM YANLISTI)
=========================================================================
Ilk surumde mesafe stil (CLR, 10 boyut) + seviye (2 boyut) idi - yani
agirligin %83'u "nasil oynuyor" boyutundaydi. Oysa modelin en guclu
degiskenleri deger_var (+1,44) ve log_deger (+0,88) ve bunlar mesafeye
HIC girmiyordu. Yani "benzer OYNAYANLARI" buluyorduk, "benzer DURUMDA
olanlari" degil.

Dort tanim olculdu (scripts/emsal_tani.py · 2024 hedef, havuz 2022+2023):

    tanim                        AUC   kalibrasyon  tabani asan
    stil + seviye (eski)        0,560     0,0217       %17,8
    stil + seviye + deger       0,590     0,0255       %15,7
    MODEL UZAYI (secilen)       0,662     0,0237       %13,8
    model olasiligi komsulugu   0,663     0,0305       %14,3

Model olasiligi komsulugu ayni ayirt etme gucunu veriyor ama kalibrasyonu
daha kotu VE emsalleri yorumlanamaz kiliyor: ayni olasiliga sahip iki
oyuncu bambaska olabilir. Model uzayinda komsu olanlar gercekten benzer -
scout o 40 ismi acip bakabilir.

STIL BENZERLIGI KAYBOLMADI, AYRI BIR SORU
  "Kim gibi oynuyor" sorusu Profil sayfasindaki benzer oyuncu aramasinda
  (§25) duruyor. Emsal orani "kim onun DURUMUNDAYDI" sorusunu yanitliyor.
  Iki ayri soru, iki ayri arac.

=========================================================================
ZORUNLU ESITLIKLER (mesafeye girmez, FILTREDIR)
=========================================================================
  - ayni mevki grubu   : stoperle forveti kiyaslamak anlamsiz
  - ayni KAPSAM        : 'tam' liglerde taban %57, 'sicrama_only'de %12.
                         Karistirmak orani anlamsizlastirir (§38.4).
  - benzer lig taban orani : Premier League cocuguyla Superettan cocugunu
                         emsal saymak, ligin kendisini yetenek sanmaktir
  - yas +-1,5 yil
  - AYNI OYUNCU DEGIL  : kendi baska sezonu emsali olamaz

=========================================================================
EMSAL HAVUZU ZAMAN BAKIMINDAN NE ICERIR
=========================================================================
Uretimde emsaller TUM gozlenmis sezonlardan seciliyor - 2022'de skorlanan
bir oyuncunun emsalleri arasinda 2024 oyunculari da olabilir. Bu bir
SIZINTI DEGIL cunku ifade tahmin degil betimleme. Yine de ileriye donuk
bir ifade degildir.

Ayirt etme gucu olculurken bu ozellikle engellendi: 2024 hedeflerinin
emsalleri YALNIZCA 2022+2023'ten secildi.

=========================================================================
NE IDDIA ETMIYOR
=========================================================================
Emsal orani modeli GECMEZ (0,662 vs 0,706) ve gecmesi beklenmiyor. Isi
tahmin degil GEREKCELENDIRME: kullaniciya sayabilecegi, adlarini
okuyabilecegi bir gecmis vermek.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Emsal grubu bundan kucukse ORAN URETILMEZ. Kucuk kohortta percentile
# uretmeme kuralinin (§21) aynisi: eksik kanittan makul gorunen bir sayi
# uretmek, sayi uretmemekten daha zararli.
ASGARI_EMSAL = 30
VARSAYILAN_K = 40

YAS_BANDI = 1.5          # yil
TABAN_BANDI = 0.10       # ligin taban orani farki (mutlak, 0-1)

# Mesafenin hesaplandigi ozellikler - model neyi onemsiyorsa o.
MESAFE_OZELLIKLERI = [
    "score", "score_age", "age_season_end", "minutes", "minutes_pct",
    "minutes_agepct", "rating_pct", "starts_pct", "log_deger", "deger_var",
]


def lig_taban_orani(df: pd.DataFrame, hedef_kol: str = "y") -> pd.Series:
    """Her (lig, sezon) icin gozlenen basari orani.

    Emsal eslestirmesinde lig gucu yerine BUNU kullaniyoruz. Sebep:
    league_strength kopru modelinin kaniti zayif (rho 0,654 ama
    GA [0,188 , 0,890], §31.5). Taban orani ise dogrudan olculen sey ve
    tam olarak kiyaslamak istedigimiz boyut.
    """
    return df.groupby(["league_id", "season"])[hedef_kol].transform("mean")


def mesafe_uzayi(df: pd.DataFrame, agirliklar=None,
                 ozellikler: list[str] | None = None) -> np.ndarray:
    """Standartlastirilmis, katsayiyla agirliklandirilmis ozellik matrisi.

    agirliklar: modelin |katsayi| vektoru. None ise esit agirlik.
                Agirliklandirma onemli: model 'deger_var'a 1,44,
                'starts_pct'e 0,05 veriyor - esit agirlik bu farki siler.
    """
    kul = [c for c in (ozellikler or MESAFE_OZELLIKLERI) if c in df.columns]
    X = df[kul].apply(pd.to_numeric, errors="coerce")
    X = X.fillna(X.median()).fillna(0.0).to_numpy(float)
    sd = X.std(axis=0)
    sd[sd < 1e-9] = 1.0
    Z = (X - X.mean(axis=0)) / sd
    if agirliklar is not None:
        Z = Z * np.asarray(agirliklar, float)[:Z.shape[1]]
    return Z


def emsaller(
    havuz: pd.DataFrame,
    hedef_idx,
    Z: np.ndarray,
    *,
    k: int = VARSAYILAN_K,
    yas_bandi: float = YAS_BANDI,
    taban_bandi: float = TABAN_BANDI,
) -> pd.DataFrame:
    """hedef_idx'e en yakin k emsal.

    Z: havuz ile AYNI SIRADA mesafe uzayi matrisi (mesafe_uzayi ciktisi).
       Disaridan veriliyor ki her hedef icin yeniden hesaplanmasin - ilk
       surum bunu her satirda yeniden hesapliyordu ve O(n^2) idi.
    """
    if hedef_idx not in havuz.index:
        return pd.DataFrame()
    konum = havuz.index.get_loc(hedef_idx)
    if not isinstance(konum, (int, np.integer)):
        return pd.DataFrame()       # yinelenen index etiketi
    h = havuz.loc[hedef_idx]

    uygun = (
        (havuz.index != hedef_idx)
        & (havuz.player_id != h.player_id).to_numpy()
        & (havuz.pos_group == h.pos_group).to_numpy()
        & (havuz.kapsam == h.kapsam).to_numpy()
        & ((havuz.age_season_end - h.age_season_end).abs()
           <= yas_bandi).to_numpy()
        & ((havuz.lig_taban - h.lig_taban).abs() <= taban_bandi).to_numpy()
    )
    if int(uygun.sum()) < ASGARI_EMSAL:
        return pd.DataFrame()

    d = np.linalg.norm(Z - Z[konum], axis=1)
    d = np.where(uygun, d, np.inf)
    en_yakin = np.argsort(d)[:min(k, int(uygun.sum()))]
    out = havuz.iloc[en_yakin].copy()
    out["uzaklik"] = d[en_yakin]
    return out


def wilson(olumlu: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Oran icin Wilson guven araligi.

    NEDEN GEREKLI: n=40'ta 6 olumlu "%15" demek, ama %7 ile %29 arasindaki
    her sey ayni veriyle uyumlu. Belirsizligi gostermeden oran vermek, bu
    projenin aylarca yaptigi hatanin (nokta tahmini, GA yok - §31) aynisi.
    Normal yaklasim ucta cok kotu; Wilson kucuk n ve uc oranlarda dogru.
    """
    if n <= 0:
        return float("nan"), float("nan")
    p = olumlu / n
    payda = 1 + z * z / n
    merkez = (p + z * z / (2 * n)) / payda
    yari = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / payda
    return max(0.0, merkez - yari), min(1.0, merkez + yari)


def ozet(emsal: pd.DataFrame, lig_taban: float) -> dict:
    """Emsal grubunu tek bir ifadeye indirger.

    Grup ASGARI_EMSAL'in altindaysa oran URETILMEZ (None doner).
    """
    n = len(emsal)
    if n < ASGARI_EMSAL:
        return {"n": n, "olumlu": None, "oran": None, "oran_lo": None,
                "oran_hi": None, "lig_taban": lig_taban, "kaldirac": None,
                "taban_ustunde": None, "yeterli": False}
    olumlu = int(emsal["y"].sum())
    oran = olumlu / n
    lo, hi = wilson(olumlu, n)
    kaldirac = oran / lig_taban if lig_taban and lig_taban > 0 else None
    # Karar bu bayraga bakar, kaldiraca DEGIL: taban %3 iken %15 bulmak
    # 5 kat gorunur ama n=40'ta bu fark gurultuden ayirt edilemeyebilir.
    taban_ustunde = bool(lo > lig_taban) if lig_taban is not None else None
    return {"n": n, "olumlu": olumlu, "oran": oran, "oran_lo": lo,
            "oran_hi": hi, "lig_taban": lig_taban, "kaldirac": kaldirac,
            "taban_ustunde": taban_ustunde, "yeterli": True}


def cumle(o: dict) -> str:
    """Scout dosyasina girecek ifade. Belirsizlik HER ZAMAN gosterilir."""
    if not o["yeterli"]:
        return (f"Emsal grubu yetersiz ({int(o['n'])} kisi, en az "
                f"{ASGARI_EMSAL} gerekiyor) - oran uretilmedi.")
    s = (f"Bu profildeki {int(o['n'])} oyuncudan {int(o['olumlu'])}'i "
         f"izlenen bir birinci ligde yer edindi: %{100 * o['oran']:.0f} "
         f"(%95 GA %{100 * o['oran_lo']:.0f}-%{100 * o['oran_hi']:.0f}). "
         f"Ligin taban orani %{100 * o['lig_taban']:.0f}.")
    if o["taban_ustunde"]:
        s += " Guven araligi tabanin USTUNDE - profil gercekten ayirt ediyor."
    else:
        s += (" Guven araligi tabani KAPSIYOR - bu profil tabandan ayirt "
              "edilemiyor.")
    return s


# NOT (30 Agu 2026): 'kaldirac' (oran / lig_taban) SIRALAMA ANAHTARI DEGIL.
# Olculdu: kaldiraca gore siralayinca liste, tabani %3 olan liglerle
# (Arjantin, Brezilya Serie B, Eliteserien) doluyor - kucuk payda etkisi.
# Ilk 12'nin 11'i sonradan hicbir izlenen lige cikmamisti. Kaldirac BAGLAM
# icin gosterilir; siralama modelin olasiligiyla yapilir.
