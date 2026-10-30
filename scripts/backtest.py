"""Geriye donuk test - sistem gercekten ise yariyor mu? (PLAN §8)

SORU: 2022 sezonunun verisiyle uretilen siralama, sonradan gercekten
sicrayan oyunculari on plana cikariyor mu?

Tahmin  : YALNIZCA 2022 verisi (skor, gol, dakika, o gunku piyasa degeri)
Sonuc   : 2023-24'te ne oldu
Yontem  : ilk-N isabet orani, karsilastirma tabanlariyla birlikte

IKI SONUC DEGISKENI - ikisi de bagimsiz, ikisi de kendi zayifligini tasiyor:

  A) PIYASA DEGERI BUYUMESI  (Transfermarkt)
     2022 degeri -> 2023/24 degeri. 'Sicrama' = en az 2 kat VE >= 1M EUR.
     NEDEN 2023/24, NEDEN 2025 DEGIL: TM anlik goruntusunde degerleme
     kapsami 2023'ten sonra cokuyor (20.452 -> 9.592 -> 5.986 oyuncu) ve
     kalanlar sistematik olarak daha degerli oyuncular (2022 medyani
     900k vs 600k). 2025 ufkuyla olculurse 'degerlemesi olmak' sonucun
     kendisi haline gelir ve test kendini dogrular (§16.5).

  B) LIG TERFISI  (kendi verimiz - TM'e hic bagimli degil)
     2022'de X liginde olan oyuncu 2024'te daha ust kademe bir ligde mi?
     Zayifligi: yalnizca takip ettigimiz 24 ligi gorur.

KARSILASTIRMA TABANLARI - sistem hepsini gecmeli:
  rastgele        : sansin ne verdigi
  gol             : "cok gol atan iyidir" - en yaygin naif yaklasim
  dakika          : "cok oynayan iyidir" - sinsi derecede guclu bir taban
  piyasa degeri   : EN ONEMLI TABAN. Piyasa 2022'de zaten ne dusunuyordu?
                    Sistem bunu gecemiyorsa hicbir sey eklemiyor demektir.

Ligler arasi percentile kiyasi henuz gecersiz (§5.2), bu yuzden siralama
HER LIGIN ICINDE yapilir; sonuclar sonra havuzlanir.

    python scripts/backtest.py
    python scripts/backtest.py --top 10 --min-minutes 900
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

# Windows Gorev Zamanlayici altinda stdout cp1254'e dusuyor ve Hirvat/Polonya
# isimlerindeki 'c' harfi (ć) tum zinciri UnicodeEncodeError ile
# kiriyordu (19 Agu 2026). Cikti kodlamasini burada sabitliyoruz.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scout.kaynaklar import db_yolu, tm_db_yolu  # noqa: E402
DB = db_yolu()  # SCOUT_DB ya da data/scout.duckdb (FAZ 9.5)
TM = tm_db_yolu()  # config/kaynaklar.yaml (FAZ 9.1)

RNG = np.random.default_rng(20260811)
N_BOOT = 2000

# Lig kademeleri - terfi sonucunu tanimlamak icin (dusuk sayi = daha guclu).
# Bu bir SCOUT YARGISI, veriden turetilmedi; ADIM 4'teki lig gucu modeli
# gelince olculmus katsayilarla degistirilecek.
TIER: dict[int, int] = {
    39: 1, 140: 1, 78: 1, 135: 1, 61: 1,        # Premier League, La Liga, Bundesliga, Serie A (IT), Ligue 1
    88: 2, 94: 2, 144: 2, 71: 2,                # Eredivisie, Primeira Liga, Jupiler, Serie A (BR)
    136: 3, 62: 3, 95: 3, 72: 3, 128: 3, 80: 3,  # Serie B (IT), Ligue 2, Segunda Liga, Serie B (BR), Argentina, 3. Liga
    103: 3, 113: 3, 119: 3,                     # Eliteserien, Allsvenskan, Superliga
    89: 4, 145: 4, 114: 4, 244: 4, 239: 4, 242: 4,  # Eerste Divisie, Challenger, Superettan, Veikkausliiga, Colombia, Ecuador
}


# --------------------------------------------------------------- veri
def load(min_minutes: int, max_age: float,
         tahmin_sezonu: int = 2022) -> pd.DataFrame:
    con = duckdb.connect(str(DB), read_only=True)
    con.execute(f"ATTACH '{TM}' AS tm (READ_ONLY)")

    TAHMIN = int(tahmin_sezonu)
    SONUC = 2024
    V0A, V0B = f"{TAHMIN}-01-01", f"{TAHMIN}-12-31"
    V1A, V1B = f"{TAHMIN + 1}-06-01", f"{TAHMIN + 2}-06-30"

    df = con.sql(f"""
      WITH t22 AS (
        SELECT s.player_id, s.league_id, s.league_name, s.country,
               s.player_name, s.age_season_end AS yas, s.minutes,
               s.goals, s.assists,
               n.role_name, n.score AS sistem_skoru,
               m.tm_id
        FROM player_season s
        JOIN player_natural_role n
          ON n.player_id = s.player_id AND n.league_id = s.league_id
         AND n.season = s.season
        LEFT JOIN player_meta m ON m.player_id = s.player_id
        WHERE s.season = {TAHMIN}
          AND s.minutes >= {min_minutes}
          AND s.age_season_end <= {max_age}
      ),
      -- 2022'deki piyasa degeri: tahmin aninda BILINEN bilgi
      v0 AS (
        SELECT player_id AS tm_id, max(market_value_in_eur) AS deger_2022
        FROM tm.player_valuations
        WHERE date BETWEEN '{V0A}' AND '{V0B}' GROUP BY 1
      ),
      -- 2023/24 degeri: SONUC. Kapsamin hala tam oldugu son pencere.
      v1 AS (
        SELECT player_id AS tm_id, max(market_value_in_eur) AS deger_2024
        FROM tm.player_valuations
        WHERE date BETWEEN '{V1A}' AND '{V1B}' GROUP BY 1
      )
      SELECT t22.*, v0.deger_2022, v1.deger_2024
      FROM t22
      LEFT JOIN v0 USING(tm_id)
      LEFT JOIN v1 USING(tm_id)
    """).df()

    # 2024 ligi: TIER esleme Python tarafinda daha okunakli
    l24 = con.sql(f"""
      SELECT player_id, league_id FROM player_season WHERE season = {SONUC}
    """).df()
    con.close()

    l24["tier24"] = l24.league_id.map(TIER)
    en_iyi = l24.dropna(subset=["tier24"]).groupby("player_id").tier24.min()
    df["tahmin_sezonu"] = TAHMIN
    df["tier_2022"] = df.league_id.map(TIER)
    df["tier_2024"] = df.player_id.map(en_iyi)
    return df


def sonuclari_ekle(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # --- A) piyasa degeri sicramasi -------------------------------------
    olculebilir = out.deger_2022.notna() & out.deger_2024.notna()
    kat = out.deger_2024 / out.deger_2022.replace(0, np.nan)
    out["deger_kati"] = kat.where(olculebilir)
    out["A_sicrama"] = np.where(
        olculebilir, (kat >= 2.0) & (out.deger_2024 >= 1_000_000), np.nan)

    # --- B) lig terfisi --------------------------------------------------
    # Sonuc yalnizca 2024'te BIR YERDE gorunen oyuncular icin tanimli.
    # Gorunmeyende 'terfi etmedi' demek yanlis olur: takip etmedigimiz bir
    # lige gitmis de olabilir. NaN birakip orneklemden cikariyoruz.
    gorundu = out.tier_2024.notna() & out.tier_2022.notna()
    out["B_terfi"] = np.where(gorundu, out.tier_2024 < out.tier_2022, np.nan)
    return out


# ----------------------------------------------------- degerlendirme
def ilk_n_isabet(g: pd.DataFrame, siralama: str, sonuc: str, n: int,
                 buyuk_iyi: bool = True) -> tuple[int, int]:
    """Bir lig icinde siralamanin ilk n'sinde kac isabet var?"""
    s = g.dropna(subset=[siralama, sonuc])
    if len(s) < n:
        return 0, 0
    ilk = s.nlargest(n, siralama) if buyuk_iyi else s.nsmallest(n, siralama)
    return int(ilk[sonuc].sum()), len(ilk)


