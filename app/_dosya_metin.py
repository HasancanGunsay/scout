"""Scout dosyasının Türkçe metinleri.

`src/scout/features/dosya.py` yalnızca KOD üretir (hangi risk yandı,
hangi kör nokta gösterilecek). Kelimeler burada.

Bu ayrım bir kez ihlal edildi ve sayfada Türkçe arayüzün ortasında ASCII
cümleler göründü (§35.6). `src/` dilden bağımsız kalıyor.
"""

from __future__ import annotations

import pandas as pd

from scout.features import dosya as D

RISK_METIN = {
    D.KUCUK_ORNEKLEM: (
        "**Küçük örneklem** — {dakika} dakika. Shrinkage gürültüyü "
        "bastırıyor ama {esik} dakikanın altında tek bir iyi dönem skoru "
        "taşıyabilir."),
    D.EKSIK_METRIK: (
        "**Eksik metrik** — rol ağırlığının yalnızca %{kapsam_pct:.0f}'i "
        "hesaplanabildi. Sağlayıcı bu lig-sezonda bazı metrikleri hiç "
        "yayınlamamış olabilir."),
    D.LIG_BOZUK: (
        "**Lig verisi şüpheli** — bu lig-sezonda temel metriklerde eksik "
        "tespit edildi (bkz. Veri Durumu). Skor aşağı yanlı olabilir."),
    D.SONUC_GORUNMEZ: (
        "**Sonuç kısmen görünmez** — menşeindeki lig Transfermarkt'ta oyuncu "
        "bazında izlenmiyor. Kendi ülkesinde üst lige çıkarsa **bunu "
        "göremeyiz**; yalnızca 14 Avrupa birinci ligine geçiş ölçülüyor."),
    D.DEGER_YOK: (
        "**Piyasa değeri yok** — Transfermarkt bu oyuncuya değer biçmemiş. "
        "Modelde bu, en güçlü değişken olarak skoru aşağı çekiyor. "
        "Kalitesizlik değil, **görünmezlik** anlamına gelebilir."),
    D.TEK_SEZON: (
        "**Tek sezon** — yörünge yok. Tek sezonluk parlama ile gerçek sıçrama "
        "bu veriyle ayırt edilemiyor."),
    D.YAS_SINIR: (
        "**Yaş sınırda** — {yas:.1f}. Boylamsal eğride tepe {tepe} yaş (§26); "
        "kalan gelişim penceresi dar."),
}

KOR_METIN = {
    "gk_ayak": "Ayak oyunu **kalitesi** — pas sayısı var ama baskı altında "
               "isabet yok",
    "gk_ceza_sahasi": "Ceza sahası hâkimiyeti ve çıkış kararları",
    "gk_birebir": "Birebirde zamanlama",
    "def_pozisyon": "Pozisyon alma — veri yalnızca **müdahaleyi** sayıyor, "
                    "doğru yerde durup müdahaleye gerek bırakmayanı "
                    "ödüllendirmiyor",
    "def_hava": "Hava topunda zamanlama ve gövde kullanımı",
    "def_pas_yonu": "İlerletici pasın **yönü** — 'pas' sayısı ileri mi geri mi "
                    "ayırmıyor",
    "mf_alan_acma": "Topsuz alan açma ve pres tetikleme",
    "mf_pas_kiriciligi": "Pasın **kırıcılığı** — hat arası mı, yan mı "
                         "(mekânsal veri yok)",
    "mf_tempo": "Oyun temposunu değiştirme becerisi",
    "fw_bitiricilik": "Bitiricilik **kalitesi** — xG olmadan şut seçimi "
                      "değerlendirilemiyor",
    "fw_derinlik": "Derinlik koşusu ve ofsayt zamanlaması",
    "fw_sirti_donuk": "Sırtı dönük oynama ve top tutma",
    "fizik": "Fizik: boy/kilo dışında hiçbir şey yok — hız, dayanıklılık, "
             "sıçrama",
    "karakter": "Karakter: antrenman disiplini, soyunma odası, hocayla ilişki",
    "baski_alti": "Baskı altında karar: 1-0 geride son 10 dakikada ne yapıyor",
    "sakatlik": "Sakatlık geçmişi ve tekrarlama riski",
    "sozlesme": "Sözleşme durumu ve temsilci ilişkisi",
}

KADEME_METIN = {
    0: "izlenen bir birinci ligde **iz yok**",
    1: "**göründü** ama 450 dakikanın altında",
    2: "**rotasyon** (450-899 dk)",
    3: "**yer edindi** (≥900 dk)",
    4: "**ilk-5 ligde yer edindi**",
}


def risk_cumlesi(kod: str, baglam: dict) -> str:
    kalip = RISK_METIN.get(kod)
    if not kalip:
        return kod
    b = dict(baglam)
    if "kapsam" in b:
        b["kapsam_pct"] = 100 * b["kapsam"]
    return kalip.format(**b)


def kor_cumlesi(kod: str) -> str:
    return KOR_METIN.get(kod, kod)


TAHMIN_TURU_METIN = {
    "lig-disi CV": "bu ligi hiç görmemiş modelden (lig dışı çapraz doğrulama)",
    "zaman-disi": "bu sezonu hiç görmemiş modelden (zaman dışı)",
    "uretim": "üretim modelinden (sonucu henüz bilinmeyen sezon)",
    "uretim_kalibresiz": "üretim modelinden, kalibrasyonsuz",
}


def olasilik_notu(r: dict) -> str:
    """Model olasılığının nereden geldiği (7.0) ve kalibrasyon notu (6.6)."""
    s = ("Tahmin " + TAHMIN_TURU_METIN.get(r.get("tahmin_turu"), "bilinmeyen "
         "kaynaktan") + "; lig türüne göre kalibre.")
    ham = r.get("model_ham")
    if pd.notna(ham):
        s += f" Kalibrasyon öncesi: %{100 * ham:.0f}."
        if r.get("kapsam") == "sicrama_only":
            s += (" Düşük görünürlüklü liglerde, en yeni sezonda ham değer "
                  "gerçeğe daha yakın çıktı (PLAN §50).")
    return s


def iddia(r: dict) -> str:
    """Tek cümle, yanlışlanabilir. Dosyanın başlığı."""
    p = [f"**{r['yas']:.1f}** yaşında"]
    if pd.notna(r.get("score_age")):
        p.append(f"{r['league_name']}'de yaşıtlarının **%{r['score_age']:.0f}**'i "
                 f"seviyesinde")
    s = ", ".join(p) + "."
    if pd.notna(r.get("model_olasilik")):
        s += (f" Model, 12 ay içinde izlenen bir birinci ligde yer edinme "
              f"olasılığını **%{100 * r['model_olasilik']:.0f}** veriyor")
        if pd.notna(r.get("lig_taban")):
            s += f"; ligin tabanı %{100 * r['lig_taban']:.0f}"
        s += "."
    return s


def yorunge_cumlesi(r: dict) -> str:
    """Skorlanan sezondan SONRA gerçekten ne olduğu."""
    k = D.kademe_kodu(r.get("kademe"))
    if k is None:
        return "Sonuç verisi yok."
    s = f"İzleyen 12 ayda: {KADEME_METIN.get(k, '?')}"
    if k == 0:
        return (s + ". Menşeindeki lig izlenmiyorsa bu **başarısız demek "
                "değil** (§38.4).")
    lig = r.get("en_iyi_lig")
    if lig:
        s += f" — {lig}"
    dk = r.get("lig_dk_y1") or 0
    if dk:
        s += f", {int(dk)} dakika"
    return s + "."
