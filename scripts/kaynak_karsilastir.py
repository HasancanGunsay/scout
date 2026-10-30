"""Iki Transfermarkt anlik goruntusunu karsilastir (FAZ 9.1).

Yeni bir surume gecmeden ONCE: ne degisiyor, bizim oyuncularimizi nasil
etkiliyor? Gecis kararini bu rapor ve kullanici verir; zincir otomatik gecmez
(config/kaynaklar.yaml).

    python scripts/kaynak_karsilastir.py                       # kullanilan vs en yeni
    python scripts/kaynak_karsilastir.py --eski 2026-07-11 --yeni 2026-09-05
Cikti: reports/kaynak_karsilastirma_<eski>_<yeni>.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from scout.kaynaklar import db_yolu, TM_DIZIN, TM_DOSYA, tm_anlik_goruntuler, tm_db_yolu  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = db_yolu()  # SCOUT_DB ya da data/scout.duckdb (FAZ 9.5)
TABLOLAR = ["players", "player_valuations", "appearances", "games", "game_lineups",
            "game_events", "transfers", "clubs", "competitions"]
TARIH = {"player_valuations": "date", "appearances": "date", "games": "date",
         "game_lineups": "date", "game_events": "date", "transfers": "transfer_date"}


def md_tablo(df: pd.DataFrame) -> str:
    """tabulate bagimliligi olmadan markdown tablo."""
    s = lambda v: f"{v:,}" if isinstance(v, int) else str(v)  # noqa: E731
    satirlar = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    satirlar += ["| " + " | ".join(s(v) for v in r) + " |"
                 for r in df.astype(object).itertuples(index=False)]
    return "\n".join(satirlar)


def ozet(con, sema: str) -> pd.DataFrame:
    rows = []
    for t in TABLOLAR:
        n = con.sql(f"SELECT count(*) FROM {sema}.{t}").fetchone()[0]
        mx = (con.sql(f"SELECT max({TARIH[t]}) FROM {sema}.{t}").fetchone()[0]
              if t in TARIH else None)
        rows.append({"tablo": t, "satir": n, "en_yeni": str(mx)[:10] if mx else "—"})
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eski")
    ap.add_argument("--yeni")
    a = ap.parse_args()
    eski = a.eski or tm_db_yolu().parent.name
    yeni = a.yeni or tm_anlik_goruntuler()[-1]
    if eski == yeni:
        print(f"Karsilastirilacak yeni surum yok ({eski}).")
        return 0

    con = duckdb.connect()
    con.execute(f"ATTACH '{TM_DIZIN / eski / TM_DOSYA}' AS e (READ_ONLY)")
    con.execute(f"ATTACH '{TM_DIZIN / yeni / TM_DOSYA}' AS y (READ_ONLY)")
    con.execute(f"ATTACH '{DB}' AS s (READ_ONLY)")

    oe, oy = ozet(con, "e"), ozet(con, "y")
    tablo = oe.merge(oy, on="tablo", suffixes=(f" {eski}", f" {yeni}"))
    tablo["fark"] = (tablo[f"satir {yeni}"] - tablo[f"satir {eski}"]).astype(int)
    tablo[[f"satir {eski}", f"satir {yeni}"]] = tablo[[f"satir {eski}", f"satir {yeni}"]].astype(int)

    # Bizim oyuncularimiz: 2025/26 ileriye donuk havuz + kabul edilmis API eslesmeleri
    bizim = con.sql("""
        SELECT DISTINCT player_id FROM s.tm_iddia_defteri
        UNION SELECT DISTINCT tm_id FROM s.player_links WHERE tm_id IS NOT NULL
    """).df()
    con.register("bizim", bizim)
    son_deger = """
        SELECT player_id, max(date) AS t, arg_max(market_value_in_eur, date) AS v
        FROM {s}.player_valuations WHERE player_id IN (SELECT player_id FROM bizim)
        GROUP BY 1"""
    d = con.sql(f"""
        SELECT coalesce(e.player_id, y.player_id) AS player_id,
               e.t AS t_eski, e.v AS v_eski, y.t AS t_yeni, y.v AS v_yeni
        FROM ({son_deger.format(s='e')}) e
        FULL JOIN ({son_deger.format(s='y')}) y USING (player_id)
    """).df()
    yeni_tarihli = int((d.t_yeni > d.t_eski).sum())
    degisen = d[(d.t_yeni > d.t_eski) & d.v_eski.notna() & d.v_yeni.notna()]
    oran = (degisen.v_yeni / degisen.v_eski).replace([float("inf")], pd.NA).dropna()

    # Ileriye donuk defter oyunculari (891): sezon sonu (2026-06-15) degeri
    defter = con.sql("""
        WITH d AS (SELECT DISTINCT player_id FROM s.tm_iddia_defteri WHERE season = 2025)
        SELECT d.player_id,
          (SELECT arg_max(market_value_in_eur, date) FROM e.player_valuations v
            WHERE v.player_id = d.player_id AND date <= DATE '2026-06-15') AS v_eski,
          (SELECT arg_max(market_value_in_eur, date) FROM y.player_valuations v
            WHERE v.player_id = d.player_id AND date <= DATE '2026-06-15') AS v_yeni
        FROM d""").df()
    defter_degisen = int((defter.v_eski.fillna(-1) != defter.v_yeni.fillna(-1)).sum())

    # Sozlesme bitisleri (players tablosu)
    soz = con.sql("""
        SELECT count(*) FILTER (WHERE e.contract_expiration_date IS DISTINCT FROM
                                      y.contract_expiration_date) AS degisen,
               count(*) AS toplam
        FROM e.players e JOIN y.players y USING (player_id)
        WHERE player_id IN (SELECT player_id FROM bizim)""").fetchone()

    L = [f"# Transfermarkt anlik goruntu karsilastirmasi: {eski} -> {yeni}", "",
         "Uretilen: `scripts/kaynak_karsilastir.py` · zincir hala "
         f"`{tm_db_yolu().parent.name}` kullaniyor (config/kaynaklar.yaml).", "",
         "## Tablolar", "", md_tablo(tablo), "",
         "## Bizim oyuncularimiz", "",
         f"- Kapsam: {len(bizim):,} TM oyuncusu (2025/26 havuzu + kabul edilmis eslesmeler).",
         f"- Son degeri DAHA YENI tarihli olan: **{yeni_tarihli:,}**.",
         f"- Bunlardan degeri degisen: {len(degisen):,}; yeni/eski oran medyani "
         f"{oran.median():.2f} (ceyrekler {oran.quantile(.25):.2f}-{oran.quantile(.75):.2f}).",
         f"- Sozlesme bitis tarihi degisen: {soz[0]:,} / {soz[1]:,}.", "",
         "## Ileriye donuk defter (2025/26, 891 tahmin) icin anlami", "",
         f"- Sezon sonu (2026-06-15) itibariyla piyasa degeri farkli olacak oyuncu: "
         f"**{defter_degisen} / {len(defter)}**.",
         "- Defter append-only: kayitli tahminler DEGISMEZ. Ama yeni surume gecilirse havuz "
         "ve arayuzdeki olasiliklar defterdekinden ayrisir; defter puanlamasi kayitli "
         "tahminlerle yapilir (docs/defter_2025_puanlama.md).", "",
         "## Gecis karari", "",
         "Zincir otomatik gecmez. Gecis = `config/kaynaklar.yaml` -> `anlik_goruntu` "
         "degisikligi + zincirin tam calismasi + denetim + PLAN.md kaydi, kullanici onayiyla."]
    cikti = ROOT / "reports" / f"kaynak_karsilastirma_{eski}_{yeni}.md"
    cikti.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"\n[yazildi] {cikti.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
