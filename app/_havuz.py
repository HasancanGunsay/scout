"""Havuz ekranı — veri biçimlendirme ve filtreler (FAZ 8.1).

Kullanıcı isteği (1 Eki 2026): sistem TEK İSİM vermesin, okyanustan bir
HAVUZ çıkarsın; istatistikler liste üzerinden incelensin, ayrıntı için
Sofascore'a gidilsin. Bu modül iki kaynağı ortak bir şemaya getirir:

  api  2022–24, API'nin geniş lig ağı (düşük görünürlüklü ligler dahil),
       5.893 U23 oyuncu-sezon, dışarıdan tahmin (player_tahmin)
  tm   2025/26, Transfermarkt'ın izlediği 14 Avrupa ligi, 891 U23,
       ileriye dönük defterdeki kayıt (tm_iddia_defteri, §56)

HAVUZ PUANI = model olasılığının oyuncunun KENDİ GRUBU içindeki yüzdeliği.
Grup: sezon × mevki × lig türü (api) / sezon × mevki (tm).
NEDEN OLASILIK DEĞİL: karma listede kalibre olasılık izlenen ligleri öne
çıkarıyor (§50: ucuz ilk-20'lerin %86-91'i izlenen liglerden), çünkü iki
lig türünün taban oranı çok farklı. Lig türü İÇİNDE yüzdelik kalibrasyondan
bağımsızdır (Platt monoton) — düşük görünürlüklü ligin en iyileri kendi
grubunda yarışır ve havuza kendi payıyla girer.

Yüzdelik KULLANICI FİLTRELERİNDEN ÖNCE hesaplanır: yaş ya da fiyat
süzgeci bir oyuncunun havuz puanını değiştirmez.

Streamlit içermez; testler doğrudan çağırır.
"""

from __future__ import annotations

import unicodedata
from urllib.parse import quote_plus

import pandas as pd

from _metrikler import Metrik

KAYNAK_API = "api"
KAYNAK_TM = "tm"
KAYNAK_ADI = {
    KAYNAK_API: "2022–24 · geniş lig ağı",
    KAYNAK_TM: "2025/26 · Avrupa ligleri",
}
KAYNAK_ACIKLAMA = {
    KAYNAK_API: "API-Football: 23 lig, düşük görünürlüklü ligler dahil. "
                "Zengin maç istatistiği; tahminler eğitim verisini görmemiş "
                "modelden (dışarıdan).",
    KAYNAK_TM: "Transfermarkt: izlenen 14 Avrupa ligi, en son tamamlanan "
               "sezon. İstatistik sınırlı (süre, gol, asist, sahadayken "
               "skor); havuz 2027 yazında puanlanacak (ileriye dönük defter).",
}

GRUP = {KAYNAK_API: ["season", "kapsam", "pos_group"],
        KAYNAK_TM: ["season", "pos_group"]}

DILIMLER = [10, 25, 50, 100]
DILIM_ADI = {10: "İlk %10", 25: "İlk %25", 50: "İlk %50", 100: "Hepsi"}

MEVKILER = ["Goalkeeper", "Defender", "Midfielder", "Attacker"]
KAPSAM_ADI = {"sicrama_only": "Düşük görünürlük", "tam": "İzlenen lig"}

# src/ ASCII yazar (tm_tarih.INCE_MEVKI); Türkçe karşılık arayüzde
INCE_MEVKI_ADI = {
    "Sag bek": "Sağ bek", "Sag orta saha": "Sağ orta saha",
    "Sag kanat": "Sağ kanat", "On libero": "Ön libero",
    "Ikinci forvet": "İkinci forvet",
}

TM_LIG_ADI = {
    "GB1": "İngiltere · Premier League", "ES1": "İspanya · LaLiga",
    "IT1": "İtalya · Serie A", "L1": "Almanya · Bundesliga",
    "FR1": "Fransa · Ligue 1", "NL1": "Hollanda · Eredivisie",
    "PO1": "Portekiz · Liga Portugal", "BE1": "Belçika · Pro League",
    "TR1": "Türkiye · Süper Lig", "SC1": "İskoçya · Premiership",
    "DK1": "Danimarka · Superliga", "GR1": "Yunanistan · Super League",
    "RU1": "Rusya · Premier Liga", "UKR1": "Ukrayna · Premier Liga",
}

