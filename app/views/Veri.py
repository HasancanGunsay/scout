"""Veri — toplama durumu ve eşleşme kuyruğu (FAZ 8.4).

8.4'e kadar iki ayrı sayfaydı ("Veri durumu", "Eşleşme kuyruğu"); ikisi de
sistemin bakım yüzü. Gövdeler app/_veri_durumu.py ve app/_eslesme.py'de.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _eslesme as ES
import _shared as sh
import _veri_durumu as VD
import streamlit as st

sh.page_setup("Veri", "Neyin ne kadar toplandığı, otomatik çalışmanın durumu, "
                      "API kotası, bilinen kör noktalar ve Transfermarkt "
                      "eşleşmesi bekleyen vakalar.", "database")

durum, kuyruk = st.tabs(["Durum", "Eşleşme kuyruğu"])
with durum:
    VD.goster()
with kuyruk:
    ES.goster()
