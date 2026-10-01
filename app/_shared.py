"""Streamlit sayfalari icin ortak yardimcilar."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DB = ROOT / "data" / "scout.duckdb"
ROLES_YAML = ROOT / "config" / "roles.yaml"

from scout.scoring.engine import load_roles, score_role  # noqa: E402

MEVKI_TR = {"Goalkeeper": "Kaleci", "Defender": "Defans",
            "Midfielder": "Orta saha", "Attacker": "Forvet"}

# Brezilya liglerinde kadro kapsami kismi (§11.10) - kullaniciya soylenmeli
PARTIAL_COVERAGE_LEAGUES = {71, 72, 75}


def page_setup(title: str, subtitle: str = "", icon: str | None = None) -> None:
    """Sayfa basligi + veri tazeligi kontrolu.

    refresh_snapshot() burada cagriliyor: arayuz veritabaninin kopyasindan
    okuyor ve baglanti @st.cache_resource ile onbellekli. Gunluk is arayuz
    acikken veriyi guncellerse, bu cagri olmadan kullanici ESKI veriyi
    gormeye devam eder ve bunu fark etmez.
    """
    import _style as ui

    ui.inject()
    if refresh_snapshot():
        st.toast("Veri güncellendi, tazelendi.", icon=":material/refresh:")
    ui.page_header(title, subtitle, icon)


def _snapshot_path() -> Path:
    """Arayuzun okudugu kopyanin yolu."""
    return DB.with_name("scout_ui_snapshot.duckdb")


@st.cache_resource
def _con():
    """Veritabaninin KOPYASINI ac.

    NEDEN KOPYA: DuckDB'de acik bir baglanti dosyayi kilitliyor. Streamlit
    acikken gunluk otomatik is (build_db / build_features / build_scores)
    "dosya baska bir islem tarafindan kullaniliyor" hatasiyla cokuyordu.

    Arayuz kendi kopyasindan okuyor, yazma islerinin yolu hep acik kaliyor.
    Kopya ~27 MB, saniyenin altinda. Kaynak dosya degistiginde tazeleniyor.
    """
    snap = _snapshot_path()
    try:
        need = (not snap.exists()) or snap.stat().st_mtime < DB.stat().st_mtime
        if need:
            shutil.copy2(DB, snap)
    except OSError:
        # kopya alinamadiysa (ornegin yazma sirasinda) elde varsa onu kullan
        if not snap.exists():
            raise
    return duckdb.connect(str(snap), read_only=True)


def refresh_snapshot() -> bool:
    """Kaynak veritabani guncellendiyse arayuzu tazele."""
    snap = _snapshot_path()
    if not snap.exists() or snap.stat().st_mtime < DB.stat().st_mtime:
        st.cache_resource.clear()
        st.cache_data.clear()
        return True
    return False


def data_age() -> str:
    import datetime as _dt
    return _dt.datetime.fromtimestamp(DB.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


@st.cache_data(ttl=300)
def load_features() -> pd.DataFrame:
    """Ozellikler + (varsa) Transfermarkt meta verisi.

    Meta yalnizca guvenle eslesen oyuncularda dolu (§13.2). Eslesmeyenlerde
    NaN kalir - bu bilincli: yanlis piyasa degeri, eksik olandan beterdir.
    """
    if table_exists("player_meta"):
        return _con().sql("""
            SELECT f.*,
                   m.market_value_eur, m.peak_market_value_eur, m.contract_until,
                   m.foot, m.tm_position, m.agent_name, m.tm_url,
                   m.international_caps, m.confidence AS match_confidence
            FROM player_features f
            LEFT JOIN player_meta m ON m.player_id = f.player_id
        """).df()
    return _con().sql("SELECT * FROM player_features").df()


@st.cache_data(ttl=300)
def load_scores() -> pd.DataFrame:
    return _con().sql("SELECT * FROM player_scores").df()


@st.cache_data(ttl=300)
def load_natural() -> pd.DataFrame:
    return _con().sql("SELECT * FROM player_natural_role").df()


@st.cache_data(ttl=300)
def table_exists(name: str) -> bool:
    q = "SELECT count(*) FROM information_schema.tables WHERE table_name = ?"
    return _con().execute(q, [name]).fetchone()[0] > 0


@st.cache_data
def roles():
    return load_roles(ROLES_YAML)


# ------------------------------------------------------------- havuz (8.1)
# Havuz ve Takip sayfalari ayni cercevelerden okur: kart, takip satiri ve
# havuz tablosu ayni sayiyi gostersin.
@st.cache_data(ttl=300)
def havuz_api() -> pd.DataFrame:
    """API havuzu (player_ranking, 2022-24) + istatistikler + TM bugunku durum."""
    import _havuz as HV
    import _metrikler as MK
    from scout.scoring.engine import column_for

    try:
        r = _con().sql("""
            SELECT r.*, n.role_name, l.tm_id, o.gozlem_ay,
                   p.current_club_name AS simdi_kulup,
                   p.market_value_in_eur AS simdi_deger,
                   p.name AS tm_ad, p.url AS tm_url
            FROM player_ranking r
            LEFT JOIN player_natural_role n USING (player_id, league_id, season)
            LEFT JOIN player_outcome o USING (player_id, league_id, season)
            LEFT JOIN player_links l USING (player_id)
            LEFT JOIN tm_players p ON p.player_id = l.tm_id
        """).df()
    except Exception:
        return pd.DataFrame()
    f = load_features()
    anahtar = ["player_id", "league_id", "season"]
    ek = [k for k in MK.TUMU if k in f.columns]
    ek += [c for c in f.columns if c.endswith("_pct") and c != "collection_pct"]
    # kart profilindeki yuzdeliklerin ham degerleri (katalogda olmayanlar dahil)
    ek += [column_for(m)[:-len("_pct")] for ms in HV.API_PROFIL.values()
           for m in ms if column_for(m)[:-len("_pct")] in f.columns]
    ek = [c for c in dict.fromkeys(ek + ["team_name", "firstname", "lastname"])
          if c not in r.columns]
    r = r.merge(f[anahtar + ek], on=anahtar, how="left")
    return HV.api_hazirla(r)


@st.cache_data(ttl=300)
def havuz_tm() -> pd.DataFrame:
    """TM 2025/26 havuzu: ileriye donuk defterdeki kayit (§56)."""
    import _havuz as HV

    try:
        r = _con().sql("""
            SELECT d.*, t.mac, t.tam_mac_payi, t.yedek_payi, t.kart_90,
                   t.pm_on90, t.pm_on_goreli, t.gf_on90, t.ga_on90,
                   t.takim_ppg, t.boy, t.ayak, p.url AS tm_url
            FROM tm_iddia_defteri d
            LEFT JOIN tm_oyuncu_sezon t USING (player_id, comp, season)
            LEFT JOIN tm_players p ON p.player_id = d.player_id
            WHERE d.season = (SELECT max(season) FROM tm_iddia_defteri)
        """).df()
    except Exception:
        return pd.DataFrame()
    return HV.tm_hazirla(r)


# ----------------------------------------------------------- takip (8.2)
# Eski "shortlist" (reports/shortlist.json) yerine. Dosya hic olusmamisti -
# tasinacak veri yoktu. Depolama ve gunluk: src/scout/takip.py
from scout import takip as TK  # noqa: E402


def takip_listesi() -> dict:
    """Onbelleksiz: kucuk dosya, her tiklamada degisiyor."""
    return TK.yukle()


def takibe_al(r: pd.Series) -> dict:
    """Havuz satirindan (havuz_api / havuz_tm) takibe al."""
    api = None
    if r.kaynak == "api":
        api = (int(r.player_id), int(r.league_id), int(r.season))
    return TK.ekle(
        r.kisi, r.oyuncu, kaynak=r.kaynak, anahtar=r.anahtar,
        sonuc_gorunur=bool(r.sonuc_gorunur),
        model_olasilik=r.model_olasilik, havuz_puani=r.havuz_puani,
        deger=r.deger if r.get("deger_var") == 1 else None, api=api)


@st.cache_data(ttl=300)
def tm_kimligi(api_player_id: int) -> int | None:
    x = _con().execute("SELECT tm_id FROM player_links WHERE player_id = ?",
                       [int(api_player_id)]).fetchone()
    return int(x[0]) if x and x[0] is not None else None


def takip_api_degistir(player_id: int, league_id: int, season: int,
                       ad: str) -> bool:
    """Kesif/Profil dugmesi: API oyuncu-sezonunu takibe al ya da cikar.
    Doner: artik takipte mi.

    Satir havuzdaysa (U23, >=450 dk) havuzun iddiasi kaydedilir; degilse
    yalniz kisi. Sonucu bilinmeyen satir YOK sayilmaz: temkinli taraf
    (sonuc_gorunur=True, goz testi sayilmaz)."""
    kisi = TK.kisi_anahtari(tm_kimligi(player_id), player_id)
    if TK.takipte(takip_listesi(), kisi):
        TK.sil(kisi)
        return False
    h = havuz_api()
    anahtar = f"{int(player_id)}-{int(league_id)}-{int(season)}"
    satir = h[h.anahtar == anahtar] if len(h) else h
    if len(satir):
        takibe_al(satir.iloc[0])
    else:
        TK.ekle(kisi, ad, kaynak="api", anahtar=anahtar, sonuc_gorunur=True,
                api=(int(player_id), int(league_id), int(season)))
    return True


def takipte_api(player_id: int) -> bool:
    kisi = TK.kisi_anahtari(tm_kimligi(player_id), player_id)
    return TK.takipte(takip_listesi(), kisi)


# ---------------------------------------------------------------- uyarilar
def incomplete_leagues(df: pd.DataFrame) -> pd.DataFrame:
    """Toplaması süren lig-sezonlar."""
    if "league_complete" not in df.columns:
        return pd.DataFrame()
    inc = (
        df[~df["league_complete"].astype(bool)]
        .groupby(["league_id", "country", "league_name", "season"], as_index=False)
        .agg(oyuncu=("player_id", "nunique"),
             pct=("collection_pct", "max"),
             takim_done=("teams_done", "max"),
             takim_total=("teams_total", "max"))
    )
    return inc


def incomplete_warning(df: pd.DataFrame) -> None:
    """Yarım toplanmış ligler için uyarı.

    Percentile'lar kohort içinde hesaplanıyor. Lig yarım toplandıysa kohort
    da yarım demektir — ve toplama TAKIM TAKIM yapıldığı için örnek rastgele
    değil kümeli. Yani sapma var, sadece gürültü değil.
    """
    inc = incomplete_leagues(df)
    if inc.empty:
        return
    satirlar = " · ".join(
        f"**{r.country}/{r.league_name} {int(r.season)}** "
        f"({int(r.takim_done)}/{int(r.takim_total)} takım, %{r.pct:.0f})"
        for r in inc.itertuples()
    )
    st.warning(
        f"**Toplaması süren ligler:** {satirlar}\n\n"
        "Bu liglerde percentile ve skorlar **yarım bir örneklem** üzerinden "
        "hesaplanıyor. Toplama takım takım ilerlediği için örnek rastgele değil — "
        "sayılar yanıltıcı olabilir. Lig tamamlanınca skorlar değişecek.",
        icon=":material/hourglass_top:",
    )


def coverage_warning(league_ids) -> None:
    """Kismi kadro kapsami uyarisi - sistem herkesi gormuyorsa scout bilmeli."""
    hit = set(league_ids) & PARTIAL_COVERAGE_LEAGUES
    if hit:
        st.warning(
            "**Kısmi kadro kapsamı:** Brezilya liglerinde kadrolar 3 sayfayı aştığı için "
            "ücretsiz API planında oyuncuların bir kısmı (tahmini %5-10) çekilemiyor. "
            "Kayıp rastgeledir — sadece az oynayanlar değil. Bu listede olmayan bir oyuncu, "
            "kötü olduğu için değil görünmediği için olmayabilir.",
            icon="⚠️",
        )


@st.cache_data(ttl=300)
def lig_kalitesi() -> pd.DataFrame:
    """build_db'nin urettigi veri kalitesi karnesi (§21)."""
    con = _con()
    try:
        return con.sql("SELECT * FROM league_quality").df()
    except Exception:
        return pd.DataFrame()


