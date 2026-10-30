"""Atomik build kapisi (FAZ 9.5): yarim kalan zincir canli veritabanini degistirmez."""
import duckdb

from scout import build_kaydi as BK

BILINEN = ["toplama tamam", "bilinen saglayici eksigi"]


def test_karar_kurallari():
    assert BK.karar(False, BILINEN, BILINEN).gecis is False
    assert BK.karar(True, BILINEN, None).gecis is False             # denetim calismadi
    assert BK.karar(True, BILINEN, BILINEN).gecis is True          # bilinenler engellemez
    assert BK.karar(True, BILINEN, BILINEN[:1]).gecis is True      # duzelme de gecer
    k = BK.karar(True, BILINEN, BILINEN + ["player_scores bos"])
    assert k.gecis is False and k.yeni_kaldi == ["player_scores bos"]


def _db(yol, deger):
    con = duckdb.connect(str(yol))
    con.execute("CREATE OR REPLACE TABLE t AS SELECT ? AS v", [deger])
    con.close()


def _oku(yol):
    con = duckdb.connect(str(yol), read_only=True)
    v = con.sql("SELECT v FROM t").fetchone()[0]
    con.close()
    return v


def test_basarili_build_canliya_gecer_eskisi_prev(tmp_path):
    canli, kopya = tmp_path / "scout.duckdb", tmp_path / "scout.build.duckdb"
    _db(canli, "eski")
    BK.hazirla(canli, kopya)
    _db(kopya, "yeni")                                   # zincir kopyaya yazdi
    BK.uygula(BK.karar(True, BILINEN, BILINEN), canli, kopya)
    assert _oku(canli) == "yeni"
    assert _oku(tmp_path / "scout.prev.duckdb") == "eski"
    assert not kopya.exists()


def test_yarim_kalan_build_canliyi_degistirmez(tmp_path):
    canli, kopya = tmp_path / "scout.duckdb", tmp_path / "scout.build.duckdb"
    _db(canli, "eski")
    BK.hazirla(canli, kopya)
    _db(kopya, "yarim")
    BK.uygula(BK.karar(False, BILINEN, None), canli, kopya)
    assert _oku(canli) == "eski"
    assert _oku(tmp_path / "scout.red.duckdb") == "yarim"     # inceleme icin saklandi


ZINCIR = ["build_db.py", "build_features.py", "build_links.py", "build_scores.py",
          "build_outcomes.py", "build_sonra.py", "build_ranking.py", "build_emsal.py",
          "audit.py", "defter.py"]


def test_zincir_betikleri_scout_db_kullanir(tmp_path):
    """30 Eki 2026: build_db, SCOUT_DB'yi yok sayip canli dosyaya yazdi (OUT
    sabitti) ve paket yolunu eklemedigi icin coktu. Her zincir betigi, AYRI
    bir surecte ve kendi yol ayarlariyla yuklenince SCOUT_DB'ye yazmali."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    kok = Path(__file__).resolve().parents[1]
    hedef = tmp_path / "kopya.duckdb"
    kod = ("import runpy,sys,json; g=runpy.run_path(sys.argv[1], run_name='yukleme'); "
           "print(json.dumps(str(g.get('OUT') or g.get('DB'))))")
    env = {**os.environ, "SCOUT_DB": str(hedef), "PYTHONIOENCODING": "utf-8"}
    for b in ZINCIR:
        r = subprocess.run([sys.executable, "-c", kod, str(kok / "scripts" / b)],
                           cwd=tmp_path, env=env, capture_output=True, text=True,
                           encoding="utf-8")
        assert r.returncode == 0, f"{b} yuklenemedi:\n{r.stderr[-600:]}"
        import json
        assert json.loads(r.stdout.strip().splitlines()[-1]) == str(hedef), \
            f"{b} SCOUT_DB'yi kullanmiyor: {r.stdout[-200:]}"


def test_betiklerde_sabit_canli_yol_yok():
    from pathlib import Path

    kok = Path(__file__).resolve().parents[1]
    for f in sorted((kok / "scripts").glob("*.py")):
        t = f.read_text(encoding="utf-8")
        assert '"scout.duckdb"' not in t, f"{f.name}: sabit veritabani yolu (db_yolu kullan)"


def test_kayit_append_only(tmp_path):
    kayit = tmp_path / "build_kaydi.csv"
    for z in (True, False):
        k = BK.karar(z, BILINEN, BILINEN)
        BK.kayit_yaz(kayit, BK.satir("id", "bas", z, "", "2026-07-11", BILINEN, BILINEN, k))
    satirlar = kayit.read_text(encoding="utf-8").strip().splitlines()
    assert len(satirlar) == 3 and satirlar[0].startswith("build_id")
