"""FAZ 2: siralama modelini egit ve UC TABANLA karsilastir.

    python scripts/train_model.py                # yalnizca EGITIM + LOLO CV
    python scripts/train_model.py --test         # TUTULAN pencereyi ac (2024)

SIZINTI DISIPLINI
  --test bayragi olmadan 2024 verisi HIC okunmaz. Model secimi, ozellik
  secimi, hiperparametre - hepsi 2022+2023 icinde lig-disarida-birak
  (leave-one-league-out) CV ile yapilir. Test penceresi bir kez acilir.

YENILMESI GEREKEN UC TABAN (ucunu birden yenmezse model REDDEDILIR)
  A  mevcut uzman agirlikli skor  - yeni, eskisinden iyi olmali
  B  piyasa degeri                - piyasayi yenmek projenin tek iddiasi
  C  dakika + yas                 - en aptal makul model; bunu yenemeyen
                                    model hicbir sey ogrenmemistir

C ozellikle kasitli. §27'de "yukselis sinyali" guclu sanilmis, olculunce
mevcut seviyenin gerisinde kalmisti. En basit rakip bastan tanimlaniyor.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout.model.ranker import (esli_bootstrap, fark_ga, hedef,  # noqa: E402
                                lig_ici_auc)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = ROOT / "data" / "scout.duckdb"
EGITIM_SEZONLARI = (2022, 2023)
TEST_SEZONU = 2024

# Tahmin aninda BILINEBILIR ozellikler. Sezon sonunda elimizde olmayan
# hicbir sey giremez - sonuc penceresi sezon bitisinden SONRA basliyor.
OZELLIKLER = [
    "score",              # uzman agirlikli rol skoru (kendi kohortunda)
    "score_age",          # yasitlarina gore
    "age_season_end",
    "minutes",
    "minutes_pct",        # ligdeki dakika payi
    "minutes_agepct",     # yasitlarina gore dakika payi
    "rating_pct",
    "starts_pct",
    "log_deger",          # piyasa degeri (sezon sonu itibariyla)
    "deger_var",          # degerlemesi VAR MI - "bilinmiyor" != "ucuz"
]

# Tabanlar
TABAN_A = "score"
TABAN_B = "log_deger"
TABAN_C = "basit"        # dakika + yas ile egitilmis lojistik

# IKINCIL, HUKMU DEGISTIRMEZ: piyasa degeri VERILMEDEN egitilmis model.
# Projenin asil sorusu bu - "piyasanin gormedigini goruyor muyuz". Kabul
# kriteri yine tam modele gore; bu sutun yalnizca BILGI icin raporlanir.
# Test sonucuna gore bu iki modelden birini SECMEK sizinti olurdu; secim
# simdi yapiliyor: BIRINCIL MODEL TAM MODELDIR.
OZELLIKLER_SAF = [k for k in OZELLIKLER if k not in ("log_deger", "deger_var")]


def veri_yukle(con, sezonlar) -> pd.DataFrame:
    q = f"""
        SELECT o.player_id, o.league_id, o.season, o.player_name,
               o.league_name, o.country, o.kapsam, o.kademe,
               o.age_season_end, o.minutes, o.score,
               f.score_age, f.minutes_pct, f.minutes_agepct,
               f.rating_pct, f.starts_pct, f.pos_group
        FROM player_outcome o
        JOIN (SELECT s.player_id, s.league_id, s.season, s.score_age,
                     ft.minutes_pct, ft.minutes_agepct, ft.rating_pct,
                     ft.starts_pct, ft.pos_group
              FROM player_natural_role s
              JOIN player_features ft USING (player_id, league_id, season)) f
          USING (player_id, league_id, season)
        WHERE o.season IN ({','.join(str(s) for s in sezonlar)})
          AND o.age_season_end < 23 AND o.minutes >= 450
          AND o.score IS NOT NULL
    """
    df = con.sql(q).df()

    # lig gucu (§22-23) - skora UYGULANMIYOR ama ozellik olarak verilebilir
    try:
        lg = con.sql("SELECT lig, zorluk FROM league_strength").df()
        ad = con.sql("""SELECT DISTINCT league_id, league_name || ' (' || country || ')' lig
                        FROM player_features""").df()
        lg = lg.merge(ad, on="lig", how="inner")
        df = df.merge(lg[["league_id", "zorluk"]].rename(
            columns={"zorluk": "lig_gucu"}), on="league_id", how="left")
    except Exception:
        df["lig_gucu"] = np.nan
    if "lig_gucu" not in df.columns:
        df["lig_gucu"] = np.nan
    df["lig_gucu"] = df["lig_gucu"].fillna(df["lig_gucu"].median())

    # Piyasa degeri: sezon BITISINDEN onceki son degerleme (sizinti yok)
    deger = con.sql("""
        SELECT o.player_id, o.league_id, o.season,
               max_by(v.market_value_in_eur, v.date) AS deger
        FROM player_outcome o
        JOIN player_links l USING (player_id)
        JOIN tm_player_valuations v ON v.player_id = l.tm_id
        -- SIZINTI EMNIYETI: sezon bitisi Avrupa'da 15 Haziran olarak
        -- tanimli, ama ligler ~25 Mayis'ta bitiyor ve arada transfer
        -- penceresi aciliyor. 15 Haziran'daki bir degerleme, tahmin
        -- etmeye calistigimiz transferi ZATEN yansitiyor olabilir.
        -- Bir ay geri cekiliyor.
        WHERE v.date <= o.sezon_bitis - INTERVAL 1 MONTH
        GROUP BY 1,2,3
    """).df()
    df = df.merge(deger, on=["player_id", "league_id", "season"], how="left")

    # EKSIK DEGERI SIFIR SAYMA (30 Agu 2026, kullanicinin isaretiyle bulundu).
    # Olculdu: satirlarin %31,8'inde degerleme yok ve eksiklik SISTEMATIK -
    #   kapsam 'tam'          -> %0,3-7,7 eksik
    #   kapsam 'sicrama_only' -> %38,6-56,0 eksik
    # Yani tam da en cok onemsedigimiz dusuk gorunurluklu liglerde eksik.
    # log1p(0) yazmak modele "bu Brezilya Serie B cocugu 0 EUR eder" demekti
    # ve katsayisi +2,67 oldugu icin hepsini dibe itiyordu. Veikkausliiga'nin
    # eksik metrigi 0 saymasiyla (§21) ayni hata.
    #
    # Dogrusu: "bilinmiyor" ile "ucuz" AYRI seyler.
    #   deger_var  -> bilgi var mi (modelin ogrenebilecegi bir sinyal;
    #                 degerlemesi olmamak baslibasina gorunurluk isareti)
    #   log_deger  -> eksikse kendi lig-sezonunun MEDYANI ile doldurulur,
    #                 yani "bu ligde ortalama bir oyuncu" varsayimi
    df["deger_var"] = df.deger.notna().astype(int)
    df["log_deger"] = np.log1p(df.deger)
    med = df.groupby(["league_id", "season"]).log_deger.transform("median")
    df["log_deger"] = df.log_deger.fillna(med).fillna(df.log_deger.median())

    df["y"] = hedef(df.kademe)
    return df


_UYARILDI: set[str] = set()


def _hazirla(df: pd.DataFrame, kolonlar: list[str], ref: pd.DataFrame | None = None):
    """Eksikleri EGITIM medyaniyla doldur.

    ref: medyanin hesaplanacagi EGITIM kumesi. Verilmezse df'in kendisi.

    HATA (30 Eyl 2026'da bulundu): onceki surum eksikleri df'in KENDI
    medyaniyla dolduruyordu. Test kumesi icin bu, test dagilimindan bilgi
    sizdirir (kucuk ama gercek) ve daha kotusu TEK SATIRLIK tahminde
    medyan o satirin kendisi olur: eksik deger NaN kalir -> 0.0'a duser.
    score_age icin ham 0 cok uc bir degerdir. Toplu degerlendirmede etkisi
    ihmal edilebilir; tek oyunculuk siralamada (Scout dosyasi) ciddi olurdu.
    """
    X = df[kolonlar].apply(pd.to_numeric, errors="coerce")
    R = X if ref is None else ref[kolonlar].apply(pd.to_numeric, errors="coerce")
    for c in [c for c in kolonlar if R[c].isna().all()]:
        if c not in _UYARILDI:
            print(f"  ! ozellik EGITIMDE TAMAMEN BOS, katkisi olmayacak: {c}")
            _UYARILDI.add(c)
    med = R.median().fillna(0.0)
    return X.fillna(med).to_numpy(float)


def egit(Xtr, ytr, Xte, C=1.0):
    """L2 duzenlilestirilmis lojistik. Standartlastirma iceride."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    m = make_pipeline(StandardScaler(),
                      LogisticRegression(C=C, max_iter=2000))
    m.fit(Xtr, ytr)
    return m, m.predict_proba(Xte)[:, 1]