def veri_kalitesi_uyarisi(league_ids) -> None:
    """Saglayici verisi eksik olan ligler icin uyari (§21).

    NEDEN GEREKLI: veri tarafi duzeltildi - eksik metrik artik 0 sayilmiyor,
    NaN kaliyor ve kapsam esigi altinda skor uretilmiyor. Ama kullanici
    bunu bilmezse "bu ligde neden kimse cikmiyor" diye dusunur. Eksikligi
    GORUNUR kilmak, gizlemek kadar onemli.
    """
    lq = lig_kalitesi()
    if lq.empty:
        return
    hit = lq[lq.league_id.isin(list(league_ids)) & (lq.kalite != "tam")]
    if hit.empty:
        return

    eksik = hit[hit.kalite == "metrik_eksik"]
    mac = hit[hit.kalite == "mac_eksik"]

    # Butun ligler secildiginde her biri ayri kutu acinca ekran uyari
    # duvarina donuyordu. Tek kutuda topluyoruz; ayrinti katlanir halde.
    if len(eksik):
        adlar = " · ".join(f"**{r.country}/{r.league_name} {int(r.season)}**"
                           for r in eksik.itertuples())
        st.error(
            f"**{len(eksik)} lig-sezonda sağlayıcı temel istatistikleri "
            f"yayınlamıyor:** {adlar}\n\n"
            "Bu metrikler **sıfır değil, yok**. Bu liglerin oyuncularının çoğuna "
            "skor üretilmiyor (ağırlığın %35'i hesaplanamıyorsa skor bastırılır). "
            "Listede az oyuncu görmen bundan — oyuncular kötü olduğu için değil, "
            "**ölçülemedikleri** için yok.",
            icon=":material/report:",
        )
        with st.expander("Hangi metrikler eksik?"):
            st.dataframe(
                eksik[["country", "league_name", "season", "eksik_metrikler"]]
                .rename(columns={"country": "Ülke", "league_name": "Lig",
                                 "season": "Sezon",
                                 "eksik_metrikler": "Yayınlanmayan metrikler"}),
                hide_index=True, use_container_width=True,
            )

    if len(mac):
        adlar = " · ".join(
            f"**{r.country}/{r.league_name} {int(r.season)}** "
            f"(medyanın %{r.sayim_orani*100:.0f}'i)" for r in mac.itertuples())
        st.warning(
            f"**{len(mac)} lig-sezonda istatistikler eksik:** {adlar}\n\n"
            "Dakikalar tam ama detaylı istatistik maçların bir kısmında yok. "
            "**Lig içi sıralama geçerli** (herkes eşit etkileniyor), ama bu "
            "ligleri başka bir ligle karşılaştırma — oyuncular yapay olarak "
            "zayıf görünür.",
            icon=":material/warning:",
        )


