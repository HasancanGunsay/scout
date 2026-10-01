"""Faz 2: Kimlik eslestirme -> player_links + player_meta

API-Football oyuncularini Transfermarkt kayitlariyla baglar; boylece
piyasa degeri, sozlesme bitisi, ayak, menajer gibi baglamsal filtreler (§1.9)
kullanilabilir hale gelir.

Ciktilar:
  player_links  - eslesme tablosu (guven seviyesiyle)
  player_meta   - kabul edilen eslesmelerin TM meta verisi
  reports/eslesme_kuyrugu.csv - manuel onay bekleyenler (D seviyesi)
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout.resolve.matcher import build_links, kabul_disini_bosalt  # noqa: E402

# Windows Gorev Zamanlayici altinda stdout cp1254'e dusuyor ve Hirvat/Polonya
# isimlerindeki 'c' harfi (ć) tum zinciri UnicodeEncodeError ile
# kiriyordu (19 Agu 2026). Cikti kodlamasini burada sabitliyoruz.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DB = ROOT / "data" / "scout.duckdb"
QUEUE = ROOT / "reports" / "eslesme_kuyrugu.csv"
# Arayuzden verilen manuel kararlar - otomatik eslestirmeyi EZER
DECISIONS = ROOT / "reports" / "eslesme_kararlari.json"


def apply_decisions(links: pd.DataFrame) -> pd.DataFrame:
    """Kullanicinin manuel kararlarini uygula (§1.6 manuel onay kuyrugu).

    Karar formati: {"<player_id>": {"tm_id": 123, "action": "accept"|"reject"}}
    Manuel karar her zaman otomatik sonucu ezer ve bir daha sorulmaz.
    """
    import json

    if not DECISIONS.exists():
        return links
    try:
        dec = json.loads(DECISIONS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return links

    for pid_str, d in dec.items():
        mask = links.player_id == int(pid_str)
        if not mask.any():
            continue
        if d.get("action") == "accept":
            links.loc[mask, "confidence"] = "M"
            links.loc[mask, "reason"] = "manuel onay"
            if d.get("tm_id"):
                links.loc[mask, "tm_id"] = d["tm_id"]
        elif d.get("action") == "reject":
            links.loc[mask, "confidence"] = "X"
            links.loc[mask, "reason"] = "manuel red"
            links.loc[mask, "tm_id"] = None
    print(f"[man] {len(dec)} manuel karar uygulandi")
    return links


def main() -> int:
    con = duckdb.connect(str(DB))

    # en cok dakikali sezonu temsilci al (kulup kaniti icin takim adi lazim)
    api = con.sql("""
        SELECT player_id, player_name, firstname, lastname,
               birth_date, nationality, team_name
        FROM (
          SELECT *, row_number() OVER (PARTITION BY player_id ORDER BY minutes DESC) rn
          FROM player_features
        ) WHERE rn = 1
    """).df()
    tm = con.sql("""
        SELECT player_id AS tm_id, name, first_name, last_name,
               date_of_birth, country_of_citizenship, current_club_name
        FROM tm_players
    """).df()
    print(f"[in]  API {len(api):,} oyuncu | TM {len(tm):,} kayit")

    # tm_id yalniz kabul edilmis eslesmede dolu (PLAN §60): asagidaki her
    # tuketici (sonuc, deger, arayuz) tm_id uzerinden baglaniyor
    links = kabul_disini_bosalt(apply_decisions(build_links(api, tm)))
    con.execute("CREATE OR REPLACE TABLE player_links AS SELECT * FROM links")

    # kabul edilenleri TM meta verisiyle birlestir
    meta = con.sql("""
        SELECT l.player_id, l.tm_id, l.confidence, l.name_score,
               t.market_value_in_eur      AS market_value_eur,
               t.highest_market_value_in_eur AS peak_market_value_eur,
               t.contract_expiration_date AS contract_until,
               t.foot, t.sub_position     AS tm_position,
               t.agent_name, t.country_of_citizenship AS tm_nationality,
               t.current_club_name        AS tm_club,
               t.international_caps, t.international_goals,
               t.url                      AS tm_url
        FROM player_links l
        JOIN tm_players t ON t.player_id = l.tm_id
        WHERE l.confidence IN ('A','B','M')
    """).df()
    con.execute("CREATE OR REPLACE TABLE player_meta AS SELECT * FROM meta")

    # manuel onay kuyrugu - C seviyesi (belirsiz, kabul EDILMEDI)
    queue = links[links.confidence == "C"]
    if len(queue):
        QUEUE.parent.mkdir(parents=True, exist_ok=True)
        queue.to_csv(QUEUE, index=False, encoding="utf-8-sig")

    # ---------------------------------------------------------------- rapor
    pd.set_option("display.width", 200)
    print(f"\n[ok]  player_links {len(links):,} | player_meta {len(meta):,}\n")

    print("--- guven seviyesine gore ---")
    summary = (
        links.confidence.value_counts().rename_axis("seviye").reset_index(name="n")
        .assign(pct=lambda d: (100 * d.n / len(links)).round(1))
        .sort_values("seviye")
    )
    aciklama = {
        "A": "tek aday + isim tutuyor -> KABUL",
        "B": "coklu aday, net kazanan -> KABUL",
        "C": "belirsiz -> manuel onay kuyrugunda, kullanilmiyor",
        "D": "reddedildi (isim tutmuyor / cakisma)",
        "-": "TM veri setinde aday yok (kapsam sorunu, algoritma degil)",
    }
    summary["aciklama"] = summary.seviye.map(aciklama)
    print(summary.to_string(index=False))

    ok = links.confidence.isin(["A", "B", "M"]).sum()
    print(f"\n  KABUL EDILEN: {ok}/{len(links)} ({100*ok/len(links):.1f}%)")
    print("  karsilastirma: naif ad+dogum %43.6 | esiksiz 'tek aday' kurali %66.8")
    print("  (esiksiz kural yanlis eslesme uretiyordu - §13.2)")

    print("\n--- lig bazinda kapsam ---")
    print(con.sql("""
        SELECT f.league_name AS lig, f.season AS sezon,
               count(DISTINCT f.player_id) AS oyuncu,
               count(DISTINCT m.player_id) AS eslesen,
               round(100.0*count(DISTINCT m.player_id)/count(DISTINCT f.player_id),1) AS pct,
               count(DISTINCT m.player_id) FILTER (WHERE m.market_value_eur IS NOT NULL)
                 AS piyasa_degeri_var,
               count(DISTINCT m.player_id) FILTER (WHERE m.contract_until IS NOT NULL)
                 AS sozlesme_var
        FROM player_features f
        LEFT JOIN player_meta m ON m.player_id = f.player_id
        GROUP BY 1,2 ORDER BY oyuncu DESC
    """).df().to_string(index=False))

    print("\n--- lakap vakalarindan ornekler (A seviyesi, isim skoru dusuk) ---")
    nick = links[(links.confidence == "A") & (links.name_score < 60)]
    print(nick[["player_name", "tm_name", "name_score", "reason"]]
          .head(10).to_string(index=False) if len(nick) else "  yok")

    if len(queue):
        print(f"\n--- manuel onay kuyrugu: {len(queue)} kayit -> {QUEUE}")
        print(queue[["player_name", "tm_name", "name_score", "n_candidates", "reason"]]
              .head(8).to_string(index=False))

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
