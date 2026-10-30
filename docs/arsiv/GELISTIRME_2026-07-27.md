# Geliştirme Notları

**Denetim tarihi:** 27 Temmuz 2026
**Kapsam:** 27 otomatik kontrol + kod incelemesi + veri derinlik analizi
**Sonuç:** 25 geçti · 2 kaldı · 1 kritik hata bulundu ve düzeltildi

Sistem durumu: **çalışıyor ama doğrulanmadı.** Boru hattı uçtan uca sağlam,
veri bütünlüğü temiz, ama sistemin *işe yarayıp yaramadığı* henüz ölçülmedi.
En büyük açık madde bu (→ P0-1).

---

## 0. Denetimde bulunan ve DÜZELTİLEN

### ⛔ Sessiz veri kaybı: `Forward` mevki etiketi
**Bulgu:** API-Football mevki etiketini tutarsız döndürüyor — çoğu zaman
`"Attacker"`, bazen `"Forward"`. Kodda yalnızca 4 etiket tanınıyordu, `Forward`
alanlar `Unknown` grubuna düşüyor → kohortsuz kalıyor → **percentile ve skor
hiç üretilmiyordu.**

**Etki:** 16 oyuncu, 18.196 dakika. İçlerinde:
- **B. Ould-Chikh** — 3.129 dakika (tam sezon), düzeltme sonrası skoru **96.3**
- **A. van den Hurk** — 2.269 dakika, skor **90.4**

Yani sistem, listenin tepesine oynayan oyuncuları sessizce gizliyordu.
Hiçbir hata mesajı yoktu; sadece yoklardı.

**Düzeltme:** `POSITION_ALIASES` eşlemesi + tanınmayan etiket için uyarı
(`src/scout/features/metrics.py`). Artık yeni bir etiket gelirse sessizce
kaybolmuyor, log'a uyarı basılıyor.

**Ders:** "Bilinmeyen kategoriyi sessizce bir kova'ya at" deseni tehlikeli.
Her `else: "Unknown"` dalı bir uyarı üretmeli.

---

## ✅ Doğruluk paketi — tamamlandı (28 Temmuz 2026)

| Madde | Durum |
|---|---|
| P0-2 Tamamlanmamış lig uyarısı | ✅ `league_complete` / `collection_pct` alanları; Keşif'te yarım ligler **varsayılan olarak gizli**, opt-in toggle + uyarı |
| P0-3 Probe artıkları | ✅ `build_db.py` yalnızca `leagues.yaml`'daki ligleri alıyor (Serie C Supercoppa elendi) |
| P1-4 Ölü `refresh_snapshot()` | ✅ `page_setup()`'a bağlandı; Veri Durumu'na "tazele" düğmesi + veri yaşı eklendi |
| P1-5 Sabit kodlanmış tarih | ✅ `latest_tm_db()` en yeni anlık görüntüyü otomatik seçiyor |
| P1-1 Test altyapısı | ✅ **44 test**, `pytest.ini`, günlük işe denetim adımı eklendi |

**Yeni bulunan ve düzeltilen:** API bazı Arjantinli oyuncuda mevki alanını
**boş** döndürüyor (6 oyuncu, 1.823 dakika). `Forward` hatasıyla aynı sınıf:
kohortsuz kalıp skor almıyorlar. Artık uyarı basılıyor ve denetimde
"kohortsuz oyuncu yok" kontrolü var. **Kalıcı çözüm (mevki çıkarımı) → P1-6.**

**Ayrıca:** Keşif'teki lig multiselect'i toggle durumuna bağlı `key` aldı —
kullanıcı "yarım ligleri göster" dediğinde yeni ligler otomatik seçili geliyor.
Öncesinde Streamlit eski seçimi koruduğu için liste boş görünüyordu.

---

## P0 — Doğruluk. Bunlar yapılmadan sisteme güvenilmez.

### P0-1 ⭐ Geriye dönük test hiç yapılmadı
PLAN §8 sistemin başarı kriterini tanımlıyor: *2022 verisiyle U21 listesi üret,
2024'te kimin gerçekten üst lige/daha büyük kulübe geçtiğine bak.* Rastgele
seçimden ve "gol sayısına göre sırala"dan anlamlı ölçüde iyi olmalı.

**Bu test hiç çalıştırılmadı.** Şu an elimizde güzel görünen ama doğruluğu
bilinmeyen bir sistem var. Sistem yanlış olabilir ve bunu bilemeyiz.

- **Bağımlılık:** 2022 sezonu verisi (şu an sadece 2024 toplanıyor)
- **Efor:** 2-3 gün (veri geldikten sonra)
- **Nasıl:** `config/leagues.yaml` sezon sırası zaten `[2024, 2022, 2023]` —
  2022 çiftinin gelmesi bekleniyor. Transfermarkt `transfers` tablosu hedef
  değişkeni sağlar (kim nereye gitti).