# API ülke adları İngilizce geliyor; TM tarafıyla aynı dilde görünsün
ULKE_ADI = {
    "Argentina": "Arjantin", "Belgium": "Belçika", "Brazil": "Brezilya",
    "Colombia": "Kolombiya", "Denmark": "Danimarka", "Ecuador": "Ekvador",
    "England": "İngiltere", "France": "Fransa", "Germany": "Almanya",
    "Italy": "İtalya", "Netherlands": "Hollanda", "Norway": "Norveç",
    "Portugal": "Portekiz", "Spain": "İspanya", "Sweden": "İsveç",
}

# siralama.sonra_metni_kodu kodlarının Türkçesi (Mevki Sıralaması da kullanır)
SONRA_ADI = {
    "yer_edindi": "✅ yer edindi", "rotasyon": "rotasyon (450-899 dk)",
    "gorundu": "göründü (<450 dk)", "iz_yok": "iz yok",
    "iz_yok_gorunmez": "iz yok*", "bilinmiyor": "—",
}

# TM havuzunun istatistik aileleri (API aileleri _metrikler.AILELER'de)
TM_AILELER: dict[str, list[Metrik]] = {
    "Süre ve rol": [
        Metrik("dakika_payi", "Dakika payı %", "%.0f%%", yuzde=True,
               aciklama="Takımın lig dakikalarının yüzde kaçında sahadaydı."),
        Metrik("ilk11_payi", "İlk 11 payı %", "%.0f%%", yuzde=True,
               aciklama="Takımın lig maçlarının yüzde kaçına ilk 11'de başladı."),
        Metrik("tam_mac_payi", "Tam maç %", "%.0f%%", yuzde=True,
               aciklama="İlk 11 başladığı maçların yüzde kaçını bitirdi."),
        Metrik("yedek_payi", "Yedekten giriş %", "%.0f%%", yuzde=True,
               aciklama="Oynadığı maçların yüzde kaçına yedekten girdi."),
        Metrik("mac", "Maç", "%d"),
        Metrik("ilk11", "İlk 11", "%d"),
    ],
    "Üretim": [
        Metrik("ga_90", "Gol+asist /90", "%.2f"),
        Metrik("gol", "Gol", "%d"),
        Metrik("asist", "Asist", "%d"),
        Metrik("kart_90", "Kart /90", "%.2f", dusuk_iyi=True,
               aciklama="Sarı = 1, kırmızı = 3 sayılır."),
    ],
    "Takım katkısı": [
        Metrik("pm_on_goreli", "Takıma göre +/- /90", "%+.2f",
               aciklama="Sahadayken 90 dakikadaki gol farkı, eksi takımın "
                        "sezon geneli gol farkı. Pozitif = o sahadayken "
                        "takım ortalamasından iyi. Gürültülü: rakip ve "
                        "takım arkadaşlarından etkilenir."),
        Metrik("pm_on90", "Sahadayken +/- /90", "%+.2f"),
        Metrik("gf_on90", "Sahadayken atılan /90", "%.2f"),
        Metrik("ga_on90", "Sahadayken yenen /90", "%.2f", dusuk_iyi=True),
        Metrik("takim_ppg", "Takımın puan/maç", "%.2f",
               aciklama="Oynadığı dakikalarla ağırlıklı takım puan ortalaması."),
    ],
}
TM_TUMU: dict[str, Metrik] = {m.kol: m for ms in TM_AILELER.values() for m in ms}

# Seçili oyuncu kartındaki yüzdelik profil.
# api: player_features'taki *_pct (kendi lig+sezon+mevki havuzunda, yüksek
#      = iyi; faul/kart/yenen gol zaten ters çevrilmiş, percentile.invert)
# tm : havuzun kendi içinde (aynı mevkideki U23 yaşıtları) hesaplanır
API_PROFIL = {
    "Goalkeeper": ["saves", "goals_conceded", "passes", "rating"],
    "Defender": ["tackles_padj", "interceptions_padj", "blocks_padj",
                 "duel_win_pct", "passes", "key_passes", "rating"],
    "Midfielder": ["passes", "key_passes", "np_ga", "dribbles_won",
                   "tackles_padj", "interceptions_padj", "duel_win_pct",
                   "rating"],
    "Attacker": ["np_goals", "np_ga", "shots", "key_passes", "dribbles_won",
                 "duels_won", "fouls_drawn", "rating"],
}
TM_PROFIL = ["dakika_payi", "ilk11_payi", "tam_mac_payi", "ga_90",
             "pm_on_goreli", "ga_on90", "kart_90", "takim_ppg"]


# ------------------------------------------------------------------ hesap
def havuz_puani(df: pd.DataFrame, grup: list[str],
                kol: str = "model_olasilik") -> pd.Series:
    """0-100: grubun en iyisi 100'e yakın. İlk %10 = puan > 90."""
    return 100.0 * df.groupby(grup, dropna=False)[kol].rank(
        pct=True, method="average")


