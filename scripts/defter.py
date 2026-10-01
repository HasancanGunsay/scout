"""FAZ 5: hesap defteri - iddiayi kaydet, sonuc gelince puanla.

    python scripts/defter.py --kaydet          # bugunku iddialari yaz
    python scripts/defter.py --rapor           # sicil raporu
    python scripts/defter.py --kaydet --rapor

DEFTER APPEND-ONLY. Ayni gun ayni oyuncu iki kez yazilmaz; gecmis kayit
ASLA guncellenmez. Bir iddianin degeri, geri alinamamasindan gelir.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout.model.defter import (SUTUNLAR, bolumle,  # noqa: E402
                                disaridan_degerlendirme, eski_iddia_sayisi,
                                iddia_kaydi, kalibrasyon, kullanici_ortusmesi,
                                nerede_yaniliyor, puanla)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = ROOT / "data" / "scout.duckdb"
ILK_N = 50           # her sezon-kapsam icin kac iddia kaydedilsin
YEDEK = ROOT / "data" / "defter" / "iddia_defteri.csv"   # git'te izlenir


def yedekle(con) -> None:
    """Defter YENIDEN URETILEMEZ (kayit_tarihi). DB gitignore'da oldugu icin
    her kayittan sonra surum kontrolundeki CSV'ye aynalanir."""
    d = _defteri_oku(con)
    if d.empty:
        return
    YEDEK.parent.mkdir(parents=True, exist_ok=True)
    d.sort_values(["kayit_tarihi", "season", "player_id", "league_id"]).to_csv(
        YEDEK, index=False, encoding="utf-8", lineterminator="\n")
    print(f"[yedek] {len(d):,} satir -> {YEDEK.relative_to(ROOT)}")


def _defteri_oku(con) -> pd.DataFrame:
    try:
        return con.sql("SELECT * FROM iddia_defteri").df()
    except Exception:
        return pd.DataFrame(columns=SUTUNLAR)


def sema_guncelle(con) -> None:
    """7.0 oncesi defterde tahmin_turu sutunu yok; eklenir. Eski satirlar
    NULL kalir (= uretim modeli, orneklem ici). Gecmis kayit DEGISMEZ."""
    try:
        con.execute("ALTER TABLE iddia_defteri "
                    "ADD COLUMN IF NOT EXISTS tahmin_turu VARCHAR")
    except duckdb.CatalogException:
        pass                                   # defter henuz yok


def kaydet(con) -> int:
    """Bugunku en guclu iddialari deftere yaz. Yinelenenleri atla."""
    aday = con.sql(f"""
        SELECT o.player_id, o.league_id, o.season, o.player_name,
               o.league_name, o.kapsam, m.model_olasilik, m.tahmin_turu,
               e.oran, e.lig_taban,
               row_number() OVER (PARTITION BY o.season, o.kapsam
                                  ORDER BY m.model_olasilik DESC) rn
        FROM player_outcome o
        JOIN player_tahmin m USING (player_id, league_id, season)
        LEFT JOIN player_emsal e USING (player_id, league_id, season)
        WHERE o.age_season_end < 23 AND o.minutes >= 450
    """).df()
    aday = aday[aday.rn <= ILK_N]

    eski = _defteri_oku(con)
    if len(eski):
        var = set(zip(eski.player_id, eski.league_id, eski.season))
        aday = aday[[(a, b, c) not in var for a, b, c
                     in zip(aday.player_id, aday.league_id, aday.season)]]
    if aday.empty:
        print("[kaydet] yeni iddia yok - hepsi zaten defterde")
        return 0

    yeni = pd.DataFrame([iddia_kaydi(r) for _, r in aday.iterrows()])
    con.register("yeni", yeni)
    con.execute("""CREATE TABLE IF NOT EXISTS iddia_defteri AS
                   SELECT * FROM yeni WHERE 1=0""")
    con.execute("INSERT INTO iddia_defteri BY NAME SELECT * FROM yeni")
    print(f"[kaydet] {len(yeni):,} yeni iddia deftere yazildi")
    return len(yeni)


