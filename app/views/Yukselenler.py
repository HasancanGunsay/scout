"""Yükselenler - sezonlar arası gelişim eğrisi (ADIM 6).

Wonderkid avında tek bir sezonun fotoğrafı değil YÖNÜ önemli:
18 yaşında 70 alıp 20 yaşında 88 alan oyuncu, iki sezondur 85 alandan
daha güçlü bir sinyaldir.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _shared as sh
import _style as ui
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sh.page_setup(
    "Yükselenler",
    "Aynı oyuncunun iki sezonu. Skorun kendisi değil, DEĞİŞİMİ. "
    "Karşılaştırma her zaman sabit rol üzerinden yapılır.",
    "trending_up",
)

g = sh.gelisim_tablosu()
if g.empty:
    ui.empty_state(
        "Gelişim verisi yok",
        "İki sezonda da yeterli dakika oynamış oyuncu bulunamadı. "
        "2022 sezonunun toplanması sürüyor olabilir.",
    )
    st.stop()

# ------------------------------------------------------------------ filtreler
with st.sidebar:
    st.header("Filtreler")
    yas_max = st.slider("2022'deki azami yaş", 16.0, 40.0, 23.0, 0.5)
    min_dk = st.slider("Her iki sezonda asgari dakika", 450, 3000, 900, 50)
    sadece_ayni_lig = st.checkbox(
        "Sadece aynı ligde kalanlar", False,
        help="Lig değiştirenlerde skor farkı, kohortun değişmesinden de "
             "kaynaklanabilir. Ölçüldü: ortalamada fark yok (−5,38 vs −5,42), "
             "ama tek tek oyuncuda etkili olabilir.",
    )
    sadece_ayni_rol = st.checkbox(
        "Sadece doğal rolü değişmeyenler", False,
        help="Doğal rolü değişen oyuncuda karşılaştırma sabit rol üzerinden "
             "yapılır ama yorum zorlaşır — oyuncu artık başka bir iş yapıyor.",
    )
    # SEVIYE FILTRESI - olculdu, kritik (§27): yukselis TEK BASINA zayif
    # bir sinyal (1,19-1,28x), mevcut seviye ondan hep daha iyi (1,35-1,81x).
    # Ama SEVIYE SABITKEN yukselis ek bilgi katiyor (+6,7 / +10,0 puan).
    # Dogru kullanim: once seviyeye gore ele, sonra yukselise gore sirala.
    # Varsayilan filtre bu akisi zorunlu kiliyor.
    min_skor = st.slider(
        "Asgari 2024 skoru", 0, 90, 60, 5,
        help="Önce seviyeye göre ele, sonra yükselişe göre sırala. "
             "Yükseliş tek başına zayıf bir sinyal; iyi oyuncular arasında "
             "ayırt edici. Ölçüm için PLAN §27.",
    )
    yon = st.radio("Sırala", ["En çok yükselenler", "En çok düşenler"],
                   horizontal=False)

alt = g[(g.age_season_end_0 <= yas_max)
        & (g.minutes_0 >= min_dk) & (g.minutes_1 >= min_dk)]
if sadece_ayni_lig:
    alt = alt[~alt.lig_degisti]
if sadece_ayni_rol and "dogal_rol_degisti" in alt.columns:
    alt = alt[~alt.dogal_rol_degisti]
alt = alt[alt.score_1 >= min_skor]

if alt.empty:
    ui.empty_state("Filtrelere uyan oyuncu yok", "Yaş veya dakika sınırını gevşet.")
    st.stop()

alt = alt.sort_values("gelisim", ascending=(yon == "En çok düşenler"))

k = st.columns(4)
k[0].metric("Oyuncu", f"{len(alt)}")
k[1].metric("Medyan değişim", f"{alt.gelisim.median():+.1f}")
k[2].metric("Lig değiştiren", f"{int(alt.lig_degisti.sum())}")
k[3].metric("Rolü değişen",
            f"{int(alt.dogal_rol_degisti.sum())}"
            if "dogal_rol_degisti" in alt.columns else "—")

ui.badges(("Sabit rol üzerinden", "info"),
          (f"≤{yas_max:g} yaş (2022)", "mute"),
          (f"≥{min_dk} dk × 2 sezon", "mute"))

st.warning(
    "**Yükseliş tek başına zayıf bir sinyaldir — ölçüldü (PLAN §27).** "
    "2022→2023 yükselişiyle 2024 sonucunu tahmin ettik: lig terfisinde "
    "1,28×, piyasa değeri artışında 0,99× (yani şans seviyesi). Aynı testte "
    "**mevcut skor 1,81× ve 1,37×** ile hep önde. Bir sezonluk yükselişin "
    "büyük kısmı ortalamaya dönüş. "
    "**Ama seviye sabitken yükseliş ek bilgi katıyor** (+6,7 ve +10,0 puan). "
    "Bu yüzden kenar çubuğunda **asgari skor filtresi** var: önce seviyeye "
    "göre ele, sonra yükselişe göre sırala. Bu listeyi tek başına keşif "
    "aracı olarak kullanma.",
    icon=":material/warning:",
)

st.info(
    "**Sıfır çizgisi ~0'dır, mutlak değer değil sıralama önemli.** Rol her "
    "oyuncu için iki sezonun ortalamasını en yükseğe çıkaran rolde "
    "sabitlenir — tek bir sezona sabitlemek sonucu kurgu gereği kaydırıyordu "
    "(ölçüldü: −5,4 ve +3,9, aynı veriyle ters işaret). Ayrıntı: PLAN §24.",
    icon=":material/info:",
)

# ------------------------------------------------------------------ tablo
gos = alt.head(50).copy()
gos["Oyuncu"] = gos.player_name_0
gos["Yaş (2022)"] = gos.age_season_end_0.round(1)
gos["Rol"] = gos.role_name_0
gos["2022"] = gos.score_0.round(1)
gos["2024"] = gos.score_1.round(1)
gos["Değişim"] = gos.gelisim.round(1)
gos["Lig (2022→2024)"] = gos.apply(
    lambda r: r.league_name_0 if r.league_name_0 == r.league_name_1
    else f"{r.league_name_0} → {r.league_name_1}", axis=1)
gos["Takım (2024)"] = gos.team_name_1

st.dataframe(
    gos[["Oyuncu", "Yaş (2022)", "Rol", "Lig (2022→2024)", "Takım (2024)",
         "2022", "2024", "Değişim"]],
    hide_index=True, width="stretch", height=460,
    column_config={
        "Değişim": st.column_config.NumberColumn(
            "Değişim", format="%+.1f",
            help="Sabit rolde 2024 skoru eksi 2022 skoru."),
        "2022": st.column_config.ProgressColumn("2022", min_value=0, max_value=100,
                                                format="%.0f"),
        "2024": st.column_config.ProgressColumn("2024", min_value=0, max_value=100,
                                                format="%.0f"),
    },
)

# ------------------------------------------------------------------ grafik
st.subheader("İlk 15 — iki sezonun yolu")
ilk = alt.head(15)
fig = go.Figure()
for r in ilk.itertuples():
    fig.add_trace(go.Scatter(
        x=[2022, 2024], y=[r.score_0, r.score_1], mode="lines+markers",
        name=r.player_name_0, hovertemplate="%{y:.1f}<extra>" + r.player_name_0 + "</extra>",
    ))
fig.update_layout(xaxis=dict(tickvals=[2022, 2024], title=None),
                  yaxis=dict(title="Skor (sabit rol)", range=[0, 100]),
                  height=430, showlegend=True,
                  legend=dict(font=dict(size=11)))
st.plotly_chart(ui.apply_plotly(fig), width="stretch")