def lig_ici_auc(df: pd.DataFrame, kol: str, sonuc: str) -> float:
    """Lig ici AUC - ilk-N'den COK DAHA GUCLU bir olcut.

    NEDEN: ilk-N yalnizca lig basina 15-20 oyuncuya bakip geri kalan bini
    atiyor; varyansi buyuk. AUC tum orneklemi kullanir. Olculdu (29 Agu):
        SISTEM - dakika farki, ilk-N ile GA [-0,096 , +0,049]
                              AUC  ile GA [-0,083 , +0,006]
    Ikisi de raporlaniyor: ilk-N KARAR icin (kullanici ilk 10'a bakiyor),
    AUC YONTEM KIYASI icin.
    """
    a, w = [], []
    for _, g in df.groupby("league_id"):
        t = g.dropna(subset=[kol, sonuc])
        y = t[sonuc].astype(int)
        if y.nunique() < 2 or len(t) < 25:
            continue
        a.append(roc_auc_score(y, t[kol]))
        w.append(len(t))
    return float(np.average(a, weights=w)) if a else np.nan


def _esli_bootstrap(df: pd.DataFrame, tabanlar: dict, sonuc: str, n: int,
                    B: int = 200) -> tuple[pd.DataFrame, pd.DataFrame]:
    """ESLESTIRILMIS + OYUNCU BAZLI bootstrap.

    ESLESTIRILMIS: her yeniden ornekte TUM yontemler ayni ornekte hesaplanir.
    Yontemler ayni oyunculara uygulandigi ve yuksek korelasyonlu oldugu icin
    farkin varyansi var(A)+var(B) degil var(A-B)'dir - cok daha kucuk.

    OYUNCU BAZLI: satir degil OYUNCU cekilir. Terfi sonucunda iki tahmin
    penceresi havuzlandigi icin ayni oyuncu birden fazla satirda olabilir;
    satirlari bagimsiz saymak araligi yapay olarak daraltirdi.

    Her yeniden ornekte ligler BIR KEZ dolasilir ve tum yontemler ayni
    gecişte hesaplanir - aksi halde ornek iki katina cikinca cok yavas.
    """
    oyuncu_gruplari = df.groupby("player_id").indices
    oyuncular = np.array(list(oyuncu_gruplari.keys()))
    adlar = list(tabanlar)
    ilk_n_kayit: dict[str, list] = {ad: [] for ad in adlar}
    auc_kayit: dict[str, list] = {ad: [] for ad in adlar}

    for _ in range(B):
        sec = RNG.choice(oyuncular, len(oyuncular), replace=True)
        s = df.iloc[np.concatenate([oyuncu_gruplari[o] for o in sec])]
        h = {ad: 0 for ad in adlar}
        t = {ad: 0 for ad in adlar}
        a_top = {ad: 0.0 for ad in adlar}
        a_agirlik = {ad: 0.0 for ad in adlar}
        for _, g in s.groupby("league_id"):
            for ad in adlar:
                kolon, buyuk = tabanlar[ad]
                x, y = ilk_n_isabet(g, kolon, sonuc, n, buyuk)
                h[ad] += x
                t[ad] += y
                q = g.dropna(subset=[kolon, sonuc])
                yy = q[sonuc].astype(int)
                if yy.nunique() >= 2 and len(q) >= 25:
                    a_top[ad] += roc_auc_score(yy, q[kolon]) * len(q)
                    a_agirlik[ad] += len(q)
        for ad in adlar:
            if t[ad]:
                ilk_n_kayit[ad].append(h[ad] / t[ad])
            if a_agirlik[ad]:
                auc_kayit[ad].append(a_top[ad] / a_agirlik[ad])

    satir = []
    for ad in adlar:
        r = {"yontem": ad}
        v, av = ilk_n_kayit[ad], auc_kayit[ad]
        if len(v) >= 30:
            lo, hi = np.percentile(v, [2.5, 97.5])
            r["ga_alt"], r["ga_ust"] = round(lo * 100, 1), round(hi * 100, 1)
        if len(av) >= 30:
            r["auc"] = round(float(np.mean(av)), 3)
        satir.append(r)

    ref = "SISTEM skoru"
    farklar = []
    if len(auc_kayit.get(ref, [])) >= 30:
        for ad in adlar:
            if ad == ref or len(auc_kayit[ad]) != len(auc_kayit[ref]):
                continue
            f = np.array(auc_kayit[ref]) - np.array(auc_kayit[ad])
            lo, hi = np.percentile(f, [2.5, 97.5])
            farklar.append({"kiyas": f"SISTEM - {ad}",
                            "auc_farki": round(float(np.mean(f)), 3),
                            "ga_alt": round(lo, 3), "ga_ust": round(hi, 3),
                            "ayirt_edilebilir": bool(lo > 0 or hi < 0)})
    return pd.DataFrame(satir), pd.DataFrame(farklar)