def dilim_icinde(puan: pd.Series, dilim: int) -> pd.Series:
    """'İlk %X' — puan > 100-X. Hepsi (100) herkesi alır."""
    return puan > (100 - dilim)


def grup_yuzdeligi(df: pd.DataFrame, kol: str, grup: list[str],
                   dusuk_iyi: bool = False) -> pd.Series:
    """Bir metriğin grup içi yüzdeliği (yüksek = iyi)."""
    p = 100.0 * df.groupby(grup, dropna=False)[kol].rank(
        pct=True, method="average")
    return 100.0 - p if dusuk_iyi else p


def sofascore_url(ad: str, kulup: str | None = None) -> str:
    """Sofascore oyuncu sayfasına tek tık (8.3).

    Sofascore'un arama adresi YOK (/search?q= → 404, 1 Eki 2026'da
    denendi). DuckDuckGo '!ducky' ilk sonuca yönlendirir; 'site:' ile
    sonuç Sofascore'a sınırlı. Denendi: Pio Esposito + Inter, Kenan Yıldız
    + Juventus, André Gomes + FC Alverca (aynı adlı ünlü orta saha varken
    doğru kişi: 2004 doğumlu kaleci - kulübü değişmiş olsa da). Kulüp
    eş adlıları ayırır; tam ad kısaltmadan iyi sonuç verir.
    """
    q = f"!ducky site:sofascore.com {ad}" + (f" {kulup}" if kulup else "")
    return "https://duckduckgo.com/?q=" + quote_plus(q)


def tm_url(profil: str | None, ad: str) -> str:
    """Kabul edilmiş eşleşmede birebir profil; yoksa TM hızlı arama.
    (Profil adresi yalnız kabul edilmiş eşleşmeden gelir - §60.)"""
    if isinstance(profil, str) and profil.startswith("http"):
        return profil
    return ("https://www.transfermarkt.com/schnellsuche/ergebnis/"
            "schnellsuche?query=" + quote_plus(ad))


def _metin(s) -> str | None:
    return s if isinstance(s, str) and s.strip() else None


def ozet_anahtar(anahtarlar) -> str:
    """Satır kümesinin kısa özeti (tablo widget anahtarı için)."""
    import hashlib
    return hashlib.md5("|".join(map(str, anahtarlar)).encode()).hexdigest()[:10]


def sade(s: str) -> str:
    """Arama için: aksan ve büyük/küçük harf duyarsız ('Rúben' ~ 'ruben')."""
    s = str(s).replace("ı", "i").replace("İ", "i")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def filtrele(df: pd.DataFrame, *, dilim: int = 100,
             mevkiler: list[str] | None = None,
             ligler: list[str] | None = None,
             kapsam: str | None = None,
             yas_max: float | None = None, min_dk: float | None = None,
             fiyat_tavani: float | None = None, degersiz_dahil: bool = True,
             ara: str = "") -> pd.DataFrame:
    """Ortak şema üzerinde süzgeç. Boş liste = süzme (hepsi).

    Değeri bilinmeyen oyuncu fiyat tavanından ETKİLENMEZ; yalnız
    `degersiz_dahil` ile dışarıda bırakılır. Değeri yok, 0 € demek değil
    (§56.4: ilk defter yazımı bunu karıştırmıştı).
    """
    m = dilim_icinde(df["havuz_puani"], dilim)
    if mevkiler:
        m &= df["pos_group"].isin(mevkiler)
    if ligler:
        m &= df["lig"].isin(ligler)
    if kapsam:
        m &= df["kapsam"] == kapsam
    if yas_max is not None:
        m &= df["yas"] <= yas_max
    if min_dk is not None:
        m &= df["dk"] >= min_dk
    degerli = df["deger_var"].fillna(0).astype(int) == 1
    if fiyat_tavani is not None:
        m &= ~degerli | (df["deger"] <= fiyat_tavani)
    if not degersiz_dahil:
        m &= degerli
    if ara.strip():
        aranan = sade(ara.strip())
        m &= df["oyuncu"].map(sade).str.contains(aranan, regex=False)
    return df[m]


# ------------------------------------------------------- ortak şemaya çevir
ORTAK = ["kaynak", "anahtar", "kisi", "oyuncu", "yas", "kulup", "lig",
         "pos_group", "mevki", "dk", "deger", "deger_var", "kapsam", "season",
         "model_olasilik", "havuz_puani", "sonuc_gorunur"]