def reliability_note(df: pd.DataFrame, min_minutes: int) -> None:
    if df.empty:
        return
    low = (df["minutes"] < min_minutes).sum()
    if low:
        st.caption(
            f"{low} oyuncu {min_minutes} dakikanın altında. Skorları istatistiksel olarak "
            "ortalamaya çekildi (shrinkage) ama yine de temkinli bak."
        )


# ------------------------------------------------------------- guven sinyali
# §18.4: dakika, U21'de olctugumuz her metrikten iyi bir tek basina
# siralayici (%60,0 isabet). Ama SKORA GIRMIYOR - dakika hem sebep hem
# sonuc oldugu icin agirliga konursa listeler "cok oynayan yasli oyuncu"ya
# kayar. Bunun yerine ayri bir sinyal olarak gosteriliyor:
#   skor  = "ne kadar iyi oynadi"
#   guven = "kulubu ona ne kadar guvendi"
# Yasitlarina gore olcmek onemli: 19 yasinda %70 dakika almak dikkate deger,
# 28 yasinda siradan.
GUVEN_ESIKLERI = [
    (80.0, "Vazgeçilmez", "ok"),
    (60.0, "Sık oynuyor", "info"),
    (35.0, "Rotasyon", "mute"),
    (0.0, "Az süre", "warn"),
]