### P1-6 Mevki çıkarımı (yeni)
6 oyuncuda API mevki alanı boş → kohortsuz → skorsuz. Şu an uyarı basılıyor
ama sorun çözülmüyor. Bu oyuncuların **istatistikleri var** — kurtarış sayısı
kaleci olduğunu, aksiyon payları hangi mevkiye yakın olduğunu söyler.

- **Çözüm:** `roles/cluster.py`'deki `action_shares()` makinesini kullanarak
  en yakın mevki merkezine ata; `pos_group_inferred` bayrağıyla işaretle.
- **Efor:** 2-3 saat
- **Aciliyet:** Şu an 6 oyuncu (%0.2). 30 günlük toplama sonunda ~60 olabilir.

### P0-4 Eksik doğum tarihi sessizce eleniyor
1 oyuncu (Daan Visser, 30 dk) doğum tarihi olmadan geliyor. Yaş filtresi
uygulandığında sessizce düşüyor. Şu an etkisi ihmal edilebilir ama veri
büyüdükçe artacak.

- **Çözüm:** Sayısını arayüzde göster ("3 oyuncu yaş verisi olmadığı için
  filtre dışında"). Mümkünse Transfermarkt eşleşmesinden doğum tarihini doldur.
- **Efor:** 1 saat

---

## P1 — Güvenilirlik. Sistem çalışıyor ama kırılgan.

### P1-2 Build zinciri atomik değil
`build_features` başarılı olup `build_scores` çökerse, `player_features` yeni
ama `player_scores` eski kalıyor. Arayüz tutarsız veri gösterir ve bunu
belli etmez.

- **Çözüm:** Zinciri tek bir DuckDB transaction'ında çalıştır, ya da her
  tabloya `build_id` damgası koyup arayüzde uyuşmazlığı tespit et.
- **Efor:** 3-4 saat

### P1-3 GIL çökmesinin kök nedeni bulunmadı
27 Temmuz'da `build_links.py` `Fatal Python error: PyEval_SaveThread` ile
çöktü. Manuel çalıştırınca tekrar etmedi. Hipotez: Windows'ta
numpy/scipy/sklearn'in ayrı OpenMP runtime'ları çakışıyor.

Hafifletildi (thread sayısı 1, yeniden deneme) ama **kök neden doğrulanmadı.**
Tekrar edebilir.

- **Öneri:** Tekrarlarsa `faulthandler` çıktısını sakla; gerekirse
  `build_links` adımını ayrı bir süreçte, sklearn import etmeden çalıştır.
- **Efor:** tekrar ederse araştırılacak

> Çözülen maddelerin ayrıntısı yukarıdaki "Doğruluk paketi" bölümünde.

---

## P2 — Metodoloji. Sistemin analitik derinliği.

### P2-1 Lig gücü katsayısı yok (PLAN §5.2)
Ligler arası skor karşılaştırması **geçersiz**. Arayüz bunu uyarıyla
söylüyor ama çözmüyor. Wonderkid avının özü farklı liglerden oyuncuları
kıyaslamak olduğu için bu ciddi bir eksik.

- **Bağımlılık:** Birden fazla ligin verisi (şu an 3 lig-sezon)
- **Yakıt:** Transfermarkt `transfers` tablosu (35.139 kayıt)
- **Efor:** 1-2 hafta — projenin en zor parçası

### P2-2 Yaş eğrisi devre dışı (PLAN §12.2)
Tek sezonluk kesitsel veri hayatta kalma yanlılığı taşıdığı için bilinçli
olarak kapatıldı. Boylamsal (aynı oyuncu, çok sezon) fit gerekiyor.

- **Bağımlılık:** 2022 + 2023 + 2024 aynı oyuncular için
- **Efor:** 2 gün (veri geldikten sonra)
- **Not:** `AgeCurve.informative` şartı sağlanınca kendiliğinden devreye girer

### P2-3 Rol ayrımı yalnızca savunmada
Çift tepelilik testi sadece stoper/bek ayrımını destekledi. Orta saha ve
forvette ayrık rol yapısı yok — mekânsal veri (pas yönü, dokunuş bölgesi)
olmadığı için.

- **Not:** Sistem bunu kendiliğinden yeniden test ediyor; veri büyüdükçe
  yeni ayrımlar destek bulursa otomatik devreye girer. Ek iş gerekmiyor.

### P2-4 Possession-adjusted metrikler yok (PLAN §1.4)
Topa çok sahip olan takımın stoperi az defansif aksiyon yapar — kötü olduğu
için değil, fırsat bulamadığı için. Şu an bu düzeltilmiyor.

- **Gereken:** `/teams/statistics` endpoint'inden takım topa sahip olma oranı
- **Maliyet:** lig-sezon başına ~20 ek istek (kota baskısı)
- **Efor:** 1 gün

### P2-5 Supervised kalibrasyon katmanı yok (PLAN §5.3 Katman 3)
Ağırlıklar şu an tamamen uzman görüşü. "Hangi metrikler gerçekten sıçrama
öngörüyor" sorusu veriyle cevaplanmadı.

- **Bağımlılık:** P0-1 (geriye dönük test) ile aynı veri
- **Efor:** 3-4 gün

---

## P3 — Ürün. Eksik yetenekler.

| Madde | Açıklama | Efor |
|---|---|---|
| **Kadro analizi sayfası** | PLAN §6'da var, yapılmadı. Takım rol haritası, eksik pozisyonlar, "kim kimin yerine oynar" | 1 gün |
| **Benzer oyuncu arama** | PLAN §3'te `similarity/` modülü planlandı, yok. "Bu oyuncuya benzeyenler" | 1 gün |
| **Gelişim eğrisi** | Sezonlar arası oyuncu takibi. Veri var olunca değerli | 4 saat |
| **Kişisel tercih modeli** | PLAN §5.3 Katman 5. Scout raporlarından öğrenme. **Şu an 0 rapor var** — önce rapor birikmeli | — |
| **"Yeni yükselen" uyarısı** | PLAN Faz 8. Geçen haftaya göre en çok sıçrayanlar | 4 saat |

---

## Teknik borç

- **Probe script'leri arşiv durumda** — `probe_fbref_comps.py`, `probe_coverage.py`,
  `probe_players_shape.py`, `analyze_players_fields.py`, `explore_*.py`.
  Artık kullanılmıyorlar ama `scripts/` dizinini kalabalıklaştırıyorlar.
  → `scripts/archive/` altına taşı, README'de arşiv olduklarını belirt.
- **`load_features()` her sayfada tüm tabloyu çekiyor** (2.057 × 240 sütun).
  Şu an sorun değil; 25 lig × 3 sezonda ~50.000 satıra çıkacak. O noktada
  sütun seçimi veya sorgu bazlı yükleme gerekir.
- **`app/views/*.py` içinde tekrarlanan kalıplar** — radar metrik listeleri
  Profil ve Karşılaştırma'da iki kez tanımlı. Ortak modüle taşınmalı.
- **PLAN.md 602 satır** — hâlâ okunabilir ama büyüyor. Bulgular (§11-§14)
  ayrı bir `BULGULAR.md`'ye taşınabilir.

---

## Değiştirilemeyecek kısıtlar (bilinçli kabul)

Bunlar "yapılacak" değil, "böyle kalacak" — ücretsiz veri kaynaklarının
doğasından geliyor.

| Kısıt | Neden |
|---|---|
| Sezonlar 2022–2024 | Ücretsiz plan güncel sezonu vermiyor. Çözüm ücretli plan (~€19/ay). |
| xG yok | Ücretsiz kaynaklarda mevcut değil. Şut hacmi + isabet ile telafi ediliyor. |
| Mekânsal veri yok | Pas yönü/uzunluğu, dokunuş bölgesi yok → rol ayrımı sığ kalıyor. |
| Brezilya kadro kaybı %5-10 | `page<=3` sınırı. Kayıp rastgele; arayüzde uyarı var. |
| İtalya Serie C/D | `stats_players=False` — oyuncu istatistiği hiç yok. |
| Transfermarkt kapsamı | CC0 veri seti yalnızca 14 birinci lig. Serie B'de tavan %56. |
| Fiziksel/karakter verisi | Hiçbir ücretsiz kaynakta yok. Göz testine ve scout raporuna devredildi. |

---

## Önerilen sıra

**Tamamlanan (28 Tem):** P0-2, P0-3, P1-1, P1-4, P1-5 — doğruluk paketi

**Sıradaki (veri beklemeyen):**
1. **P1-6** mevki çıkarımı (2-3 saat) — kohortsuz kalan oyuncuları kurtarır
2. **P0-4** eksik doğum tarihi görünürlüğü (1 saat)
3. **P1-2** build zinciri atomikliği (3-4 saat)
4. **P3** kadro analizi / benzer oyuncu (1+1 gün) — ürün değeri

**Veri bekleyen:**
5. **P0-1 geriye dönük test** — 2022 verisi gelince. **En önemli madde.**
   Sistemin işe yarayıp yaramadığı hâlâ ölçülmedi.
6. **P2-2** yaş eğrisi (çoklu sezon gelince kendiliğinden aktifleşir)
7. **P2-1** lig gücü modeli
8. **P2-5** supervised kalibrasyon

