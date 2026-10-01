"""Kadro Analizi - bir takımın rol haritası, eksikleri, kim kimin yerine oynar (ADIM 6).

Keşif sayfası "kim iyi" diye sorar. Bu sayfa "BİZE KİM LAZIM" diye sorar.
İkisi aynı soru değil: ligin en iyi ön liberosu, zaten iki tane ön liberosu
olan takım için bir şey ifade etmez.

ÖLÇÜM NASIL KURULDU
  Rol skorları zaten (lig, sezon, mevki) kohortu içinde percentile.
  Dolayısıyla AYNI LİG İÇİNDE takım-takım kıyas meşru: elmayla elma.
  Karşılaştırma tabanı "ligin ortalama takımının o roldeki EN İYİSİ" -
  yani her takımın o roldeki en iyi oyuncusunun medyanı. Takım seviyesinde
  taban almak gerekiyor, çünkü oyuncu seviyesinde medyan almak yedekleri
  de sayar ve tabanı yapay olarak aşağı çeker.

  Bu sayfa LİGLER ARASI kıyas YAPMAZ. Lig gücü düzeltmesi geriye dönük
  testte sonucu kötüleştiriyordu (§23), o yüzden skora uygulanmıyor.

"KIM KIMIN YERINE OYNAR" - ÖLÇÜLDÜ (§35)
  İlk sürümde "doğrulanamaz" yazıyordu. Yanlıştı: doğrulanabilir bir sonuç
  değişkeni var - KULÜPLERİN KENDİ DAVRANIŞI. Bir rolün en iyisi ayrıldığında
  yerine gelen, ligdeki rastgele bir aynı-mevki oyuncusundan daha mı benzer
  stilde? 2.510 değişimde EVET: gelenin yüzdelik sırası 0,406 (0,50 rastgele),
  %95 GA [0,394 , 0,417].

  AMA mevkiye göre çarpıcı biçimde değişiyor ve KALECİDE TERSİNE DÖNÜYOR
  (-0,170, GA tamamı negatif). Sayfa mevkiye göre ölçümü açıktan gösteriyor;
  kalecide kırmızı uyarı veriyor.

EŞİK ±12 - ÖLÇÜLDÜ (§35)
  İlk sürümde ±8'di ve bir varsayımdı. Kadrosu değişmemiş takım-rol
  çiftlerinde fark sezonlar arası kendiliğinden oynuyor; ±8 bandı bu
  vakaların yalnızca %51'ini kapsıyordu.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _shared as sh
import _style as ui
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from scout.features.squad import ESIK  # noqa: E402
from scout.features.squad import rol_haritasi as kadro_rol_haritasi  # noqa: E402
from scout.features.squad import yas_profili  # noqa: E402
from scout.features.squad import yedek_benzerligi_notu  # noqa: E402

sh.page_setup(
    "Kadro Analizi",
    "Bir takımın rol haritası. Nerede güçlü, nerede boşluk var, "
    "kim kimin yerine oynar.",
    "stadium",
)

nat = sh.load_natural()
scores = sh.load_scores()
if scores.empty:
    ui.empty_state("Skor verisi yok", "Önce build_scores.py çalıştırılmalı.")
    st.stop()

# ------------------------------------------------------------------ seçim
with st.sidebar:
    st.header("Takım")

    ligler = (nat[["league_id", "league_name", "country"]]
              .drop_duplicates().sort_values(["country", "league_name"]))
    ligler["etiket"] = ligler.country + " · " + ligler.league_name
    lig_sec = st.selectbox("Lig", ligler.etiket.tolist())
    lig_id = int(ligler.loc[ligler.etiket == lig_sec, "league_id"].iloc[0])

    sezonlar = sorted(nat.loc[nat.league_id == lig_id, "season"].unique(), reverse=True)
    sezon = st.selectbox("Sezon", sezonlar)

    lig_kadro = nat[(nat.league_id == lig_id) & (nat.season == sezon)]
    takimlar = sorted(lig_kadro.team_name.dropna().unique())
    if not takimlar:
        ui.empty_state("Takım bulunamadı", "Bu lig-sezon henüz toplanmamış olabilir.")
        st.stop()
    takim = st.selectbox("Takım", takimlar)

    st.divider()
    min_dk = st.slider(
        "Asgari dakika", 0, 2000, 450, 50,
        help="Bu dakikanın altındaki oyuncular rol haritasında sayılmaz. "
             "450 dakika, shrinkage sonrası skorun anlamlı olduğu alt sınır.",
    )

sh.veri_kalitesi_uyarisi([lig_id])

# Kadro kapsamı uyarısı (§11.10): Brezilya'da 4. sayfa alınamıyor.
kayip = lig_kadro.team_name.value_counts()
if len(kayip) and kayip.get(takim, 0) < 14:
    st.warning(
        f"Bu kadroda yalnızca {int(kayip.get(takim, 0))} oyuncu görünüyor. "
        "Sağlayıcıdan kadronun tamamı alınamamış olabilir - eksik rollerin "
        "gerçekten boş olduğuna değil, GÖRÜNMEDİĞİNE bakıyorsunuz."
    )

# ------------------------------------------------------- rol haritası verisi
lig_skor = scores[(scores.league_id == lig_id) & (scores.season == sezon)].copy()
lig_skor = lig_skor[lig_skor.minutes >= min_dk]
lig_skor = lig_skor[lig_skor.score.notna()]

if lig_skor.empty:
    ui.empty_state(
        "Yeterli oyuncu yok",
        f"{min_dk} dakika eşiğinin üstünde skorlanabilen oyuncu bulunamadı.",
    )
    st.stop()

harita = kadro_rol_haritasi(lig_skor, takim, esik=ESIK)
if harita.empty:
    ui.empty_state("Bu takımda skorlanabilir oyuncu yok",
                   "Dakika eşiğini düşürmeyi deneyin.")
    st.stop()

# rol_haritasi yasi istege bagli birakiyor - grafik onu kullaniyor
if "age_season_end" not in harita.columns:
    harita["age_season_end"] = np.nan

kadro = lig_skor[lig_skor.team_name == takim]

# ------------------------------------------------------------------ özet
dk = pd.to_numeric(kadro.drop_duplicates("player_id").minutes, errors="coerce")
yas = pd.to_numeric(kadro.drop_duplicates("player_id").age_season_end, errors="coerce")
gecerli = dk.notna() & yas.notna()
ort_yas = float((yas[gecerli] * dk[gecerli]).sum() / dk[gecerli].sum()) if gecerli.any() else np.nan

c1, c2, c3, c4 = st.columns(4)
c1.metric("Skorlanan oyuncu", kadro.player_id.nunique())
c2.metric("Dakika ağırlıklı yaş", f"{ort_yas:.1f}" if np.isfinite(ort_yas) else "—")
c3.metric("Güçlü rol", int((harita.durum == "guclu").sum()))
c4.metric("Boşluk", int((harita.durum == "bosluk").sum()))

st.caption(
    f"Karşılaştırma tabanı: **{lig_sec} {sezon}** ligindeki takımların "
    f"o roldeki en iyi oyuncularının medyanı. Aynı lig içinde kıyas - "
    f"lig gücü düzeltmesi uygulanmıyor (§23'te ölçüldü, sonucu kötüleştiriyor)."
)

# ------------------------------------------------------------- rol haritası
ui.section(
    "Rol haritası",
    f"Takımın o roldeki en iyisi, ligin ortalama takımının en iyisine göre. "
    f"±{ESIK:.0f} percentile içi 'ortalama' sayılıyor. Bu eşik ÖLÇÜLDÜ "
    f"(§35): kadrosu değişmemiş takım-rol çiftlerinde fark, sezonlar "
    f"arası kendiliğinden ±12 oynuyor. Önceki ±8 eşiği vakaların "
    f"yalnızca %51'ini kapsıyordu - gürültüye 'boşluk' diyordu.",
)

# Modul ASCII etiket dondurur (src/ genelinde oldugu gibi); gosterim
# etiketleri yalnizca burada.
renk = {"guclu": "#15803D", "ortalama": "#94A3B8", "bosluk": "#B91C1C"}
DURUM_ADI = {"guclu": "güçlü", "ortalama": "ortalama", "bosluk": "boşluk"}
fig = go.Figure(go.Bar(
    x=harita.fark,
    y=harita.role_name,
    orientation="h",
    marker_color=[renk[d] for d in harita.durum],
    customdata=np.stack([harita.player_name, harita.score, harita.lig_taban,
                         harita.age_season_end, harita.minutes], axis=-1),
    hovertemplate=(
        "<b>%{y}</b><br>En iyimiz: %{customdata[0]}<br>"
        "Skor: %{customdata[1]:.1f} · Lig tabanı: %{customdata[2]:.1f}<br>"
        "Yaş: %{customdata[3]:.1f} · Dakika: %{customdata[4]:.0f}<extra></extra>"
    ),
))
fig.update_layout(height=460, xaxis_title="ligin ortalama takımına göre fark",
                  yaxis_title=None, margin=dict(l=0, r=0, t=10, b=0))
fig.add_vline(x=0, line_width=1, line_color="#475569")
st.plotly_chart(ui.apply_plotly(fig), width="stretch")

tablo = harita[["role_name", "player_name", "age_season_end", "minutes",
                "score", "lig_taban", "fark", "derinlik", "durum"]].copy()
tablo.columns = ["rol", "en iyimiz", "yaş", "dk", "skor", "lig tabanı",
                 "fark", "derinlik", "durum"]
tablo["durum"] = tablo.durum.map(DURUM_ADI)
st.dataframe(
    tablo.style.format({"yaş": "{:.1f}", "dk": "{:.0f}", "skor": "{:.1f}",
                        "lig tabanı": "{:.1f}", "fark": "{:+.1f}"}),
    width="stretch", hide_index=True,
)
st.caption(
    "**derinlik** = o rolde ligin oyuncu medyanının üstünde kaç oyuncumuz var. "
    "1 ise tek adama bağımlıyız. **0** ise en iyimiz bile ligin oyuncu "
    "medyanının altında - o rolde kimse yok demek."
)
st.caption(
    "Aynı oyuncu birden çok rolün en iyisi olabilir; bu bir ilk 11 değil, "
    "rol haritası. Bir forvet hem 'bitirici' hem 'pres yapan' olarak "
    "puanlanır - hangi işi ne kadar iyi yaptığını gösterir."
)

tek_adam = harita[(harita.derinlik <= 1) & (harita.fark >= ESIK)]
if len(tek_adam):
    st.info(
        "**Tek adama bağımlı güçlü roller:** "
        + ", ".join(f"{r.role_name} ({r.player_name})"
                    for r in tek_adam.itertuples())
        + ". Bu roller bugün güçlü ama yedeksiz."
    )

# ------------------------------------------------------------- yaş profili
ui.section(
    "Yaş profili",
    "Dakikaların kaçı hangi yaşa gidiyor. Kadro yenileme ihtiyacını "
    "oyuncu SAYISI değil, oynanan DAKİKA gösterir.",
)

ozet = yas_profili(kadro)
if len(ozet) and ozet.dakika.sum():
    f2 = go.Figure(go.Bar(
        x=ozet.bant.astype(str), y=ozet.pay,
        marker_color=["#1E40AF", "#2563EB", "#64748B", "#D97706", "#B91C1C"],
        text=[f"{p:.0f}%<br>{int(n)} oyuncu" for p, n in zip(ozet.pay, ozet.oyuncu)],
        textposition="outside",
    ))
    f2.update_layout(height=300, yaxis_title="dakika payı (%)",
                     xaxis_title=None, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(ui.apply_plotly(f2), width="stretch")

    yasli_pay = float(ozet.loc[ozet.bant.astype(str).isin(["28-30", "31+"]), "pay"].sum())
    genc_pay = float(ozet.loc[ozet.bant.astype(str).isin(["U21", "21-23"]), "pay"].sum())
    st.caption(
        f"Dakikaların **%{yasli_pay:.0f}**'i 28 yaş ve üstüne, "
        f"**%{genc_pay:.0f}**'i 23 yaş ve altına gidiyor. "
        "Bu bir kıyas değil betimleme - hangi oranın 'doğru' olduğunu "
        "ölçmedik, kulübün stratejisine bağlı."
    )

# --------------------------------------------------- kim kimin yerine oynar
ui.section(
    "Kim kimin yerine oynar",
    "Stil benzerliği (§25). Bir oyuncu gittiğinde veya sakatlandığında "
    "işini kim devralabilir, kadro dışından kim benzer iş yapıyor.",
)

st.caption(
    "**Ölçüldü (§35).** Sonuç değişkeni kulüplerin kendi davranışı: bir "
    "rolün en iyisi ayrıldığında yerine gelen, rastgele bir aynı-mevki "
    "oyuncusundan daha mı benzer stilde? 2.510 değişimde evet - gelenin "
    "yüzdelik sırası 0,406 (0,50 = rastgele), %95 GA [0,394 , 0,417]. "
    "Ama etki mevkiye göre çarpıcı biçimde değişiyor; seçilen oyuncunun "
    "mevkisine ait ölçüm aşağıda."
)

def _benzer_tablo(b, *, lig_sutunu: bool):
    """Benzerlik sonucunu gosterime hazirla.

    DIKKAT: benzerler() player_features satirlarini oldugu gibi donduruyor -
    yas, lig, mevki ZATEN icinde. Yalnizca 'score' eksik, o da
    player_natural_role'den geliyor. Yasi da nat'tan cekmeye calismak
    sutun cakismasi ("age_season_end_x/_y") ve KeyError uretiyordu.
    """
    skor = (nat[["player_id", "league_id", "season", "score"]]
            .drop_duplicates(["player_id", "league_id", "season"]))
    g = b.merge(skor, on=["player_id", "league_id", "season"], how="left")
    sut = ["player_name", "age_season_end", "score", "benzerlik"]
    ad = {"player_name": "oyuncu", "age_season_end": "yaş", "score": "skor"}
    if lig_sutunu and "league_name" in g.columns:
        sut.insert(1, "league_name")
        ad["league_name"] = "lig"
    return (g[sut].rename(columns=ad)
            .style.format({"yaş": "{:.1f}", "skor": "{:.1f}",
                           "benzerlik": "{:.0f}"}))


feats = sh.load_features()
sec_ad = st.selectbox(
    "Oyuncu",
    kadro.drop_duplicates("player_id").sort_values("score", ascending=False)
         .player_name.tolist(),
)
sec = kadro[kadro.player_name == sec_ad].iloc[0]

hedef = feats[(feats.player_id == sec.player_id)
              & (feats.league_id == lig_id)
              & (feats.season == sezon)]

def _tr(x: float) -> str:
    """Ondalik ayraci virgul - arayuzun geri kalaniyla tutarli."""
    return f"{x:+.2f}".replace(".", ",")


_sv, _ort, _lo, _hi, _n = yedek_benzerligi_notu(str(sec.get("pos_group", "")))
if _sv == "bilinmiyor":
    st.info("Bu mevki grubu için ölçüm yok.")
else:
    _ga = f"{_tr(_ort)}, %95 GA [{_tr(_lo)} , {_tr(_hi)}]"
    if _sv == "ters":
        st.error(
            f":warning: **Bu mevkide ölçüm TERS çıktı** (n={_n}). Kulüpler bu "
            f"mevkide ayrılanın yerine rastgeleden **daha FARKLI** stilde "
            f"oyuncu alıyor ({_ga}). Aşağıdaki liste yanlış yol "
            f"gösterebilir: stil vektörü (pas ve müdahale hacimleri) bu "
            f"mevkide anlamlı bir şey ölçmüyor olabilir."
        )
    elif _sv == "guclu":
        st.success(
            f"Bu mevkide kulüpler belirgin biçimde benzer stil arıyor "
            f"({_ga}, n={_n}). Araç burada kulüplerin gerçekten yaptığı işi "
            f"ölçüyor."
        )
    else:
        st.warning(
            f"Bu mevkide etki **zayıf** ama sıfırdan ayırt edilebiliyor "
            f"({_ga}, n={_n}). Fikir verir, tek başına yeterli değildir."
        )

if hedef.empty:
    st.info("Bu oyuncunun stil vektörü üretilemedi (metrik eksik olabilir).")
else:
    d1, d2 = st.columns(2)

    with d1:
        st.markdown("**Kadro içi kapak**")
        ic_ids = kadro.player_id.unique()
        havuz_ic = feats[(feats.league_id == lig_id) & (feats.season == sezon)
                         & (feats.player_id.isin(ic_ids))]
        b_ic = sh.benzer_oyuncular(havuz_ic, hedef.index[0], n=5)
        if b_ic.empty:
            st.caption("Aynı mevki grubunda yeterli takım arkadaşı yok.")
        else:
            st.dataframe(
                _benzer_tablo(b_ic, lig_sutunu=False),
                width="stretch", hide_index=True,
            )

    with d2:
        st.markdown("**Kadro dışı aday**")
        tum_lig = st.checkbox(
            "Tüm liglerde ara", False,
            help="Ligler arası skor kıyası yapılmıyor - farklı ligdeki bir "
                 "adayın skoru KENDİ liginin kohortuna göre. Doğrudan "
                 "karşılaştırmayın.",
        )
        havuz_dis = feats if tum_lig else feats[(feats.league_id == lig_id)
                                                & (feats.season == sezon)]
        havuz_dis = havuz_dis[~havuz_dis.player_id.isin(ic_ids)]
        havuz_dis = pd.concat([hedef, havuz_dis])
        b_dis = sh.benzer_oyuncular(havuz_dis, hedef.index[0], n=8)
        if b_dis.empty:
            st.caption("Benzer stilde oyuncu bulunamadı.")
        else:
            st.dataframe(
                _benzer_tablo(b_dis, lig_sutunu=True),
                width="stretch", hide_index=True,
            )
