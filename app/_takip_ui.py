"""Takip listesi arayüz parçaları (FAZ 8.2) — Havuz kartı ve Takip sayfası
aynı düğmeleri kullanır. Depolama: src/scout/takip.py.

Yazmalar Streamlit geri çağrılarında (on_click/on_change) yapılıyor: geri
çağrı betik yeniden çalışmadan ÖNCE işler, yani aynı tıklamada liste,
yıldız sütunu ve kart güncel görünür; not kutusu da kayıttan sonra boşalır.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import _havuz as HV
import _shared as sh
import _style as ui
from scout import takip as TK

DURUM_ADI = {"izle": "İzleniyor", "ilgilen": "İlgileniyorum",
             "oncelikli": "Öncelikli", "birakildi": "Bıraktım"}
DURUM_RENK = {"izle": "info", "ilgilen": "ok", "oncelikli": "warn",
              "birakildi": "mute"}


def tarih(zaman: str) -> str:
    """'2026-10-01T17:05:00' → '1 Eki 2026'."""
    AY = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl",
          "Eki", "Kas", "Ara"]
    t = pd.Timestamp(zaman)
    return f"{t.day} {AY[t.month - 1]} {t.year}"


def _al_cb(r: pd.Series) -> None:
    sh.takibe_al(r)
    st.toast(f"{r.oyuncu} takip listesine eklendi.", icon=":material/bookmark_added:")


def _durum_cb(kisi: str, key: str) -> None:
    yeni = st.session_state.get(key)
    if yeni:
        TK.durum_degistir(kisi, yeni)


def _not_cb(kisi: str, key: str) -> None:
    metin = (st.session_state.get(key) or "").strip()
    if metin:
        TK.not_ekle(kisi, metin)
        st.session_state[key] = ""
        st.toast("Not kaydedildi.", icon=":material/edit_note:")


def durum_secici(kisi: str, mevcut: str, yer: str) -> None:
    key = f"durum_{yer}_{kisi}"
    st.session_state[key] = mevcut       # liste başka yerde değiştiyse eşitle
    st.segmented_control(
        "Durum", TK.DURUMLAR, format_func=DURUM_ADI.get, key=key,
        required=True, on_change=_durum_cb, args=(kisi, key),
        help="Bıraktım = listede kalır; 'bıraktım, sonra yıldızlaştı' da "
             "öğretici bir kayıttır. Tamamen çıkarmak için Takip listesi.")


def not_girisi(kisi: str, yer: str) -> None:
    key = f"not_{yer}_{kisi}"
    a, b = st.columns([4, 1], vertical_alignment="bottom")
    a.text_input("Not ekle", key=key,
                 placeholder="ör. 12 Eki – Ajax maçı: baskı altında soğukkanlı")
    b.button("Kaydet", key=f"{key}_btn", on_click=_not_cb, args=(kisi, key),
             width="stretch")


def baglantilar(ad: str, kulup: str | None, profil: str | None) -> None:
    """Sofascore + Transfermarkt, yeni sekmede (8.3)."""
    a, b = st.columns(2)
    a.link_button("Sofascore", HV.sofascore_url(ad, kulup),
                  icon=":material/open_in_new:", width="stretch",
                  help=f"'{ad}'" + (f" + '{kulup}'" if kulup else "")
                       + " ile aranıp ilk sonuç açılır (DuckDuckGo).")
    b.link_button("Transfermarkt", HV.tm_url(profil, ad),
                  icon=":material/open_in_new:", width="stretch",
                  help="Eşleşmesi doğrulanmış oyuncuda profil; değilse arama."
                  if not (isinstance(profil, str) and profil) else
                  "Transfermarkt profili.")


def takip_kutusu(r: pd.Series) -> None:
    """Havuz kartının takip bölümü."""
    liste = sh.takip_listesi()
    if not TK.takipte(liste, r.kisi):
        st.button("Takibe al", icon=":material/bookmark_add:", type="primary",
                  key=f"takip_al_{r.anahtar}", on_click=_al_cb, args=(r,))
        if bool(r.sonuc_gorunur):
            st.caption("Bu sezonun sonucu belli: seçimin listende durur ama "
                       "hesap defterinde **göz testi sayılmaz**.")
        return
    k = liste["oyuncular"][r.kisi]
    ui.badges(("★ Takipte", "ok"), (DURUM_ADI[k["durum"]], DURUM_RENK[k["durum"]]),
              (f"Eklendi: {tarih(k['eklendi'])}", "mute"),
              (f"{len(k['notlar'])} not", "mute"))
    durum_secici(r.kisi, k["durum"], "havuz")
    not_girisi(r.kisi, "havuz")
    if st.button("Takip listesinde aç", icon=":material/bookmarks:",
                 key=f"takip_ac_{r.kisi}"):
        st.switch_page("views/Takip.py", query_params={"kisi": r.kisi})
