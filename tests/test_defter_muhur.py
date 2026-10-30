"""Ileriye donuk defter: muhur dogrulama ve tek acilisli puanlama (FAZ 9.2)."""
import json

import numpy as np
import pandas as pd
import pytest

import scripts.tm_defter as td
from scout.model.tm_defter import dosya_parmak_izi, muhur_dogrula

GERCEK_CSV = td.CSV
GERCEK_MUHUR = td.MUHUR


def test_gercek_defter_muhurle_ayni():
    """Commit'li defter dosyasi muhurlendigi andan beri degismedi."""
    muhur_dogrula(GERCEK_CSV, json.loads(GERCEK_MUHUR.read_text(encoding="utf-8")))
    assert len(pd.read_csv(GERCEK_CSV)) == json.loads(
        GERCEK_MUHUR.read_text(encoding="utf-8"))["satir"]


def _sentetik(tmp_path, n=480, seed=0):
    rng = np.random.default_rng(seed)
    d = pd.DataFrame({
        "player_id": np.arange(n), "comp": rng.choice(["GB1", "ES1", "IT1"], n),
        "season": 2025, "pos_group": rng.choice(["Defender", "Midfielder", "Attacker"], n),
        "ucuz": rng.random(n) < .5,
    })
    gizli = rng.random(n)
    d["model_olasilik"] = np.clip(gizli + rng.normal(0, .2, n), .01, .99)
    for k in ["saf_olasilik", "basit_olasilik", "piyasa_olasilik"]:
        d[k] = np.clip(gizli + rng.normal(0, .4, n), .01, .99)
    csv = tmp_path / "defter.csv"
    d.to_csv(csv, index=False)
    muhur = tmp_path / "muhur.json"
    muhur.write_text(json.dumps({"sha256": dosya_parmak_izi(csv)}), encoding="utf-8")
    sonuc = d[["player_id", "comp", "season"]].assign(
        kademe=np.where(gizli > .5, 3, 1), pencere_tam=True)
    return csv, muhur, sonuc


def _yollar(tmp_path):
    return dict(acilis=tmp_path / "acilis.json", rapor=tmp_path / "rapor.md")


def test_tek_acilis_ikinci_puanlama_reddedilir(tmp_path, monkeypatch):
    monkeypatch.setattr(td, "tm_db_yolu", lambda: tmp_path / "2026-09-05" / "x.duckdb")
    csv, muhur, sonuc = _sentetik(tmp_path)
    y = _yollar(tmp_path)
    assert td.puanla_cmd(csv, muhur, sonuc=sonuc, B=40, **y) == 0
    assert y["acilis"].exists() and "P1 model - dakika+yas" in y["rapor"].read_text(encoding="utf-8")
    acilis = json.loads(y["acilis"].read_text(encoding="utf-8"))
    assert acilis["sonucu_gelen"] == len(sonuc)
    assert td.puanla_cmd(csv, muhur, sonuc=sonuc, B=40, **y) == 1      # ikinci kez: RED


def test_pencere_acikken_hicbir_sey_yazilmaz(tmp_path):
    csv, muhur, sonuc = _sentetik(tmp_path)
    y = _yollar(tmp_path)
    assert td.puanla_cmd(csv, muhur, sonuc=sonuc.assign(pencere_tam=False), **y) == 0
    assert not y["acilis"].exists() and not y["rapor"].exists()


def test_degistirilmis_defter_puanlanmaz(tmp_path):
    csv, muhur, sonuc = _sentetik(tmp_path)
    d = pd.read_csv(csv)
    d.loc[0, "model_olasilik"] = 0.99                    # sonradan "duzeltme"
    d.to_csv(csv, index=False)
    with pytest.raises(ValueError, match="degismis"):
        td.puanla_cmd(csv, muhur, sonuc=sonuc, **_yollar(tmp_path))