def lolo_cv(df: pd.DataFrame, kolonlar: list[str], C: float) -> pd.Series:
    """Lig-disarida-birak: her lig bir kez test, hep digerleriyle egitilir.

    Sezon bazli bolmek yetmez - ayni ligin baska sezonu modele o ligin
    tuhafliklarini ogretir. Genelleme sorusunun dogru kurulusu 'hic
    gormedigi ligde ne yapiyor'.
    """
    tah = pd.Series(np.nan, index=df.index)
    for lig in df.league_id.unique():
        te = df.league_id == lig
        tr = ~te
        if ytr_yetersiz(df.loc[tr, "y"]) or te.sum() < 10:
            continue
        _, p = egit(_hazirla(df[tr], kolonlar), df.loc[tr, "y"].to_numpy(),
                    _hazirla(df[te], kolonlar, ref=df[tr]), C)
        tah[te] = p
    return tah


def ytr_yetersiz(y: pd.Series) -> bool:
    return y.nunique() < 2 or y.sum() < 20


def rapor(df: pd.DataFrame, kolonlar: list[str], baslik: str) -> pd.DataFrame:
    print(f"\n{'=' * 70}\n{baslik}\n{'=' * 70}")
    for k in kolonlar:
        print(f"  lig-ici AUC  {k:12s} = {lig_ici_auc(df, k):.3f}")
    bs = esli_bootstrap(df, kolonlar)
    print("\n  --- MODEL - TABAN farklari (esli, oyuncu bazli bootstrap) ---")
    satir = []
    for taban in (TABAN_A, TABAN_B, TABAN_C):
        if taban not in kolonlar:
            continue
        o, lo, hi = fark_ga(bs, "model", taban)
        gecti = lo > 0
        print(f"  model - {taban:12s} = {o:+.3f}  %95 GA [{lo:+.3f}, {hi:+.3f}]"
              f"   {'GECTI' if gecti else 'GECMEDI'}")
        satir.append(dict(taban=taban, fark=o, lo=lo, hi=hi, gecti=gecti))
    return pd.DataFrame(satir)


