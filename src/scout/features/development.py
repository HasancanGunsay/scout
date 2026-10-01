"""Gelisim egrisi - ayni oyuncunun sezonlar arasi degisimi (ADIM 6).

SORU: kim yukseliyor? Wonderkid avinda tek bir sezonun fotografi degil,
YONU onemli. 18 yasinda 70 alip 20 yasinda 88 alan oyuncu, iki sezondur
85 alandan daha degerli bir sinyaldir.

UC TUZAK VE COZUMLERI

1) ROL DEGISIMI - en sinsi olan.
   Olculdu: iki sezonu olan 5.659 oyuncunun 2.732'si (yarisi!) 'dogal rol'
   degistirmis. Ham skorlari karsilastirmak FARKLI SABLONLARI
   karsilastirmak olur - bir oyuncunun 'Stoper - Yikici' skoruyla
   'Bek - Hucumcu' skoru ayni birimde degildir.
   Cozum: delta HER ZAMAN SABIT ROL uzerinden. player_scores'ta her
   oyuncunun 14 rol skoru da duruyor, ayni sablonu iki sezonda da okuyoruz.

2) LIG DEGISIMI.
   Skor lig ICI percentile. Eerste Divisie'de 80. percentile olup
   Eredivisie'de yine 80 olan oyuncu aslinda GELISMISTIR. Delta bunu
   gormez. Bu yuzden lig degisimi ayrica isaretleniyor - duzeltme
   yapilmiyor (gerekce PLAN §23), ama kullanici gormeli.

3) YAS.
   Iki yillik pencerede genc oyuncu zaten gelisir. 'yasitlarina gore'
   (score_age) deltasi bu kismi soguruyor; ikisi de dondurulup yan yana
   gosteriliyor.
"""

from __future__ import annotations

import pandas as pd

# Delta guvenilir olsun diye iki sezonda da aranan asgari dakika
MIN_DAKIKA = 450


def gelisim(
    scores: pd.DataFrame,
    natural: pd.DataFrame,
    *,
    onceki: int = 2022,
    sonraki: int = 2024,
    min_dakika: int = MIN_DAKIKA,
    rol_kaynagi: str = "ortak",
) -> pd.DataFrame:
    """Sezonlar arasi gelisim tablosu.

    Parameters
    ----------
    scores      : player_scores (oyuncu x rol x sezon)
    natural     : player_natural_role (oyuncunun her sezondaki dogal rolu)
    rol_kaynagi : 'ortak'   -> VARSAYILAN. Iki sezonun ORTALAMASINI en
                               yuksek yapan rol. Simetrik oldugu icin
                               hicbir sezonu kayirmaz.
                  'onceki'  -> oyuncunun ONCEKI sezondaki dogal rolu
                  'sonraki' -> SONRAKI sezondaki dogal rolu

                  DIKKAT (olculdu): 'dogal rol' 14 rolun MAKSIMUMUDUR.
                  Rolu tek bir sezona sabitlemek o sezonun skorunu
                  maksimum, otekini maksimum-olmayan yapar ve fark KURGU
                  GEREGI kayar. Olculdu: 'onceki' ile ortalama gelisim
                  -5,41; 'sonraki' ile +3,89. Ayni veri, ters isaret.
                  'ortak' bu secilim etkisini simetriyle kaldirir.

    Returns
    -------
    Her satir bir oyuncu: iki sezonun skoru, delta, ve baglam bayraklari.
    """
    ikisi = scores[scores.season.isin([onceki, sonraki])]

    if rol_kaynagi == "ortak":
        # Iki sezonda da skoru olan (oyuncu, rol) ciftleri arasindan,
        # ORTALAMASI en yuksek olani sec. Simetrik -> yon yanliligi yok.
        ort = (ikisi.dropna(subset=["score"])
               .groupby(["player_id", "role"])
               .agg(ort=("score", "mean"), n=("season", "nunique"))
               .reset_index())
        ort = ort[ort.n == 2]
        sabit = (ort.sort_values("ort", ascending=False)
                 .drop_duplicates("player_id")[["player_id", "role"]]
                 .rename(columns={"role": "sabit_rol"}))
    else:
        sezon = onceki if rol_kaynagi == "onceki" else sonraki
        sabit = (natural[natural.season == sezon][["player_id", "role"]]
                 .drop_duplicates("player_id")
                 .rename(columns={"role": "sabit_rol"}))

    s = ikisi.merge(sabit, on="player_id", how="inner")
    s = s[s.role == s.sabit_rol]

    kolonlar = ["player_id", "player_name", "score", "score_age", "coverage",
                "minutes", "age_season_end", "league_name", "country",
                "team_name", "role_name"]
    kolonlar = [c for c in kolonlar if c in s.columns]
    # Sezon ici transferde ayni oyuncu-sezon icin birden fazla satir
    # olabilir; en cok dakikali kaydi esas aliyoruz.
    a = (s[s.season == onceki].sort_values("minutes", ascending=False)
         .drop_duplicates("player_id")[kolonlar])
    b = (s[s.season == sonraki].sort_values("minutes", ascending=False)
         .drop_duplicates("player_id")[kolonlar])

    out = a.merge(b, on="player_id", suffixes=("_0", "_1"))
    out = out[(out.minutes_0 >= min_dakika) & (out.minutes_1 >= min_dakika)]
    out = out.dropna(subset=["score_0", "score_1"])

    out["gelisim"] = out.score_1 - out.score_0
    if "score_age_0" in out.columns:
        out["gelisim_yas"] = out.score_age_1 - out.score_age_0

    # Baglam bayraklari - duzeltme DEGIL, gorunurluk
    out["lig_degisti"] = out.league_name_0 != out.league_name_1
    if "role_name_0" in out.columns:
        # Bir oyuncu ayni sezonda birden fazla ligde olabilir (sezon ici
        # transfer) - tekillestirmeden index kurulamaz.
        dogal = (natural[natural.season.isin([onceki, sonraki])]
                 [["player_id", "season", "role_name"]])
        d0 = (dogal[dogal.season == onceki].drop_duplicates("player_id")
              .set_index("player_id").role_name)
        d1 = (dogal[dogal.season == sonraki].drop_duplicates("player_id")
              .set_index("player_id").role_name)
        out["dogal_rol_degisti"] = (
            out.player_id.map(d0) != out.player_id.map(d1))

    return out.sort_values("gelisim", ascending=False).reset_index(drop=True)
