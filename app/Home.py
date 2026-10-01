"""Scout - uygulama girisi ve navigasyon.

Navigasyon st.navigation ile kuruluyor; boylece ikonlar Material Symbols
(emoji degil) ve sayfalar is akisina gore gruplaniyor:

  KESIF AKISI   Keşif -> Profil -> Karşılaştırma -> Shortlist
                (sistemin verdigi 10 -> senin sectigin 3 -> goz testi)
  ARAÇLAR       Laboratuvar (serbest sorgu)
  VERİ          Durum, eşleşme kuyruğu
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

st.set_page_config(
    page_title="Scout",
    page_icon=":material/sports_soccer:",
    layout="wide",
    initial_sidebar_state="expanded",
)

import _style as ui  # noqa: E402

ui.inject()

V = Path(__file__).resolve().parent / "views"

pages = {
    "Keşif akışı": [
        st.Page(V / "Kesif.py", title="Keşif", icon=":material/search:", default=True),
        st.Page(V / "Profil.py", title="Oyuncu profili", icon=":material/person:"),
        st.Page(V / "Karsilastirma.py", title="Karşılaştırma", icon=":material/balance:"),
        st.Page(V / "Yukselenler.py", title="Yükselenler", icon=":material/trending_up:"),
        st.Page(V / "Mevki_Siralamasi.py", title="Mevki sıralaması", icon=":material/leaderboard:"),
        st.Page(V / "Scout_Dosyasi.py", title="Scout dosyası", icon=":material/assignment:"),
        st.Page(V / "Shortlist.py", title="Shortlist & rapor", icon=":material/fact_check:"),
    ],
    "Araçlar": [
        st.Page(V / "Kadro_Analizi.py", title="Kadro analizi", icon=":material/stadium:"),
        st.Page(V / "Hesap_Defteri.py", title="Hesap defteri", icon=":material/history_edu:"),
        st.Page(V / "Laboratuvar.py", title="Laboratuvar", icon=":material/science:"),
    ],
    "Veri": [
        st.Page(V / "Veri_Durumu.py", title="Veri durumu", icon=":material/database:"),
        st.Page(V / "Eslesme_Kuyrugu.py", title="Eşleşme kuyruğu", icon=":material/link:"),
    ],
}

with st.sidebar:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:9px;padding:2px 0 14px">'
        '<div style="width:30px;height:30px;border-radius:7px;background:#1E40AF;'
        'display:flex;align-items:center;justify-content:center;color:#fff;'
        'font-weight:700;font-size:14px;font-family:Fira Code,monospace">S</div>'
        '<div><div style="font-weight:700;font-size:1rem;line-height:1.1">Scout</div>'
        '<div style="font-size:.7rem;color:#64748B;letter-spacing:.02em">'
        'yetenek keşif sistemi</div></div></div>',
        unsafe_allow_html=True,
    )

st.navigation(pages).run()