def _ikincil(df: pd.DataFrame) -> None:
    """Piyasa degeri VERILMEDEN egitilmis model. Hukmu degistirmez."""
    bs = esli_bootstrap(df, ["model_saf", TABAN_B], B=400)
    o, lo, hi = fark_ga(bs, "model_saf", TABAN_B)
    print(f"\n  [ikincil, hukum disi] piyasa degeri VERILMEDEN:")
    print(f"    lig-ici AUC model_saf = {lig_ici_auc(df, 'model_saf'):.3f}")
    print(f"    model_saf - piyasa    = {o:+.3f}  %95 GA [{lo:+.3f}, {hi:+.3f}]")


def kaydet(con, C: float) -> None:
    """Uretim modeli: TUM pencerelerle egit, tahminleri DB'ye yaz.

    DIKKAT: bu model 2024'u de gormus durumda. Hicbir BASARIM IDDIASI
    buna dayanmaz - iddia yalnizca tutulan pencere sonucundan gelir.
    Burada amac uretimde mumkun olan en cok veriyle calismak.
    """
    import joblib

    hepsi = pd.concat([veri_yukle(con, EGITIM_SEZONLARI),
                       veri_yukle(con, (TEST_SEZONU,))], ignore_index=True)
    m, p = egit(_hazirla(hepsi, OZELLIKLER), hepsi.y.to_numpy(),
                _hazirla(hepsi, OZELLIKLER), C)
    hepsi["model_olasilik"] = p
    hepsi["model_skor"] = (100 * pd.Series(p).rank(pct=True)).round(1)

    yol = ROOT / "data" / "model_ranker.joblib"
    joblib.dump({"model": m, "ozellikler": OZELLIKLER,
                 "medyan": hepsi[OZELLIKLER].apply(pd.to_numeric, errors="coerce")
                 .median().fillna(0.0).to_dict()}, yol)

    kol = ["player_id", "league_id", "season", "model_olasilik", "model_skor"]
    tab = hepsi[kol]
    # Ana baglanti read_only acildi; yazmak icin onu kapatip yeniden aciyoruz
    # (DuckDB ayni dosyaya farkli yapilandirmayla ikinci baglanti kabul etmiyor).
    con.close()
    con2 = duckdb.connect(str(DB))
    con2.register("tab", tab)
    con2.execute("CREATE OR REPLACE TABLE player_model_score AS SELECT * FROM tab")
    con2.close()
    print(f"[kaydet] {len(tab):,} tahmin -> player_model_score")
    print(f"[kaydet] model -> {yol.name}\n")