def degerlendir(df: pd.DataFrame, sonuc: str, n: int) -> pd.DataFrame:
    """Her taban icin ligler havuzlanmis ilk-N isabet orani."""
    tabanlar = {
        "SISTEM skoru": ("sistem_skoru", True),
        "gol": ("goals", True),
        "dakika": ("minutes", True),
        "piyasa degeri (2022)": ("deger_2022", True),
    }
    # TAM VAKA kisiti: her yontem AYNI havuzdan secmeli. Aksi halde bir
    # yontem 80, digeri 100 oyuncu secer ve oranlar kiyaslanamaz - lig
    # bilesimi de degisir. Siralama degiskenlerinden biri bile eksikse
    # o oyuncu tum yontemler icin disarida kalir.
    gerekli = [k for k, _ in tabanlar.values()] + [sonuc]
    df = df.dropna(subset=gerekli)

    satir = []
    for ad, (kolon, buyuk) in tabanlar.items():
        h = t = 0
        for _, g in df.groupby("league_id"):
            a, b = ilk_n_isabet(g, kolon, sonuc, n, buyuk)
            h, t = h + a, t + b
        satir.append({"yontem": ad, "isabet": h, "secilen": t,
                      "oran": h / t if t else np.nan})

    # rastgele taban: ayni buyuklukte rastgele secim, N_BOOT kez
    havuz = df.dropna(subset=[sonuc])
    oranlar = []
    for _ in range(N_BOOT):
        h = t = 0
        for _, g in havuz.groupby("league_id"):
            if len(g) < n:
                continue
            h += int(g[sonuc].to_numpy()[RNG.choice(len(g), n, replace=False)].sum())
            t += n
        if t:
            oranlar.append(h / t)
    rast = float(np.mean(oranlar)) if oranlar else np.nan
    satir.append({"yontem": "rastgele", "isabet": np.nan,
                  "secilen": np.nan, "oran": rast})

    res = pd.DataFrame(satir)
    res["kat_rastgele"] = res.oran / rast if rast else np.nan
    # OLCEGE DUYARSIZ basari: rastgeleden mukemmele giden yolun ne kadari
    # kat edildi? 0 = sans seviyesi, 1 = secilen herkes pozitif.
    # NEDEN GEREKLI: "rastgelenin 2 kati" kriteri taban orana gore bambaska
    # seyler istiyor. Ulasilabilir azami kat = 1/taban. Taban %13,5 iken 7,4x
    # mumkun, taban %42 iken yalnizca 2,36x. Ayni esik bir yerde kolay,
    # otekinde neredeyse imkansiz (§17.4'te fark edildi, 29 Agu'da duzeltildi).
    res["basari"] = ((res.oran - rast) / (1.0 - rast)) if rast < 1 else np.nan

    # --- BOOTSTRAP GUVEN ARALIGI (29 Agu 2026 denetiminde eklendi) ---
    # NEDEN: aylarca nokta tahminleri kiyaslayip "gol sistemi geciyor",
    # "dakika U21de onde" gibi hukumler verdik. Denetimde olculdu: bu
    # farklarin HICBIRI ayirt edilebilir degil. Ornek:
    #   SISTEM - gol = -5,0 puan, %95 GA [-13,4 , +4,1]
    # Ilk-N secimi 15-20 oyuncu oldugu icin varyans buyuk. GA olmadan
    # bu tablodan siralama hukmu CIKARILAMAZ.
    ci, farklar = _esli_bootstrap(df, tabanlar, sonuc, n)
    res = res.merge(ci, on="yontem", how="left")
    res.attrs["farklar"] = farklar
    # rastgele dagilimin ust kuyrugu: sistem sansla aciklanabilir mi?
    if oranlar:
        esik = float(np.quantile(oranlar, 0.95))
        res["sansi_asti"] = res.oran > esik
    return res.sort_values("oran", ascending=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20, help="lig basina ilk N")
    ap.add_argument("--min-minutes", type=int, default=450)
    ap.add_argument("--max-age", type=float, default=21.0)
    a = ap.parse_args()

    pd.set_option("display.width", 200)
    # IKI TAHMIN PENCERESI (29 Agu 2026, denetim §31 sonrasi)
    # Amac: degerlendirme orneklemini buyutup guven araliklarini daraltmak.
    #
    # AMA pencereler ESIT DEGIL - olculdu:
    #   2022 -> 2023/24 deger sonucu: 6.716 eslesmisin 5.251i olculebilir (%78)
    #   2023 -> 2024/25 deger sonucu: 3.225 eslesmisin   721i olculebilir (%22)
    # Ikincisi TM degerleme kapsaminin cokusu (§17.1) ve kalanlar sistematik
    # olarak daha degerli oyuncular. Deger sonucuna eklemek, bilerek
    # kacindigimiz secilim yanliligini geri getirir.
    #
    # Bu yuzden: TERFI sonucu iki pencereden havuzlanir (kendi verimiz,
    # TMe bagimli degil), DEGER sonucu yalnizca 2022de kalir.
    d22 = sonuclari_ekle(load(a.min_minutes, a.max_age, 2022))
    d23 = sonuclari_ekle(load(a.min_minutes, a.max_age, 2023))
    df = d22
    df_terfi = pd.concat([d22, d23], ignore_index=True)

    print("=" * 78)
    print(f"GERIYE DONUK TEST - 2022 tahmini, 2023/24 sonucu")
    print(f"Orneklem: U{int(a.max_age)}, >={a.min_minutes} dk, lig basina ilk {a.top}")
    print("=" * 78)
    print(f"\n2022 oyuncusu               : {len(df):,}")
    print(f"  piyasa degeri sonucu olcul.: {int(df.A_sicrama.notna().sum()):,}")
    print(f"  lig terfisi sonucu olculeb.: {int(df_terfi.B_terfi.notna().sum()):,} "
          f"(havuzlanmis, {int(df.B_terfi.notna().sum()):,} yalnizca 2022)")

    for kod, ad in [("A_sicrama", "A) PIYASA DEGERI SICRAMASI (>=2 kat ve >=1M EUR)"),
                    ("B_terfi", "B) LIG TERFISI (2024'te daha ust kademe)")]:
        kaynak = df_terfi if kod == "B_terfi" else df
        alt = kaynak.dropna(subset=[kod])
        if len(alt) < a.top * 2:
            print(f"\n--- {ad} ---\n  yetersiz ornek ({len(alt)}), atlandi")
            continue
        taban_oran = alt[kod].mean()
        print(f"\n{'-' * 78}\n{ad}")
        print(f"  orneklem {len(alt):,} oyuncu, {int(alt[kod].sum())} pozitif "
              f"(taban oran %{taban_oran*100:.1f})")
        r = degerlendir(alt, kod, a.top)
        g = r.copy()
        g["oran"] = (g.oran * 100).round(1)
        g["kat_rastgele"] = g.kat_rastgele.round(2)
        g["basari"] = g.basari.round(3)
        print()
        print(g.to_string(index=False))
        f = r.attrs.get("farklar")
        if f is not None and len(f):
            print()
            print("  SISTEM ile farklar (AUC, esli bootstrap %95 GA):")
            print("  " + f.to_string(index=False).replace(chr(10), chr(10) + "  "))

    print("\n" + "=" * 78)
    print("KABUL KRITERI (PLAN §8, 29 Agu 2026'da duzeltildi)")
    print("-" * 78)
    print("ESKI kriter 'rastgelenin 2 kati' idi ve HATALIYDI: ulasilabilir azami")
    print("kat = 1/taban_oran. Taban %13 iken 7,4x mumkun, taban %42 iken sadece")
    print("2,36x. Ayni esik bir kohortta kolay, otekinde neredeyse imkansizdi.")
    print("")
    print("YENI kriter - ucu birden saglanmali:")
    print("  1) SISTEM skoru rastgelenin %95 esigini gecmeli  (sansi_asti=True)")
    print("  2) SISTEM skoru TUM tabanlari gecmeli            (gol, dakika, piyasa)")
    print("  3) basari orani >= 0,15                          (olcege duyarsiz)")
    print("")
    print("     basari = (gozlenen - rastgele) / (1 - rastgele)")
    print("     0 = sans seviyesi, 1 = secilen herkes pozitif")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
