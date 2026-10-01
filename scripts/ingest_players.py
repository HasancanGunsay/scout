"""Faz 1b / Adim 4: Oyuncu sezon istatistiklerini kademeli cek.

ROTA SECIMI (olcumle belirlendi, §11.7):
  /players?league=X&season=Y            -> ucretsiz planda page<=3, yani sadece 60 oyuncu. KULLANILAMAZ.
  /players?team=X&season=Y              -> tum musabakalar karisik geliyor, gurultulu.
  /players?league=X&team=T&season=Y     -> DOGRU ROTA. Istatistikler tek lige filtreli.

Maliyet: lig-sezon basina 1 (/teams) + takim_sayisi * sayfa(1-3) ~ 40-60 istek.

100 istek/gun kisitiyla yasamak icin:
  - GOREV KUYRUGU  : (sezon, oncelik, lig, takim, sayfa) sirasiyla isler
  - DEVAM EDEBILIR : durum _ingest_state.json'da; yarin kaldigi yerden devam eder
  - KOTA DOSTU     : kota bitince temiz durur
  - ONBELLEK       : cekilmis sayfa tekrar istenmez

Kullanim:
    python scripts/ingest_players.py --plan        # istek atmadan durum
    python scripts/ingest_players.py               # kota bitene kadar cek
    python scripts/ingest_players.py --budget 20   # sadece 20 istek
    python scripts/ingest_players.py --only-season 2024
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scout.ingest.apifootball import ApiFootball, ApiError, QuotaExhausted  # noqa: E402

# Windows Gorev Zamanlayici altinda stdout cp1254'e dusuyor ve Hirvat/Polonya
# isimlerindeki 'c' harfi (ć) tum zinciri UnicodeEncodeError ile
# kiriyordu (19 Agu 2026). Cikti kodlamasini burada sabitliyoruz.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "leagues.yaml"
STATE = ROOT / "data" / "raw" / "apifootball" / "_ingest_state.json"

MAX_PAGE = 3  # ucretsiz plan siniri


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"leagues": {}}


def save_state(s: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=1), encoding="utf-8")


class Budget:
    def __init__(self, n: int) -> None:
        self.left = n

    def take(self) -> None:
        if self.left <= 0:
            raise QuotaExhausted("bu calistirmanin butcesi doldu")
        self.left -= 1


def do_league_season(api, state, lg, season, budget) -> None:
    key = f"{lg['id']}:{season}"
    ent = state["leagues"].setdefault(key, {"teams": {}, "complete": False, "team_ids": None})
    if ent["complete"]:
        return

    label = f"{lg['country']}/{lg['name']} {season}"

    # 1) takim listesi (lig-sezon basina bir kez)
    if ent["team_ids"] is None:
        budget.take()
        t = api.get("teams", {"league": lg["id"], "season": season})
        ent["team_ids"] = [x["team"]["id"] for x in t.get("response", [])]
        ent["team_names"] = {str(x["team"]["id"]): x["team"]["name"] for x in t.get("response", [])}
        print(f"  {label}: {len(ent['team_ids'])} takim", flush=True)
        save_state(state)

    if not ent["team_ids"]:
        ent["complete"] = True
        print(f"  {label}: TAKIM YOK - atlaniyor\n", flush=True)
        save_state(state)
        return

    # 2) takim basina oyuncu sayfalari
    for tid in ent["team_ids"]:
        tstate = ent["teams"].setdefault(str(tid), {"pages": [], "total": None, "done": False})
        if tstate["done"]:
            continue
        tname = ent.get("team_names", {}).get(str(tid), tid)

        page = 1
        while page <= MAX_PAGE:
            if page in tstate["pages"]:
                page += 1
                continue
            budget.take()
            try:
                p = api.get(
                    "players",
                    {"league": lg["id"], "team": tid, "season": season, "page": page},
                )
            except ApiError as exc:
                print(f"    !! {tname}: {exc}", flush=True)
                tstate["done"] = True
                break

            total = p.get("paging", {}).get("total", 1) or 1
            tstate["total"] = total
            tstate["pages"].append(page)
            save_state(state)

            if total > MAX_PAGE and page == MAX_PAGE:
                print(
                    f"    ~ {tname}: {total} sayfa var, ucretsiz planda ilk {MAX_PAGE} alindi",
                    flush=True,
                )
            page += 1
            if page > min(total, MAX_PAGE):
                tstate["done"] = True
                break
        else:
            tstate["done"] = True

    if all(v["done"] for v in ent["teams"].values()) and len(ent["teams"]) == len(ent["team_ids"]):
        ent["complete"] = True
        print(f"  -> TAMAM: {label}\n", flush=True)
    save_state(state)


COVERAGE_CSV = ROOT / "data" / "raw" / "coverage_api_all.csv"


def _istatistiksiz_atla(tasks) -> dict:
    """stats_players=False olan (lig_id, sezon) ciftlerini bul.

    Kapsam taramasi yoksa hicbir sey atlanmaz - bilmiyorsak engellememek,
    yanlis engellemekten iyidir.
    """
    if not COVERAGE_CSV.exists():
        return {}
    try:
        import pandas as pd
        d = pd.read_csv(COVERAGE_CSV)
    except Exception:
        return {}
    bayrak = {(int(r.league_id), int(r.season)): bool(r.stats_players)
              for r in d.itertuples() if getattr(r, "type", "") == "League"}
    yok = {}
    for s, lg in tasks:
        if bayrak.get((int(lg["id"]), int(s))) is False:
            yok[(int(lg["id"]), int(s))] = lg["country"] + "/" + lg["name"] + " " + str(s)
    return yok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--only-season", type=int)
    args = ap.parse_args()

    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    leagues = sorted(cfg["leagues"], key=lambda x: x["priority"])
    seasons = [args.only_season] if args.only_season else cfg["seasons"]
    state = load_state()
    api = ApiFootball()

    tasks = [(s, lg) for s in seasons for lg in leagues]

    # OYUNCU ISTATISTIGI OLMAYAN lig-sezonlari ATLA (29 Agu 2026).
    # API /leagues yanitindaki "stats_players" bayragi DOGRU cikiyor: bozuk
    # buldugumuz dort lig-sezonun (Veikkausliiga 2022+2024, Liga Pro 2022,
    # Segunda Liga 2022, Superettan 2022) hepsinde bayrak False idi. Yani API
    # bize bastan soylemis, biz yine de yuzden fazla istek harcamisiz.
    #
    # Bayrak GUVENILIR bir OLUMSUZLUK filtresi ama kaliteyi garanti etmez:
    # Segunda Liga 2024 bayragi True oldugu halde sayimlari medyanin %15i
    # cikti (PLAN §21.3). Yeni lig eklerken bu ayrimi hatirla.
    atlanan = _istatistiksiz_atla(tasks)
    if atlanan:
        print("[atla]  " + str(len(atlanan)) + " lig-sezon: API oyuncu "
              "istatistigi yok (stats_players=False) - kota harcanmayacak")
        for ad in list(atlanan.values())[:6]:
            print("          " + ad)
        tasks = [(s, lg) for (s, lg) in tasks
                 if (int(lg["id"]), int(s)) not in atlanan]
    print(f"[kota]  bugun {api.used_today}/{api.daily_limit}, kalan {api.remaining}")
    print(f"[gorev] {len(tasks)} lig-sezon\n")

    if args.plan:
        done = sum(1 for s, lg in tasks
                   if state["leagues"].get(f"{lg['id']}:{s}", {}).get("complete"))
        # ~45 istek/lig-sezon (olculmus ortalama)
        est = (len(tasks) - done) * 45
        print(f"tamamlanan          : {done}/{len(tasks)} lig-sezon")
        print(f"tahmini kalan istek : ~{est}")
        print(f"tahmini kalan gun   : ~{est // api.daily_limit + 1}")
        for s, lg in tasks:
            k = f"{lg['id']}:{s}"
            e = state["leagues"].get(k, {})
            if e:
                nteams = len(e.get("teams", {}))
                tot = len(e.get("team_ids") or [])
                mark = "TAMAM" if e.get("complete") else f"{nteams}/{tot} takim"
                print(f"   {lg['country']}/{lg['name']} {s}: {mark}")
        return 0

    budget = Budget(args.budget if args.budget is not None else api.remaining)
    start = api.used_today

    try:
        for season, lg in tasks:
            do_league_season(api, state, lg, season, budget)
    except QuotaExhausted as exc:
        print(f"\n[dur]   {exc}")
    except Exception as exc:  # noqa: BLE001
        print(f"\n[HATA]  {type(exc).__name__}: {exc}")
        save_state(state)
        api.close()
        return 1

    save_state(state)
    done = sum(1 for s, lg in tasks
               if state["leagues"].get(f"{lg['id']}:{s}", {}).get("complete"))
    print(f"\n[ozet]  bu calistirmada {api.used_today - start} istek")
    print(f"[ozet]  tamamlanan: {done}/{len(tasks)} lig-sezon")
    print(f"[ozet]  bugun kalan kota: {api.remaining}")
    print("\nYarin ayni komutu calistir - kaldigi yerden devam eder.")
    api.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
