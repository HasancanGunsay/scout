"""Hesap Defteri — sistem ne dedi, ne oldu (FAZ 5).

Bir scout ekibini EKİP yapan şey, iddiasının kaydının tutulmasıdır.
Bu sayfadan önce hiçbir iddiamız yazılı değildi, dolayısıyla hiçbiri
yanlışlanamıyordu.

İKİ BÖLÜM VE ARALARINDAKİ FARK KRİTİK — ayrıntı: src/scout/model/defter.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _shared as sh
import _style as ui
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from scout.model.defter import (bolumle,  # noqa: E402
                                disaridan_degerlendirme, eski_iddia_sayisi,
                                kalibrasyon, kullanici_ortusmesi,
                                nerede_yaniliyor, puanla)

sh.page_setup(
    "Hesap Defteri",
    "Sistem ne dedi, ne oldu. İddianın değeri geri alınamamasından gelir.",
    "history_edu",
)


@st.cache_data(ttl=300)
def _defter():
    con = sh._con()
    try:
        d = con.sql("SELECT * FROM iddia_defteri").df()
    except Exception:
        return None, None, None
    s = con.sql("""SELECT player_id, league_id, season, sezon_bitis, kademe,
                          gozlem_ay, age_season_end, league_name
                   FROM player_outcome""").df()
    try:
        t = con.sql("SELECT * FROM player_tahmin").df()
    except Exception:
        t = None
    return d, s, t


defter, sonuc, tahmin = _defter()
if defter is None or defter.empty:
    ui.empty_state(
        "Defter boş",
        "Önce `python scripts/defter.py --kaydet` çalıştırılmalı.",
    )
    st.stop()

b = bolumle(defter, sonuc.drop(columns="league_name"))
pro = puanla(b["prospektif"])
# 7.0: kalibrasyon raporu defterin iddialarindan DEGIL, disaridan tahminlerden
retro = (disaridan_degerlendirme(tahmin, sonuc) if tahmin is not None
         else pd.DataFrame())
eski = eski_iddia_sayisi(defter)

c1, c2, c3 = st.columns(3)
c1.metric("Toplam iddia", f"{len(defter):,}")
c2.metric("Geçmişe dönük", f"{len(b['retrospektif']):,}",
          help="Kayıt anında sonuç zaten biliniyordu. Sicil DEĞİL. "
               f"Bunların {eski}'i, sezonu eğitimde görmüş modelle kaydedildi "
               "(Faz 7.0 öncesi); kalibrasyon raporunda kullanılmıyor.")
c3.metric("İleriye dönük", f"{len(pro):,}",
          help="Kayıt anında sonuç bilinmiyordu. Gerçek sicil budur.")

# ------------------------------------------------------- İLERİYE DÖNÜK
ui.section("İleriye dönük defter", "Gerçek sicil. Kayıt anında sonuç "
                                   "bilinmiyordu.")
if pro.empty:
    st.info(
        "**Boş — ve bu normal.** Elimizdeki en yeni sezon 2024 ve onun "
        "12 aylık sonuç penceresi kapandı. 2025 sezonu ücretsiz API'de "
        "açıldığında (30 günde bir sınanıyor) bu bölüm dolmaya başlar. "
        "O güne kadar aşağıdaki bölüm bir **sicil değil, kalibrasyon "
        "raporudur**."
    )
else:
    gelen = pro[pro.gerceklesti.notna()]
    st.metric("Sonucu bekleyen", f"{len(pro) - len(gelen):,}")
    if len(gelen) >= 20:
        st.metric("Gerçek isabet", f"%{100 * gelen.gerceklesti.mean():.1f}",
                  delta=f"model %{100 * gelen.model_olasilik.mean():.1f} demişti")
    elif len(gelen):
        st.caption(f"{len(gelen)} sonuç geldi — sicil için en az 20 gerekiyor.")

# ------------------------------------------------------ GEÇMİŞE DÖNÜK
ui.section("Geçmişe dönük kalibrasyon",
           "Modelin nerede yanıldığını gösterir.")
# Sayfanin EN ONEMLI cekincesi - ui.section alt metni fazla sessiz kaliyor,
# uyari olarak veriliyor.
st.warning(
    "**Bu bir sicil DEĞİL, başarı iddiası DEĞİL** — 2022-24'ün sonucu zaten "
    "biliniyor. Buradaki sayılar yalnızca modelin **nerede yanıldığını** "
    "gösterir. Gerçek sicil, yukarıdaki ileriye dönük bölümde birikecek."
)
st.caption(
    f"Kaynak: {len(retro):,} **dışarıdan** tahmin — her oyuncunun olasılığı, "
    "o ligi ya da o sezonu hiç görmemiş modelden geliyor. Defterdeki eski "
    "iddialar (sezonu eğitimde görmüş modelle kaydedildikleri için iyimser) "
    "bu rapora girmiyor."
)

if retro.empty:
    st.caption("Geçmişe dönük kayıt yok.")
    st.stop()

k = kalibrasyon(retro)
if len(k):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines",
                             line=dict(dash="dash", color="#94A3B8"),
                             name="kusursuz kalibrasyon"))
    fig.add_trace(go.Scatter(x=k.dedi, y=k.oldu, mode="markers+lines",
                             marker=dict(size=11, color="#1E40AF"),
                             text=[f"n={int(n)}" for n in k.n],
                             hovertemplate="model dedi %{x:.2f}<br>"
                                           "gerçekleşen %{y:.2f}<br>"
                                           "%{text}<extra></extra>",
                             name="gözlenen"))
    fig.update_layout(height=380, xaxis_title="model ne dedi",
                      yaxis_title="ne oldu",
                      margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(ui.apply_plotly(fig), width="stretch")
    st.caption("Köşegenin **altında** kalan nokta = model fazla umutlu.")

st.markdown("**Nerede yanılıyor?** `sapma > 0` = model fazla umutlu.")
for boyut, ad in [("kapsam", "Lig türü"), ("league_name", "Lig"),
                  ("season", "Sezon")]:
    n = nerede_yaniliyor(retro, boyut)
    if len(n):
        with st.expander(ad, expanded=(boyut == "kapsam")):
            st.dataframe(
                n.rename(columns={boyut: ad, "dedi": "model dedi",
                                  "oldu": "gerçekleşen"})
                 .style.format({"model dedi": "{:.2f}",
                                "gerçekleşen": "{:.2f}",
                                "sapma": "{:+.3f}"}),
                width="stretch", hide_index=True)

# --------------------------------------------------- SENİN SEÇİMLERİN
ui.section("Senin seçimlerin",
           "Bir scout ekibinde asıl öğrenme burada: sistem ve insan nerede "
           "ayrışıyor, ayrışınca kim haklı çıkıyor.")
# 8.2: kaynak takip listesi. İki ayrı soru, iki ayrı kutu:
#   ileriye dönük = sonuç belli DEĞİLKEN seçtiklerin -> göz testinin sınavı
#   geriye dönük  = sonuç ekrandayken seçtiklerin   -> yalnız döküm
from scout import takip as TK  # noqa: E402
from scout.model.tm_defter import PENCERE_BITIS  # noqa: E402

liste = sh.takip_listesi()
secimler = list(liste["oyuncular"].values())
if not secimler:
    st.caption("Takip listen boş. Havuz'dan oyuncu takibe aldıkça bu bölüm "
               "dolar.")
else:
    st.markdown("**İleriye dönük — göz testinin sınavı**")
    ileri = [k for k in secimler if not k["ilk"]["sonuc_gorunur"]]
    if not ileri:
        st.caption("Henüz yok. Sonucu belli olmayan sezondan (2025/26 "
                   "havuzu) takibe aldıkların burada sayılır.")
    else:
        tm = sh.havuz_tm()
        p_sec = [k["ilk"]["model_olasilik"] for k in ileri
                 if k["ilk"]["model_olasilik"] is not None]
        a, bb, c = st.columns(3)
        a.metric("Seçimin", len(ileri))
        if p_sec and len(tm):
            bb.metric("Seçtiklerinin model ortalaması",
                      f"%{100 * sum(p_sec) / len(p_sec):.0f}",
                      delta=f"havuz geneli %{100 * tm.model_olasilik.mean():.0f}",
                      delta_color="off")
        c.metric("Puanlanacağı tarih", PENCERE_BITIS.strftime("%d.%m.%Y"),
                 help="Sonuç penceresi kapanınca, TM defteriyle aynı gün "
                      "puanlanır. Sistemin aynı oyuncular için ne dediği de "
                      "kayıtlı: kim haklı çıktı, o zaman görülecek.")
        dag = pd.Series([k["durum"] for k in ileri]).value_counts()
        AD = {"izle": "izleniyor", "ilgilen": "ilgileniyorum",
              "oncelikli": "öncelikli", "birakildi": "bıraktım"}
        st.caption("Durumların: " + " · ".join(
            f"{AD[d]} {n}" for d, n in dag.items()))

    st.markdown("**Geriye dönük — döküm, göz testi değil**")
    o = kullanici_ortusmesi(TK.api_secimleri(liste), pd.concat([retro, pro]))
    if not o.get("n"):
        st.caption("2022–24 havuzundan takibe aldığın oyuncu yok.")
    else:
        a, bb = st.columns(2)
        a.metric("Seçtiklerinin model ortalaması",
                 f"%{100 * o['ort_model']:.0f}",
                 delta=f"tüm oyuncular %{100 * o['ort_model_geneli']:.0f}",
                 delta_color="off")
        if o.get("gerceklesme") is not None:
            bb.metric("Seçtiklerinin gerçekleşmesi",
                      f"%{100 * o['gerceklesme']:.0f}",
                      delta=f"tüm oyuncular %{100 * o['gerceklesme_geneli']:.0f}",
                      delta_color="off")
        st.caption(f"{o['n']} oyuncu eşleşti. Bunları seçerken 12 aylık "
                   "sonuç belliydi (Havuz'da da görünüyor). Bu oranlar senin "
                   "gözünü değil, seçtiğin oyuncuların profilini anlatır.")
