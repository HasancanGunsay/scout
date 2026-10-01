"""Veri sayfasi (8.4: Veri durumu + Esleme kuyrugu birlesti) acilir."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

pytestmark = pytest.mark.skipif(
    not ((ROOT / "data" / "scout.duckdb").exists()
         or (ROOT / "data" / "scout_ui_snapshot.duckdb").exists()),
    reason="veritabani yok")


def test_iki_sekme_de_acilir():
    at = AppTest.from_file(str(ROOT / "app" / "views" / "Veri.py"),
                           default_timeout=180)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert [t.label for t in at.tabs] == ["Durum", "Eşleşme kuyruğu"]
    metin = " ".join(str(m.value) for m in at.markdown)
    assert "Bilinen eksikler" in " ".join(str(s.value) for s in at.subheader)
    assert "Transfermarkt eşleşmesi" in metin
    assert any(m.label == "Kuyrukta" for m in at.metric)
