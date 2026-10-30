"""Faz 1c: Ham API-Football JSON'larini analitik tabloya cevir -> data/scout.duckdb

Idempotent: her calistirmada tabloyu bastan kurar. Ham veri data/raw altinda
dokunulmadan durdugu icin bu guvenli - donusum mantigi degistiginde tekrar calistir.

Cikan tablo: player_season
  bir satir = (oyuncu, lig, sezon, takim) dortlusu

Veri sekli tuzagi (§11.6): bir oyuncunun 'statistics' dizisinde birden fazla giris
olabilir ve bazilari tamamen bos stub. Burada ilgili lige ait ve dakikasi olan
girisler aliniyor; ayni oyuncu sezon ici kulup degistirmisse her kulup ayri satir.
"""

from __future__ import annotations

import json
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

CACHE = ROOT / "data" / "raw" / "apifootball" / "players"
# 30 Eki 2026: burasi sabit 'data/scout.duckdb' idi ve FAZ 9.5 gecisinde
# atlandi (degisken adi DB degil OUT). Atomik build'in ilk denemesinde
# build_db SCOUT_DB'yi yok sayip CANLI dosyaya yazdi; canli .red kopyasindan
# geri yuklendi. test_build_kaydi.test_zincir_betikleri_scout_db_kullanir sinar.
OUT = db_yolu()  # SCOUT_DB ya da data/scout.duckdb (FAZ 9.5)
STATE = ROOT / "data" / "raw" / "apifootball" / "_ingest_state.json"
LEAGUES_YAML = ROOT / "config" / "leagues.yaml"


def latest_tm_db() -> Path | None:
    """Zincirin kullandigi Transfermarkt anlik goruntusu.

    Tarihce: once sabit '2026-07-11', sonra "klasordeki en yeni". Ikincisi
    30 Eki 2026'da tehlikeli cikti: yeni bir surum indirilince zincir onu
    sessizce alip baska betiklerin sabit surumuyle karistiriyordu. Artik
    config/kaynaklar.yaml'daki surum (scout.kaynaklar.tm_db_yolu).
    """
    from scout.kaynaklar import tm_db_yolu
    try:
        return tm_db_yolu()
    except FileNotFoundError as exc:
        print(f"  ! {exc}")
        return None

# API alan yolu -> tablo sutunu
METRIC_MAP = {
    "games.appearences": "apps",
    "games.lineups": "starts",
    "games.minutes": "minutes",
    "games.rating": "rating",
    "games.position": "position",
    "goals.total": "goals",
    "goals.assists": "assists",
    "goals.conceded": "goals_conceded",
    "goals.saves": "saves",
    "shots.total": "shots",
    "shots.on": "shots_on",
    "passes.total": "passes",
    "passes.key": "key_passes",
    "passes.accuracy": "pass_accuracy",
    "tackles.total": "tackles",
    "tackles.blocks": "blocks",
    "tackles.interceptions": "interceptions",
    "duels.total": "duels",
    "duels.won": "duels_won",
    "dribbles.attempts": "dribbles",
    "dribbles.success": "dribbles_won",
    "dribbles.past": "dribbled_past",
    "fouls.drawn": "fouls_drawn",
    "fouls.committed": "fouls_made",
    "cards.yellow": "yellow",
    "cards.red": "red",
    "penalty.scored": "pens_scored",
    "penalty.missed": "pens_missed",
    "penalty.won": "pens_won",
    "substitutes.in": "sub_in",
    "substitutes.out": "sub_out",
    "substitutes.bench": "bench",
}

NUMERIC = [c for c in METRIC_MAP.values() if c != "position"]


def dig(d: dict, path: str):
    for part in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(part)
    return d