def rapor(con) -> None:
    defter = _defteri_oku(con)
    if defter.empty:
        print("[rapor] defter bos - once --kaydet")
        return
    sonuc = con.sql("""SELECT player_id, league_id, season, sezon_bitis,
                              kademe, gozlem_ay, age_season_end, league_name
                       FROM player_outcome""").df()
    b = bolumle(defter, sonuc.drop(columns="league_name"))
    pro = puanla(b["prospektif"])
    # 7.0: gecmise donuk rapor defterin (orneklem ici) iddialarindan DEGIL,
    # disaridan tahminlerden
    retro = disaridan_degerlendirme(
        con.sql("SELECT * FROM player_tahmin").df(), sonuc)

    print(f"\n{'=' * 70}")
    print("HESAP DEFTERI")
    print("=" * 70)
    print(f"  toplam iddia            : {len(defter):,}")
    print(f"  GECMISE DONUK (sonuc zaten biliniyordu) : "
          f"{len(b['retrospektif']):,}  (7.0 oncesi, orneklem ici: "
          f"{eski_iddia_sayisi(defter):,})")
    print(f"  ILERIYE DONUK (sonuc bekleniyor)        : {len(pro):,}")

    if len(retro):
        print(f"\n--- GECMISE DONUK: KALIBRASYON RAPORU ---")
        print("    DIKKAT: bu bir SICIL DEGIL; sonuc zaten biliniyor. Kaynak:")
        print(f"    player_tahmin - DISARIDAN tahminler ({len(retro):,} satir),")
        print("    defterin orneklem ici iddialari DEGIL. Isi: modelin NEREDE")
        print("    yanildigini cevabi bilmeyen modelle gostermek.")
        k = kalibrasyon(retro)
        if len(k):
            print("\n  model ne dedi / ne oldu:")
            print(k.to_string(index=False))

        for boyut, ad in [("kapsam", "kapsam"), ("league_name", "lig")]:
            n = nerede_yaniliyor(retro, boyut)
            if len(n):
                print(f"\n  nerede yaniliyor ({ad}) - sapma>0 = model FAZLA umutlu:")
                print(n.head(8).to_string(index=False))

    if len(pro):
        print(f"\n--- ILERIYE DONUK DEFTER ---")
        bekleyen = pro[pro.gerceklesti.isna()]
        gelen = pro[pro.gerceklesti.notna()]
        print(f"  sonucu bekleyen : {len(bekleyen):,}")
        print(f"  sonucu gelen    : {len(gelen):,}")
        if len(gelen) >= 20:
            print(f"  GERCEK ISABET   : %{100 * gelen.gerceklesti.mean():.1f} "
                  f"(model ortalamasi %{100 * gelen.model_olasilik.mean():.1f})")
        elif len(gelen):
            print("  (henuz sicil raporu icin cok az - en az 20 gerekiyor)")
    else:
        print("\n--- ILERIYE DONUK DEFTER ---")
        print("  Bos. BU NORMAL: elimizdeki en yeni sezon 2024 ve onun")
        print("  12 aylik penceresi kapandi. 2025 API'de acilinca dolar.")

    # kullanici secimleriyle ortusme (8.2: takip listesi; shortlist.json
    # hic olusmamisti). GERIYE DONUK: secerken sonuc ekrandaydi.
    from scout import takip
    sl = takip.api_secimleri(takip.yukle())
    if sl:
        o = kullanici_ortusmesi(sl, pd.concat([retro, pro]))
        if o.get("n"):
            print(f"\n--- SENIN SECIMLERIN (geriye donuk, goz testi DEGIL) ---")
            print(f"  takipte defterde olan      : {o['n']}")
            print(f"  ortalama model olasiligi   : %{100 * o['ort_model']:.1f} "
                  f"(defter geneli %{100 * o['ort_model_geneli']:.1f})")
            if o.get("gerceklesme") is not None:
                print(f"  gerceklesme                : "
                      f"%{100 * o['gerceklesme']:.1f} "
                      f"(defter geneli %{100 * o['gerceklesme_geneli']:.1f})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kaydet", action="store_true")
    ap.add_argument("--rapor", action="store_true")
    a = ap.parse_args()
    if not (a.kaydet or a.rapor):
        a.rapor = True

    con = duckdb.connect(str(DB))
    sema_guncelle(con)
    if a.kaydet:
        kaydet(con)
        yedekle(con)
    if a.rapor:
        rapor(con)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
