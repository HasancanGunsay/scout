"""Sistem denetimi - iddialari FIILEN sina.

Her kontrol bir iddiayi test eder ve GECTI / KALDI / UYARI dondurur.
Amac hos gorunmek degil, kirik olani bulmak.

    python scripts/audit.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scout.kaynaklar import db_yolu  # noqa: E402

from scout.scoring import engine as eng  # noqa: E402

# Windows Gorev Zamanlayici altinda stdout cp1254'e dusuyor ve Hirvat/Polonya
# isimlerindeki 'c' harfi (ć) tum zinciri UnicodeEncodeError ile
# kiriyordu (19 Agu 2026). Cikti kodlamasini burada sabitliyoruz.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DB = db_yolu()  # SCOUT_DB ya da data/scout.duckdb (FAZ 9.5)
ROLES = ROOT / "config" / "roles.yaml"

RESULTS: list[tuple[str, str, str]] = []


def check(name: str, ok: bool | None, detail: str = "") -> None:
    RESULTS.append((("GECTI" if ok else "KALDI") if ok is not None else "UYARI",
                    name, detail))


def main() -> int:
    con = duckdb.connect(str(DB), read_only=True)
    q = lambda s: con.sql(s).df()  # noqa: E731

    tables = {r[0] for r in con.sql(
        "SELECT table_name FROM information_schema.tables").fetchall()}

    # ---------------------------------------------------------- 1. tablolar
    for t in ["player_season", "player_features", "player_scores",
              "player_natural_role", "player_links", "player_meta"]:
        check(f"tablo mevcut: {t}", t in tables)

    f = q("SELECT * FROM player_features")
    s = q("SELECT * FROM player_scores")

    # ---------------------------------------------------------- 2. butunluk
    check("her oyuncu-lig-sezon tekil",
          f.duplicated(["player_id", "league_id", "season"]).sum() == 0,
          f"{f.duplicated(['player_id','league_id','season']).sum()} yinelenen")

    check("dakika <= mac*120 (imkansiz deger yok)",
          (f.minutes <= f.apps * 120).all(),
          f"{(f.minutes > f.apps*120).sum()} ihlal")

    check("ilk11 <= mac", (f.starts <= f.apps).all(),
          f"{(f.starts > f.apps).sum()} ihlal")

    check("dogum tarihi eksik yok", f.birth_date.isna().sum() == 0,
          f"{f.birth_date.isna().sum()} eksik")

    check("rating 3-10 araliginda",
          bool(f.rating.dropna().between(3, 10).all()),
          f"aralik {f.rating.min():.2f}-{f.rating.max():.2f}")

    # 'Ã' veya 'Â' iceriyor olmak TEK BASINA bozukluk degil: 'Ângelo' (pt) ve
    # 'M. El Âdfaoui' (ar) gecerli isimler. Eski kontrol bunlari bozuk sayip
    # yanlis alarm veriyordu. Dogru olcut: build_db'nin duzelticisi bu ismi
    # HALA degistirebiliyor mu? Degistirebiliyorsa gercekten cift kodlanmistir.
    def _cift_kodlanmis(s: object) -> bool:
        if not isinstance(s, str) or not any(c in s for c in ("Ã", "Â")):
            return False
        try:
            return s.encode("latin-1").decode("utf-8") != s
        except (UnicodeEncodeError, UnicodeDecodeError):
            return False

    bozuk = f.player_name.map(_cift_kodlanmis)
    check("bozuk karakter yok", not bool(bozuk.any()),
          f"{int(bozuk.sum())} isim cift kodlanmis" if bozuk.any() else "")

    # Kohortsuz kalan oyuncu = sessizce skorsuz kalan oyuncu.
    # 'Forward' hatasi tam olarak buydu (16 oyuncu, biri tam sezon).
    unk = f[f.pos_group == "Unknown"]
    check("kohortsuz oyuncu yok (mevki atanabildi)", len(unk) == 0,
          f"{len(unk)} oyuncu, {int(unk.minutes.sum())} dakika skorsuz"
          if len(unk) else "")

    # ---------------------------------------------------------- 3. metrikler
    p90 = [c for c in f.columns if c.endswith("_p90") and not c.endswith("_sh_p90")]
    neg = {c: int((f[c] < 0).sum()) for c in p90 if (f[c] < 0).any()}
    check("negatif per-90 yok", not neg, str(neg))

    sh_cols = [c for c in f.columns if c.endswith("_sh")]
    check("shrinkage sutunlari uretildi", len(sh_cols) >= 20, f"{len(sh_cols)} sutun")

    w_cols = [c for c in f.columns if c.endswith("_p90_w")]
    bad_w = {c: float(f[c].max()) for c in w_cols if f[c].max() > 1.001}
    check("shrinkage agirliklari 0-1 araliginda", not bad_w, str(bad_w))

    pct_cols = [c for c in f.columns if c.endswith("_sh_pct")]
    rng = f[pct_cols].stack()
    check("percentile 0-100 araliginda",
          bool(rng.min() >= 0 and rng.max() <= 100),
          f"{rng.min():.1f}-{rng.max():.1f}")

    # ---------------------------------------------------------- 4. kohortlar
    cs = (f.groupby(["league_id", "season", "role_cohort"]).size()
          .reset_index(name="n"))
    small = cs[cs.n < 12]
    check("tum kohortlar >=12 kisi", len(small) == 0,
          f"{len(small)} kucuk kohort: "
          + ", ".join(f"{r.role_cohort}({r.n})" for r in small.itertuples())[:120])

    # kucuk kohortlarda percentile URETILMEMELI
    if len(small):
        key = small[["league_id", "season", "role_cohort"]].apply(tuple, axis=1)
        fk = f[["league_id", "season", "role_cohort"]].apply(tuple, axis=1)
        sub = f[fk.isin(set(key))]
        leaked = int(sub[pct_cols].notna().sum().sum())
        check("kucuk kohortta percentile uretilmemis", leaked == 0,
              f"{leaked} deger sizmis")

    # ---------------------------------------------------------- 5. skorlar
    check("skor 0-100 araliginda",
          bool(s.score.dropna().between(0, 100).all()),
          f"{s.score.min():.1f}-{s.score.max():.1f}")

    check("her oyuncunun en az bir rol skoru var",
          s.player_id.nunique() >= f.player_id.nunique() * 0.95,
          f"{s.player_id.nunique()}/{f.player_id.nunique()}")

    # katki toplami skora esit olmali (aciklanabilirlik dogru mu?)
    smp = s.dropna(subset=["contrib"]).head(200)
    diffs = []
    for _, r in smp.iterrows():
        try:
            c = json.loads(r.contrib)
        except (json.JSONDecodeError, TypeError):
            continue
        if c:
            diffs.append(abs(sum(c.values()) - r.score))
    check("waterfall katkilari skora toplaniyor",
          bool(diffs) and max(diffs) < 0.6,
          f"azami sapma {max(diffs):.3f}" if diffs else "ornek yok")

    # rol sablonu kume kisitina uyuyor mu?
    if "role_cluster" in f.columns:
        m = s.merge(f[["player_id", "league_id", "season", "role_cluster"]],
                    on=["player_id", "league_id", "season"], how="left")
        cb = m[m.role.isin(["cb_ball_playing", "cb_stopper"])]
        leak = int((cb.role_cluster == "Defender::Bek").sum())
        check("stoper sablonu bekleri puanlamiyor", leak == 0, f"{leak} sizinti")

    # --- sablon agirliklarinin KARSILIGI var mi? --------------------------
    # Bu kontrol olmadigi icin iki hata haftalarca sessizce yasadi (§16):
    #   - 'rating' 13 sablonda agirlikliydi ama 'rating_pct' hic uretilmiyordu
    #   - kaleci sablonu agirliginin %82'si karsiliksizdi (saves, goals_conceded)
    # engine.py eksik sutunu sessizce ATLAR ve kalan agirligi yeniden
    # normalize eder; skor makul gorunur, oysa metrik hic sayilmamistir.
    roles, _ = eng.load_roles(ROLES)
    fcols = set(f.columns)
    eksik: dict[str, list[str]] = {}
    for role in roles:
        for metric, w in role.weights.items():
            if w == 0:
                continue
            for age_band in (False, True):
                col = eng.column_for(metric, age_band=age_band)
                if col not in fcols:
                    eksik.setdefault(role.key, []).append(col)
    kayip_agirlik = sum(
        sum(w for m, w in r.weights.items()
            if eng.column_for(m) not in fcols) / (sum(abs(v) for v in r.weights.values()) or 1)
        for r in roles
    ) / max(len(roles), 1)
    check("her sablon agirliginin sutun karsiligi var",
          not eksik,
          f"{len(eksik)} sablonda eksik, ortalama %{kayip_agirlik*100:.0f} agirlik karsiliksiz: "
          + "; ".join(f"{k}: {sorted(set(v))}" for k, v in list(eksik.items())[:3])
          if eksik else "")

    # --- lig-sezon bazinda metrik yayinlanmis mi? -------------------------
    # Veikkausliiga 2024'te 17 metrik HIC yayinlanmamisti; null->0 donusumu
    # bunlari sifira cevirince 324 oyuncuya var olmayan veriden skor
    # uretildi ve ortalamasi 50,5 ile gayet normal gorundu (§21).
    # build_db 'league_quality' tablosunu uretir - TEK DOGRULUK KAYNAGI.
    # Denetim mantigi kendisi yeniden hesaplamiyor; ayni kod uc yerde
    # yasarsa zamanla birbirinden ayrisir.
    if "league_quality" in tables:
        lq = q("SELECT * FROM league_quality")
        eks = lq[lq.kalite == "metrik_eksik"]
        check("her lig-sezonda temel metrikler yayinlanmis",
              len(eks) == 0,
              "; ".join(f"{r.league_name} {r.season}: {r.eksik_metrikler}"
                        for r in eks.itertuples()) if len(eks) else "")
        mac = lq[lq.kalite == "mac_eksik"]
        check("sayimlar dakikayla tutarli (eksik mac yok)",
              len(mac) == 0,
              ", ".join(f"{r.league_name} {r.season}: medyanin "
                        f"%{r.sayim_orani*100:.0f}'i"
                        for r in mac.itertuples()) if len(mac) else "")
    else:
        check("league_quality tablosu uretilmis", None,
              "build_db.py calistirilmali")

    # --- ters cevirme tam olarak BIR KEZ uygulanmis mi? -------------------
    # percentile.invert sutunu cevirip '<anahtar>_inverted' isaretini birakir;
    # engine bu isareti gorunce kendisi cevirmez. Isaret yoksa engine ikinci
    # kez cevirir ve "cok faul yapan iyidir" sonucu cikar - gercekten oldu.
    invert_keys = {m for r in roles for m in r.invert}
    isaretsiz = sorted(k for k in invert_keys if f"{k}_inverted" not in fcols)
    check("ters cevrilen metrikler isaretlenmis (cift cevirme yok)",
          not isaretsiz,
          f"isaretsiz: {isaretsiz}" if isaretsiz else f"{len(invert_keys)} metrik")

    # ---------------------------------------------------------- 6. eslestirme
    if "player_links" in tables:
        li = q("SELECT * FROM player_links")
        acc = li[li.confidence.isin(["A", "B", "M"])]
        check("kabul edilen eslesmelerde isim skoru >=85",
              bool((acc.name_score.dropna() >= 85).all()),
              f"asgari {acc.name_score.min():.0f}" if len(acc) else "-")
        check("bir TM kaydina tek oyuncu bagli",
              acc.tm_id.dropna().duplicated().sum() == 0,
              f"{acc.tm_id.dropna().duplicated().sum()} cakisma")
        # §60: reddedilen/belirsiz aday kimlik olarak KULLANILMAMALI
        red = li[~li.confidence.isin(["A", "B", "M"])]
        check("kabul disi eslesmede tm_id bos (aday ayri sutunda)",
              int(red.tm_id.notna().sum()) == 0,
              f"{int(red.tm_id.notna().sum())} satir dolu - build_links calistir")
        if "player_outcome" in tables:
            n = q("""SELECT count(*) n FROM player_outcome o
                     JOIN player_links l USING (player_id)
                     WHERE l.confidence NOT IN ('A','B','M')""").n[0]
            check("sonuclar yalniz kabul edilmis eslesmeden olculuyor",
                  int(n) == 0, f"{int(n)} satir baska kisinin kariyerinden")

    # ---------------------------------------------------------- 7. kota/durum
    qf = ROOT / "data" / "raw" / "apifootball" / "_quota.json"
    if qf.exists():
        qd = json.loads(qf.read_text(encoding="utf-8"))
        check("kota sayaci makul", 0 <= qd.get("used", -1) <= 200,
              f"{qd.get('date')} · {qd.get('used')}/100")

    st = ROOT / "data" / "raw" / "apifootball" / "_ingest_state.json"
    if st.exists():
        sd = json.loads(st.read_text(encoding="utf-8"))
        done = sum(1 for v in sd.get("leagues", {}).values() if v.get("complete"))
        check("toplama ilerliyor", done > 0, f"{done} lig-sezon tamam")

    # --- 30 Agu 2026 denetiminde bulunan uc kusur, tekrar etmesin ---

    # 1) Skoru olmayan oyuncuya "dogal rol" etiketi atanmasin.
    #    Eskiden ORDER BY score DESC tum-NULL durumunda satir sirasina
    #    dusuyordu ve kazanan roles.yaml'deki ILK rol oluyordu.
    sahte = con.sql("""SELECT count(*) n FROM player_natural_role
                       WHERE score IS NULL AND role IS NOT NULL""").df().n[0]
    check("skorsuz oyuncuya dogal rol atanmamis", int(sahte) == 0,
          f"{int(sahte)} sahte etiket")

    # 2) Imkansiz yas kalmamis olmali. Ust sinir GENIS: Miura 56 yasinda
    #    oynadi, o gercek - elenmemeli.
    yas = con.sql("""SELECT count(*) n FROM player_features
                     WHERE age_season_end IS NOT NULL
                       AND (age_season_end < 14 OR age_season_end > 60)""").df().n[0]
    check("imkansiz yas yok (14-60 disi)", int(yas) == 0, f"{int(yas)} kayit")

    # 3) GENELCI SABLON UYARISI - duzeltilebilir bir hata degil, yapisal
    #    bir gercek. "Dogal rol" 14 rolun ARGMAX'i; genelci sablon otekilerin
    #    ortalamasina cok yakin oldugu icin (fw_complete r=0,91) neredeyse
    #    hicbir zaman maksimum olmuyor. Sayi gorunur kalsin diye raporlaniyor.
    pay = con.sql("""
        WITH t AS (SELECT role, count(*) n FROM player_natural_role
                   WHERE role IS NOT NULL GROUP BY 1)
        SELECT role, n FROM t ORDER BY n LIMIT 1""").df()
    if len(pay):
        check("genelci sablon nadiren dogal rol (yapisal)", None,
              f"en az secilen: {pay.role[0]} ({int(pay.n[0])} kez) - "
              f"argmax genelci sablonu secemez, PLAN §36")

    # ------------------------------------------------ 7.0: tek dogruluk kaynagi
    # DuckDB tablo zaman damgasi tutmuyor. Eski kalmayi ICERIKTEN yakala:
    # sonuc tablosu yeniden kuruldu ama siralama kurulmadiysa kademe ayrisir.
    if {"player_tahmin", "player_ranking", "player_outcome"} <= tables:
        pt = q("SELECT * FROM player_tahmin")
        anahtar = ["player_id", "league_id", "season"]
        check("player_tahmin anahtari tekil",
              pt.duplicated(anahtar).sum() == 0,
              f"{pt.duplicated(anahtar).sum()} yinelenen")
        eksik = q("""SELECT count(*) n FROM player_ranking r
                     ANTI JOIN player_tahmin t USING (player_id, league_id, season)
                  """).n[0]
        check("player_tahmin her siralama satirini kapsiyor", eksik == 0,
              f"{eksik} siralama satirinin tahmini yok")
        ayrisan = q("""SELECT count(*) n FROM player_ranking r
                       JOIN player_outcome o USING (player_id, league_id, season)
                       WHERE r.kademe IS DISTINCT FROM o.kademe""").n[0]
        check("player_ranking guncel (kademe player_outcome ile ayni)",
              ayrisan == 0,
              f"{ayrisan} satirda kademe ayrisiyor"
              + (" - build_ranking calistir" if ayrisan else ""))
        orneklem_ici = int(pt.tahmin_turu.isin(
            ["uretim", "uretim_kalibresiz"]).sum()) if len(pt) else 0
        sonucu_bilinen = q("""SELECT count(*) n FROM player_tahmin t
                              JOIN player_outcome o USING (player_id, league_id, season)
                              WHERE t.tahmin_turu LIKE 'uretim%'
                                AND o.gozlem_ay >= 12""").n[0]
        check("sonucu bilinen sezonlarda uretim (orneklem ici) tahmini yok",
              sonucu_bilinen == 0,
              f"{sonucu_bilinen} / {orneklem_ici} uretim satirinin sonucu belli")
    else:
        check("tablo mevcut: player_tahmin", False,
              "build_ranking calistirilmamis")

    # ---------------------------------------------------------- kaynak tazeligi (FAZ 9.1)
    # Dis kaynak durursa (TM Temmuz 2026'da durdu) bunu fark eden kontrol
    # yoktu. UYARI: duzeltmesi elimizde degil ama gorunur olmali.
    from scout.kaynaklar import tum_bulgular
    for b in tum_bulgular():
        check(b.kontrol, {"GECTI": True, "KALDI": False}.get(b.sonuc), b.detay)

    # sirlar repoya sizmis mi?
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8") if (ROOT / ".gitignore").exists() else ""
    check(".env gitignore'da", ".env" in gi)

    # ---------------------------------------------------------- rapor
    con.close()
    df = pd.DataFrame(RESULTS, columns=["sonuc", "kontrol", "detay"])
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 70)

    print("=" * 96)
    print("SISTEM DENETIMI")
    print("=" * 96)
    for r in ("KALDI", "UYARI", "GECTI"):
        sub = df[df.sonuc == r]
        if len(sub):
            print(f"\n--- {r} ({len(sub)}) ---")
            print(sub[["kontrol", "detay"]].to_string(index=False))

    n_fail = int((df.sonuc == "KALDI").sum())
    print(f"\n{'=' * 96}")
    print(f"TOPLAM: {len(df)} kontrol · {int((df.sonuc=='GECTI').sum())} gecti · "
          f"{n_fail} kaldi · {int((df.sonuc=='UYARI').sum())} uyari")
    if OZET_JSON:
        # FAZ 9.5: atomik build kapisi bunu okur (build_kaydi.py)
        Path(OZET_JSON).write_text(json.dumps({
            "toplam": len(df), "gecti": int((df.sonuc == "GECTI").sum()),
            "kaldi": n_fail, "uyari": int((df.sonuc == "UYARI").sum()),
            "kaldi_kontroller": sorted(df[df.sonuc == "KALDI"].kontrol.tolist()),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if n_fail else 0


OZET_JSON: str | None = None

if __name__ == "__main__":
    import argparse
    _ap = argparse.ArgumentParser()
    _ap.add_argument("--ozet-json", help="sonuc ozetini bu dosyaya yaz (build kapisi)")
    OZET_JSON = _ap.parse_args().ozet_json
    sys.exit(main())