def guven_seviyesi(pct: float | None) -> tuple[str, str]:
    """Dakika percentile'ini okunabilir bir guven etiketine cevir."""
    if pct is None or pd.isna(pct):
        return "—", "mute"
    for esik, etiket, kind in GUVEN_ESIKLERI:
        if pct >= esik:
            return etiket, kind
    return "—", "mute"


def guven_sutunu(df: pd.DataFrame) -> pd.Series:
    """Yasitlarina gore dakika percentile'i; yoksa kohort ici percentile'a duser.

    Yas bandi kohortu kucukse (min 8 kisi) NaN gelir - o zaman genel
    kohort percentile'i kullanilir, o da yoksa bos birakilir.
    """
    yas = df["minutes_agepct"] if "minutes_agepct" in df.columns else pd.Series(
        np.nan, index=df.index)
    genel = df["minutes_pct"] if "minutes_pct" in df.columns else pd.Series(
        np.nan, index=df.index)
    return pd.to_numeric(yas, errors="coerce").fillna(
        pd.to_numeric(genel, errors="coerce"))


# ---------------------------------------------------------------- canli skor
def rescore(feats: pd.DataFrame, role, overrides: dict, age_band: bool):
    """Slider'lar degistiginde skoru yeniden hesapla (§5.3 Katman 4)."""
    sub = feats[feats["pos_group"] == role.pos_group]
    score, contrib, cov = score_role(sub, role, age_band=age_band,
                                     weight_overrides=overrides)
    out = sub.copy()
    out["score"] = score
    out["coverage"] = cov
    return out, contrib


