"""Toplama tahmini - veri seti ne zaman yeterli olur?

Tahmin yerine OLCUM: tamamlanmis lig-sezonlarin gercek istek maliyetinden
yola cikip kalan sureyi hesaplar. Ayrica geriye donuk testin (§8) ne zaman
mumkun olacagini soyler - o test 2022 + 2024 CIFTINI gerektiriyor.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "raw" / "apifootball" / "_ingest_state.json"
CFG = ROOT / "config" / "leagues.yaml"
DAILY = 100


def main() -> int:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    leagues = sorted(cfg["leagues"], key=lambda x: x["priority"])
    seasons = cfg["seasons"]
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"leagues": {}}
    L = state.get("leagues", {})

    # --- olculen maliyet -------------------------------------------------
    done_rows = []
    for key, v in L.items():
        if not v.get("complete"):
            continue
        pages = sum(len(t.get("pages", [])) for t in v.get("teams", {}).values())
        lid, season = key.split(":")
        done_rows.append({"lig": int(lid), "sezon": int(season),
                          "takim": len(v.get("team_ids") or []),
                          "istek": pages + 1})  # +1 = /teams cagrisi
    done = pd.DataFrame(done_rows)

    if done.empty:
        print("Henuz tamamlanmis lig-sezon yok, tahmin yapilamaz.")
        return 1

    ort = done.istek.mean()
    ort_takim = done.takim.mean()
    print("=" * 78)
    print("OLCULEN MALIYET (tamamlanmis lig-sezonlar)")
    print("=" * 78)
    print(done.sort_values("istek", ascending=False).to_string(index=False))
    print(f"\n  ortalama: {ort:.0f} istek / lig-sezon  ({ort_takim:.0f} takim)")
    print(f"  aralik  : {done.istek.min()}-{done.istek.max()}")

    # --- kuyruk sirasi ---------------------------------------------------
    # ingest_players.py: for season in seasons: for league in oncelik sirasi
    queue = [(s, lg) for s in seasons for lg in leagues]
    kalan_istek = 0
    eta = {}
    for s, lg in queue:
        k = f"{lg['id']}:{s}"
        v = L.get(k, {})
        if v.get("complete"):
            eta[k] = 0
            continue
        harcanan = sum(len(t.get("pages", [])) for t in v.get("teams", {}).values())
        kalan_istek += max(ort - harcanan, 5)
        eta[k] = kalan_istek

    print("\n" + "=" * 78)
    print("TAHMINI TAMAMLANMA (bugunden itibaren gun)")
    print("=" * 78)
    rows = []
    for s, lg in queue:
        k = f"{lg['id']}:{s}"
        gun = 0 if eta[k] == 0 else int(eta[k] / DAILY) + 1
        rows.append({"oncelik": lg["priority"], "ulke": lg["country"],
                     "lig": lg["name"], "sezon": s,
                     "durum": "TAM" if eta[k] == 0 else f"~{gun} gun"})
    df = pd.DataFrame(rows)
    pd.set_option("display.max_rows", 100)
    print(df.to_string(index=False))

    total_gun = int(kalan_istek / DAILY) + 1
    print(f"\n  TUM KUYRUK: ~{kalan_istek:.0f} istek = ~{total_gun} gun")

    # --- geriye donuk test ne zaman? -------------------------------------
    print("\n" + "=" * 78)
    print("GERIYE DONUK TEST (§8) NE ZAMAN MUMKUN?")
    print("=" * 78)
    print("Gereken: ayni lig icin 2022 (tahmin) + 2024 (sonuc) cifti.\n")

    for n in (3, 5, 8, 12):
        core = leagues[:n]
        need = 0
        for s in seasons:
            for lg in core:
                k = f"{lg['id']}:{s}"
                if s not in (2022, 2024):
                    continue
                v = L.get(k, {})
                if v.get("complete"):
                    continue
                harcanan = sum(len(t.get("pages", [])) for t in v.get("teams", {}).values())
                need += max(ort - harcanan, 5)
        # kuyruk sirasi geregi 2022'ye gecmek icin TUM 2024'un bitmesi gerekiyor
        blok_2024 = sum(
            max(ort - sum(len(t.get("pages", [])) for t in L.get(f"{lg['id']}:2024", {}).get("teams", {}).values()), 5)
            for lg in leagues
            if not L.get(f"{lg['id']}:2024", {}).get("complete")
        )
        sirali = blok_2024 + sum(
            max(ort - sum(len(t.get("pages", [])) for t in L.get(f"{lg['id']}:2022", {}).get("teams", {}).values()), 5)
            for lg in core
            if not L.get(f"{lg['id']}:2022", {}).get("complete")
        )
        print(f"  ilk {n:2} lig icin 2022+2024:")
        print(f"     saf ihtiyac        : ~{need:.0f} istek = ~{int(need/DAILY)+1} gun")
        print(f"     MEVCUT KUYRUKLA    : ~{sirali:.0f} istek = ~{int(sirali/DAILY)+1} gun")

    print("\n  NOT: kuyruk 'genislik once' - TUM ligler 2024, sonra 2022.")
    print("  Yani 2022 verisi, 25 ligin 2024'u bitmeden GELMEYE BASLAMIYOR.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
