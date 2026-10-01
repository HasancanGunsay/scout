"""Kesif sayfasi: mevki + rol secimi (1 Eki 2026, kullanici: "rol
degistiremiyorum"). Secici kenar cubugunda 23 ligin altinda kaliyordu;
sayfanin ustune alindi. Sinanan: rol degisince siralama o sablonla
yapiliyor, mevki degisince o mevkinin rolleri geliyor."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAYFA = ROOT / "app" / "views" / "Kesif.py"
veri_var = pytest.mark.skipif(
    not ((ROOT / "data" / "scout.duckdb").exists()
         or (ROOT / "data" / "scout_ui_snapshot.duckdb").exists()),
    reason="veritabani yok")

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402


def _bg(at, etiket):
    return [b for b in at.get("button_group") if b.label == etiket][0]


@veri_var
def test_rol_ve_mevki_sayfanin_ustunde_degisir():
    at = AppTest.from_file(str(SAYFA), default_timeout=180)
    at.run()
    assert not at.exception
    rol = _bg(at, "Rol (puanlama şablonu)")
    hedef = rol.options[-1]
    rol.set_value(hedef).run()
    assert not at.exception
    assert [m for m in at.metric if m.label == "Rol"][0].value == hedef

    _bg(at, "Mevki").set_value("Defender").run()
    assert not at.exception
    secenek = _bg(at, "Rol (puanlama şablonu)").options
    assert secenek and all(s.startswith(("Stoper", "Bek")) for s in secenek)
    assert [m for m in at.metric if m.label == "Rol"][0].value == secenek[0]