def metric_label(m: str) -> str:
    return {
        "np_ga": "gol+asist (penaltısız)", "np_goals": "gol (penaltısız)",
        "goals": "gol", "assists": "asist", "shots": "şut", "shots_on": "isabetli şut",
        "key_passes": "kilit pas", "passes": "pas", "tackles": "top çalma",
        "interceptions": "kesme", "blocks": "blok", "def_actions": "savunma aksiyonu",
        # possession-adjusted surumler (§32) - takim baglamindan arindirilmis
        "tackles_padj": "top çalma (takım ayarlı)",
        "interceptions_padj": "kesme (takım ayarlı)",
        "def_actions_padj": "savunma aksiyonu (takım ayarlı)",
        "blocks_padj": "blok (takım ayarlı)", "duels_padj": "ikili mücadele (takım ayarlı)",
        "duels": "ikili mücadele", "duels_won": "kazanılan mücadele",
        "dribbles": "çalım denemesi", "dribbles_won": "başarılı çalım",
        "fouls_drawn": "kazanılan faul", "fouls_made": "yapılan faul",
        "cards": "kart", "rating": "maç reytingi", "saves": "kurtarış",
        "goals_conceded": "yenilen gol", "duel_win_pct": "mücadele kazanma %",
        "dribble_pct": "çalım başarı %", "shot_accuracy": "isabet %",
        "goals_per_shot": "şut başına gol", "starts_pct": "ilk 11 oranı",
    }.get(m, m)


# --------------------------------------------------------- lig gucu baglami
@st.cache_data(ttl=300)
def lig_gucu() -> pd.DataFrame:
    """league_strength tablosu (§23). Kapi gecilmediyse tablo YOKTUR."""
    try:
        return _con().sql("SELECT * FROM league_strength").df()
    except Exception:
        return pd.DataFrame()


