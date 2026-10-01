"""Egitim medyaniyla eksik-deger doldurma testleri (30 Eyl 2026 hatasi)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import train_model as tm  # noqa: E402


def test_tek_satir_egitim_medyaniyla_dolar():
    """ESKI HATA: tek satirlik tahminde medyan o satirin kendisiydi, eksik
    deger NaN kalip 0.0'a dusuyordu (score_age icin cok uc)."""
    tr = pd.DataFrame({"a": [10.0, 20.0, 30.0], "b": [1.0, 2.0, 3.0]})
    te = pd.DataFrame({"a": [np.nan], "b": [2.0]})
    X = tm._hazirla(te, ["a", "b"], ref=tr)
    assert X[0, 0] == 20.0            # egitim medyani, 0.0 degil


def test_ref_yoksa_geriye_uyumlu():
    d = pd.DataFrame({"a": [1.0, np.nan, 3.0]})
    assert tm._hazirla(d, ["a"])[1, 0] == 2.0


def test_test_kumesi_medyani_kullanilmaz():
    """Test dagilimindan bilgi sizmamali: cok farkli test medyani sonucu
    degistirmemeli."""
    tr = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
    te = pd.DataFrame({"a": [np.nan, 1000.0, 2000.0]})
    assert tm._hazirla(te, ["a"], ref=tr)[0, 0] == 2.0


def test_egitimde_tamamen_bos_sutun_sifira_duser():
    tr = pd.DataFrame({"a": [np.nan, np.nan]})
    te = pd.DataFrame({"a": [np.nan]})
    assert tm._hazirla(te, ["a"], ref=tr)[0, 0] == 0.0
