"""Scout - uygulama girisi ve navigasyon.

Navigasyon st.navigation ile kuruluyor; boylece ikonlar Material Symbols
(emoji degil) ve sayfalar is akisina gore gruplaniyor:

  SCOUT    Havuz -> Takip listesi -> Oyuncu -> Karşılaştırma
           (okyanustan havuz -> senin sectiklerin -> goz testi)
  ANALİZ   Keşif (rol şablonu), Mevki sıralaması, Yükselenler, Kadro, Laboratuvar
  SİSTEM   Hesap defteri, Veri (durum + eşleşme kuyruğu)
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

# 8.4: 13 sayfa -> 11, uc grup. Gunluk is akisi en ustte:
#   Scout   havuzdan sec -> takibe al -> oyuncuyu incele -> yan yana koy
#   Analiz  farkli merceklerle arama (rol sablonu, mevki, gelisim, kadro)
#   Sistem  sistemin karnesi ve bakimi
pages = {
    "Scout": [
        # 8.1: havuz giris sayfasi - kullanicinin vizyonu "tek isim degil, havuz"
        st.Page(V / "Havuz.py", title="Havuz", icon=":material/waves:", default=True),
        # 8.2: eski "Shortlist & rapor"un yerine (rapor formu buraya tasindi)
        st.Page(V / "Takip.py", title="Takip listesi", icon=":material/bookmarks:"),
        # 8.4: Profil + Scout dosyasi tek sayfa (sekmeler)
        st.Page(V / "Oyuncu.py", title="Oyuncu", icon=":material/person:"),
        st.Page(V / "Karsilastirma.py", title="Karşılaştırma", icon=":material/balance:"),
    ],
    "Analiz": [
        st.Page(V / "Kesif.py", title="Keşif (rol şablonu)", icon=":material/search:"),
        st.Page(V / "Mevki_Siralamasi.py", title="Mevki sıralaması", icon=":material/leaderboard:"),
        st.Page(V / "Yukselenler.py", title="Yükselenler", icon=":material/trending_up:"),
        st.Page(V / "Kadro_Analizi.py", title="Kadro analizi", icon=":material/stadium:"),
        st.Page(V / "Laboratuvar.py", title="Laboratuvar", icon=":material/science:"),
    ],
    "Sistem": [
        st.Page(V / "Hesap_Defteri.py", title="Hesap defteri", icon=":material/history_edu:"),
        # 8.4: Veri durumu + Esleme kuyrugu tek sayfa (sekmeler)
        st.Page(V / "Veri.py", title="Veri", icon=":material/database:"),
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

st.navigation(pages, expanded=True).run()