def lig_zorlugu_notu(league_ids) -> None:
    """Secili liglerin zorluk farkini SAYIYLA goster.

    NEDEN SKORA UYGULANMIYOR (olculdu, §23): lig duzeltmesini skora eklemek
    geriye donuk testte sonucu KOTULESTIRIYOR. Duzeltme katsayisi k icin
    havuzlanmis ilk-40 isabet orani:
        k=0  %37,5   k=10  %27,5   k=34  %5,0     (terfi sonucu)
    Sebep: olctugumuz sonuc deger BUYUMESI, lig duzeltmesi ise deger
    SEVIYESI icin optimize ediyor. Premier League oyuncusu zaten pahali;
    wonderkid firsati tam da modelin 'kolay' dedigi liglerde.

    Bu yuzden zorluk skoru DEGISTIRMEZ, yalnizca BAGLAM olarak gosterilir:
    "bu 85 hangi seviyede kazanildi".
    """
    lg = lig_gucu()
    if lg.empty:
        return
    con = _con()
    ad = con.sql("""SELECT DISTINCT league_id, country || '/' || league_name AS lig
                    FROM player_season""").df()
    esle = ad[ad.league_id.isin(list(league_ids))].merge(lg, on="lig", how="inner")
    if len(esle) < 2:
        return
    esle = esle.sort_values("zorluk", ascending=False)
    fark = float(esle.zorluk.max() - esle.zorluk.min())
    ust, alt = esle.iloc[0], esle.iloc[-1]
    # 20 ligi tek satira dizmek okunmaz oluyordu: uclari goster, tamami katlanir.
    satir = (f"en zor **{ust.lig}** ({ust.zorluk:+.2f}) · "
             f"en kolay **{alt.lig}** ({alt.zorluk:+.2f})")
    st.info(
        f"**Lig zorluğu (ölçüldü, köprü oyuncu yöntemi):** {satir}\n\n"
        f"Seçili ligler arasında **{fark:.2f} standart sapmalık** fark var. "
        "Skorlar bu farka göre **düzeltilmiyor** — düzeltmeyi denedik ve geriye "
        "dönük testte sonucu kötüleştirdi: değer *büyümesi* aradığımız için "
        "güçlü lig oyuncusunu öne almak ters etki yapıyor. Sayı burada "
        "**bağlam** olarak duruyor: aynı skor, zorluğu düşük ligde daha kolay "
        "kazanılmıştır.",
        icon=":material/balance:",
    )
    with st.expander(f"Seçili {len(esle)} ligin zorluk sıralaması"):
        st.dataframe(
            esle[["lig", "zorluk", "kopru"]]
            .rename(columns={"lig": "Lig", "zorluk": "Zorluk",
                             "kopru": "Köprü oyuncu"}),
            hide_index=True, use_container_width=True,
        )


# ----------------------------------------------------------- gelisim egrisi
@st.cache_data(ttl=300)
def gelisim_tablosu(onceki: int = 2022, sonraki: int = 2024) -> pd.DataFrame:
    """Sezonlar arasi gelisim (§24).

    Rol SABIT tutulur ve iki sezonun ortalamasina gore secilir - tek bir
    sezona sabitlemek sonucu kurgu geregi kaydiriyor (dogal rol = 14 rolun
    maksimumu). Olculdu: -5,4 ve +3,9; simetrik secimle -0,8.
    """
    from scout.features.development import gelisim as _gelisim

    try:
        return _gelisim(load_scores(), load_natural(),
                        onceki=onceki, sonraki=sonraki)
    except Exception:
        return pd.DataFrame()


# ------------------------------------------------------- benzer oyuncular
def benzer_oyuncular(havuz: pd.DataFrame, hedef_idx, n: int = 8) -> pd.DataFrame:
    """Stil olarak en yakin oyuncular (§25).

    Onbelleklenmiyor: havuz kullanicinin filtrelerine gore her seferinde
    farkli ve hedef oyuncu degisiyor - onbellek isabet etmezdi.
    """
    from scout.features.similarity import benzerler

    try:
        return benzerler(havuz, hedef_idx, n=n)
    except Exception:
        return pd.DataFrame()


# ------------------------------------------------------- boylamsal yas egrisi
@st.cache_data(ttl=300)
def yas_egrisi() -> pd.Series:
    """yas -> beklenen skor seviyesi (PLAN §26).

    Tablo yalnizca egri sekil kapisini GECERSE uretilir; yoksa bos doner
    ve arayuz duzeltmeyi hic sunmaz.
    """
    try:
        d = _con().sql("SELECT yas, seviye FROM age_curve_long ORDER BY yas").df()
        return d.set_index("yas").seviye
    except Exception:
        return pd.Series(dtype=float)


def yasa_gore_duzelt(df: pd.DataFrame, skor_col: str = "score") -> pd.Series:
    """Skoru, oyuncunun yasinda BEKLENEN seviyeye gore duzelt.

    Canli hesaplanan skora uygulanir - kullanici agirliklari degistirince
    duzeltme de guncellenmeli.
    """
    egri = yas_egrisi()
    if egri.empty or skor_col not in df.columns:
        return pd.Series(np.nan, index=df.index)
    yas = pd.to_numeric(df["age_season_end"], errors="coerce").round()
    bek = yas.clip(egri.index.min(), egri.index.max()).map(egri)
    return df[skor_col] - bek
