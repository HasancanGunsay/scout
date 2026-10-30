"""ADIM 4 - Lig gucu modeli (PLAN §5.2)

SORU: Brezilya Serie B'de 85. percentile ile Danimarka Superliga'da 85.
percentile ayni sey mi? Simdiye kadar cevap "bilmiyoruz"du ve arayuz her
coklu lig sorgusunda "ligler arasi kiyas gecersiz" uyarisi veriyordu.

NEDEN LIG ORTALAMALARI KULLANILAMAZ (olculdu, §21):
  - 'rating': saglayici lig ICINDE normalize ediyor. Allsvenskan 6.992 >
    Premier League 6.944 > La Liga 6.907. Cetvel olarak degersiz.
  - 'ikili mucadele kazanma %': lig icinde SIFIR TOPLAMLI. Ortalamasi her
    ligde matematiksel olarak ~0.50 (olculdu: 0.506-0.521). Ayni sey
    calim basarisi icin de gecerli.
  - Genel kural: lig ici goreli her metrigin ortalamasi insaat geregi
    sabittir. Hicbir lig ici toplam lig gucunu olcemez.

BU YUZDEN TEK GECERLI YOL: KOPRU OYUNCULAR.
Ayni oyuncu iki ligde. Ortalamalar sabit olsa da BIREYSEL degisim
bilgilidir: ust lige cikan oyuncunun kendi ikili mucadele kazanma orani
duser. Fark, iki ligin zorluk farkini olcer.

MODEL
    delta_i = beta(varis ligi) - beta(cikis ligi) + yas etkisi + gurultu

  En kucuk kareler, referans lig beta = 0. Yas kontrolu sart: 2022->2024
  iki yillik bosluk, 20 yasindaki gelisir 33 yasindaki geriler.

DURUSTLUK SINIRLARI
  - 2022 verisi yalnizca 5 ligde: graf YILDIZ seklinde. Varis ligleri
    birbirine yalnizca bu 5 kaynak uzerinden bagli.
  - Az koprulu ligler cok gurultulu. Asgari kopru sarti uygulanip
    altindakiler RAPOR EDILMEZ - tahmin uretmemek, kotu tahmin uretmekten iyi.
  - Bozuk ligler disarida (§21): sayimlari eksik olan lig, yapay olarak
    "zayif" gorunur ve modeli zehirler.

    python scripts/league_strength.py
    python scripts/league_strength.py --min-kopru 8
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

# Windows Gorev Zamanlayici altinda stdout cp1254'e dusuyor ve Hirvat/Polonya
# isimlerindeki 'c' harfi (ć) tum zinciri UnicodeEncodeError ile
# kiriyordu (19 Agu 2026). Cikti kodlamasini burada sabitliyoruz.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scout.kaynaklar import db_yolu  # noqa: E402
DB = db_yolu()  # SCOUT_DB ya da data/scout.duckdb (FAZ 9.5)

# §21'de olculen bozuk lig-sezonlar - modele GIRMEZ.
# Veikkausliiga: 17 metrik hic yayinlanmamis.
# Segunda Liga / Superettan: dakikalar tam ama sayimlar eksik (medyanin
# %15 ve %48'i) - yapay olarak zayif gorunurler.
# SECILIM YANLILIGI DUZELTMESI (19 Agu 2026, olculdu)
# Kopru yonteminin zayif noktasi: KIM tasindigi ile NEREYE tasindigi
# iliskili. Olculdu (997 kopru):
#     yukari cikan : n=526, 2022 dakikasi 1759, yas 23.2
#     asagi inen   : n=267, 2022 dakikasi 1447, yas 27.0
# Yani asagi inenler yasli ve kenarda kalmis oyuncular; metrikleri lig
# zorlugundan BAGIMSIZ olarak duser ve varis ligini yapay olarak
# "zor" gosterir. Belirti: Almanya 3. Liga ust siralarda cikiyordu.
#
# Alti duzeltme denendi ve onsel siralamayla uyuma gore OLCULDU:
#     mevcut (yas+yas^2)                 rho +0.551   3.Liga 4. sirada
#     yalnizca takim tasinmasi           rho +0.657   ama 4 lig kayboluyor
#     >=900 dk cikis + dakika kontrolu   rho +0.644   20 lig korunuyor, 3.Liga 7.
#     cift-esit agirlik                  rho +0.581
#     iki sezonda da >=900 dk            rho +0.580
# Secilen: cikista duzenli oyuncu sarti + cikis dakikasi kontrolu.
# Gerekce: yanliligin KANALINI (kenardaki oyuncu) dogrudan kapatiyor,
# lig kapsamini daraltmiyor ve anomaliyi en cok azaltan varyant.
MIN_DK_CIKIS = 900

BOZUK = {"Finland/Veikkausliiga", "Portugal/Segunda Liga", "Sweden/Superettan",
         "Ecuador/Liga Pro"}

# Cetvel metrikleri. Sectiklerimiz "rakip kalitesine duyarli" olanlar:
# daha iyi rakibe karsi bunlar DUSER. Stil metrikleri (pas hacmi) disarida -
# onlar takim taktigini olcer, lig zorlugunu degil.
CETVEL = {
    "duel_win_pct":   "ikili mucadele kazanma %",
    "dribble_pct":    "calim basari %",
    "shot_accuracy":  "isabet %",
    "np_ga_p90":      "penaltisiz gol+asist/90",
    "shots_p90":      "sut/90",
    "key_passes_p90": "anahtar pas/90",
}


def kopruleri_bul(min_dk: int) -> pd.DataFrame:
    con = duckdb.connect(str(DB), read_only=True)
    sec = ", ".join(f"f.{c}" for c in CETVEL)
    df = con.sql(f"""
      WITH s AS (
        SELECT f.player_id, f.season, f.league_id, f.league_name, f.country, f.pos_group,
               f.minutes, f.age_season_end, {sec}
        FROM player_features f
        WHERE f.minutes >= {min_dk} AND f.pos_group <> 'Goalkeeper'
      )
      SELECT a.player_id,
             a.league_id AS lig_a, a.country || '/' || a.league_name AS ad_a, a.minutes AS dk_a,
             a.age_season_end AS yas,
             b.league_id AS lig_b, b.country || '/' || b.league_name AS ad_b, b.minutes AS dk_b,
             {", ".join(f"a.{c} AS {c}_a, b.{c} AS {c}_b" for c in CETVEL)}
      FROM s a JOIN s b USING(player_id)
      WHERE a.season = 2022 AND b.season = 2024 AND a.league_id <> b.league_id
    """).df()
    con.close()
    df = df[~df.ad_a.isin(BOZUK) & ~df.ad_b.isin(BOZUK)]
    # Cikista duzenli oynamayanlar secilim yanliligi tasiyor - disarida
    df = df[df.dk_a >= MIN_DK_CIKIS]
    return df.reset_index(drop=True)


def fit_metrik(df: pd.DataFrame, metrik: str) -> tuple[pd.Series, float, int]:
    """Bir cetvel metrigi icin lig etkilerini kestir.

    Donen: (lig -> etki, R^2, kullanilan kopru sayisi)
    Etki pozitifse: o ligde bu metrik DAHA YUKSEK cikiyor = lig DAHA KOLAY.
    """
    s = df.dropna(subset=[f"{metrik}_a", f"{metrik}_b", "yas"]).copy()
    if len(s) < 30:
        return pd.Series(dtype=float), np.nan, len(s)

    s["delta"] = s[f"{metrik}_b"] - s[f"{metrik}_a"]
    ligler = sorted(set(s.ad_a) | set(s.ad_b))
    ref = s.ad_a.value_counts().idxmax()          # en cok kopruye sahip lig referans
    serbest = [x for x in ligler if x != ref]
    idx = {lg: i for i, lg in enumerate(serbest)}

    # X: varis ligi +1, cikis ligi -1 (referans sutunu yok)
    X = np.zeros((len(s), len(serbest) + 3))
    for r, (a, b) in enumerate(zip(s.ad_a, s.ad_b, strict=False)):
        if b in idx:
            X[r, idx[b]] += 1.0
        if a in idx:
            X[r, idx[a]] -= 1.0
    # kontroller: yas, yas^2 ve CIKIS DAKIKASI (secilim yanliligi vekili)
    X[:, -3] = s.yas - s.yas.mean()
    X[:, -2] = (s.yas - s.yas.mean()) ** 2
    ldk = np.log(s.dk_a.clip(lower=1).to_numpy(float))
    X[:, -1] = ldk - ldk.mean()

    y = s.delta.to_numpy(float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r2 = 1.0 - np.sum((y - X @ beta) ** 2) / max(np.sum((y - y.mean()) ** 2), 1e-12)

    etki = pd.Series({ref: 0.0} | {lg: float(beta[i]) for lg, i in idx.items()})
    return etki, float(r2), len(s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-dk", type=int, default=450)
    ap.add_argument("--yaz", action="store_true",
                    help="kapi gecilirse katsayilari league_strength tablosuna yaz")
    ap.add_argument("--min-kopru", type=int, default=6,
                    help="bu kadar koprusu olmayan lig RAPOR EDILMEZ")
    a = ap.parse_args()
    pd.set_option("display.width", 200)

    df = kopruleri_bul(a.min_dk)
    print("=" * 78)
    print("LIG GUCU MODELI - kopru oyuncu yontemi")
    print("=" * 78)
    print(f"\n{len(df)} kopru oyuncu (2022 ve 2024'te farkli ligde, >={a.min_dk} dk)")
    print(f"bozuk ligler disarida: {', '.join(sorted(BOZUK))}")

    kopru_sayisi = pd.concat([df.ad_a, df.ad_b]).value_counts()
    print(f"\n--- lig basina kopru sayisi ---")
    print(kopru_sayisi.to_string())

    yeterli = set(kopru_sayisi[kopru_sayisi >= a.min_kopru].index)
    print(f"\n{len(yeterli)}/{len(kopru_sayisi)} lig >={a.min_kopru} kopru esigini gecti")

    print("\n" + "-" * 78)
    print("CETVEL METRIKLERI - her biri ayri fit")
    print("-" * 78)
    sonuc, agirlik = {}, {}
    for m, ad in CETVEL.items():
        etki, r2, n = fit_metrik(df, m)
        if etki.empty:
            print(f"  {ad:28} yetersiz ornek ({n})")
            continue
        # metrigi kendi olcegine bol ki metrikler birlestirilebilsin
        olcek = df[f"{m}_a"].std()
        sonuc[ad] = (etki / olcek) if olcek and np.isfinite(olcek) else etki
        agirlik[ad] = max(r2, 0.0)
        print(f"  {ad:28} n={n:4}  R2={r2:+.3f}")

    if not sonuc:
        print("\nHicbir metrik fit edilemedi.")
        return 1

    tbl = pd.DataFrame(sonuc)
    tbl = tbl[tbl.index.isin(yeterli)]
    # R2 agirlikli ortalama: kotu uyan metrik az soz sahibi olsun
    w = pd.Series(agirlik).reindex(tbl.columns).fillna(0.0)
    tbl["BIRLESIK"] = (tbl * w).sum(axis=1) / max(w.sum(), 1e-12)
    tbl["kopru"] = kopru_sayisi.reindex(tbl.index)

    # Isaret cevir: etki pozitif = metrik yuksek = lig KOLAY.
    # 'zorluk' okunakli olsun diye tersine ceviriyoruz.
    tbl["ZORLUK"] = -tbl["BIRLESIK"]
    tbl = tbl.sort_values("ZORLUK", ascending=False)

    print("\n" + "=" * 78)
    print("LIG ZORLUK SIRALAMASI (yuksek = daha zor)")
    print("=" * 78)
    print("Referans lig 0.00. Deger, metriklerin standart sapmasi cinsinden.\n")
    print(tbl[["ZORLUK", "kopru"]].round(3).to_string())

    print("\n--- metrik bazinda (isaretler tutarli mi? tutarsizsa guvenme) ---")
    print((-tbl[[c for c in tbl.columns
                 if c not in ("BIRLESIK", "ZORLUK", "kopru")]]).round(2).to_string())

    kod = yuz_gecerliligi(tbl)

    # Katsayilari YALNIZCA kapiyi gectiyse yaz. Gecmediyse eski tablo da
    # silinir - yarim gecerli bir modelin sessizce kullanilmasi en kotusu.
    con = duckdb.connect(str(DB))
    if kod == 0 and a.yaz:
        cikti = (tbl[["ZORLUK", "kopru"]].reset_index()
                 .rename(columns={"index": "lig", "ZORLUK": "zorluk"}))
        cikti["olculdu"] = pd.Timestamp.now().strftime("%Y-%m-%d")
        con.execute("CREATE OR REPLACE TABLE league_strength AS SELECT * FROM cikti")
        print("")
        print(f"[yazildi] league_strength tablosu - {len(cikti)} lig")
    elif a.yaz:
        con.execute("DROP TABLE IF EXISTS league_strength")
        print("")
        print("[silindi] kapi gecilmedigi icin league_strength tablosu kaldirildi")
    con.close()
    return kod


# Kaba onsel siralama (dusuk sayi = daha guclu). backtest.py'deki TIER ile
# ayni scout yargisi. Model bunu YENIDEN URETEMIYORSA kendi kestirimine
# guvenilmez - onseli dogrulatmak icin degil, SANITY icin kullaniliyor.
ONSEL = {
    "England/Premier League": 1, "Spain/La Liga": 1, "Germany/Bundesliga": 1,
    "France/Ligue 1": 1, "Italy/Serie A": 1,
    "Netherlands/Eredivisie": 2, "Portugal/Primeira Liga": 2,
    "Belgium/Jupiler Pro League": 2, "Brazil/Serie A": 2,
    "France/Ligue 2": 3, "Italy/Serie B": 3, "Brazil/Serie B": 3,
    "Argentina/Liga Profesional Argentina": 3, "Germany/3. Liga": 3,
    "Norway/Eliteserien": 3, "Sweden/Allsvenskan": 3, "Denmark/Superliga": 3,
    "Netherlands/Eerste Divisie": 4, "Belgium/Challenger Pro League": 4,
    "Colombia/Primera A": 4,
}
MIN_UYUM = 0.60   # Spearman; altindaysa model yayina ALINMAZ


def yuz_gecerliligi(tbl: pd.DataFrame) -> int:
    """Model kaba futbol gercekligini yeniden uretebiliyor mu?

    Ligler ULKE/AD bicimiyle anahtarlaniyor. Yalnizca 'league_name'
    kullanmak Brezilya Serie A ile Italya Serie A'yi (ve iki Serie B'yi)
    TEK LIG sayiyordu - ustelik 339 kopruyle referans lig oydu.
    """
    print("\n" + "=" * 78)
    print("YUZ GECERLILIGI KONTROLU")
    print("=" * 78)

    ortak = [i for i in tbl.index if i in ONSEL]
    if len(ortak) < 5:
        print(f"KARAR: YAYINA ALINMAZ - onselle ortak lig {len(ortak)} < 5.")
        print("Model, kiyaslanabilecek kadar lig kestiremedi.")
        return 1

    s = tbl.loc[ortak, "ZORLUK"]
    onsel_sira = pd.Series({i: -ONSEL[i] for i in ortak})   # yuksek = guclu
    rho = s.corr(onsel_sira, method="spearman")
    print(f"onselle ortak lig : {len(ortak)}")
    print(f"Spearman uyumu    : {rho:+.3f}   (esik {MIN_UYUM})")

    # Anahtarlar ULKE/AD bicimde; duz ad aramak her zaman 'eksik' derdi.
    eksik = [lg for lg in ("England/Premier League", "Spain/La Liga",
                           "Germany/Bundesliga")
             if lg not in tbl.index]
    if eksik:
        print(f"UYARI: referans ligler tabloda yok (yetersiz kopru): {eksik}")

    if not np.isfinite(rho) or rho < MIN_UYUM or eksik:
        print("")
        print("KARAR: **YAYINA ALINMAZ**")
        print("Siralamanin iki ucu dogru (Premier League en zor, Eerste")
        print("Divisie en kolay) ama genel uyum esigin altinda.")
        print("")
        print("BILINEN SAPMA KAYNAGI - kopru yonteminin secilim yanliligi:")
        print("  Bir lige DUSEN oyuncu tipik olarak gerileyen/kenarda kalan")
        print("  oyuncudur; metrikleri lig zorlugundan bagimsiz duser. Ust")
        print("  lige CIKAN ise secilmis en iyilerdir. Iki yon simetrik degil.")
        print("  Belirti: Almanya 3. Liga ust siralarda cikiyor.")
        print("")
        print("Cozum yonu: (a) 2023 sezonu -> ayni oyuncunun coklu gecisi,")
        print("(b) transfer yonune gore agirliklandirma, (c) yas x dakika")
        print("etkilesimi. 2023 geldikce tekrar calistir.")
        return 1

    print("\nKARAR: yayina alinabilir.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
