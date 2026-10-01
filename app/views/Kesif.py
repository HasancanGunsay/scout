"""Keşif - ana arama ekranı. Filtreler + canlı ağırlık slider'ları."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _shared as sh
import _style as ui
import pandas as pd
import streamlit as st

sh.page_setup(
    "Keşif",
    "Filtreleri daralt, rol şablonunu seç, ağırlıkları kendi aramana göre ayarla. "
    "Sıralama anında güncellenir. Beğendiklerini takibe al.",
    "search",
)

feats = sh.load_features()
role_list, thresholds = sh.roles()

# Mevki + rol SAYFANIN ÜSTÜNDE (1 Eki 2026, kullanıcı: "rol değiştiremiyorum").
# Kenar çubuğunda menünün ve 23 ligin seçili durduğu Lig kutusunun altında
# kalıyordu - çalışıyordu ama bulunamıyordu. Aramanın ana kararı bu ikisi.
MEVKI_ADI = {"Goalkeeper": "Kaleci", "Defender": "Defans",
             "Midfielder": "Orta saha", "Attacker": "Forvet"}
with st.container(border=True):
    c_pos, c_rol = st.columns([1, 2.2])
    pos = c_pos.segmented_control(
        "Mevki", list(MEVKI_ADI), format_func=MEVKI_ADI.get,
        default="Attacker", required=True, key="ks_pos")
    roles_for_pos = [r for r in role_list if r.pos_group == pos]
    role_names = [r.name for r in roles_for_pos]
    # anahtar mevkiye bağlı: mevki değişince rol o mevkinin ilk şablonuna döner
    role_name = c_rol.pills(
        "Rol (puanlama şablonu)", role_names, default=role_names[0],
        required=True, key=f"ks_rol_{pos}",
        help="Skor bu şablonun ağırlıklarıyla hesaplanır. Ağırlıkları soldaki "
             "'Ağırlıklar' bölümünden kendi aramana göre değiştirebilirsin.")
    role = next(r for r in roles_for_pos if r.name == role_name)


# ------------------------------------------------------------------ filtreler
with st.sidebar:
    st.header("Filtreler")

    # Toplaması süren ligler varsayılan olarak DIŞARIDA - yarım örneklemde
    # hesaplanan percentile yanıltıcıdır (§P0-2).
    complete_ids = set(
        feats.loc[feats.get("league_complete", True).astype(bool), "league_id"].unique()
    )
    show_incomplete = st.checkbox(
        "Toplaması süren ligleri de göster",
        value=False,
        help="Yarım toplanmış liglerde percentile'lar eksik örneklem üzerinden "
             "hesaplanır ve yanıltıcı olabilir. Varsayılan olarak gizlenir.",
    )

    pool = feats if show_incomplete else feats[feats.league_id.isin(complete_ids)]
    if pool.empty:
        pool = feats
        show_incomplete = True

    leagues = (
        pool[["league_id", "country", "league_name"]]
        .drop_duplicates()
        .assign(label=lambda d: d.country + " / " + d.league_name)
        .sort_values("label")
    )
    if not show_incomplete:
        st.caption(f"{len(feats.league_id.unique()) - len(complete_ids)} lig "
                   "toplaması sürdüğü için gizli.")

    # key toggle'a bagli: kullanici "toplaması süren ligleri göster" dedigi anda
    # widget sifirlanip YENI ligler de secili gelir. Aksi halde Streamlit eski
    # secimi koruyor ve yeni ligler listeye girse bile isaretsiz kaliyor.
    picked_leagues = st.multiselect(
        "Lig", leagues.label.tolist(), default=leagues.label.tolist(),
        key=f"ligler_{int(show_incomplete)}",
    )
    lids = leagues[leagues.label.isin(picked_leagues)].league_id.tolist()

    seasons = sorted(feats.season.dropna().unique().astype(int), reverse=True)
    picked_seasons = st.multiselect("Sezon", seasons, default=seasons)

    st.divider()
    age_max = st.slider("Azami yaş (sezon sonu)", 16.0, 40.0, 23.0, 0.5)
    min_min = st.slider("Asgari dakika", 0, 3000, 450, 50)

    age_band_mode = st.toggle(
        "Yaşıtlarıyla kıyasla",
        value=True,
        help="Açık: oyuncu kendi yaş bandındaki oyuncularla kıyaslanır (wonderkid "
             "sinyali). Kapalı: tüm mevki havuzuyla kıyaslanır (şimdiki güç).",
    )

    # Boylamsal yas egrisi duzeltmesi (PLAN §26, denetim §31).
    # Egrinin KENDISI saglam olculdu (4.848 gecis, tepe 25, sekil kapisi).
    # Ama duzeltmenin ham skoru GECTIGI kanitlanmadi: +1,6 puan,
    # %95 GA [-6,7 , +10,0]. Ilk surumde "1,62x vs 1,52x" diye benimsenmisti;
    # bootstrap denetimi o farkin gurultu oldugunu gosterdi.
    # 23 yas ustunde hic sunulmuyor - orada etki NEGATIF ve buyuk (0,51x).
    yas_egrisi_mumkun = not sh.yas_egrisi().empty
    yas_egrisi = False
    if yas_egrisi_mumkun and age_max <= 23.0:
        yas_egrisi = st.toggle(
            "Yaş eğrisine göre düzelt",
            value=False,
            help="Skoru, oyuncunun yaşında BEKLENEN seviyeye göre düzeltir. "
                 "Eğri aynı oyuncunun sezonlar arası değişiminden ölçüldü "
                 "(4.848 geçiş, tepe 25 yaş) — bu ölçüm sağlam. "
                 "AMA düzeltmenin ham skordan daha iyi sonuç verdiği "
                 "KANITLANMADI: fark +1,6 puan, %95 güven aralığı "
                 "[-6,7 , +10,0] (PLAN §31). Alternatif bir bakış olarak "
                 "sunuluyor, üstünlük iddiası yok. 23 yaş üstünde hiç "
                 "sunulmuyor - orada ölçüldü ve açıkça zararlı.",
        )
    elif yas_egrisi_mumkun:
        st.caption("Yaş eğrisi düzeltmesi yalnızca azami yaş ≤23 iken sunulur "
                   "(üstünde ölçüldü ve zararlı).")

    # ---- baglamsal filtreler (§1.9) - yalnizca meta veri varsa
    has_meta = "market_value_eur" in feats.columns
    mv_max = None
    contract_before = None
    only_matched = False
    if has_meta:
        st.divider()
        st.subheader("Bağlam")
        st.caption(
            f"Transfermarkt eşleşmesi olan oyuncularda dolu "
            f"({feats.market_value_eur.notna().sum()}/{len(feats)})."
        )
        mv_vals = feats.market_value_eur.dropna()
        if len(mv_vals):
            cap = int(mv_vals.max())
            mv_max = st.slider(
                "Azami piyasa değeri (€)", 0, cap, cap, max(cap // 100, 1000),
                format="%d",
            )
        contract_before = st.selectbox(
            "Sözleşmesi şu tarihten önce bitenler",
            ["(filtreleme)", "2025-06-30", "2026-06-30", "2027-06-30"],
        )
        only_matched = st.checkbox(
            "Sadece meta verisi olanlar", False,
            help="Piyasa değeri / sözleşme bilgisi bulunmayan oyuncuları gizler. "
                 "Dikkat: eşleşmemek kötü oyuncu olmak demek değil — "
                 "Transfermarkt veri seti Serie B'nin yarısını kapsamıyor.",
        )

# ------------------------------------------------------------------ agirliklar
with st.sidebar:
    st.divider()
    st.header("Ağırlıklar")
    st.caption(
        f"**{role.name}** şablonu. Kaydırarak kendi aramanı kur — "
        "sıralama anında güncellenir."
    )
    if st.button("Şablona dön", use_container_width=True):
        for m in role.weights:
            st.session_state.pop(f"w_{role.key}_{m}", None)
        st.rerun()

    overrides = {}
    for m, w in role.weights.items():
        overrides[m] = st.slider(
            sh.metric_label(m), 0, 40, int(w), 1, key=f"w_{role.key}_{m}"
        )

# ------------------------------------------------------------------ hesapla
sub = pool[
    pool.league_id.isin(lids)
    & pool.season.isin(picked_seasons)
    & (pool.pos_group == role.pos_group)
]

if sub.empty:
    ui.empty_state("Filtrelere uyan oyuncu yok",
                   "Yaş veya dakika sınırını gevşetmeyi dene.")
    st.stop()

scored, contrib = sh.rescore(sub, role, overrides, age_band_mode)
scored = scored[(scored.age_season_end <= age_max) & (scored.minutes >= min_min)]

# baglamsal filtreler - meta verisi OLMAYANLARI elememek icin dikkatli
if has_meta:
    if mv_max is not None and mv_max < int(feats.market_value_eur.max() or 0):
        scored = scored[scored.market_value_eur.isna() | (scored.market_value_eur <= mv_max)]
    if contract_before and contract_before != "(filtreleme)":
        cu = pd.to_datetime(scored.contract_until, errors="coerce")
        scored = scored[cu.isna() | (cu <= pd.Timestamp(contract_before))]
    if only_matched:
        scored = scored[scored.market_value_eur.notna() | scored.contract_until.notna()]

if yas_egrisi:
    # Duzeltme CANLI skora uygulaniyor - kullanici agirliklari degistirince
    # sonuc da degismeli (player_scores'taki sabit sutun degil).
    scored = scored.assign(score_vs_yas=sh.yasa_gore_duzelt(scored))
    scored = scored.sort_values("score_vs_yas", ascending=False)
else:
    scored = scored.sort_values("score", ascending=False)

# --- baslik seridi: ne aradigin ve skorun ne anlama geldigi tek bakista
k = st.columns([2, 1, 1, 1])
k[0].metric("Rol", role.name)
k[1].metric("Bulunan", f"{len(scored)}")
k[2].metric("Medyan skor", f"{scored.score.median():.0f}" if len(scored) else "—")
k[3].metric("900+ dakika", f"{int((scored.minutes >= 900).sum())}")

chips = [
    ("Yaşıtlarına göre" if age_band_mode else "Şimdiki güç", "info"),
    (f"≤{age_max:g} yaş", "mute"),
    (f"≥{min_min} dk", "mute"),
]
if len(lids) > 1 or len(picked_seasons) > 1:
    chips.append(("Ligler arası: skor düzeltilmiyor", "warn"))
ui.badges(*chips)

sh.incomplete_warning(scored)
sh.coverage_warning(lids)
sh.veri_kalitesi_uyarisi(lids)
sh.lig_zorlugu_notu(lids)

# Lig gucu katsayisi ARTIK VAR (§23) ama skora uygulanmiyor - gerekcesi
# lig_zorlugu_notu() icinde. Katsayi yoksa eski uyari gecerli kalir.
if (len(picked_seasons) > 1 or len(lids) > 1) and sh.lig_gucu().empty:
    st.warning(
        "Birden fazla lig/sezon seçili. **Lig gücü katsayısı henüz kurulmadı** — "
        "ligler arası skor karşılaştırması güvenilir değil. Aynı lig içindeki sıralama geçerli.",
        icon=":material/warning:",
    )

cols = ["player_name", "age_season_end", "team_name", "league_name", "season",
        "position", "minutes", "apps", "rating", "score", "coverage"]
labels = {
    "player_name": "Oyuncu", "age_season_end": "Yaş", "team_name": "Takım",
    "league_name": "Lig", "season": "Sezon", "position": "Mevki",
    "minutes": "Dakika", "apps": "Maç", "rating": "Reyting",
    "score": "Skor", "coverage": "Kapsam",
    "market_value_eur": "Değer (€)", "contract_until": "Sözleşme",
}
if has_meta:
    cols += ["market_value_eur", "contract_until"]

show = scored.head(60)[cols].rename(columns=labels)
show["Yaş"] = show["Yaş"].round(1)
show["Skor"] = show["Skor"].round(1)
show["Kapsam"] = show["Kapsam"].round(2)

# Guven sinyali (§18.4) - skorun YANINDA, icinde degil.
guven = sh.guven_sutunu(scored.head(60))
if guven.notna().any():
    show.insert(show.columns.get_loc("Skor") + 1, "Güven",
                guven.to_numpy().round(0))

colcfg = {
    "Skor": st.column_config.ProgressColumn(
        "Skor", min_value=0, max_value=100, format="%.1f",
        help="0-100. Seçili rol ağırlıklarıyla, kendi kohortundaki percentile'lardan.",
    ),
    "Kapsam": st.column_config.NumberColumn(
        "Kapsam", format="%.2f",
        help="Ağırlığın ne kadarı hesaplanabildi. 1.00 = tüm metrikler mevcut.",
    ),
    "Güven": st.column_config.ProgressColumn(
        "Güven", min_value=0, max_value=100, format="%.0f",
        help="Kulübü ona ne kadar güveniyor: yaşıtları arasında aldığı "
             "dakikanın percentile'ı. Skora DAHİL DEĞİLDİR — skor 'ne kadar "
             "iyi oynadı', bu 'ne kadar oynatıldı' sorusunu cevaplar. "
             "Geriye dönük testte U21'de tek başına en güçlü sinyaldi.",
    ),
    "Dakika": st.column_config.NumberColumn("Dakika", format="%d"),
    "Maç": st.column_config.NumberColumn("Maç", format="%d"),
    "Reyting": st.column_config.NumberColumn("Reyting", format="%.2f"),
    "Yaş": st.column_config.NumberColumn("Yaş", format="%.1f"),
}
if has_meta:
    colcfg["Değer (€)"] = st.column_config.NumberColumn("Değer (€)", format="%d")
    colcfg["Sözleşme"] = st.column_config.DateColumn("Sözleşme", format="YYYY-MM")

st.dataframe(show, use_container_width=True, hide_index=True, height=540,
             column_config=colcfg)

sh.reliability_note(scored, thresholds.get("min_minutes_reliable", 450))

# ------------------------------------------------------------------ takip
st.divider()
ui.section("Takibe al",
           "İzlemek istediklerini işaretle; Takip listesinde notlarını tutarsın, "
           "Karşılaştırma ekranında yan yana gelirler.")
names = scored.head(60).apply(
    lambda r: f"{r.player_name} · {r.team_name} · {int(r.season)}", axis=1
).tolist()
c_pick, c_btn = st.columns([3, 1])
pick = c_pick.selectbox("Oyuncu", ["—"] + names, label_visibility="collapsed")
if pick != "—" and c_btn.button("Takibe al / çıkar", type="primary", width="stretch"):
    row = scored.head(60).iloc[names.index(pick)]
    added = sh.takip_api_degistir(int(row.player_id), int(row.league_id),
                                  int(row.season), row.player_name)
    st.success(f"{row.player_name} takip listesine eklendi." if added
               else f"{row.player_name} takip listesinden çıkarıldı.")