def kisi(tm_id, api_id) -> str:
    """Takip listesinin kişi anahtarı — scout.takip.kisi_anahtari ile AYNI
    biçim (testle korunuyor). Burada kopya: bu modül src'ye bağımlı değil."""
    if tm_id is not None and not pd.isna(tm_id):
        return f"tm:{int(tm_id)}"
    return f"api:{int(api_id)}"


def api_hazirla(raw: pd.DataFrame) -> pd.DataFrame:
    """player_ranking (+ özellikler, + TM güncel durum) → ortak şema."""
    d = raw.copy()
    d["kaynak"] = KAYNAK_API
    d["anahtar"] = (d.player_id.astype(str) + "-" + d.league_id.astype(str)
                    + "-" + d.season.astype(str))
    d["oyuncu"] = d.player_name
    d["yas"] = d.age_season_end
    d["kulup"] = d.team_name.fillna("—")
    d["lig"] = d.country.map(ULKE_ADI).fillna(d.country) + " · " + d.league_name
    d["mevki"] = d.role_name.fillna("—") if "role_name" in d else "—"
    d["dk"] = d.minutes
    # 8.3 bağlantıları: TM'deki tam ad > API ad+soyad > API kısa ad
    # ("T. Abed" gibi kısaltma aramayı bozar); kulüp: bugünkü > o sezonki
    api_tam = ((d.firstname.fillna("") + " " + d.lastname.fillna("")).str.strip()
               if {"firstname", "lastname"} <= set(d.columns)
               else pd.Series("", index=d.index))
    tm_ad = d.tm_ad if "tm_ad" in d else pd.Series(None, index=d.index)
    d["tam_ad"] = [_metin(a) or _metin(b) or c
                   for a, b, c in zip(tm_ad, api_tam, d.player_name)]
    simdi = d.simdi_kulup if "simdi_kulup" in d else pd.Series(None, index=d.index)
    d["arama_kulup"] = [_metin(a) or _metin(b) for a, b in zip(simdi, d.kulup)]
    if "tm_url" not in d:
        d["tm_url"] = None
    tm = d.tm_id if "tm_id" in d else pd.Series(None, index=d.index)
    d["kisi"] = [kisi(t, p) for t, p in zip(tm, d.player_id)]
    # 12 aylık pencere kapandıysa sonuç biliniyor: o andaki seçim göz testi
    # sayılmaz (bilinmiyorsa da sayılmaz - temkinli taraf)
    d["sonuc_gorunur"] = (d.gozlem_ay.fillna(99) >= 12 if "gozlem_ay" in d
                          else True)
    d["havuz_puani"] = havuz_puani(d, GRUP[KAYNAK_API])
    return d


def tm_hazirla(raw: pd.DataFrame, bugun=None) -> pd.DataFrame:
    """tm_iddia_defteri (+ tm_oyuncu_sezon) → ortak şema.

    Sezon içinde lig değiştiren oyuncu (9 kişi) iki satırdır: iki ayrı
    kulüp-sezon, defterde de öyle.
    """
    d = raw.copy()
    d["kaynak"] = KAYNAK_TM
    d["anahtar"] = (d.player_id.astype(str) + "-" + d.comp.astype(str)
                    + "-" + d.season.astype(str))
    d["oyuncu"] = d.player_name
    d["kulup"] = d.kulup.fillna("—")
    d["lig"] = d.comp.map(TM_LIG_ADI).fillna(d.comp)
    d["mevki"] = d.ince_mevki.map(lambda m: INCE_MEVKI_ADI.get(m, m)).fillna("—")
    d["kapsam"] = "tam"
    d["tam_ad"] = d.player_name
    gk = d.guncel_kulup if "guncel_kulup" in d else pd.Series(None, index=d.index)
    d["arama_kulup"] = [_metin(a) or _metin(b) for a, b in zip(gk, d.kulup)]
    if "tm_url" not in d:
        d["tm_url"] = None
    d["kisi"] = [kisi(p, None) for p in d.player_id]
    d["sonuc_gorunur"] = (pd.Timestamp(bugun or pd.Timestamp.today())
                          >= pd.to_datetime(d.pencere_bitis))
    d["havuz_puani"] = havuz_puani(d, GRUP[KAYNAK_TM])
    for k in TM_PROFIL:
        if k in d:
            d[f"{k}_hpct"] = grup_yuzdeligi(d, k, GRUP[KAYNAK_TM],
                                           TM_TUMU[k].dusuk_iyi)
    return d