def to_num(v):
    """'85%' -> 85.0, '183 cm' -> 183.0, None -> None"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().rstrip("%").replace(" cm", "").replace(" kg", "")
    try:
        return float(s)
    except ValueError:
        return None


def fix_mojibake(s):
    """'JoÃ£o' -> 'João'. Kaynakta cift kodlanmis kayitlar var (§11.9)."""
    if not isinstance(s, str) or not any(c in s for c in ("Ã", "Â")):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def target_league_ids() -> set[int]:
    """config/leagues.yaml'daki hedef ligler.

    Kesif asamasinda test icin cekilen kayitlar (Ligue 1 tek sayfa,
    Serie C Supercoppa) production tablolarina sizmisti; arayuzde lig
    listesinde gorunup kafa karistiriyordu. Artik yalnizca hedef ligler alinir.
    """
    import yaml

    cfg = yaml.safe_load(LEAGUES_YAML.read_text(encoding="utf-8"))
    return {int(l["id"]) for l in cfg["leagues"]}


def collection_status() -> pd.DataFrame:
    """Lig-sezon basina toplama durumu.

    NEDEN GEREKLI: toplama 34 gune yayiliyor, yani her gun en az bir lig
    YARIM halde. Yarim bir ligde percentile hesaplamak YANILTICI - ustelik
    takim takim topladigimiz icin ornek rastgele degil KUMELI; 5/28 takim
    demek "5 tam takim" demek ve o takimlar guclu ya da zayif olabilir.
    Yani sapma var, sadece gurultu degil.

    Bu tablo, arayuzun 'bu ligin verisi henuz tam degil' diyebilmesini saglar.
    """
    if not STATE.exists():
        return pd.DataFrame(columns=["league_id", "season", "league_complete",
                                     "teams_done", "teams_total", "collection_pct"])
    st = json.loads(STATE.read_text(encoding="utf-8"))
    rows = []
    for key, v in st.get("leagues", {}).items():
        lid, season = key.split(":")
        total = len(v.get("team_ids") or [])
        done = sum(1 for t in v.get("teams", {}).values() if t.get("done"))
        rows.append({
            "league_id": int(lid), "season": int(season),
            "league_complete": bool(v.get("complete")),
            "teams_done": done, "teams_total": total,
            "collection_pct": round(100 * done / total, 1) if total else 0.0,
        })
    return pd.DataFrame(rows)


def parse_cache() -> pd.DataFrame:
    rows = []
    files = sorted(CACHE.glob("*.json"))
    if not files:
        raise SystemExit(f"Onbellekte oyuncu verisi yok: {CACHE}")

    for f in files:
        payload = json.loads(f.read_text(encoding="utf-8"))
        for rec in payload.get("response", []):
            pl = rec.get("player", {}) or {}
            birth = pl.get("birth", {}) or {}
            for st in rec.get("statistics", []) or []:
                lg = st.get("league", {}) or {}
                tm = st.get("team", {}) or {}
                if not dig(st, "games.minutes"):
                    continue  # oynamamis / bos stub kaydi
                row = {
                    "player_id": pl.get("id"),
                    "player_name": pl.get("name"),
                    "firstname": pl.get("firstname"),
                    "lastname": pl.get("lastname"),
                    "age": pl.get("age"),
                    "birth_date": birth.get("date"),
                    "birth_country": birth.get("country"),
                    "nationality": pl.get("nationality"),
                    "height_cm": to_num(pl.get("height")),
                    "weight_kg": to_num(pl.get("weight")),
                    "league_id": lg.get("id"),
                    "league_name": lg.get("name"),
                    "country": lg.get("country"),
                    "season": lg.get("season"),
                    "team_id": tm.get("id"),
                    "team_name": tm.get("name"),
                    "captain": dig(st, "games.captain"),
                }
                for path, col in METRIC_MAP.items():
                    v = dig(st, path)
                    row[col] = v if col == "position" else to_num(v)
                rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("Ayristirilacak kayit bulunamadi.")

    # --- 0) hedef disi ligleri ele (probe artiklari) ----------------------
    targets = target_league_ids()
    before = len(df)
    dropped = df[~df.league_id.isin(targets)]
    if len(dropped):
        names = dropped.groupby("league_name").size().to_dict()
        print(f"  ! hedef disi {len(dropped)} kayit elendi (probe artigi): {names}")
    df = df[df.league_id.isin(targets)]
    if df.empty:
        raise SystemExit(f"Hedef liglere ait kayit yok ({before} kayit elendi).")

    # Ayni (oyuncu, lig, sezon, takim) birden fazla sayfada gorunebilir
    df = df.drop_duplicates(subset=["player_id", "league_id", "season", "team_id"])

    # --- 1) Bozuk karakter onarimi -----------------------------------------
    for c in ["player_name", "firstname", "lastname", "team_name"]:
        df[c] = df[c].map(fix_mojibake)

    # --- 2) Sayim metriklerinde null = 0 (§11.8) ---------------------------
    # API oynamis oyuncuda bile "0 gol" yerine null donduruyor.
    # rating ve pass_accuracy HARIC - orada null gercekten eksik veri.
    count_cols = [
        "goals", "assists", "shots", "shots_on", "key_passes", "tackles",
        "blocks", "interceptions", "duels", "duels_won", "dribbles",
        "dribbles_won", "dribbled_past", "fouls_drawn", "fouls_made",
        "yellow", "red", "pens_scored", "pens_missed", "pens_won",
        "sub_in", "sub_out", "bench",
    ]
    # AMA: yalnizca lig o metrigi GERCEKTEN yayinliyorsa (§21).
    # Bazi liglerde saglayici detayli istatistigi hic vermiyor. Orada null'i
    # 0 yapmak "bilinmiyor"u sessizce "sifir"a cevirir ve oyuncu olculmemis
    # degil KOTU gorunur. Olculdu: Veikkausliiga 2024'te sut/ikili/tackle/
    # anahtar pas TAMAMEN null'di; 0'a cevrilince 324 oyuncuya 1.301 skor
    # uretildi (ortalama 50,5) - hepsi uydurma sifirlardan. Skor makul
    # gorundugu icin hata gorunmezdi.
    #
    # Kural: bir (lig, sezon) icinde metrigin TAMAMI null ise NaN birak.
    # Boylece percentile uretilmez, kapsam duser ve motor kalan agirligi
    # yeniden normalize eder - eksiklik skorun icinde degil YANINDA durur.
    eksik_rapor: dict[str, list[str]] = {}
    for c in count_cols:
        if c not in df.columns:
            continue
        dolu = df.groupby(["league_id", "season"])[c].transform(
            lambda s: s.notna().any())
        df[c] = df[c].where(~dolu, df[c].fillna(0.0))
        for (lid, sez), g in df[~dolu].groupby(["league_id", "season"]):
            eksik_rapor.setdefault(f"{g.league_name.iloc[0]} {sez}", []).append(c)

    if eksik_rapor:
        print("  ! bazi lig-sezonlarda metrik HIC yayinlanmamis "
              "(NaN birakildi, 0 sayilmadi):")
        for lig, metrikler in sorted(eksik_rapor.items()):
            print(f"      {lig}: {len(metrikler)} metrik - {', '.join(metrikler[:6])}"
                  + (" ..." if len(metrikler) > 6 else ""))

    # --- 3) Sezon ici transferlerde cift sayim (§11.9) ---------------------
    # API, kulup degistiren oyuncuda ayni sezon toplamini HER IKI takim
    # satirinda tekrarlayabiliyor (ornek: Dalberson 1350dk + 1350dk).
    # Satirlari toplamak dakikayi ikiye katlar. Cozum: oyuncu-lig-sezon
    # basina TEK satir birak, en cok dakikali kaydi asil kabul et.
    grp = ["player_id", "league_id", "season"]
    df["multi_team"] = df.groupby(grp)["team_id"].transform("size") > 1
    df["all_teams"] = df.groupby(grp)["team_name"].transform(lambda s: " + ".join(s.astype(str)))
    df = (
        df.sort_values("minutes", ascending=False)
        .drop_duplicates(subset=grp, keep="first")
        .reset_index(drop=True)
    )

    # --- 4) Toplama durumu ------------------------------------------------
    status = collection_status()
    if len(status):
        df = df.merge(status, on=["league_id", "season"], how="left")
    for c, dflt in [("league_complete", False), ("teams_done", 0),
                    ("teams_total", 0), ("collection_pct", 0.0)]:
        if c not in df.columns:
            df[c] = dflt
    df["league_complete"] = df["league_complete"].fillna(False).astype(bool)
    df["collection_pct"] = df["collection_pct"].fillna(0.0)

    # --- 5) Turetilmis alanlar ---------------------------------------------
    df["birth_date"] = pd.to_datetime(df["birth_date"], errors="coerce")
    df["nineties"] = df["minutes"] / 90.0
    # Sezon sonundaki yas - yas duzeltmesi (§1.3) bunu kullanir
    df["age_season_end"] = (
        pd.to_datetime(df["season"].astype("Int64").astype(str) + "-12-31")
        - df["birth_date"]
    ).dt.days / 365.25

    # Saglayici bazen imkansiz dogum tarihi veriyor. Olculdu (30 Agu 2026):
    # iki oyuncunun dogum tarihi 2026 gorunuyordu ve yaslari -3,6 cikiyordu.
    # Negatif yas age_band'e dusmuyor ama takim ortalama yasi, yas egrisi ve
    # yas filtreleri gibi her yerde sessizce tasiniyordu. 44-56 yas araligi
    # ELENMEZ: Buffon (44,9), Fabio (44,3), Miura (56,8) gercek.
    imkansiz = df["age_season_end"].notna() & (
        (df["age_season_end"] < YAS_ALT) | (df["age_season_end"] > YAS_UST))
    if imkansiz.any():
        ornek = df.loc[imkansiz, ["player_name", "birth_date"]].head(3)
        print(f"  ! {int(imkansiz.sum())} oyuncuda imkansiz dogum tarihi - "
              f"yas ve dogum tarihi NULL birakildi")
        for r in ornek.itertuples():
            print(f"      {r.player_name}: {r.birth_date}")
        # ayri ayri: biri float, oteki datetime - tek atamada tip cakisiyor
        df.loc[imkansiz, "age_season_end"] = float("nan")
        df.loc[imkansiz, "birth_date"] = pd.NaT
    return df


# Makul yas siniri. Ust sinir GENIS tutuldu: Miura 56 yasinda
# Segunda Liga'da oynadi, Buffon 44 - bunlar gercek, elenmemeli.
YAS_ALT, YAS_UST = 14.0, 60.0

# Veri kalitesi degerlendirmesinde bakilan temel metrikler
TEMEL_METRIKLER = ["shots", "duels", "tackles", "key_passes", "passes"]
# Pas/90'i tum lig-sezonlarin medyanina oranladiginda bu esigin altiysa
# maclarin bir kismi eksik demektir (§21.3). Olculdu: saglam ligler
# %83-118 bandinda, Superettan %48, Segunda Liga %15.
EKSIK_MAC_ESIGI = 0.65


def lig_kalitesi(df: pd.DataFrame) -> pd.DataFrame:
    """Lig-sezon basina veri kalitesi karnesi (§21).

    TEK DOGRULUK KAYNAGI: hem denetim hem arayuz burayi okur. Ayni mantigi
    uc yerde ayri yazarsak zamanla birbirinden ayrisirlar.

    kalite:
      tam            - sorun yok
      metrik_eksik   - saglayici bazi metrikleri HIC yayinlamiyor
      mac_eksik      - dakikalar tam ama sayimlar eksik (bazi maclar yok)
    """
    oyn = df[(df.minutes >= 900) & (df.position != "Goalkeeper")].copy()
    satir = []
    for (lid, sez), g in df.groupby(["league_id", "season"]):
        eksik = [m for m in TEMEL_METRIKLER
                 if m in g.columns and g[m].notna().sum() == 0]
        go = oyn[(oyn.league_id == lid) & (oyn.season == sez)]
        pas90 = float((go.passes / go.minutes * 90).mean()) if len(go) else np.nan
        satir.append({
            "league_id": lid, "season": sez,
            "league_name": g.league_name.iloc[0], "country": g.country.iloc[0],
            "eksik_metrikler": ", ".join(eksik),
            "n_eksik_metrik": len(eksik),
            "pas90": pas90,
        })
    out = pd.DataFrame(satir)
    if out.empty:
        return out

    med = out.pas90.median(skipna=True)
    out["sayim_orani"] = (out.pas90 / med).round(3) if med and np.isfinite(med) else np.nan
    out["kalite"] = np.where(
        out.n_eksik_metrik > 0, "metrik_eksik",
        np.where(out.sayim_orani < EKSIK_MAC_ESIGI, "mac_eksik", "tam"))
    return out.drop(columns=["pas90"])


def main() -> int:
    df = parse_cache()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(OUT))
    con.execute("CREATE OR REPLACE TABLE player_season AS SELECT * FROM df")

    kalite = lig_kalitesi(df)
    con.execute("CREATE OR REPLACE TABLE league_quality AS SELECT * FROM kalite")
    kotu = kalite[kalite.kalite != "tam"]
    if len(kotu):
        print(f"  ! {len(kotu)} lig-sezonda veri kalitesi sorunu "
              "(league_quality tablosuna yazildi):")
        for r in kotu.itertuples():
            detay = (r.eksik_metrikler if r.n_eksik_metrik
                     else f"sayimlar medyanin %{r.sayim_orani*100:.0f}'i")
            print(f"      {r.country}/{r.league_name} {r.season} [{r.kalite}]: {detay}")

    # Transfermarkt meta katmanini yanina kopyala (§11.5)
    tm_db = latest_tm_db()
    if tm_db:
        print(f"  Transfermarkt anlik goruntusu: {tm_db.parent.name}")
        con.execute(f"ATTACH '{tm_db}' AS tm (READ_ONLY)")
        for t in ["players", "player_valuations", "transfers", "competitions", "clubs"]:
            try:
                con.execute(f"CREATE OR REPLACE TABLE tm_{t} AS SELECT * FROM tm.{t}")
            except duckdb.Error as exc:
                print(f"  ! tm.{t} kopyalanamadi: {exc}")
        con.execute("DETACH tm")

    print(f"[ok] {len(df):,} oyuncu-lig-sezon-takim satiri -> {OUT}\n")

    pd.set_option("display.width", 200)
    print("--- lig-sezon bazinda ---")
    print(
        con.sql("""
        SELECT country, league_name, season,
               count(*) AS oyuncu,
               count(*) FILTER (WHERE minutes >= 900) AS "900dk+",
               round(avg(rating), 2) AS ort_rating,
               any_value(teams_done) || '/' || any_value(teams_total) AS takim,
               CASE WHEN any_value(league_complete) THEN 'tam'
                    ELSE 'TOPLANIYOR %' || cast(any_value(collection_pct) AS INT)
               END AS durum
        FROM player_season GROUP BY 1,2,3 ORDER BY 1,2,3
    """).df().to_string(index=False)
    )

    print("\n--- veri kalitesi ---")
    print(
        con.sql("""
        SELECT count(*) AS satir,
               count(*) FILTER (WHERE multi_team) AS "sezon_ici_transfer(*)",
               count(*) FILTER (WHERE birth_date IS NULL) AS dogum_yok,
               count(*) FILTER (WHERE player_name LIKE '%Ã%') AS bozuk_karakter,
               count(*) FILTER (WHERE rating IS NULL) AS rating_yok
        FROM player_season
    """).df().T.to_string(header=False)
    )
    print("  (*) tek satira indirildi, en cok dakikali kayit esas alindi - §11.9")

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
