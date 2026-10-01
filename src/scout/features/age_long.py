"""BOYLAMSAL yas egrisi - ayni oyuncunun kendi degisimi (ADIM 3).

NEDEN KESITSEL FIT ISE YARAMADI (iki kez reddedildi, §19)
Bir sezonun (ya da havuzlanmis sezonlarin) yas-performans kesitine egri
uydurmak HAYATTA KALMA YANLILIGI tasir: 35 yasinda hala oynayanlar
secilmis bir azinliktir. Egri onlarin iyiligini YASA mal eder ve
"yas ilerledikce performans artiyor" der. Olculdu: fit edilen egri
16 yasindan 38'e MONOTON ARTIYORDU, hic tepe yapmadan.

BU MODULUN YAKLASIMI: FARK YONTEMI
Ayni oyuncunun ardisik sezonlari arasindaki DEGISIME bakariz:

    delta_yillik = (metrik[t2] - metrik[t1]) / (sezon[t2] - sezon[t1])

Oyuncu kendi kontrolu olur - kalitesi diferansiyelde duser. Yas basina
ortalama delta, egrinin O YASTAKI EGIMIDIR. Egimleri kumulatif toplayinca
egrinin kendisi cikar.

KALAN YANLILIK - DURUSTCE
Fark yontemi hayatta kalma yanliligini AZALTIR ama YOK ETMEZ. Cok kotu
oynayan oyuncu ertesi sezon oynamaz, dolayisiyla onun (negatif) deltasi
hic olculmez. Bu, egriyi ozellikle ileri yaslarda YUKARI cekler; yani
gercek dususu HAFIFE ALIR. Bu modul dusus tahminini "en iyimser senaryo"
olarak sunar ve orneklem kaybini raporlar.

Genclerde ayni sorun cok daha kucuk: 19 yasinda kotu oynayan oyuncuya
genellikle ikinci bir sezon verilir.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MIN_DAKIKA = 450        # her iki sezonda da
MIN_BIN = 15            # bir yas kutusunda bu kadar gozlem yoksa guvenilmez
YAS_ARALIGI = (17.0, 36.0)


def gecisler(
    df: pd.DataFrame,
    metrik: str,
    *,
    min_dakika: int = MIN_DAKIKA,
    yas_col: str = "age_season_end",
    ayni_lig: bool = True,
) -> pd.DataFrame:
    """Ayni oyuncunun ardisik sezon ciftleri -> yillik degisim.

    Bir oyuncunun 3 sezonu varsa 2 gecis uretir (t1->t2, t2->t3).
    Aradaki bosluk 1 yildan buyukse degisim yila bolunur.

    ayni_lig : True ise yalnizca AYNI LIGDE kalan gecisler kullanilir.
        NEDEN VARSAYILAN: 'score' lig ICI percentile. Oyuncu lig
        degistirince kohortu da degisir ve delta iki sebebi karistirir:
        yaslanma + kohort degisimi. Olculdu - etki gercek ve buyuk:
            tum gecisler        -> tepe 23 yas
            yalnizca ayni lig   -> tepe 25 yas
        Ayni lig kisiti daha temiz bir tanimlama; bedeli orneklem
        (7.084 -> 4.808 gecis).
    """
    k = ["player_id", "season"]
    alt = df[df["minutes"] >= min_dakika].dropna(subset=[metrik, yas_col])
    if ayni_lig and "league_id" in alt.columns:
        tek = alt.groupby("player_id").league_id.transform("nunique") == 1
        alt = alt[tek]
    # sezon ici transferde ayni oyuncu-sezon birden fazla satir olabilir
    alt = (alt.sort_values("minutes", ascending=False)
           .drop_duplicates(k)
           .sort_values(k))

    out = []
    for _, g in alt.groupby("player_id", sort=False):
        g = g.sort_values("season")
        for i in range(len(g) - 1):
            a, b = g.iloc[i], g.iloc[i + 1]
            fark_yil = float(b.season - a.season)
            if fark_yil <= 0:
                continue
            out.append({
                "player_id": a.player_id,
                "yas_orta": (float(a[yas_col]) + float(b[yas_col])) / 2.0,
                "delta_yillik": (float(b[metrik]) - float(a[metrik])) / fark_yil,
                "agirlik": float(min(a.minutes, b.minutes)),
                "fark_yil": fark_yil,
            })
    return pd.DataFrame(out)


class BoylamsalYasEgrisi:
    """Fark yontemiyle yas egrisi.

    fit sonrasi:
        egim_    : yas -> yillik beklenen degisim
        egri_    : yas -> kumulatif seviye (17 yas = 0 referans)
        tepe_yas_, dusus_
    """

    def __init__(self, min_bin: int = MIN_BIN, aralik: tuple = YAS_ARALIGI,
                 derece: int = 2):
        self.min_bin = min_bin
        self.aralik = aralik
        self.derece = derece      # egim ~ yas polinom derecesi (0 = duzlestirme yok)
        self.egim_: pd.DataFrame | None = None
        self.egri_: pd.DataFrame | None = None
        self.tepe_yas_: float = np.nan
        self.dusus_: float = np.nan
        self.n_gecis_: int = 0
        self.n_oyuncu_: int = 0

    def fit(self, df: pd.DataFrame, metrik: str, **kw) -> "BoylamsalYasEgrisi":
        g = gecisler(df, metrik, **kw)
        self.n_gecis_ = len(g)
        self.n_oyuncu_ = int(g.player_id.nunique()) if len(g) else 0
        if len(g) < 100:
            return self

        lo, hi = self.aralik
        g = g[(g.yas_orta >= lo) & (g.yas_orta <= hi)].copy()
        g["kutu"] = np.floor(g.yas_orta).astype(int)

        satir = []
        for kutu, grup in g.groupby("kutu"):
            if len(grup) < self.min_bin:
                continue
            w = grup.agirlik.to_numpy(float)
            d = grup.delta_yillik.to_numpy(float)
            ort = float(np.average(d, weights=w))
            # agirlikli standart hata
            var = float(np.average((d - ort) ** 2, weights=w))
            satir.append({"yas": int(kutu), "egim": ort, "n": len(grup),
                          "se": float(np.sqrt(var / max(len(grup), 1)))})
        if not satir:
            return self

        self.egim_ = pd.DataFrame(satir).sort_values("yas").reset_index(drop=True)

        # DUZLESTIRME: ham kutu ortalamalari gurultulu - uc kutularda n
        # kucuk ve isaret zipliyor (olculdu: 19'da -1,66, 20'de +0,68,
        # 21'de -0,71). Kumulatif toplam bu gurultuyu BIRIKTIRIR, yani
        # egrinin sekli birkac gurultulu kutunun esiri olur.
        # Egimi yasin polinomu olarak modelleyip oyle topluyoruz.
        yas_v = self.egim_.yas.to_numpy(float)
        egim_v = self.egim_.egim.to_numpy(float)
        w = self.egim_.n.to_numpy(float)
        if self.derece > 0 and len(yas_v) > self.derece + 1:
            kat = np.polyfit(yas_v, egim_v, self.derece, w=np.sqrt(w))
            self.egim_["egim_duz"] = np.polyval(kat, yas_v)
        else:
            self.egim_["egim_duz"] = egim_v

        # Egimleri topla -> egri. Ilk yas 0 referans.
        seviye = np.concatenate([[0.0], np.cumsum(self.egim_.egim_duz.to_numpy())])
        yaslar = np.concatenate([[self.egim_.yas.iloc[0]],
                                 self.egim_.yas.to_numpy() + 1])
        self.egri_ = pd.DataFrame({"yas": yaslar, "seviye": seviye})

        i = int(self.egri_.seviye.idxmax())
        self.tepe_yas_ = float(self.egri_.yas.iloc[i])
        sonrasi = self.egri_.seviye.iloc[i:]
        self.dusus_ = float(self.egri_.seviye.iloc[i] - sonrasi.min())
        return self

    @property
    def makul(self) -> bool:
        """Egri futbolca makul mu? (§19'daki sekil kapisinin aynisi)

        Tepe 23-32 arasinda olmali ve tepeden sonra anlamli dusus olmali.
        Bu kapi kesitsel egriyi reddetmisti; boylamsal egri de ayni
        sinavdan gecmek zorunda - yontem degisti diye standart dusmez.
        """
        if self.egri_ is None or not np.isfinite(self.tepe_yas_):
            return False
        aralik = float(self.egri_.seviye.max() - self.egri_.seviye.min())
        if aralik <= 0:
            return False
        return (23.0 <= self.tepe_yas_ <= 32.0
                and self.dusus_ >= 0.15 * aralik)