def kayan_baslangic(con, C: float) -> None:
    """BAGIMSIZ ikinci geri test: 2022 ile egit, 2023'u sirala.

    Ana kurulum (2022+2023 -> 2024) tek bir test penceresine dayaniyor. Bu,
    ikinci ve tamamen ayri bir pencere: model 2023'u ve 2024'u HIC gormedi.
    Sonuc iki pencerede tutarliysa guven artar; tutarsizsa tek pencereye
    fazla guvenmisiz demektir.

    NOT: 2023 ana kurulumda EGITIM verisi; bu test ana modelin testi degil,
    ayri bir sinama. Model secmek icin kullanilmaz.
    """
    tr = veri_yukle(con, (2022,))
    te = veri_yukle(con, (2023,))
    print(f"[kayan] egitim 2022: {len(tr):,} · test 2023: {len(te):,} "
          f"(olumlu %{100 * te.y.mean():.1f})")
    for ad, kol in (("model", OZELLIKLER), ("basit", ["minutes",
                    "minutes_agepct", "age_season_end"]),
                    ("model_saf", OZELLIKLER_SAF)):
        _, te[ad] = egit(_hazirla(tr, kol), tr.y.to_numpy(),
                         _hazirla(te, kol, ref=tr), C)
    kol = ["model", TABAN_A, TABAN_B, TABAN_C]
    rapor(te, kol, "KAYAN BASLANGIC (2022 -> 2023) · ayri pencere")
    _ikincil(te)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true",
                    help="TUTULAN 2024 penceresini ac (bir kez!)")
    ap.add_argument("--C", type=float, default=1.0)
    ap.add_argument("--kaydet-yalniz", action="store_true",
                    help="test penceresini ACMADAN uretim modelini kaydet "
                         "(model spesifikasyonu degismediginde: yalniz "
                         "eksik-deger/altyapi duzeltmesi sonrasi)")
    ap.add_argument("--kayan", action="store_true",
                    help="kayan baslangic: 2022 ile egit -> 2023 sirala")
    ap.add_argument("--kaydet", action="store_true",
                    help="modeli TUM sezonlarla egit, tahminleri DB'ye yaz")
    a = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    if a.kaydet_yalniz:
        # Spesifikasyon degismedi; CV ve kayan dogrulandi. Tutulan 2024
        # penceresi ACILMIYOR - bu bir model secimi degil, kayit adimi.
        kaydet(con, a.C)      # icinde con'u kapatiyor
        return 0
    if a.kayan:
        kayan_baslangic(con, a.C)
        con.close()
        return 0
    tr = veri_yukle(con, EGITIM_SEZONLARI)
    print(f"[egitim] {len(tr):,} satir · olumlu {int(tr.y.sum()):,} "
          f"(%{100 * tr.y.mean():.1f}) · {tr.league_id.nunique()} lig")

    kolonlar = ["model", TABAN_A, TABAN_B, TABAN_C]

    # C tabani: yalnizca dakika + yas
    tr["basit"] = lolo_cv(tr, ["minutes", "minutes_agepct", "age_season_end"], a.C)
    # aday model
    tr["model"] = lolo_cv(tr, OZELLIKLER, a.C)
    tr["model_saf"] = lolo_cv(tr, OZELLIKLER_SAF, a.C)   # ikincil

    trc = tr.dropna(subset=["model", "basit", "model_saf"])
    rapor(trc, kolonlar, "EGITIM PENCERESI (2022+2023) · lig-disarida-birak CV")
    _ikincil(trc)

    # Katsayilar: FAZ 4'teki scout dosyasi bunlara dayanacak, okunabilir olmali
    m, _ = egit(_hazirla(tr, OZELLIKLER), tr.y.to_numpy(),
                _hazirla(tr, OZELLIKLER), a.C)
    kat = pd.Series(m[-1].coef_[0], index=OZELLIKLER).sort_values(key=abs,
                                                                 ascending=False)
    print("\n  --- katsayilar (standartlastirilmis) ---")
    for k, v in kat.items():
        print(f"    {k:16s} {v:+.3f}")

    if not a.test:
        print("\n[!] Test penceresi ACILMADI. Model kesinlestikten sonra:")
        print("    python scripts/train_model.py --test\n")
        con.close()
        return 0

    # ---------------- TUTULAN PENCERE ----------------
    te = veri_yukle(con, (TEST_SEZONU,))
    print(f"\n[test]   {len(te):,} satir · olumlu {int(te.y.sum()):,} "
          f"(%{100 * te.y.mean():.1f}) · {te.league_id.nunique()} lig")

    _, te["basit"] = egit(_hazirla(tr, ["minutes", "minutes_agepct", "age_season_end"]),
                          tr.y.to_numpy(),
                          _hazirla(te, ["minutes", "minutes_agepct", "age_season_end"], ref=tr), a.C)
    _, te["model"] = egit(_hazirla(tr, OZELLIKLER), tr.y.to_numpy(),
                          _hazirla(te, OZELLIKLER, ref=tr), a.C)

    _, te["model_saf"] = egit(_hazirla(tr, OZELLIKLER_SAF), tr.y.to_numpy(),
                              _hazirla(te, OZELLIKLER_SAF, ref=tr), a.C)
    son = rapor(te, kolonlar, f"TUTULAN PENCERE ({TEST_SEZONU}) · hic gorulmedi")
    _ikincil(te)

    print("\n" + "=" * 70)
    if len(son) and son.gecti.all():
        print("HUKUM: model UC TABANI DA gecti - benimsenebilir.")
    else:
        kalan = son[~son.gecti].taban.tolist() if len(son) else ["hepsi"]
        print(f"HUKUM: model REDDEDILDI - su tabani gecemedi: {kalan}")
        print("Uzman agirliklariyla devam edilir. Model egitmis olmak icin")
        print("model kullanilmayacak.")
    print("=" * 70 + "\n")

    if a.kaydet:
        if not (len(son) and son.gecti.all()):
            print("[!] Model reddedildi - kaydedilmiyor.\n")
            con.close()
            return 1
        kaydet(con, a.C)      # icinde con'u kapatiyor
        return 0
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
