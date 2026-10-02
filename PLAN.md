# Scout Ağı — Proje Planı

**Amaç:** Düşük görünürlüklü liglerde (Brezilya, Fransa L1/L2, İtalya B/C, Kuzey ligleri) genç yetenekleri
veri üzerinden tespit eden, mevkiye özel puanlayan, sıralayan ve karşılaştıran bir sistem.
Çıktı: "izlenecek 10 oyuncu" listesi → kullanıcı elemesi → 3 kişilik shortlist → göz testi.

**Temel felsefe:** Sistem karar vermez, *dikkati yönlendirir*. Nihai karar göz testinde.
Sistemin işi, izlenecek 10 kişiyi 3000 kişilik havuzdan doğru seçmek.

---

## 0. Karar Özeti (kullanıcı onayı ile sabitlendi)

| Konu | Karar |
|---|---|
| Kapsam | Wonderkid avı: BR Série A/B, FR Ligue 1/2, IT Serie B/C, Kuzey ligleri (SE/NO/DK/NL/BE/AT/CH/PT) |
| Arayüz | Python + Streamlit (lokal web dashboard) |
| Skorlama | Hibrit: uzman ağırlıklı şablon + supervised doğrulama + kullanıcı ayarlı slider'lar |
| Amaç | U21/U23 keşif + transfer hedefi + kadro analizi + serbest sorgulama (hepsi) |
| Veri | Şimdilik %100 ücretsiz kaynaklar |

---

## 1. Senin Kaçırdığın Kritik Noktalar

Bunlar sistemin işe yarayıp yaramayacağını belirleyen şeyler. Fikrin sağlam, ama bu 10 madde
olmadan sistem "güzel görünen ama yanlış oyuncuları öneren" bir şeye dönüşür.

### 1.1 ⭐ Lig Gücü Katsayısı — EN KRİTİK PROBLEM
Serie C'de 90'da 0.8 gol atan bir forvet, Ligue 1'de 0.4 atan forvetten **daha iyi değildir**.
Farklı liglerdeki istatistikler doğrudan karşılaştırılamaz. Bu düzeltme olmadan sistemin
tüm sıralaması çöp olur — ve senin seçtiğin kapsamda (5 farklı ülke, 3 farklı seviye)
bu problem maksimum şiddette.

**Çözüm:** Lig-arası transfer yapan oyuncuların performans değişimini ölçerek ampirik
dönüşüm katsayısı hesaplanır. (Ör. Serie B → Serie A geçen 200 oyuncunun xG/90'ı ortalama
%38 düşüyorsa, katsayı 0.62.) Buna Club Elo ve UEFA katsayıları ile çapraz doğrulama eklenir.
Bu, projenin en değerli ve en özgün parçası. Detay: §5.2.

### 1.2 Örneklem Büyüklüğü / Güvenilirlik
6 maçta 4 gol atan 18 yaşındaki bir çocuk, 34 maçta 12 gol atandan "daha iyi" görünür.
Ham per-90 değerleri az dakikada gürültüden ibarettir.
**Çözüm:** Empirical Bayes shrinkage — az dakikası olan oyuncunun skoru lig ortalamasına
doğru çekilir. Her skorun yanında bir *güven aralığı* gösterilir. Ayrıca metriklerin
"stabilizasyon eşiği" farklıdır (şut sayısı ~500 dk'da stabilize olur, gol dönüşümü ~2000 dk'da).

### 1.3 Yaş Eğrisi Düzeltmesi
19 yaşında Ligue 2'de ortalama bir sezon, 26 yaşında aynı sezondan **çok daha değerlidir**.
Wonderkid avı yaptığın için bu şart.
**Çözüm:** Yaşa göre beklenen performans eğrisi çıkarılır; oyuncu kendi yaş grubuna göre
percentile alır. İki skor gösterilir: **Şimdiki Skor** ve **Yaş-Düzeltmeli Potansiyel Skoru**.

### 1.4 Takım Bağlamı (Context Effects)
Topa çok sahip olan takımın stoperi az defansif aksiyon yapar — kötü olduğundan değil,
fırsat bulamadığından. Kötü takımın kanadı çok top kaybeder çünkü destek yoktur.
**Çözüm:** Possession-adjusted (pAdj) defansif metrikler + takım seviyesinde normalizasyon.
Ayrıca "takımının xG'sinin yüzde kaçına katkı veriyor" gibi *pay* metrikleri.

### 1.5 Mevki Tespiti Güvenilmez
Veri kaynaklarındaki "MF" etiketi hiçbir şey ifade etmiyor. Bir "MF" regista da olabilir,
box-to-box da, 10 numara da. Aynı ağırlıklarla puanlarsan saçmalarsın.
**Çözüm:** Etiket yerine *rol kümeleme* — oyuncunun kendi istatistik profilinden hangi role
ait olduğunu k-means/GMM ile tespit et. 15 mevki yerine ~18 **rol** tanımla (§4).

### 1.6 Kimlik Eşleştirme (Entity Resolution)
"Vinícius José Paixão de Oliveira Júnior" (FBref) = "Vinicius Junior" (Transfermarkt)
= "Vini Jr." (Sofascore). Bu üç kaydı birleştiremezsen ne market value ne sözleşme bilgisi
ekleyebilirsin. Brezilya'da bu problem katlanarak büyüyor (herkesin lakabı var).
**Çözüm:** Ad normalizasyonu + doğum tarihi + kulüp + mevki üzerinden fuzzy matching,
düşük güvenli eşleşmeler için manuel onay kuyruğu. Küçümsenmemeli, gerçek bir iş yükü.

### 1.7 Veriyle Ölçülemeyen Şeyler
Free veride **yok**: fiziksel veri (hız, koşu mesafesi, sprint), ikili mücadele detayı,
karakter/mentalite, yaralanma geçmişi derinliği, oyun zekası, taktik disiplin.
**Çözüm:** Sistem bunları ölçmeye *çalışmamalı*. Bunun yerine bu boşluklar
göz testi aşamasına devredilir ve scout rapor formunda (§1.8) yapılandırılmış olarak toplanır.

### 1.8 ⭐ Geri Besleme Döngüsü (Kapalı Çevrim)
Bu, sistemi zamanla akıllandıran şey ve neredeyse herkes atlar.
İzlediğin 3 oyuncu hakkındaki *kendi kararın* sisteme geri girmezse, sistem hiç öğrenmez.
**Çözüm:** Her shortlist oyuncusu için yapılandırılmış scout raporu (1-5 puanlar + notlar).
Bu kayıtlar zamanla supervised modelin eğitim etiketi olur → sistem *senin gözünü* öğrenir.
Bu, projeyi "genel bir araç"tan "sana özel bir araca" dönüştüren tek şey.

### 1.9 Bağlamsal Filtreler (İstatistik Dışı)
En iyi oyuncu, alınamayacak oyuncuysa listede yer kaplamamalı:
sözleşme bitiş tarihi, piyasa değeri, uyruk/pasaport (AB kotası), FIFA Madde 19
(18 yaş altı uluslararası transfer yasağı — Brezilya taramasında birebir vurur),
yabancı kontenjanı, sakatlık geçmişi.

### 1.10 Veri Hijyeni ve Yasallık
- **Rate limiting:** FBref agresif ban atıyor (3 sn/istek sınırı, aşarsan 429 + IP ban).
  Politeness layer + agresif lokal cache **zorunlu**, sonradan eklenemez.
- **Snapshot'lama:** Her çekim tarihli olarak saklanır. Sezon ortasında veri değişir;
  "3 hafta önce bu oyuncu neredeydi" sorusu cevaplanabilir olmalı → gelişim eğrisi.
- **Idempotent ETL:** Aynı işi iki kez çalıştırmak veriyi bozmamalı.
- **ToS:** Kişisel/analitik kullanım için scraping genelde tolere ediliyor;
  veriyi yeniden yayınlamak/satmak farklı bir konu. Sistem lokal ve kişisel kalacak.

### 1.11 Hayatta Kalma Yanlılığı (Survivorship Bias)
Veride sadece *oynayan* oyuncular var. Yetenekli ama teknik direktör tarafından
oynatılmayan 18 yaşındaki çocuk sisteme hiç görünmez. Bu tamamen çözülemez ama
"az dakika + yüksek verim" kombinasyonu ayrı bir keşif filtresi olarak öne çıkarılabilir.

---

## 2. Veri Kaynakları (Hepsi Ücretsiz)

> ✅ Bu bölüm **Faz 0'da fiilen doğrulandı** (26 Tem 2026). Bulgular §11'de.
> İlk taslaktaki FBref-merkezli plan, ölçüm sonrası terk edildi.

### Katman A — Performans İstatistikleri (çekirdek)

**API-Football** (api-sports.io) — resmî, anahtarlı, izinli REST API.
- Ücretsiz katman: **100 istek/gün**, 00:00 UTC'de sıfırlanır, tüm endpoint'ler açık
- 1200+ lig — İtalya Serie C ve Brezilya Série B dahil (FBref'te yok)
- Oyuncu başına sezonluk: şut, isabet, pas, kilit pas, pas %, top çalma, kesme,
  ikili mücadele (kazanılan/toplam), dribbling, faul, kart, penaltı, dakika, yaş, mevki, rating
- ⚠️ Bilinen zayıflık: alt liglerde detaylı istatistik kapsamı seyrek olabiliyor.
  **`/leagues` endpoint'i sezon başına `coverage` bayrakları döndürüyor** — tek istekle
  tüm kapsam matrisini çıkarabiliyoruz. Faz 1'in ilk işi bu.

**Bütçe yönetimi (100 istek/gün ciddi bir kısıt):**
- Her yanıt diske ham JSON olarak yazılır, asla iki kez istenmez
- Kalıcı istek sayacı + günlük kota koruması (kotayı aşan çağrı reddedilir, beklemez)
- Ligler öncelik sırasına göre kademeli çekilir — tam kapsam birkaç haftaya yayılır
- Sezon sonu verileri bir kez çekilir ve dondurulur; sadece aktif sezon yenilenir

### Katman B — Bağlam / Meta Veri

**transfermarkt-datasets** (`dcaribou/transfermarkt-datasets`) — **CC0-1.0 (kamu malı)**,
hesap gerekmez, haftalık yenilenir, hazır DuckDB dosyası (~195 MB).
- Tablolar: `players`, `clubs`, `competitions`, `games`, `appearances`,
  `player_valuations`, `transfers`, `game_lineups`, `game_events`, `national_teams`
- 40+ müsabaka, 37.000+ oyuncu, 1.800.000+ maç katılımı
- ⭐ `transfers` tablosu **lig gücü modelinin (§5.2) doğrudan yakıtı** — lig değiştiren
  oyuncuların geçmişi buradan gelir. Bu tek başına projeyi hızlandırıyor.
- `player_valuations` → piyasa değeri zaman serisi; `players` → sözleşme bitişi, uyruk, boy, ayak

**Club Elo** — kulüp gücü zaman serisi, lig gücü modelinin çapraz doğrulaması (açık, ücretsiz).

**Wikidata** — doğum tarihi doğrulama ve isim varyantları; kimlik eşleştirmenin (§1.6)
en temiz yardımcısı, özellikle Brezilya lakapları için.

### ❌ Kullanılmayacak Kaynaklar (gerekçeli)

| Kaynak | Neden reddedildi |
|---|---|
| **FBref** | (a) Ölçümde **bozuk/kırpılmış sayfa** döndürdü — Ligue 1'de bile xG sütunu gelmedi; (b) erişim ancak `undetected-chromedriver` + otomatik CAPTCHA/Cloudflare çözümüyle mümkün. Sürekli çalışan bir sistemde bot korumasını sistematik aşmak kapsam dışı. Detay §11.2. |
| **Sofascore / FotMob / WhoScored** | Resmî olmayan, izinsiz endpoint'ler. Aynı kategori. |
| **Kaggle mirror** | Aynı veri CC0 olarak doğrudan indirilebiliyorken hesap zorunluluğu gereksiz. |

### Kütüphaneler
`httpx` + `tenacity` (API istemcisi, retry/backoff), `duckdb` (analitik motor + Transfermarkt
veri seti zaten DuckDB), `pandas`, `scikit-learn`, `statsmodels`, `streamlit`, `plotly`,
`rapidfuzz` (isim eşleştirme), `pydantic` (API yanıt şeması doğrulama).

> `soccerdata` kaldırıldı — FBref kararıyla birlikte gereksizleşti (§11.2).
> Python **3.12** venv kullanılıyor (3.14'te bazı DS wheel'ları henüz eksik).

---

## 3. Mimari

```
Scout/
├── data/
│   ├── raw/          # Ham çekilen dosyalar, tarihli snapshot — ASLA elle düzenlenmez
│   ├── interim/      # Parse edilmiş, henüz birleştirilmemiş
│   ├── processed/    # Temiz, birleştirilmiş, modellenmeye hazır (parquet)
│   └── scout.duckdb  # Sorgu katmanı — Streamlit ve notebook buradan okur
├── src/scout/
│   ├── ingest/       # Kaynak başına bir çekici (fbref.py, fotmob.py, transfermarkt.py...)
│   │   └── _http.py  # Ortak politeness/cache/retry katmanı — TÜM çekiciler bunu kullanır
│   ├── resolve/      # Kimlik eşleştirme (§1.6)
│   ├── features/     # per90, pAdj, percentile, shrinkage, yaş düzeltme
│   ├── league/       # Lig gücü modeli (§1.1) — projenin kalbi
│   ├── roles/        # Rol kümeleme + rol tanımları (§1.5)
│   ├── scoring/      # Ağırlık şablonları + skor hesabı + supervised katman
│   ├── similarity/   # "Bu oyuncuya benzeyenler" arama
│   └── config/       # roles.yaml, leagues.yaml, weights.yaml — kod değil VERİ
├── app/              # Streamlit sayfaları
├── notebooks/        # Serbest keşif (§ amaç: "merak")
├── reports/          # Scout raporları + shortlist dışa aktarımları
└── tests/
```

**İlke:** Ağırlıklar, rol tanımları ve lig listeleri **YAML dosyalarında** tutulur, kodda değil.
Sen bunları kod yazmadan değiştirebilmelisin.

### Kapsam Katmanları (veri seviyesine göre)
- **Tier 1** (tam gelişmiş veri): FR L1/L2, BR Série A, IT Serie B, NL, PT, BE, Kuzey ligleri
  → tam 12-15 metrikli skorlama
- **Tier 2** (kısmi): BR Série B, IT Serie C
  → azaltılmış metrik setiyle skorlama, arayüzde açıkça "sınırlı veri" etiketi
- **Tier 3** (temel): Serie D vb.
  → skorlanmaz, sadece "radar" listesi (aykırı gol/asist üretenler manuel inceleme için)

Tier'lar arası skorlar **asla doğrudan karşılaştırılmaz** — arayüz bunu engeller.

---

## 4. Roller ve Metrikler

15 klasik mevki yerine ~18 **rol** (§1.5). Her rol için 12-15 metrik. Örnekler:

**Ball-Playing CB:** progressive passes/90, pas isabeti (uzun/kısa ayrı), progressive carries,
pAdj interceptions, hava topu kazanma %, ikili mücadele %, savunma hattı yüksekliği vekili,
top kaybı/90, faul/90, ceza sahasına giren pas, pas alma sonrası ilerleme, kart oranı

**Inverted Winger:** non-penalty xG/90, xA/90, dribbling başarı %, ceza sahasına taşıma,
progressive carries/90, şut kalitesi (xG/şut), SCA/90, pres yoğunluğu, top kaybı/taşıma,
ceza sahası dokunuşu/90, geriye pas oranı, hedefe isabetli şut %

**Pressing Forward:** pres/90 (rakip yarı alan), pres başarısı %, hücum yarı alanda top kazanma,
karşı-pres, xG/90, xG dönüşüm farkı, hava topu, tutunma başarısı, hücum derinliği,
ilk-dokunuş kaybı, gol dışı katkı (SCA), koşu mesafesi vekili

> Tam liste `src/scout/config/roles.yaml` içinde tanımlanacak ve senin düzenlemene açık olacak.

---

## 5. Skorlama Motoru

### 5.1 İşlem Hattı
```
Ham istatistik
  → per-90 / possession-adjusted normalizasyon
  → Lig Gücü Katsayısı ile ölçekleme          (§1.1)
  → Rol içinde percentile'a çevirme (0-100)
  → Empirical Bayes shrinkage (dakika bazlı)   (§1.2)
  → Rol ağırlıkları ile ağırlıklı toplam
  → İki çıktı: Şimdiki Skor + Yaş-Düzeltmeli Potansiyel Skoru  (§1.3)
```

### 5.2 Lig Gücü Modeli
1. Son 8 sezonda lig değiştiren tüm oyuncular tespit edilir
2. Her oyuncunun transfer öncesi/sonrası per-90 metrikleri karşılaştırılır
3. Yaş, dakika ve takım gücü kontrol değişkeni olarak modele girer (karışık etkiler modeli)
4. Ortaya lig çiftleri arası bir dönüşüm matrisi çıkar
5. Club Elo ve UEFA katsayıları ile çapraz doğrulanır

Bu tek başına 1-2 haftalık iş ama sistemin geri kalanı buna dayanıyor.

### 5.3 Hibrit Ağırlıklar (senin istediğin gibi)
- **Katman 1 — Uzman şablonu:** Her rol için futbolca mantıklı başlangıç ağırlıkları (YAML)
- **Katman 2 — Veri doğrulaması:** Korelasyon/PCA ile fazlalık metrikler ayıklanır
  (ör. "tackle" ve "interception" %85 korelasyonluysa ikisine ayrı ağırlık vermek hatalı)
- **Katman 3 — Supervised kalibrasyon:** Hedef = "3 yıl içinde daha güçlü bir lige transfer oldu mu"
  Model, hangi metriklerin gerçekten sıçrama öngördüğünü söyler; şablon ağırlıkları buna göre
  ayarlanır. **Model karar vermez, ağırlıkları bilgilendirir.** Şeffaflık korunur.
- **Katman 4 — Senin slider'ların:** Arayüzde her metriğin ağırlığını canlı değiştirebilirsin.
  "Bugün pres yapan bir 9 arıyorum" → pres ağırlığını yükselt, sıralama anında güncellenir.
  Ayarlarını isimlendirip kaydedebilirsin ("Pressing 9 v2").
- **Katman 5 (ileride) — Senin gözün:** Scout raporların (§1.8) yeterli sayıya ulaşınca
  senin beğeni örüntünü öğrenen kişisel bir model.

### 5.4 Şeffaflık Zorunluluğu
Her skorun yanında **neden** o skoru aldığı gösterilir: hangi metrikler ne kadar katkı verdi
(waterfall grafiği). Açıklanamayan skor, güvenilmeyen skordur.

---

## 6. Streamlit Arayüzü — Sayfalar

1. **🔍 Keşif (Discovery)** — Ana ekran. Filtreler: lig, yaş, mevki/rol, dakika, piyasa değeri,
   sözleşme bitişi, uyruk. Sistem sıralaması + skor + güven aralığı. Slider paneli yan tarafta.
2. **👤 Oyuncu Profili** — Radar grafik (rol percentile'ları), skor açıklaması (waterfall),
   sezonluk gelişim eğrisi, benzer oyuncular, meta veriler, video arama linkleri.
3. **⚖️ Karşılaştırma** — 2-5 oyuncu yan yana: üst üste radar, metrik tablosu, farkların vurgusu.
   *(Senin "10'u 3'e indirme" adımının ana aracı.)*
4. **📋 Shortlist & Scout Raporu** — Oyuncu işaretleme, izleme listesi, yapılandırılmış
   rapor formu (§1.8), notlar, PDF/markdown dışa aktarımı.
5. **🧪 Laboratuvar** — Serbest sorgulama. Ham metrik tablosu, herhangi iki metriğin
   dağılım grafiği, özel filtre, DuckDB SQL kutusu. *(Senin "merak" ihtiyacın.)*
6. **🏟️ Kadro Analizi** — Bir takımın kadro haritası, rol bazında güçlü/zayıf noktalar,
   "kim kimin yerine oynar" benzerlik ağı.
7. **⚙️ Veri Durumu** — Hangi lig ne zaman güncellendi, kapsam matrisi, eşleştirme kuyruğu,
   veri kalitesi uyarıları.

---

## 7. Yol Haritası

### Faz 0 — Keşif ve Doğrulama ✅ TAMAMLANDI (26 Tem 2026)
- [x] Ortam kurulumu (Python 3.12 venv)
- [x] FBref lig envanteri çıkarıldı (68 erkek kulüp ligi)
- [x] FBref veri kalitesi ölçüldü → **elendi** (§11.2)
- [x] Alternatif kaynaklar doğrulandı → API-Football + transfermarkt-datasets
- [x] Serie C/D kararı verildi

Bu faz planı kurtardı: FBref üzerine 3 hafta harcanıp sonra bozuk veri fark edilecekti.

### Faz 1 — Veri Boru Hattı (1 hafta) ⬅️ SIRADAKİ
**1a — Transfermarkt ✅ TAMAMLANDI (26 Tem 2026)**
- [x] CC0 DuckDB veri setini indir + sürümle → `data/raw/transfermarkt/2026-07-11/`
- [x] Tabloları keşfet, kapsamı ölç → §11.5 (**sadece 14 birinci lig, 2. lig yok**)
- [x] Şemalar çıkarıldı

**1b — API-Football (kullanıcının API anahtarı gerekir)**
- [ ] Anahtarı `.env` ile yükle (repoya asla girmez, `.gitignore`'da)
- [ ] Kota korumalı istemci: kalıcı sayaç, günlük limit, ham JSON cache, retry
- [ ] `/leagues` → **tek istekle tüm kapsam matrisi** (`coverage` bayrakları)
- [ ] Kapsam matrisine göre lig önceliklendirmesi ve çekim kuyruğu
- [ ] `/players` çekici — kademeli, kotaya saygılı, kaldığı yerden devam eden

**1c — Ortak**
- [ ] DuckDB şeması + idempotent yükleme
- [ ] Veri kalitesi testleri (şema doğrulama, aykırı değer alarmları)

### Faz 2 — Kimlik Eşleştirme ✅ (26 Tem 2026) — bkz. §13
- [x] İsim normalizasyonu (aksan, lakap, çok parçalı Brezilya isimleri)
- [x] Doğum tarihi + uyruk bloklaması + fuzzy isim + kulüp kanıtı
- [x] Manuel onay kuyruğu arayüzü (`app/pages/7_Eslesme_Kuyrugu.py`)
- [x] Kalıcı `player_links` / `player_meta` tabloları
- [x] Piyasa değeri + sözleşme filtreleri arayüze bağlandı

### Faz 3 — Özellik Mühendisliği ✅ (26 Tem 2026) — bkz. §12
- [x] per-90 + oran metrikleri (20 sayım + 5 oran) — `features/metrics.py`
- [x] Empirical Bayes shrinkage + güven aralıkları — `features/shrinkage.py`
- [x] Kohort içi percentile — `features/percentile.py`
- [x] Yaş bandı percentile'ı — `features/age.py`
- [ ] Yaş **eğrisi** — makine hazır ama **kullanılmıyor**, çoklu sezon bekliyor (§12.2)
- [ ] possession-adjusted — takım topa sahip olma verisi gerekiyor (ek API isteği)

### Faz 4 — Lig Gücü Modeli (1-2 hafta) ⭐
- [ ] Lig değiştiren oyuncu veri seti oluşturma
- [ ] Karışık etkiler modeli
- [ ] Dönüşüm matrisi + Club Elo doğrulaması
- [ ] Ayrı doğrulama: "model gerçekten iyi transferleri öngörebiliyor mu?"

### Faz 5 — Skorlama ✅ kısmen (26 Tem 2026)
- [x] `config/roles.yaml` — 14 rol şablonu, futbolca gerekçeli ağırlıklar
- [x] Skor motoru + **açıklanabilirlik (waterfall)** — `scoring/engine.py`
- [x] İki skor: `score` (şimdiki güç) ve `score_age` (yaşıtlarına göre)
- [x] Canlı ağırlık slider'ları (§5.3 Katman 4)
- [x] Rol ayrımı — **doğrulanmış ayrım** yöntemiyle (§14). Serbest kümeleme
      denendi ve reddedildi; yalnızca istatistiksel kanıtı olan ayrım uygulanıyor.
- [ ] Supervised kalibrasyon (§5.3 Katman 3) — çoklu sezon bekliyor

### Faz 6 — Streamlit Arayüzü ✅ (26 Tem 2026)
- [x] Ana sayfa + Keşif + Profil + Karşılaştırma + Shortlist + Laboratuvar + Veri Durumu
- [x] Radar, waterfall, canlı slider, kısmi kapsam uyarıları
- [x] Kadro Analizi sayfası (§34)

### Faz 7 — Geri Besleme Döngüsü ✅ kısmen (26 Tem 2026)
- [x] Scout rapor formu (teknik/fizik/zeka/karakter 1-5 + karar + notlar)
- [x] "Sistemin skoru doğru muydu" sorusu — kalibrasyon etiketi
- [x] Rapor geçmişi + CSV dışa aktarım
- [ ] Kişisel tercih modeli — yeterli rapor birikince

### Faz 8 — Otomasyon
- [ ] Haftalık veri yenileme (zamanlanmış görev)
- [ ] "Yeni yükselen oyuncu" uyarısı — geçen haftaya göre en çok sıçrayanlar

---

## 8. Başarı Kriteri (bunu şimdiden tanımlamak önemli)

Sistem şu testi geçmeli: **Geriye dönük test.**
2022 verisiyle çalıştır, o zamanki U21 listesinin ilk 20'sini al.
2026'da bu 20 oyuncunun kaçı gerçekten üst lige/daha büyük kulübe geçti?
Rastgele seçimden ve "sadece gol sayısına göre sırala"dan anlamlı ölçüde iyi olmalı.

Bu test geçilmezse skorlama motoru yeniden düşünülür. Sistem "hoş görünüyor" diye kabul edilmez.

---

## 9. Riskler

| Risk | Etki | Önlem |
|---|---|---|
| Serie C/D'de gelişmiş veri yok | Kapsam daralır | Tier sistemi; Faz 0'da erken öğreniriz |
| FBref IP ban | Pipeline durur | Politeness + cache; alternatif kaynak yedeği |
| Kaynak HTML yapısı değişir | Scraper kırılır | Şema testleri + kaynak başına izolasyon |
| Kimlik eşleştirme kalitesi düşük | Meta veri eksik kalır | Manuel onay kuyruğu; düşük güvenli eşleşmeler işaretlenir |
| Lig gücü modeli yeterli örnek bulamaz | Karşılaştırmalar şüpheli | Club Elo prior'ı ile Bayesçi harmanlama |
| Aşırı uyum (overfitting) | Sistem geçmişi ezberler | Zaman-bazlı ayrım ile geriye dönük test |

---

## 11. Faz 0 Bulguları (26 Temmuz 2026 — ölçülmüş, tahmin değil)

### 11.1 FBref lig envanteri
`scripts/probe_fbref_comps.py` → `data/raw/fbref_comps.csv` (153 müsabaka, 68 erkek kulüp ligi).

- ❌ **İtalya Serie C ve Serie D FBref'te yok.** Sadece Serie A ve Serie B var.
  (İlk plandaki tahmin doğrulandı.) Brezilya Série C de yok.
- ✅ Beklenmedik kazanımlar: **Eerste Divisie** (NED 2), **Superettan** (SWE 2),
  **Challenger Pro League** (BEL 2), **3. Liga** (GER 3), ve **tüm Güney Amerika** —
  Arjantin, Kolombiya, Uruguay, Ekvador, Şili, Paraguay, Peru, Bolivya, Venezuela.
  Wonderkid avı için bu ligler Big-5'ten çok daha verimli.
- Ayrıca gerçek gençlik ligleri mevcut: U19/U17 DFB Youth League, Premier League 2.

### 11.2 FBref neden elendi
`scripts/probe_coverage.py` ile Ligue 1, Ligue 2, Serie B, Brezilya Série A ölçüldü:

1. **Dönen veri bozuk.** Dördünde de 21 sütunluk temel tablo geldi — xG, npxG, xAG,
   PrgC, PrgP yok. Önbellekteki ham HTML'de `data-stat="xg"` sayısı **sıfır**.
   Kritik nokta: **Ligue 1'de de sıfır.** Ligue 1'de FBref'te kesinlikle xG var,
   yani veri yok değil — bize kırpılmış sayfa servis ediliyor. Sayfalarda
   shooting/passing/possession sekmelerine giden linkler bile yok.
2. **Erişim yöntemi kabul edilemez.** Düz HTTP isteği 403 veriyor. `soccerdata`
   bunu `sb.Driver(uc=True)` (undetected-chromedriver) ve `uc_gui_handle_captcha()` /
   `uc_gui_handle_cf()` çağrılarıyla aşıyor (`soccerdata/_common.py:587,608,613`).
   Tek seferlik bir sorgu ayrı, ama haftalık otomatik yenilenen 36 lig × 6 tablo
   ölçeğinde bot korumasını sistematik aşmak bu projenin kapsamı dışında.
   Pratik gerekçe de var: ban riski + zaten ban'dan önce sessizce yanlış veri veriyor.

**Sonuç:** FBref birincil kaynak olmaktan çıkarıldı. `config/fbref_league_dict.json` ve
probe script'leri arşiv olarak duruyor — lig envanteri hâlâ referans değerinde.

### 11.3 Yeni kaynak stratejisi (doğrulandı)
- **API-Football** ücretsiz katman: 100 istek/gün, tüm endpoint'ler, 1200+ lig — teyit edildi
- **transfermarkt-datasets**: CC0-1.0, 195 MB DuckDB, 11 Tem 2026 tarihli, doğrudan indirilebilir — teyit edildi

### 11.5 Transfermarkt CC0 veri seti — ölçüldü (26 Tem 2026)
İndirildi (195 MB, 11 Tem 2026 sürümü) ve `scripts/explore_transfermarkt.py` +
`scripts/explore_tm_depth.py` ile haritalandı.

**Ne var:**
| Tablo | Satır | Değer |
|---|---|---|
| `game_lineups` | 3.179.016 | kadro/ilk11 |
| `appearances` | 1.894.350 | maç bazında gol/asist/dakika/kart (2012→2026) |
| `game_events` | 1.274.469 | gol, kart, değişiklik |
| `player_valuations` | 507.815 | piyasa değeri zaman serisi |
| `players` | 50.149 | **%99,9 doğum tarihi**, 7.249 U21, 31,5k piyasa değeri, 31,5k sözleşme bitişi, mevki, ayak, boy, menajer |
| `transfers` | 35.139 | transfer geçmişi |

**⚠️ Ne YOK — planı doğrudan etkileyen sınır:**
- **Sadece 1. lig kapsamı. Hiçbir 2. lig yok.** Ligue 2, Serie B, Eerste Divisie,
  Superettan, Challenger Pro League, Brezilya Série B — hiçbiri yok. Serie C zaten yok.
- Son 3 sezonda `appearances` verisi olan **yalnızca 14 lig**: İspanya, İtalya, İngiltere,
  Türkiye, Portekiz, Almanya, Hollanda, Fransa, Rusya, Ukrayna, Belçika, İskoçya, Yunanistan, Danimarka.
- `competitions` tablosunda Brezilya (BRA1) ve Arjantin (ARG1) listeli **ama maç verisi gelmiyor**.
  Kuzey ligleri (Norveç, İsveç) de aynı durumda — sadece Danimarka'nın verisi var.
- Gelişmiş metrik **hiç yok**: xG, pas, top çalma, ikili mücadele yok. Sadece gol/asist/dakika/kart.
- `transfers`: lig değiştiren ve iki ligi de bilinen transfer sayısı **3.455 (1.109 tekil oyuncu)** —
  lig gücü modeli için çalışır ama zayıf; sadece o 14 lig arasında.

**Sonuç:** Bu veri seti senin wonderkid tezini **tek başına taşıyamaz** — hedef liglerinin
hiçbirini kapsamıyor. Ama iki şey için gerçekten değerli:
1. **Meta katmanı**: piyasa değeri, sözleşme bitişi, uyruk, mevki, yaş — bağlamsal filtreler (§1.9)
2. **Prototip laboratuvarı**: lig gücü modeli (§5.2) ve yaş eğrisi (§1.3) bu 14 ligde
   şimdi kurulup doğrulanabilir; API-Football gelince aynı model yeni liglere genişletilir.

**Kritik yol:** Hedef ligler (Ligue 2, Serie B/C, Brezilya B, Kuzey) **yalnızca
API-Football'dan** gelebilir. O hesap açılmadan sistemin ana tezi kurulamaz.

### 11.6 API-Football — ölçüldü (26 Tem 2026, 7 istek harcandı)
Hesap aktif (Free plan, 100 istek/gün). `/leagues` tek istekte 1.235 lig / 8.492 lig-sezon verdi.

**✅ T1 — tam skorlanabilir (58 lig).** Senin hedeflediğin liglerin neredeyse tamamı burada:
| Bölge | Ligler |
|---|---|
| Brezilya | **Serie A, Serie B**, Paulista A1, Carioca 1, Pernambucano |
| Güney Amerika | Arjantin, Şili, Kolombiya, Ekvador, Paraguay (2), Peru, Uruguay |
| Fransa | **Ligue 1, Ligue 2** |
| İtalya | Serie A, **Serie B** |
| Hollanda | Eredivisie, **Eerste Divisie** |
| Kuzey | Danimarka, Norveç, **İsveç Allsvenskan + Superettan**, Finlandiya |
| Diğer 2. ligler | Almanya 2.BL + 3.Liga, İspanya Segunda, İngiltere Championship/L1/L2, Portekiz Segunda, Belçika Challenger, Avusturya 2.Liga, Türkiye 1.Lig |

**⚠️ İtalya Serie C** (3 girone: 138/942/943): `players` ve `lineups` var ama
**`stats_players=False`** — ampirik olarak da doğrulandı, sayfa 1'deki 20 oyuncunun
hiçbirinde lige ait dakika kaydı yok. Skorlanamaz. Serie D de aynı.

**Metrik seti (Brezilya Serie B örneğinde ölçüldü — 23/31 metrik %80+ dolu):**
`appearances, lineups, minutes, rating, goals, assists, shots.total, shots.on,
passes.total, passes.key, tackles.total, tackles.interceptions, tackles.blocks,
duels.total, duels.won, dribbles.attempts, dribbles.success, fouls.drawn,
fouls.committed, cards, penalty.scored/missed, substitutes.in`
→ Mevki başına 12-15 metrik hedefi (§4) **karşılanıyor.**
Boş gelenler: `passes.accuracy` (~%14), `dribbles.past`, `penalty.won`, kaleci metrikleri.
xG **yok** — ücretsiz kaynaklarda xG'den vazgeçiyoruz, `shots`+`rating` ile telafi edilecek.

**🔴 İki sert kısıt:**
1. **Ücretsiz plan yalnızca 2022–2024 sezonlarına erişiyor.** 2025 ve 2026 kapalı.
   Yani sistem **güncel sezonu göremiyor** — "şu an patlayan çocuk kim" sorusu cevaplanamıyor.
2. **100 istek/gün + sayfa başına 20 oyuncu.** Brezilya Serie B tek sezon = 53 istek.
   Bir lig-sezonu çekmek ~30-55 istek → günde ~2 lig-sezon.
   12 lig × 3 sezon ≈ 1.500 istek ≈ **15 gün** tam kota.
   İyi haber: 2022-2024 donmuş tarih, bir kez çekilir ve sonsuza kadar önbellekte kalır.

**Veri şekli tuzağı (kodda çözüldü):** Bir oyuncunun `statistics` dizisinde birden fazla
giriş olabiliyor ve `[0]` çoğu zaman boş bir stub. Doğru yöntem: ilgili `league.id`'ye ait
ve `games.minutes` dolu girişleri almak. `scripts/analyze_players_fields.py` bunu uyguluyor.

### 11.7 Ücretsiz planın gerçek kısıtları (deneyerek bulundu)
Dokümantasyonda yazmayan, ancak çarpınca öğrenilen üç sınır:

1. **Sezon erişimi 2022–2024.** `2025` istenince: *"Free plans do not have access to
   this season, try from 2022 to 2024."*
2. **`page` parametresi en fazla 3.** `page=4`'te: *"Free plans are limited to a maximum
   value of 3 for the Page parameter."* → `/players?league=X&season=Y` ile lig başına
   yalnızca 60 oyuncu alınabiliyor. **Bu rota kullanılamaz.**
3. **Dakikalık hız limiti var** (günlük 100'ün yanı sıra). Ardışık isteklerde `429`.
   İstemciye 7 sn'lik aralık + 429'da geri çekilme eklendi.

**Seçilen rota:** `/players?league=X&team=T&season=Y`
- İstatistikler tek lige filtreleniyor (oyuncu başına tek `statistics` girişi)
- Takım kadrosu genelde ≤3 sayfaya sığıyor (Brezilya'nın kalabalık kadroları istisna —
  Santos 4 sayfa, son sayfa kayıp)
- Maliyet: lig-sezon başına 1 (`/teams`) + takım×sayfa ≈ **40–60 istek**

**Bütçe matematiği:** 25 lig × 3 sezon ≈ 3.400 istek ≈ **34 gün** tam kota.
Bu yüzden `config/leagues.yaml` öncelik sıralı ve genişlik-önce çalışıyor:
sezon sırası `[2024, 2022, 2023]` — 2022+2024 çifti geriye dönük testin (§8) tam ihtiyacı.
İlk ~10 günde öncelik 1-2 liglerinin 2024 sezonu tamamlanmış olur.

### 11.8 Veri temizligi notu — `null` ≠ eksik veri
İlk 374 satırda ölçüldü: `minutes` ve `apps` %100 dolu ama `goals` %69, `key_passes` %75,
`tackles` %82. Dakikası olan bir oyuncunun gol verisinin "eksik" olması mantıksız —
**API sayım metriklerinde sıfır yerine `null` döndürüyor.**

Kural: sayım metriklerinde (`goals`, `assists`, `shots`, `tackles`, `duels`, `dribbles`,
`fouls`, `cards`, `pens`) `null → 0`. Oran/ortalama metriklerinde (`rating`,
`pass_accuracy`) **yapılmayacak** — orada null gerçekten eksik veri.

Kullanılamayacak alanlar: `pass_accuracy` (~%6 dolu), `dribbled_past`, `pens_won`.
`saves`/`goals_conceded` yalnızca kaleciler için anlamlı.

### 11.9 Veri bütünlüğü sorunları — bulundu ve çözüldü
Brezilya Serie B 2024 tam veri setinde (731 oyuncu) yapılan denetimde üç sorun çıktı.
Tutarlılık testleri temiz geçti (0 imkânsız değer, 0 eksik doğum tarihi, rating aralıkta,
yaş dağılımı gerçekçi: 18-40, tepe 25-32).

**A) Sezon içi transferde çift sayım — ciddi.**
Kulüp değiştiren oyuncuda API aynı sezon toplamını *her iki* takım satırında
tekrarlıyor. Kanıt: Dalberson `America Mineiro(1350dk) + Guarani(1350dk)`,
David Braz `Guarani(1246dk) + Goias(1246dk)`, Thales Oleques `Avai(90dk) + Operario(90dk)` —
dakikalar birebir aynı. Bazılarında farklı ama toplamı imkânsız
(Willian Machado 3134+2594 = 5728 dk, bir sezonda mümkün değil).
Satırları toplamak **tüm per-90 metriklerini bozardı.**
→ Çözüm: oyuncu-lig-sezon başına tek satır, en çok dakikalı kayıt esas.
`multi_team` ve `all_teams` alanlarıyla işaretli. 731 oyuncuda 55 vaka (~%7).

**B) Çift kodlanmış karakterler.** `JoÃ£o Pedro Chermont` — kaynakta bozuk
(aynı dosyadaki `João Costa` sağlam). 1055 kayıtta 1 vaka. `fix_mojibake()` ile onarıldı.

**C) `null` = 0 (§11.8).** Sayım metriklerinde null→0 uygulandı, `rating`/`pass_accuracy`
hariç tutuldu.

### 11.10 ⚠️ Kabul edilen eksiklik: Brezilya kadrolarında sayfa kaybı
`page<=3` sınırı yüzünden 4 sayfalık kadroların son sayfası alınamıyor.
**Sayfa sırası dakikayla ilişkili değil** — ölçüldü:

| sayfa | oyuncu | ort. dakika | medyan |
|---|---|---|---|
| 1 | 428 | 359 | 0 |
| 2 | 423 | 745 | 395 |
| 3 | 321 | 809 | 493 |

Sıralama dakikaya göre olsaydı azalırdı; tersine artıyor → sıralama alfabetik/rastgele.
Yani kayıp **rastgele oyuncu kaybı**, sadece kullanılmayan yedekler değil.

Etki: Brezilya liglerinde takımların ~%30-40'ı 4 sayfalık, tahmini kayıp %5-10.
Avrupa liglerinde kadrolar 3 sayfaya sığdığı için kayıp yok.

**Bu bir sistem kusuru ve arayüzde görünür olacak:** Brezilya ligleri için
"kadro kapsamı kısmi" uyarısı gösterilecek. Scout, sistemin herkesi görmediğini bilmeli.

### 11.4 Kapsam kararı
- İtalya **Serie C dahil** → Tier 2 (sınırlı metrik, arayüzde açıkça etiketli)
- İtalya **Serie D kapsam dışı** → güvenilir ücretsiz veri yok, sahte kesinlik üretmektense dışarıda

---

## 12. Faz 3 Bulguları (26 Temmuz 2026)

### 12.1 ⭐ Metrik sinyal gücü — planın temel varsayımı doğrulandı
Shrinkage ağırlığı (`n/(β+n)`), bir metriğin tek sezonda ne kadar bilgi taşıdığını ölçer.
Serie B 2024, 1800+ dakika oynayan 123 oyuncuda:

| Metrik | Ağırlık | Yorum |
|---|---|---|
| passes | 0.98 | çok güvenilir |
| duels | 0.89 | |
| dribbles | 0.87 | |
| key_passes | 0.82 | |
| tackles | 0.76 | |
| shots | 0.72 | |
| **goals** | **0.33** | çoğu gürültü |
| **np_ga** | **0.32** | çoğu gürültü |
| **assists** | **0.28** | çoğu gürültü |

**Gol ve asist, tek sezonda en gürültülü metriklerdir.** Tam sezon oynayan bir forvette
bile gol oranının ancak üçte biri gerçek yeteneği yansıtıyor; gerisi Poisson gürültüsü.

Bu, §4'teki "mevki başına 12-15 metrik" tasarımının sayısal gerekçesi. Sisteme
"gol sayısına göre sırala" dedirtmek, %70 gürültüye göre sıralamak demek.
Ağırlıklandırmada hacim/süreç metrikleri öne çıkacak.

### 12.2 ⚠️ Yaş eğrisi henüz kullanılamıyor — bilinçli olarak devre dışı
Fit edildi ama **kullanılmıyor**. Gerekçe:

Tek sezonluk **kesitsel** veriyle çıkan eğri, yaş ilerledikçe performansın *arttığını*
söylüyor (17'de 6.82 → 33'te 6.95). Bu saçma; sebebi **hayatta kalma yanlılığı** (§1.11):
35 yaşında hâlâ Serie B'de oynayanlar seçilmiş bir azınlık. Ham veri de bunu doğruluyor —
yaşa göre ortalama rating neredeyse düz (6.77–6.95) ve yaşlı oyuncuların dakikası daha fazla.

`AgeCurve.informative` özelliği bu durumu otomatik yakalıyor: **en az 2 sezon** ve
eğri aralığı ≥ gürültünün %25'i şartı sağlanmadan eğri kullanılmıyor.
Şu an: 1 sezon, eğri aralığı 0.131 vs gürültü 0.188 → **devre dışı.**

Doğru yöntem **boylamsal**: aynı oyuncuyu yıllar boyunca izlemek. 2022+2023+2024
birikince yapılacak. O zamana kadar yaş düzeltmesi **yaş bandı percentile'ı** ile
yapılıyor (kaba ama sağlam, hayatta kalma yanlılığından etkilenmez).

### 12.3 Shrinkage: moment yöntemi yerine maksimum olabilirlik
İlk uygulama moment yöntemiyle (`var_toplam − var_örnekleme`) yazıldı ve **çöktü**:
Serie B forvetlerinde τ² = **−0.002** çıktı, sıfıra kırpıldı, herkes ortalamaya çekildi.
Guilherme (2390 dk, 17 g+a) ile Porfírio (37 dk, 1 gol) aynı skoru aldı — sinyal yok oldu.

Sebep: kohortta çok sayıda düşük dakikalı oyuncu varken moment kestirimi kararsız.
Çözüm: **Gamma-Poisson** (sayımlar) ve **Beta-Binom** (oranlar) önsellerini marjinal
olabilirlikle kestirmek. Her zaman geçerli bir önsel verir, düşük maruziyeti doğru
ağırlıklandırır. Düzeltme sonrası sıralama beklendiği gibi:
Guilherme 1., Porfírio ortalamaya çekilmiş.

### 12.4 Kohort büyüklükleri
Percentile için sağlıklı: Serie B 2024'te Defender 244, Attacker 221, Midfielder 216,
Goalkeeper 47. Serie A henüz kısmi (71-88). 12 kişiden küçük kohortlarda percentile
üretilmiyor (NaN) — 8 kişilik havuzda "85. percentile" anlamsız.

---

## 13. Faz 2 Bulguları — Kimlik Eşleştirme (26 Temmuz 2026)

### 13.1 Asıl sorun algoritma değil, kapsam
Naif ad+doğum eşleştirmesi %43.6 tutturuyordu. İlk varsayım "fuzzy matching ile
%85'e çıkarırız" idi. **Yanlış çıktı.** Eşleşmeyen oyuncular Transfermarkt'ta
*hiç yok* — CC0 veri seti yalnızca 14 birinci ligi kapsıyor (§11.5).

Ölçülen tavan (aynı doğum tarihi + uyruğa sahip TM adayı bulunanlar):
| Lig | API oyuncu | TM'de aday var | Tavan |
|---|---|---|---|
| Brezilya Serie A | 265 | 256 | **%96.6** |
| Brezilya Serie B | 731 | 413 | **%56.5** |

Hiçbir algoritma bu tavanı aşamaz.

### 13.2 ⚠️ "Tek aday" kuralı yanlış eşleşme üretti — düzeltildi
İlk uygulama "doğum tarihi + uyruk bloğunda tek aday varsa kabul et" diyordu ve
%66.8'e çıkıyordu. Ama üretilen eşleşmelere bakınca sorun çıktı:

| API | TM eşleşmesi | isim skoru |
|---|---|---|
| Gabriel Silva | Matheus Teixeira | 45 |
| Pablo Dyego | Guilherme Garutti | 36 |
| Matheus Nogueira | Lucas Fernandes | 51 |

Bunlar lakap vakası değil — **aynı gün doğmuş farklı Brezilyalılar**. Oyuncu TM'de
yoksa blok "tek" olur ama o tek kayıt bambaşka biridir.

İsim skoru dağılımı ölçüldü ve **iki kutuplu** çıktı: 376 vaka ≥90 (gerçek),
63 vaka <60 (tesadüf), arada neredeyse hiç kütle yok. Bu yüzden **85 eşiği**
temiz bir kesim yapıyor.

**İlke: yanlış piyasa değeri, eksik piyasa değerinden beterdir.** Scout'u yanlış
oyuncunun peşine düşürür veya iyi oyuncuyu eletir. Şüpheliyi otomatik kabul etmek
yerine manuel kuyruğa alıyoruz.

### 13.3 Nihai sonuç
| Seviye | n | % | |
|---|---|---|---|
| A | 377 | 37.7 | tek aday + isim ≥85 → kabul |
| B | 171 | 17.1 | çoklu aday, net kazanan → kabul |
| C | 105 | 10.5 | belirsiz → manuel kuyruk, **kullanılmıyor** |
| D | 344 | 34.4 | reddedildi |
| – | 2 | 0.2 | TM'de aday yok |

**Kabul: 548/999 (%54.9)** — Serie A %94.7, Serie B %40.4.
Serie B'de tavan %56.5 olduğuna göre, kalan ~16 puan belirsiz bölgede ve
bilinçli olarak reddedildi.

Kulüp benzerliği tie-break olarak eklendi (`Zeca`, `L. Rodríguez` gibi kısa
lakapların birden fazla adaya 100 puan verdiği vakaları çözüyor). Kazanç mütevazı
(+1 eşleşme) ama doğru vakaları kurtarıyor.

### 13.4 DuckDB kilit sorunu — çözüldü
Streamlit açıkken `build_*.py` "dosya başka bir işlem tarafından kullanılıyor"
hatasıyla çöküyordu; günlük otomatik iş de aynı sebeple başarısız olacaktı.
Çözüm: arayüz veritabanının **kopyasını** (`scout_ui_snapshot.duckdb`, ~27 MB)
okuyor, kaynak değişince tazeliyor. Yazma yolları hep açık.
Doğrulandı: tüm zincir Streamlit açıkken sorunsuz çalıştı.

---

## 14. Rol Ayrımı Bulguları (26 Temmuz 2026)

### 14.1 Serbest kümeleme denendi ve **reddedildi**
Planlanan yöntem GMM ile kümelemeydi (aksiyon payları → CLR → PCA → GMM/BIC).
Uygulandı, çalıştırıldı, sonuç kabul edilemezdi:

- silhouette **0.13–0.28** — net küme yapısı yok
- iki ayrı kümeye **aynı isim** düştü
- küme profilleri neredeyse özdeş: "Kanat" şut payı 0.050 vs "Santrfor" 0.053

Ham paylarla ilk deneme daha da kötüydü: `passes` tüm aksiyonların %61–84'ünü
oluşturup diğer metrikleri eziyordu. CLR (merkezli log-oran) dönüşümü bunu
düzeltti ama bu sefer küçük bileşenleri (blok: 0.005 vs 0.016) aşırı büyüttü.
Yöntem sorunu değildi — **veride ayrık rol yapısı yoktu.**

### 14.2 ⭐ Doğru soru: yapı gerçekten var mı?
Kümelemeyi zorlamak yerine soru doğrudan soruldu. Çift tepelilik testi
(Sarle bimodality coefficient + 1'e karşı 2 bileşenli GMM, BIC karşılaştırması).
Brezilya A+B 2024, 900+ dakika:

| Mevki | Metrik | Bimodalite | 2 bileşen daha iyi | Sonuç |
|---|---|---|---|---|
| **Defender** | **dribbles/90** | **0.588** ✓ | **+55.9** ✓ | **DESTEKLENDİ** |
| Defender | key_passes/90 | 0.487 | +56.2 | red |
| Midfielder | key_passes/90 | 0.537 | +20.5 | red |
| Midfielder | np_goals/90 | 0.525 | +48.9 | red |
| Attacker | shots/90 | 0.326 | −14.1 | red |
| Attacker | tackles/90 | 0.509 | +4.3 | red |

**Yalnızca stoper/bek ayrımı gerçek.** Orta saha ve forvette dağılımlar
tek tepeli — ayrık roller değil, sürekli bir spektrum var.

Bu şaşırtıcı değil: elimizde **mekânsal veri yok** (pas yönü/uzunluğu, dokunuş
bölgesi, ilerletici aksiyon). Onlarsız bir stoper ile bir ön libero birbirine
benzer. Ücretsiz kaynakların temel sınırı bu.

### 14.3 Seçilen yöntem: doğrulanmış ayrım
Kör kümeleme yerine, her aday ayrım **önce test edilir**, yalnızca çift tepelilik
kanıtlanırsa uygulanır. Kanıt yoksa mevki grubu korunur.

Avantajı: veri büyüdükçe (yeni ligler, yeni sezonlar) daha fazla ayrım
istatistiksel destek kazanıp **kendiliğinden devreye girer**. Sistem olmayan
yapıyı uydurmaz, olanı kaçırmaz.

### 14.4 Uygulanan ayrımın doğrulaması
Brezilya A+B 2024, 900+ dakika — ders kitabı ayrımı:

| Rol | n | çalım/90 | kilit pas/90 | faul kazanma/90 | blok/90 | pas/90 | mücadele % |
|---|---|---|---|---|---|---|---|
| **Bek** | 52 | 1.43 | 1.07 | 1.00 | 0.24 | 38.2 | 0.53 |
| **Stoper** | 104 | 0.32 | 0.40 | 0.55 | 0.60 | 45.3 | 0.58 |

Rol şablonları da bu ayrıma bağlandı (`cluster:` alanı): stoper şablonları
artık bekleri, bek şablonları stoperleri puanlamıyor. Ayrım bir ligde
uygulanamazsa şablon tüm mevki grubuna düşer — oyuncu skorsuz kalmaz.

**Kohortlar sağlıklı:** Serie B'de Stoper 159, Bek 85; Serie A'da 45 ve 39.

---

## 16. Sessiz Skorlama Hataları (11 Ağustos 2026 — ölçülmüş)

Üç hata da **denetimden geçiyordu**. Ortak sebepleri aynı: `scoring/engine.py`
eksik bir sütunu sessizce atlar ve kalan ağırlığı yeniden normalize eder.
Skor makul görünür, oysa metrik hiç sayılmamıştır. Yanlış cevabı **doğru
cevaptan ayırt edecek kontrol yoktu.**

### 16.1 `rating` hiçbir skora katkı vermiyordu

13 rol şablonunda ağırlıklıydı (4–30 arası) ama `build_features.py`
`rating_pct` sütununu hiç üretmiyordu. xG'miz olmadığı için rating tek genel
katkı göstergemizdi.

**Kanıt:** stoper şablonu toplam ağırlık 100, rating 8 → ölçülen kapsam
0,916–0,922. Eksik olan tam olarak %8.

**Düzeltme:** `PLAIN_COLS = ["rating"]` percentile hattına eklendi
(`_pct` ve `_agepct`). Ölçülen: Spearman(rating, skora katkı) = **+0,952**.

### 16.2 Kaleci skorlaması ağırlığın %82'sini kaybediyordu

`saves` ve `goals_conceded` per-90/shrinkage/percentile hattından hiç
geçmiyordu. "Kaleci - Kurtaran" şablonu **kurtarışı ölçmüyordu**; 586 kaleci
yalnızca pas ve kazanılan ikili mücadeleye göre sıralanıyordu.

**Kanıt:** kullanılabilen ağırlık 15/85 = **0,176** — 14 ligin hepsinde
bire bir bu değer. Finlandiya'nın 29 kalecisinin tamamı özdeş 51,7 alıyordu.

**Düzeltme:** `GK_COUNT_METRICS` eklendi. `COUNT_METRICS`'ten **ayrı**
tutuldu, çünkü ortak hattaki `fillna(0)` (a) saha oyuncularını "0 kurtarış"
ile kohorta sokar, (b) verisi eksik 63 kaleciyi "hiç kurtarış yapmamış"
gösterir. Kaleci kapsamı 0,176 → **0,949**.

### 16.3 `fouls_made` ve `cards` İKİ KEZ ters çevriliyordu

`percentile.invert()` sütunu çeviriyordu. `engine.py` ise
`f"{metric}_inverted"` işaret sütununu arıyor, **bu sütun projede hiç
üretilmiyordu**, dolayısıyla ikinci kez çeviriyordu.

**Net sonuç:** çok faul yapan ve çok kart gören oyuncu ödüllendiriliyordu.
Savunma şablonlarında ağırlığın %8'i ters işliyordu.

**Düzeltme:** `invert()` artık `{şablon_anahtarı: sütun_tabanı}` sözlüğü alıp
`<anahtar>_inverted` işaretini bırakıyor; motorun zaten var olan koruması ilk
kez gerçekten çalışıyor. Yaş bandı percentile'ları da (`_agepct`) aynı yönde
çevriliyor — daha önce çevrilmiyordu ve tesadüfen doğru çalışıyordu.

Ölçülen: Spearman(kart/90, katkı) = **−0,928**,
Spearman(faul/90, katkı) = **−0,831**.

### 16.4 Bir daha olmaması için eklenen iki denetim

| Kontrol | Ne yakalar |
|---|---|
| `her sablon agirliginin sutun karsiligi var` | 16.1 ve 16.2'yi ilk gün yakalardı |
| `ters cevrilen metrikler isaretlenmis` | 16.3'ü ilk gün yakalardı |

Ayrıca `bozuk karakter yok` kontrolü düzeltildi: `Ã`/`Â` içermek tek başına
bozukluk değil (`Ângelo`, `M. El Âdfaoui` geçerli isimler). Doğru ölçüt,
düzelticinin ismi **hâlâ değiştirebiliyor** olması.

**Genel ders:** "metrik eksikse sessizce atla ve yeniden normalize et"
davranışı skorların çökmesini engelliyor ama hatayı da görünmez kılıyor.
Kapsam (`coverage`) bu yüzden sadece hesaplanmakla kalmayıp **denetlenmeli**.

---

## 17. Geriye Dönük Test Sonuçları (11 Ağustos 2026 — ilk gerçek sınav)

`python scripts/backtest.py`. Tahmin **yalnızca 2022** verisiyle, sonuç 2023/24'te.
Sıralama her ligin içinde yapıldı (§5.2 gereği), sonra havuzlandı. Tüm
yöntemler **aynı havuzdan** seçiyor (tam vaka kısıtı).

### 17.1 Sonuç değişkeni neden 2025 değil 2023/24

Yol haritası "2022 → 2026" öngörüyordu. Ölçtüm: TM anlık görüntüsünde
değerleme kapsamı 2023'ten sonra çöküyor (20.452 → 9.592 → 5.986 oyuncu) ve
2025 değerlemesi kalanlar sistematik olarak daha değerli (2022 medyanı 900k
vs 600k). Bu ufukla ölçülürse **"değerlemesi olmak" sonucun kendisi olur** ve
test kendini doğrular. Kapsamın tam olduğu son pencere kullanıldı.

### 17.2 Sonuçlar

Değer sıçraması = 2023/24 değeri ≥ 2 kat **ve** ≥ 1M EUR.
Terfi = 2024'te daha üst kademe ligde görünmek.

| Örneklem | Sonuç | Kazanan | Sistemin katı | Geçti mi |
|---|---|---|---|---|
| Tüm yaşlar, ilk 20 | değer sıçraması | **SİSTEM %26,2** | **2,58×** | ✅ |
| Tüm yaşlar, ilk 10 | değer sıçraması | SİSTEM = gol %26,0 | 2,13× | ✅ berabere |
| Tüm yaşlar, ilk 20 | terfi | piyasa değeri %55,0 | 1,11× | ❌ |
| Tüm yaşlar, ilk 10 | terfi | piyasa değeri %60,0 | 1,11× | ❌ |
| **U21, ilk 10** | değer sıçraması | **dakika %60,0** | 1,24× | ❌ |
| **U21, ilk 20** | değer sıçraması | gol %55,0 | 1,32× | ❌ |
| **U21, ilk 10** | terfi | piyasa değeri %85,0 | **0,96×** | ❌ |
| **U21, ilk 20** | terfi | piyasa değeri %75,0 | 1,07× | ❌ |

### 17.3 Dürüst hüküm

**Sistem, asıl kullanım amacı olan U21 keşfinde henüz değer katmıyor.**
Sekiz yapılandırmanın yalnızca ikisinde kabul kriterini geçiyor ve o ikisi de
tüm yaşları kapsayan yapılandırma. U21'de "dakika" ve "gol" gibi naif
tabanların gerisinde kalıyor; bir yapılandırmada rastgeleden bile kötü (0,96×).

İki desen tutarlı ve yorumlanabilir:

1. **Değer büyümesi** (kim gelişti / ucuz kaldı) → saha metrikleri kazanıyor.
   Wonderkid avının hedefi tam olarak bu.
2. **Lig terfisi** (kim yukarı taşındı) → 2022 piyasa değeri açık ara
   kazanıyor. Mantıklı: kulüpler bilinen ismi satın alıyor, terfi itibarla
   sürülüyor. Skorumuz burada rekabet edemiyor ve etmesi de beklenmemeli.

### 17.4 Testin kendi sınırları (mazeret değil, ölçülmüş)

- **U21 örneklemi çok küçük:** 125 ve 161 oyuncu; yalnızca 2 ligde eşik
  üstünde aday var. Bu güçte bir testle orta büyüklükte bir etki görülmez.
- **Taban oran çok yüksek:** U21'de %36 ve %50. Taban %50 iken
  "rastgelenin 2 katı" kriteri **matematiksel olarak imkânsız** (%100 gerekir).
  Kriter tüm yaşlarda anlamlı (taban %11 ve %27), U21'de değil.
- Yalnızca 5 ligde 2022 verisi var (Brezilya A/B, Eerste Divisie, Ligue 2,
  Arjantin kısmi).

**Bu yüzden hüküm "sistem işe yaramıyor" değil, "U21'de işe yaradığına dair
kanıt yok".** İkisi farklı şeyler ve ikincisi de kabul edilemez.

### 17.5 Sonraki adım için hipotezler (henüz sınanmadı)

- Ağırlıklar futbolca verildi, hiç kalibre edilmedi (ADIM 5).
- U21'de dakika sayısı bu kadar güçlü bir taban olması anlamlı: genç bir
  oyuncuya güvenilip oynatılması, ölçtüğümüz her şeyden fazla bilgi
  taşıyor olabilir. Dakika bir **özellik** olarak modele girmiyor.
- Ligler arası kıyas hâlâ geçersiz (ADIM 4); test lig içi yapıldığı için bu
  sonuçları bozmuyor ama ürünün kendisini sınırlıyor.

---

## 18. Ağırlık Kalibrasyonu Sonuçları (11 Ağustos 2026)

`python scripts/calibrate.py`. L2 cezalı lojistik regresyon, **lig-dışarıda-bırak**
çapraz doğrulama. Rastgele k-fold kullanılmadı: aynı ligin oyuncuları hem
eğitimde hem testte olurdu, model lig seviyesini ezberlerdi. Özellik seçimi
de her fold'un **kendi içinde** yapıldı — tüm veriye bakarak seçmek klasik
bir sızdırma biçimi.

### 18.1 Sonuçlar (hepsi fold dışı)

| Sonuç · örneklem | Kazanan | Elle ağırlık | Kalibre | Hüküm |
|---|---|---|---|---|
| Değer sıçraması · tüm yaşlar, ilk 20 (774/91) | kalibre+dakika %28,7 | %26,2 | +2,5 puan | ihmal edilebilir |
| **Değer sıçraması · U21, ilk 10 (115/45)** | **dakika %60,0** | %46,7 | **%33,3–43,3** | **daha kötü** |
| Lig terfisi · tüm yaşlar, ilk 20 (462/185) | piyasa değeri %55,0 | %42,5 | %48,8–50,0 | iyileşti ama yetmedi |

### 18.2 Hüküm: kalibrasyon şu an gerekçelendirilemiyor

Kazanç en iyi durumda 80 seçimde **2 isabet** (21 → 23). Bu gürültünün içinde.
U21'de ise kalibrasyon sistemi açıkça bozuyor — 17 özellik / 115 örnekle
model ezberliyor ve fold dışında çöküyor. Sade model (fold içi seçimle
4 özellik) de kurtarmadı (%36,7).

**Öğrenilmiş ağırlıklar `roles.yaml`'a YAZILMADI.** Bu veriyle öğrenilen şey
ağırlık değil gürültü olurdu. Elle verilen futbolca ağırlıklar, bu örneklemde
öğrenilebilecek her şey kadar iyi.

Tekrar çalıştırılmalı: 2022 ligleri arttıkça örneklem büyüyecek. Şu an
yalnızca 5 lig var.

### 18.3 Asıl değerli çıktı: hangi metrik gerçekten ayırt ediyor

Lig içi tekil AUC (tüm yaşlar, değer sıçraması, 844 oyuncu). 0,50 = bilgi yok.

| Metrik | AUC | Yorum |
|---|---|---|
| **çalım/90** | **0,676** | tek başına **tüm sistem skorundan** (0,666) iyi |
| rating | 0,658 | §16.1'de düzeltilen metrik — değerini kanıtladı |
| np_gol+asist/90 | 0,633 | |
| şut/90 · **dakika** · anahtar pas · ikili mücadele | 0,591–0,596 | |
| piyasa değeri (2022) | 0,578 | piyasa bu ufukta zayıf tahminci |
| top çalma/90 | 0,514 | **sinyal yok** |
| faul/90 · ikili mücadele % | 0,517–0,520 | **sinyal yok** |
| blok/90 | 0,441 | **ters yönde** — zayıf takımda oynamanın vekili olabilir |

Savunma metriklerinin (top çalma, blok, ikili mücadele yüzdesi) değer
büyümesini hiç öngörmemesi dikkat çekici. İki okuması var ve ayırt edemiyoruz:
savunma katkısı gerçekten piyasa değerine yansımıyor olabilir, ya da bu
metrikler savunma katkısını ölçmekte yetersiz (§11'deki xG/possession eksiği).

### 18.4 Doğrulanan hipotez: dakika bir özellik olmalı

§17.5'te "genç oyuncuya güvenilip oynatılması bilgi taşıyor" demiştim.
Ölçüldü: U21'de **dakika tek başına en iyi sıralayıcı** (%60,0 · 1,54× ·
şansın %95 eşiğini geçti) ve U21 modelinde en büyük katsayı (0,242).

Ama dakikayı doğrudan skora eklemek riskli: dakika hem sebep hem sonuçtur
(iyi oyuncu çok oynar), ve şablon ağırlığına konursa "çok oynayan yaşlı
oyuncu" listeleri şişirir. Ürün kararı gerekiyor — ayrı bir **güven sinyali**
olarak gösterilmesi mi, yoksa skora girmesi mi?

---

## 19. Yaş Eğrisi Kendiliğinden Aktifleşti — ve Yanlıştı (11 Ağustos 2026)

2022 verisi gelince `AgeCurve.informative` şartı sağlandı ve eğri
tasarlandığı gibi **kendiliğinden devreye girdi**. Ama fit edilen eğri şuydu:

| Yaş | 16 | 20 | 26 | 32 | 38 |
|---|---|---|---|---|---|
| Beklenen rating | 6,767 | 6,863 | 6,931 | 6,950 | 6,965 |

**Monoton artıyor. Hiç tepe yapmıyor.** Gerçek futbolcu eğrisi 26-28
civarında tepe yapıp 30'dan sonra düşer.

Bu, [age.py](src/scout/features/age.py)'nin kendi uyardığı hatanın ta kendisi:
*"egri 'yas ilerledikce performans artiyor' der ki bu sacmadir."*

### 19.1 Kapı neden tutmadı

Kapı "en az iki sezon" şartı koyuyordu ve bunu **boylamsal veri** için vekil
saymıştı. Ama iki sezonu **havuzlayıp** fit etmek boylamsal yapmaz — fit hâlâ
kesitseldir. 35 yaşında hâlâ oynayanlar seçilmiş bir azınlıktır ve eğri
onların iyiliğini yaşa mal eder.

Yani şart sağlandı, sorun sağlanmadı.

### 19.2 Eklenen şekil kontrolü

`informative` artık dört şart arıyor. Yeni olan ikisi:

- **tepe noktası 23-32 yaş aralığında** olmalı
- **tepeden sonra anlamlı düşüş** olmalı (aralığın en az %15'i)

Monoton artan bir yaş eğrisi hayatta kalma yanlılığının **imzasıdır**. Şekli
futbolca yanlışsa eğri veriye değil yanlılığa uymuş demektir.

Gerçek veriyle sonuç: `tepe 45.0 yas (23-32 bekleniyor), tepeden dusus 0.000`
→ **reddedildi.** Yaş düzeltmesi yine yaş bandı percentile'ı ile yapılıyor.

`tests/test_age_curve.py` bu davranışı kilitliyor: monoton artan ve monoton
azalan eğriler reddedilmeli, 26 civarında tepe yapan eğri kabul edilmeli.

### 19.3 Etki

`rating_vs_age` skorlamada kullanılmıyor (motor `rating_pct` okuyor), bu
yüzden hiçbir skor bozulmadı. Hata yayılmadan yakalandı.

**Gerçek çözüm hâlâ boylamsal fit:** aynı oyuncunun birden çok sezonunu
izlemek. Şu an aynı oyuncunun 2022+2024'ü var ama fit hâlâ kesitsel kurulu.
ADIM 3 bu yüzden kapanmadı.

---

## 20. Güven Sinyali (11 Ağustos 2026)

§18.4'te ölçülen bulgu ürüne alındı: U21'de dakika, ölçtüğümüz her metrikten
iyi bir tek başına sıralayıcı. Ama **skora eklenmedi.**

**Neden skora değil:** dakika hem sebep hem sonuçtur (iyi oyuncu çok oynar).
Şablon ağırlığına konsaydı listeler "çok oynayan yaşlı oyuncu"ya kayardı —
wonderkid avının tam tersi. Ayrıca metrik seti ileride değişirse skorun
içinden sökmek zor olurdu.

**Nasıl gösteriliyor:** ayrı bir sütun/rozet olarak.

| | Soruyu cevaplar |
|---|---|
| **Skor** | Ne kadar iyi oynadı |
| **Güven** | Kulübü ona ne kadar güvendi |
| `reliable` bayrağı | İstatistik güvenilir mi (örneklem yeterli mi) |

Son ikisi karıştırılmamalı — biri kulüp davranışı, diğeri örneklem büyüklüğü.

Ölçüm `minutes_agepct`: **yaşıtları arasında** aldığı dakikanın percentile'ı.
19 yaşında %70 dakika almak dikkate değer, 28 yaşında sıradan. Yaş bandı
kohortu küçükse (<8 kişi) genel kohort percentile'ına düşer.

Eşikler: ≥80 Vazgeçilmez · ≥60 Sık oynuyor · ≥35 Rotasyon · altı Az süre.

---

## 21. Yayınlanmayan Metrik ≠ Sıfır (11 Ağustos 2026 — en ciddi veri hatası)

Lig gücü modeli için cetvel metriği ararken bulundu.

### 21.1 Bulgu

**Veikkausliiga 2024'te 17 metrik hiç yayınlanmıyor** — şut, ikili mücadele,
top çalma, anahtar pas, asist, blok... Maksimum değerleri bile 0.

Buna rağmen sistem **1.301 skor üretiyordu**, ortalama 50,5 ± 4,3, 220 farklı
değer. Finlandiya'ya bakan bir kullanıcı gayet normal görünen sıralı bir liste
görüyordu — tamamı uydurulmuş sıfırlardan.

**En tehlikeli yanı buydu: çıktı makul göründüğü için hata görünmezdi.**

### 21.2 Kök sebep — iki yerde birden

§11.8'deki "sayım metriklerinde null = 0" kararı doğruydu: API, oynamış
oyuncuda bile "0 gol" yerine `null` döndürüyor. Ama kural, sağlayıcının o
ligi hiç yayınlamadığı durumu ayırt etmiyordu. **"Bilinmiyor" sessizce
"sıfır"a dönüşüyor ve oyuncu ölçülmemiş değil KÖTÜ görünüyordu.**

Düzeltmek iki yer gerektirdi — ilkini yapıp bittiğini sanmak kolaydı:

| Yer | Neydi | Ne oldu |
|---|---|---|
| `build_db.py` | tüm `null`'lar `0` | (lig, sezon) içinde metriğin **tamamı** null ise NaN kalır |
| `metrics.py::_sum_cols` | `fillna(0)` | bileşenlerin tamamı NaN ise sonuç NaN (`min_count=1`) |

İlkini yapıp ölçtüğümde kapsam 0,826'da kaldı — çünkü ikincisi sıfırları geri
koyuyordu. **Kapsam 0,826 → 0,080.**

### 21.3 Eksik maç sorunu (farklı bir hata)

Pas/90'ı tüm lig-sezonların medyanına oranladım:

| Lig-sezon | Pas/90 | Medyana oran |
|---|---|---|
| Portekiz Segunda Liga 2024 | 5,6 | **%15** |
| İsveç Superettan 2024 | 18,1 | **%48** |
| (diğer 26 lig-sezon) | 31–44 | %83–118 |

Burada veri null değil, **eksik**: dakikalar tam ama detaylı istatistik
maçların bir kısmında yok (Ligue 2'de oyuncu başına 811,7 pas, Segunda
Liga'da 108,7 — ortalama dakika 1864 vs 1752).

Lig içi sıralama etkilenmiyor (herkes eşit etkileniyor), ama **ligler arası
her kıyas bozuluyor.** Bu ligler lig gücü modelinden çıkarıldı.

### 21.4 Kapsam eşiği

`min_coverage: 0.35` eklendi. Ağırlığın bu oranından azı hesaplanabiliyorsa
skor üretilmez (1.374 skor bastırıldı). Küçük kohortta percentile üretmeme
kuralının eşdeğeri: **eksik veriden makul görünen bir sayı üretmek, sayı
üretmemekten daha zararlı.**

### 21.5 Eklenen denetimler

| Kontrol | Ne yakalar |
|---|---|
| `her lig-sezonda temel metrikler yayinlanmis` | 21.1 — ligi isim isim söyler |
| `sayimlar dakikayla tutarli (eksik mac yok)` | 21.3 — medyanın %50'sinin altını |

Ayrıca yan bulgu: `dribbled_past` ve `pens_won` **hiçbir ligde** yok.
Şablonlarda kullanılmıyorlar.

---

## 22. Lig Gücü Modeli — İlk Deneme (11 Ağustos 2026)

`python scripts/league_strength.py`

### 22.1 Lig ortalamaları yapısal olarak kullanılamaz

Bu ölçüldü ve model tasarımını belirledi:

- **`rating`:** sağlayıcı lig **içinde** normalize ediyor. Allsvenskan 6,992
  > Premier League 6,944 > La Liga 6,907. Cetvel olarak değersiz.
- **`ikili mücadele kazanma %`:** lig içinde sıfır toplamlı, ortalaması her
  ligde matematiksel olarak ~0,50 (ölçüldü: 0,506–0,521). Çalım başarısı da öyle.
- **Genel kural:** lig içi göreli her metriğin ortalaması inşaat gereği
  sabittir. **Hiçbir lig içi toplam lig gücünü ölçemez.**

Tek geçerli yol köprü oyuncular. Ortalamalar sabit olsa da **bireysel değişim
bilgilidir**: üst lige çıkanın kendi kazanma oranı düşer.

### 22.2 Model

`delta_i = beta(varış) − beta(çıkış) + yaş etkisi + gürültü`, en küçük kareler,
referans lig 0. Yaş kontrolü şart (2022→2024 iki yıllık boşluk). Altı cetvel
metriği ayrı fit edilip R²'ye göre ağırlıklı birleştirildi.

### 22.3 Sonuç: YAYINA ALINMADI

| Belirti | Değer |
|---|---|
| Köprü oyuncu | 303 (bozuk ligler hariç) |
| R² aralığı | 0,054–0,172 |
| Önselle Spearman uyumu | **+0,576** (eşik 0,60) |
| Premier League / La Liga / Bundesliga | **tabloda yok** — köprü 5, 3, 3 |
| Brezilya Serie B vs Serie A | −0,026 vs 0,000 — neredeyse aynı zorlukta |

Kök sebep yapısal: **2022 verisi yalnızca 5 ligde**, dolayısıyla graf yıldız
şeklinde ve büyük liglere 3-5 köprü düşüyor.

Karar kodun içine gömüldü: `yuz_gecerliligi()` önsel sıralamayla Spearman
uyumunu ölçer, eşiğin altındaysa **çıkış kodu 1** verir. Bir sonraki
çalıştırmada kimse "sıralama iyi görünüyor" deyip geçemez.

+0,576 eşiğe yakın — model yanlış değil, **yetersiz beslenmiş.** 2022/2023
ligleri geldikçe tekrar çalıştırılmalı.

---

## 10. Sonraki Adım

**Faz 1a hemen başlayabilir** (Transfermarkt CC0 veri seti — hiçbir engel yok).

**Faz 1b için kullanıcıdan gereken tek şey:** api-sports.io ücretsiz hesabı ve API anahtarı.
Anahtar `.env` dosyasına konur, repoya girmez.

### Açık riskler / izlenecekler
- API-Football'un alt liglerdeki (özellikle Serie C) istatistik derinliği belirsiz.
  `/leagues` kapsam bayrakları ilk istekte bunu netleştirecek. Sonuca göre Serie C
  Tier 2'den Tier 3'e (radar listesi) düşebilir.
- 100 istek/gün, tam kapsamın birkaç haftaya yayılması demek. Sistem bu kısıtla
  çalışacak şekilde tasarlanıyor (kademeli çekim + kalıcı cache), sonradan eklenmiyor.

---

## 23. Lig Gücü Modeli — Kuruldu, Ölçüldü, Skora UYGULANMADI (19 Ağustos 2026)

`python scripts/league_strength.py --yaz`

### 23.1 Seçilim yanlılığı: ölçüldü ve kapatıldı

Köprü yönteminin zayıf noktası, *kim* taşındığının *nereye* taşındığıyla
ilişkili olması. 997 köprü üzerinde ölçüldü:

| Yön | n | 2022 dakikası | Yaş |
|---|---|---|---|
| Yukarı çıkan | 526 | 1.759 | 23,2 |
| Aşağı inen | 267 | 1.447 | 27,0 |

Aşağı inenler yaşlı ve kenarda kalmış oyuncular; metrikleri lig zorluğundan
**bağımsız** olarak düşüyor ve varış ligini yapay olarak "zor" gösteriyordu.
Belirtisi: Almanya 3. Liga üst sıralarda çıkıyordu.

Altı düzeltme denendi ve önsel sıralamayla uyuma göre **ölçüldü**:

| Varyant | rho | 3. Liga sırası |
|---|---|---|
| mevcut (yaş + yaş²) | +0,551 | 4 |
| yalnızca takım taşınması | +0,657 | 5 (ama 4 lig kayboluyor) |
| **≥900 dk çıkış + dakika kontrolü** | **+0,644** | **7** |
| çift-eşit ağırlık | +0,581 | 3 |
| iki sezonda da ≥900 dk | +0,580 | 3 |

Seçilen: çıkışta düzenli oyuncu şartı + çıkış dakikası kontrolü. Yanlılığın
**kanalını** doğrudan kapatıyor, lig kapsamını daraltmıyor.

Ayrıca bir hata düzeltildi: model `league_name`'e göre gruplarken **Brezilya
Serie A ile İtalya Serie A tek lig sayılıyordu** (aynı şekilde iki Serie B) —
üstelik 339 köprüyle referans lig oydu. Anahtar ülke/lig biçimine çevrildi.

### 23.2 Sonuç: kapı geçildi

Spearman uyumu **+0,595 → +0,654** (eşik 0,60). Sıralama:

```
England/Premier League   +0,278      Netherlands/Eredivisie  -0,271
Spain/La Liga            +0,162      Denmark/Superliga       -0,296
Italy/Serie A            +0,090      Belgium/Challenger      -0,316
Germany/Bundesliga       +0,007      Norway/Eliteserien      -0,434
France/Ligue 1            0,000      Sweden/Allsvenskan      -0,475
   (referans)                        Netherlands/Eerste Div. -0,639
```

Big 5 en üstte, İskandinavya ve Eerste Divisie en altta. Katsayılar
`league_strength` tablosunda — **yalnızca kapı geçilirse** yazılıyor,
geçilmezse eski tablo siliniyor.

### 23.3 Ama skora UYGULANMADI — ölçüm bunu söyledi

Düzeltmeyi `skor + k × zorluk` biçiminde uygulayıp geriye dönük testte
**havuzlanmış** (ligler arası) sıralamayla ölçtüm. k taraması:

| k | değer sıçraması (ilk 40) | lig terfisi (ilk 40) |
|---|---|---|
| **0** | **%32,5** | **%37,5** |
| 5 | %25,0 | %27,5 |
| 10 | %22,5 | %27,5 |
| 34 | %17,5 | **%5,0** |

**Düzeltme arttıkça sonuç monoton kötüleşiyor.** k=0 dört yapılandırmanın
üçünde en iyi, dördüncüsünde fark yok.

**Neden:** ölçtüğümüz sonuç değer **büyümesi**, lig düzeltmesi ise değer
**seviyesi** için optimize ediyor. Premier League oyuncusu zaten pahalı;
değerinin ikiye katlanması nadir. Wonderkid fırsatı tam da modelin "kolay"
dediği liglerde. Bu bulgu projenin kuruluş amacını doğruluyor.

### 23.4 Ürün kararı: bağlam, düzeltme değil

Zorluk katsayısı arayüzde **bilgi** olarak gösteriliyor: "en zor X, en kolay
Y, aralarında Z standart sapma fark var" + katlanır tam tablo. Skor
değişmiyor. Kullanıcı aynı skorun hangi seviyede kazanıldığını görüyor.

Eski "lig gücü katsayısı henüz kurulmadı" uyarısı yalnızca tablo yoksa
gösteriliyor.

---

## 24. Gelişim Eğrisi — Sezonlar Arası Takip (19 Ağustos 2026)

`src/scout/features/development.py` · arayüz: **Yükselenler** sayfası

Wonderkid avında tek bir sezonun fotoğrafı değil **yönü** önemli. 18 yaşında
70 alıp 20 yaşında 88 alan oyuncu, iki sezondur 85 alandan daha güçlü bir
sinyaldir.

Örneklem: iki sezonda da skoru olan **3.002 oyuncu** (≥450 dk × 2 sezon).

### 24.1 Tuzak: "doğal rol" bir MAKSİMUMDUR

İki sezonu olan 5.659 oyuncunun **2.732'si doğal rol değiştirmiş** — yani ham
skorları karşılaştırmak farklı şablonları karşılaştırmak olurdu. Çözüm olarak
rolü sabitledim. Ama bu ikinci ve daha sinsi bir hata doğurdu.

`player_natural_role` oyuncunun **14 rol arasındaki en yüksek** skorunu
seçiyor. Rolü tek bir sezona sabitlemek, o sezonun skorunu maksimum,
ötekini maksimum-olmayan yapar. Fark **kurgu gereği** kayar.

Ölçüldü — aynı veri, ters işaret:

| Rol nereden sabitlendi | Ortalama "gelişim" |
|---|---|
| 2022 (önceki) | **−5,41** |
| 2024 (sonraki) | **+3,89** |
| **iki sezonun ortalaması (simetrik)** | **−0,78** |

Simetrik seçim — *iki sezonun ortalamasını en yükseğe çıkaran rol* — hiçbir
sezonu kayırmadığı için yön yanlılığını kaldırıyor. Varsayılan bu.

`tests/test_development.py` bunu kilitliyor: sentetik veride (gerçek gelişim
yokken) tek-sezon sabitlemesi zıt işaretli sapma vermeli, simetrik seçim ~0.

### 24.2 Lig değişimi: ölçüldü, düzeltme GEREKMEDİ

Beklentim, lig değiştirenlerin deltasının sistematik düşük olmasıydı
(Højlund Serie A → Premier League, 80,0 → 19,3 gibi tek tek vakalar çarpıcı).

Ölçüm bunu **doğrulamadı**:

| | n | ortalama delta |
|---|---|---|
| Lig değiştirmeyen | 1.995 | −5,42 |
| Lig değiştiren | 1.002 | −5,38 |

Fark −0,27. Lig gücü katsayısıyla düzeltme uygulasaydım **fazla düzeltmiş**
olurdum (k=34'te fark +2,83'e çıkıyor). Düzeltme yapılmadı; lig değişimi
yalnızca **işaretleniyor** ve arayüzde filtrelenebiliyor — tek tek oyuncuda
hâlâ önemli olabilir.

### 24.3 Yaş: kaymanın sebebi değil

Kayma bütün yaş bantlarında aynı (−3,5 ile −6,4 arası), yani yaşa bağlı
değil. Sebep 24.1'deki maksimum-seçimi etkisiydi.

### 24.4 Yüz geçerliliği

En çok yükselenler listesi tanıdık isimler veriyor: **N. Woltemade**
(3. Liga → Bundesliga, 49,7 → 85,4), **R. Vermant** (Challenger Pro →
Jupiler Pro, 47,3 → 92,8), **N. Ohio** (Jupiler → Eredivisie, 45,2 → 83,3).

---

## 25. Benzer Oyuncu Arama (19 Ağustos 2026)

`src/scout/features/similarity.py` · arayüz: **Oyuncu profili** sayfasının altı

Scout iş akışının merkezindeki soru: beğendiğin oyuncuyu alamıyorsan, ona
benzeyen ve ulaşılabilir olanı bul.

### 25.1 Stil ≠ kalite

İki şey karıştırılmamalı: oyuncunun ne **yaptığı** (stil) ve bunu ne kadar
**iyi** yaptığı (kalite). Bu modül yalnızca stili ölçer; kaliteyi kullanıcı
skor/yaş/fiyat filtreleriyle kendisi süzer. İkisini tek sayıda birleştirmek
"iyi oyuncular birbirine benzer" gibi anlamsız bir sonuç verir.

**Ölçüldü:** stil komşularının skor farkı **15,3**, rastgele oyuncuların
**17,5**. İkisi yakın — yani benzerlik kalite vekili değil. Fark çok küçük
olsaydı liste sadece "iyiler" olurdu.

### 25.2 Neden CLR (centered log-ratio)?

Ham per-90 değerlerde **pas her şeyi ezer**: bir orta saha 40 pas/90 yaparken
1 şut/90 atar. Düz oran alınsa herkesin vektörü "%95 pas" olur ve farklar
kaybolur. CLR log-oran uzayına taşıyor — önemli olan mutlak hacim değil,
aksiyonların birbirine oranı.

**Beklenmedik faydası:** CLR ölçeğe duyarsızdır. Bazı liglerde sayımlar
sistematik eksik (Segunda Liga medyanın %15'i, §21.3) ama tüm metrikler aynı
oranda eksik olduğu için **log-oranlar değişmez** — stil vektörü bozulmaz.
Bu özellik `tests/test_similarity.py` içinde kilitli.

### 25.3 Yanlılık kontrolleri

| Test | Sonuç |
|---|---|
| Komşular aynı ligden mi? | %21,6 (rastgele beklenti %5,4) — 4× yoğunlaşma |
| Komşular aynı kalitede mi? | 15,3 vs 17,5 — hayır |

Lig yoğunlaşması muhtemelen gerçek taktik kültür farkı; komşuların %78'i
başka liglerden geldiği için ölçüm ligler arası iş yapıyor. Yine de bilinsin.

### 25.4 Yüz geçerliliği

**Lamine Yamal** → L. Sané, N. Madueke, F. Mastantuono, A. Hadj-Moussa
(hepsi kanat/çalımcı). **N. Woltemade** → M. Thuram, C. De Ketelaere, Hulk
(uzun forvetler). Kullanım amacı da çalışıyor: Yamal'a %77 benzeyen
Hadj-Moussa'nın piyasa değeri €2M.

### 25.5 Arayüz kararı

Yaş filtresi **varsayılan olarak sınırsız**. İlk sürümde "oyuncunun yaşı +2"
idi; gizli bir varsayılan filtre sonuçları sessizce daraltır ve kullanıcı
sebebini bilmez. Ayrıca "bunun gibi ama ucuz" ararken daha yaşlı bir oyuncu
çoğu zaman tam da ulaşılabilir olandır.

---

## 26. Boylamsal Yaş Eğrisi (29 Ağustos 2026) — ADIM 3 KAPANDI

`src/scout/features/age_long.py` · `build_scores.py` üretiyor · `age_curve_long` tablosu

Yaş eğrisi bu projede **iki kez reddedilmişti** (§19): kesitsel fit hayatta
kalma yanlılığı taşıyor, 35 yaşında hâlâ oynayanlar seçilmiş bir azınlık ve
eğri onların iyiliğini yaşa mal ediyordu — sonuç 16'dan 38'e monoton artan
bir "eğri"ydi.

2023 sezonunun gelmesiyle **1.689 oyuncunun üç sezonu** birden oluştu ve
boylamsal yaklaşım mümkün hale geldi.

### 26.1 Fark yöntemi

Aynı oyuncunun ardışık sezonları arasındaki değişime bakılıyor:

```
delta_yıllık = (metrik[t2] − metrik[t1]) / (sezon[t2] − sezon[t1])
```

Oyuncu **kendi kontrolü** olur; kalitesi diferansiyelde düşer. Yaş başına
ortalama delta eğrinin o yaştaki eğimidir, eğimler toplanınca eğri çıkar.

### 26.2 `rating` yine kullanılamadı — tutarlı bir bulgu

`rating` ile fit monoton artıyor, tepe 36. Sebebi §22.1'de ölçtüğümüzle aynı:
sağlayıcı rating'i **lig içinde normalize ediyor**. Gerileyen oyuncu daha
zayıf lige gidince rating'i değişmiyor. Rating yaş düşüşünü **yapısal olarak**
göremiyor. Hem lig gücü cetveli hem yaş eğrisi için aynı sebeple elendi.

Kullanılan metrik: `score`.

### 26.3 İki düzeltme gerekti

**Düzleştirme.** Ham kutu ortalamaları gürültülü ve kümülatif toplam gürültüyü
**biriktiriyor**: 19'da −1,66, 20'de +0,68, 21'de −0,71 gibi zıplamalar
eğrinin şeklini birkaç kutunun esiri yapıyordu. Eğim, yaşın polinomu olarak
modellenip öyle toplanıyor (derece 2).

| Düzleştirme | Tepe | Şekil kapısı |
|---|---|---|
| yok (derece 0) | 19 | ❌ |
| derece 2 | 23 | ✅ |
| derece 3 | 24 | ✅ |

**Aynı lig kısıtı.** `score` lig içi percentile olduğu için lig değişimi
kohort değişimi demek; delta iki sebebi karıştırıyor. Ölçüldü:

| | Geçiş | Tepe |
|---|---|---|
| tüm geçişler | 7.084 | 23 |
| **yalnızca aynı lig** | **4.848** | **25** |

Aynı lig kısıtı varsayılan. (Not: lig değiştirenlerin ortalama deltası +0,04,
değiştirmeyenlerin −0,51 — yani hipotezimin **tersine**, değiştirenler daha
iyi. Yine de kohort karışımı ortadan kalksın diye kısıt uygulanıyor.)

Sonuç: **tepe 25 yaş**, düşüş 13,02, şekil kapısı geçildi.

### 26.4 Ürüne alma kararı — ölçüldü, KOŞULLU

Lig gücündeki dersi tekrarladım: kapıyı geçmek ürüne koymak için yetmez.
`skor − yaşında beklenen seviye` ölçüsü geriye dönük testte sınandı.

| Kohort | Sonuç | Yaş eğrisi | Ham skor |
|---|---|---|---|
| U21 | değer sıçraması | **1,42×** | 1,18× |
| U21 | terfi | **1,30×** | 1,07× |
| U23 | değer sıçraması | 1,71× | 1,71× |
| **U23** | **terfi** | **1,62× (birinci)** | 1,52× |
| **tüm yaşlar** | değer sıçraması | **0,55×** | 2,02× |
| **tüm yaşlar** | terfi | **0,51×** | 2,22× |

Genç kohortta **hiçbir yerde zarar vermiyor, çoğu yerde iyileştiriyor** ve
U23 terfisinde sistemi birinci sıraya taşıyor. Tüm yaşlarda **felaket** —
çünkü eğri 25'ten sonra dikçe düştüğü için 35 yaşındakine devasa bonus veriyor.

**Karar:** düzeltme arayüzde yalnızca **azami yaş ≤23** iken sunuluyor.
Üstünde toggle hiç görünmüyor, yerine sebebi yazan bir not çıkıyor.
Düzeltme *canlı* skora uygulanıyor — kullanıcı ağırlıkları değiştirince
düzeltme de güncelleniyor.

Etkisi: ham skorda 8. olan Lamine Yamal (17,5) 2. sıraya, Estêvão (17,7)
1. sıraya çıkıyor. İlk-20'nin 19'u ortak — yeni liste değil, yeniden sıralama.

### 26.5 Kalan yanlılık — dürüstçe

Fark yöntemi hayatta kalma yanlılığını **azaltır, yok etmez**. Çok kötü
oynayan oyuncu ertesi sezon oynamaz, dolayısıyla onun negatif deltası hiç
ölçülmez. Bu, eğriyi özellikle ileri yaşlarda yukarı çeker; yani **gerçek
düşüş tahmin edilenden sert olabilir**. Gençlerde sorun çok daha küçük —
19 yaşında kötü oynayan oyuncuya genellikle ikinci bir sezon verilir, ve
ürün zaten yalnızca genç kohortta kullanıyor.

---

## 27. "Yükselenler" Sinyali Sınandı — Zayıf Çıktı (29 Ağustos 2026)

2023 sezonunun gelmesiyle **1.433 oyuncunun üç sezonu** oluştu ve
Yükselenler özelliğinin kuruluş varsayımı ilk kez sınanabildi:
*"yön, fotoğraftan önemlidir."*

**Tasarım:** tahmin 2022→2023 yükselişiyle, sonuç 2024'te. Örneklem dışı.
Rol üç sezonun ortalamasına göre sabitlendi (§24.1'deki simetri kuralı).

### 27.1 Önce bir yapaylık — kendi ölçümüme güvenmedim

İlk ölçüm: Spearman(2022→2023 yükselişi, 2023→2024 devamı) = **−0,414**,
yani "yükselen geri geliyor". Ama bu sayı **mekanik olarak** negatife
eğilimli: `skor_2023` tahmin ediciye artı, sonuca eksi işaretle giriyor,
dolayısıyla ölçüm gürültüsü tek başına negatif korelasyon üretir.

Bu yüzden hüküm **dışsal sonuçlarla** verildi — bizim skor gürültümüzü
paylaşmayan iki sonuç: lig terfisi ve piyasa değeri artışı.

### 27.2 Dışsal sonuçlar: yükseliş her yapılandırmada seviyenin gerisinde

| Örneklem · sonuç | Yükseliş | Mevcut seviye | Dakika |
|---|---|---|---|
| Tüm yaşlar · lig terfisi | 1,28× | **1,81×** | 0,85× |
| U23 · lig terfisi | 1,19× | **1,64×** | 1,64× |
| Tüm yaşlar · değer +%50 | **0,99×** | **1,37×** | 1,37× |
| U23 · değer +%50 | 1,24× | 1,35× | **1,76×** |

Dördünde de yükseliş, mevcut seviyenin gerisinde. Birinde **şans
seviyesinde** (0,99×). Bir sezonluk yükselişin büyük kısmı ortalamaya dönüş.

### 27.3 Ama seviye sabitken ek bilgi katıyor

Seviyeye göre üst %30 havuzu alınıp içinde yükselişe göre sıralandığında:

| Sonuç | En çok yükselen 20-30 | En az yükselen | Fark |
|---|---|---|---|
| Lig terfisi | %23,3 | %16,7 | **+6,7 puan** |
| Değer +%50 | %45,0 | %35,0 | **+10,0 puan** |

Spearman +0,048 ve +0,080 — zayıf ama tutarlı yönde. Örneklemler küçük
(429 ve 85), bu yüzden "işaret doğru, güç düşük" demek doğru olur.

### 27.4 Ürün kararı

**Yükseliş birincil sıralama ölçütü değil, iyi oyuncular arasında ayırt
edici.** Sayfa buna göre değiştirildi:

- Kenar çubuğuna **asgari skor filtresi** eklendi (varsayılan 60) — doğru
  akışı zorunlu kılıyor: önce seviyeye göre ele, sonra yükselişe göre sırala
- Sayfanın başına ölçülmüş sayılarla bir **uyarı** kondu; kullanıcı listeyi
  tek başına keşif aracı sanmasın

Bu, kendi kurduğum bir özelliğin varsayımının veriyle çürütülmesi. Özellik
kaldırılmadı çünkü koşullu değeri ölçüldü ve pozitif — ama sunumu artık
ölçüme uyuyor.

---

## 28. Kabul Kriteri Hatalıydı — Düzeltildi ve Tablo Tersine Döndü (29 Ağu 2026)

### 28.1 Hata

PLAN §8'deki kriter "rastgelenin en az **2 katı**" idi. Ama ulaşılabilir
azami kat **1/taban_oran**:

| Taban oran | Azami mümkün kat |
|---|---|
| %13,5 (tüm yaşlar) | 7,4× |
| %33,1 (U23) | 3,0× |
| %42,4 (U21) | **2,36×** |

Aynı eşik bir kohortta rahat, ötekinde neredeyse imkânsız. §17.4'te fark
edilmiş ama düzeltilmemişti — bu yüzden sistem aylarca "kriteri geçemiyor"
diye kaydedildi.

### 28.2 Yeni ölçü: ölçeğe duyarsız başarı

```
basari = (gözlenen − rastgele) / (1 − rastgele)
```

0 = şans seviyesi, 1 = seçilen herkes pozitif. Taban orandan bağımsız.

Kabul için **üçü birden**: (1) şansın %95 eşiğini geç, (2) tüm tabanları geç,
(3) başarı ≥ 0,15.

### 28.3 Düzeltme tabloyu TERSİNE ÇEVİRDİ

| Kohort | Eski ölçü (kat) | **Yeni ölçü (başarı)** |
|---|---|---|
| Tüm yaşlar · değer | 1,54× *(en iyi görünüyordu)* | **0,083** *(en kötü)* |
| U21 · değer | 1,15× *(kötü görünüyordu)* | 0,115 |
| **U23 · değer** | 1,26× | **0,133** *(en iyi)* |
| U23 · terfi | 1,17× | **0,095** |

**Sistem tam da tasarlandığı yerde — genç kohortta — en iyi çalışıyormuş.**
"Tüm yaşlarda iyi, U21'de kötü" değerlendirmemiz taban oran farkının
yarattığı bir yanılsamaydı. Bu, aylardır yanlış okuduğumuz bir tablo.

Hüküm değişmedi (hiçbiri 0,15 eşiğini geçmiyor, hepsi şansın üstünde) ama
**nereye yatırım yapılacağı** değişti: iyileştirme çabası genç kohorta
odaklanmalı, çünkü sinyal orada.

---

## 29. Dakika Skora Katılmalı mı? — Sınandı, HAYIR (29 Ağu 2026)

"Dakika" tabanı üç ayrı testte sistemi geçmişti (§18.4, §27). §20'de dakikayı
skora koymama kararı verilmişti (dairesellik + "çok oynayan yaşlı" kayması).
O karar sınandı: `skor` ile `minutes_agepct` harmanlanıp ağırlık tarandı.

| Yapılandırma | ağırlık 0 | 0,15 | 0,30 |
|---|---|---|---|
| U21 · değer | 1,18 | **1,42** | 0,94 |
| U21 · terfi | 1,11 | **1,53** | 1,53 |
| U23 · değer | **1,70** | 1,40 | 1,40 |
| U23 · terfi | **1,89** | 1,42 | 1,66 |
| Tüm yaşlar · değer | 2,03 | **2,58** | 2,58 |
| Tüm yaşlar · terfi | **2,21** | 2,21 | 1,87 |

Altının üçünde kazanıyor, üçünde kaybediyor — **tutarlı desen yok**. Üstelik
U21'de 0,15'te 1,42 iken 0,30'da 0,94'e düşüyor; komşu ağırlıklar arasındaki
bu sıçrama sinyal değil gürültü imzası (20 kişilik seçimde 2 isabet farkı
oranı uçuruyor).

**Karar: dakika skora katılmıyor.** §20'deki özgün karar sınandı ve ayakta
kaldı. Güven sinyali olarak ayrı gösterilmeye devam ediyor.

---

## 30. Kalibrasyon U23'te Tekrar Çalıştırıldı — Yine BENİMSENMEDİ, Ama Sebebi Değişti (29 Ağu 2026)

§28'de sinyalin genç kohortta olduğu ölçülünce kalibrasyon U23'te ve
24 ligle (önce 5 ligdi) tekrar çalıştırıldı.

### 30.1 Sonuç: küçük ama TUTARLI kazanç

| Sonuç · örneklem | Elle ağırlık | Kalibre + dakika | Kazanan |
|---|---|---|---|
| Değer sıçraması (1.183 oyuncu) | 1,25× | **1,32×** | gol (1,39×) |
| Lig terfisi (946 oyuncu) | 1,17× | **1,24×** | piyasa değeri (1,33×) |

11 Ağustos'un aksine yön **her iki sonuçta da aynı** (+0,07). Ama kazanç
270 seçimde 6-7 isabet ve hiçbir varyant en iyi basit tabanı geçemiyor.

### 30.2 Asıl bulgu: öğrenilen katsayılar TAKIM BAĞLAMINI öğreniyor

Kalibrasyon savunma metriklerine ısrarla negatif katsayı veriyor. Sebebini
araştırdım.

**Adım 1 — mevki karışması mı?** Hayır. Mevki grubu İÇİNDE de düşük:

| Metrik | Tüm | Stoper | Orta saha | Forvet |
|---|---|---|---|---|
| top çalma | 0,470 | 0,464 | 0,455 | 0,462 |
| kesme | 0,465 | **0,424** | 0,499 | 0,464 |

**Adım 2 — takım bağlamı mı?** Evet:

| Metrik | Tüm | Stoper |
|---|---|---|
| ham savunma aksiyonu/90 | 0,483 | 0,456 |
| takım savunmasına oranlı | 0,488 | 0,479 |
| topa sahip olma vekiliyle | 0,492 | **0,514** |
| **TAKIMIN savunma yoğunluğu** | **0,466** | **0,408** |

**Takımın kendi savunma yoğunluğu, oyuncunun metriğinden daha güçlü
anti-tahminci.** Oyuncunun "çok top çalması" büyük ölçüde takımının
zayıflığını miras alıyor: zayıf takım çok savunur, zayıf takımın oyuncusu
daha az sıçrar. Takım bağlamı arındırılınca metrikler 0,5'e yaklaşıyor —
sahte anti-sinyal kayboluyor, yerine pozitif sinyal gelmiyor.

### 30.3 Bu yüzden kalibrasyon benimsenmedi — yeni ve daha güçlü gerekçe

Öğrenilmiş ağırlıklar benimsenirse sistem şunu öğrenmiş olur:
**"zayıf takımın oyuncusundan kaçın".**

Bu, wonderkid avının **tam tersidir**. Projenin kuruluş fikri düşük
görünürlüklü liglerde, çoğu zaman zayıf takımlarda oynayan yeteneği
bulmaktır. Piyasa sonucuna fit edilen bir model, piyasanın zaten baktığı
yere bakmayı öğrenir.

Bu, §4'teki "ağırlıklar futbolca verilir" kararının ilk kez **ölçülmüş**
gerekçesidir. Önceki gerekçe "kazanç gürültü içinde"ydi; şimdi ek olarak
"öğrenilen şey yanlış şeydir" biliniyor.

### 30.4 Kalıcı bulgu: savunma metriklerimiz takım bağlamıyla kirli

Bu bir ölçüm sorunu, piyasa sorunu değil. Doğru çözüm possession-adjusted
metrikler (ROADMAP §6'da zaten "ek API gerekiyor" diye kayıtlı). Takım
toplamına oranlama kısmi bir düzeltme sağlıyor (0,456 → 0,479) ama
yetersiz — gerçek çözüm takım topa sahip olma verisi.

**Savunma metrikleri şablonlarda KALIYOR.** Kariyer ilerlemesini
öngörmemeleri, futbol kalitesini ölçmedikleri anlamına gelmiyor; bir
stoperin işi savunmaktır ve piyasa bunu ucuza alıyor olabilir. Ölçtüğümüz
tüm sonuçlar piyasa sonuçları — bu ikisini ayırt edecek verimiz yok.

---

## 31. VERİ BİLİMİ DENETİMİ (29 Ağustos 2026)

Biriken analizler ilk kez metodolojik gözle, **yeniden ölçülerek** gözden
geçirildi. Özet: bir yöntem sağlam çıktı, bir hüküm ayakta kaldı, üç
sonuç çürüdü ve bir ürün kararı geri alındı.

### 31.1 ✅ Shrinkage doğru çalışıyor — bilinen doğruyla sınandı

Sentetik veri: gerçek oran biliniyor, shrinkage onu geri bulmalı.

| Maruziyet | Ham RMSE | Çekilmiş RMSE | Ortalama ağırlık |
|---|---|---|---|
| 10 maç | 0,1470 | **0,0836** | 0,344 |
| 2 maç | 0,3034 | **0,0935** | 0,034 |

Korelasyon değişmiyor (0,516 → 0,516) — **doğru davranış**: shrinkage
monotondur, sıralamayı değiştirmez, yalnızca hatayı azaltır. Ağırlıklar
maruziyetle doğru ölçekleniyor.

### 31.2 ✅ Sistem rastgeleden anlamlı biçimde iyi

Oyuncu bazlı bootstrap, dört yapılandırma:

| Kohort · sonuç | SİSTEM − rastgele | %95 GA |
|---|---|---|
| U23 · değer | +9,0 puan | [+2,2 , +16,9] |
| U23 · terfi | +8,6 | [+2,7 , +14,7] |
| Tüm yaşlar · değer | +7,5 | [+2,5 , +12,3] |
| Tüm yaşlar · terfi | +9,1 | [+4,3 , +13,7] |

Dördünde de güven aralığı sıfırı dışlıyor. **Bu, projenin ayakta kalan en
güçlü iddiası.**

### 31.3 ❌ Tabanlarla yapılan TÜM kıyaslar gürültü içindeymiş

| Kıyas | Fark | %95 GA | Hüküm |
|---|---|---|---|
| SİSTEM − gol (U23) | −5,0 puan | [−13,4 , +4,1] | ayırt edilemiyor |
| SİSTEM − dakika (U23) | −2,2 | [−10,4 , +5,6] | ayırt edilemiyor |
| SİSTEM − gol (tüm) | −0,5 | [−6,2 , +5,3] | ayırt edilemiyor |
| SİSTEM − dakika (tüm) | +3,4 | [−2,0 , +9,2] | ayırt edilemiyor |

Aylarca "gol sistemi geçiyor", "dakika U21'de en iyi taban", "kalibrasyon
+0,07 kazandırıyor" dedik. **Hiçbiri veriyle desteklenmiyor.** Sebep: ilk-N
seçimi lig başına 15-20 oyuncu, varyans büyük.

**Sistemik düzeltme:** `backtest.py` artık her satır için bootstrap %95
güven aralığı basıyor (`ga_alt`, `ga_ust`). Bu tablodan sıralama hükmü
çıkarmak artık mümkün olmayacak.

### 31.4 ❌ Yaş eğrisi düzeltmesi GÜRÜLTÜYE dayanarak ürüne alınmıştı

§26'da "U23 terfisinde sistemi birinci yapıyor (1,62× vs 1,52×)" denip
Keşif ekranına toggle eklenmişti. Bootstrap:

| Kohort · sonuç | Yaş eğrisi − ham skor | %95 GA |
|---|---|---|
| U23 · değer | +1,6 puan | [−6,7 , +10,0] |
| U23 · terfi | +0,3 | [−6,7 , +7,0] |
| Tüm yaşlar · değer | −2,6 | [−8,2 , +2,7] |
| Tüm yaşlar · terfi | −0,5 | [−6,0 , +5,0] |

**Hiçbirinde ayırt edilemiyor.** Bu bir hata: ölçüme dayandığını sandığım
bir ürün kararı aslında gürültüye dayanıyormuş.

**Düzeltme:** özellik kaldırılmadı (zararsız ve isteğe bağlı) ama üstünlük
iddiası **arayüzden ve kod yorumlarından silindi**. Artık "alternatif bir
bakış, üstünlük kanıtlanmadı" diyor. Eğrinin *kendisi* (tepe 25, şekil
kapısı, 4.848 geçiş) sağlam ölçüm olarak duruyor — sorun onu skora
uygulamanın faydasında.

### 31.5 ⚠️ Lig gücü kapısı sağlam kanıt değil — iki ayrı sebeple

1. **Güven aralığı çok geniş:** rho = 0,654 ama lig-bootstrap %95 GA
   **[0,188 , 0,890]**. Eşiğin (0,60) altında kalma olasılığı **%35,5**.
2. **Seçim döngüselliği:** 6 varyant aynı rho ile karşılaştırılıp en iyisi
   seçildi, sonra aynı rho kabul kapısı olarak kullanıldı. Maksimum seçmek
   rho'yu yukarı yanlı yapar.

Neyse ki lig gücü **skora uygulanmadı** (uygulamak ölçüldü ve zararlıydı,
§23.3), yalnızca bağlam olarak gösteriliyor — hasar sınırlı. Ama "kapıyı
geçti" ifadesi bir daha kanıt olarak kullanılmamalı.

### 31.6 ⚠️ Mevki çıkarımı: kohortta %83,6 — ama orta sahada %63,3

Bilinen mevkilerin %20'si gizlenip tahmin edildi:

| Gerçek mevki | n | İsabet |
|---|---|---|
| Kaleci | 430 | **0,998** |
| Forvet | 1.077 | 0,928 |
| Stoper | 1.379 | 0,859 |
| **Orta saha** | 982 | **0,633** |

Hatalar orta saha→stoper (231) ve orta saha→forvet (129). Bu, rol
kümelemedeki bulgunun aynısı: orta sahanın profil sınırları gerçekten
bulanık. Kabul eşiği (0,60 olasılık) işini yapıyor — kabul edilenlerin
isabeti (%83,6), çapraz doğrulama doğruluğundan (%69,9) yüksek.

Etki küçük: yalnızca 9 oyuncuya uygulanıyor, beklenen hata ~1,5 oyuncu.

### 31.7 Genel ders

Bu projede yöntemler titizdi ama **belirsizlik hiç raporlanmadı**. Nokta
tahminleri kıyaslayıp hüküm verdik; bootstrap eklenince o hükümlerin çoğu
buhar oldu. Ayakta kalan iddia sadece "sistem rastgeleden iyi" — ki bu da
gerçek ve önemli, sadece iddia ettiğimizden daha mütevazı.

**Bundan sonra:** güven aralığı olmayan bir kıyastan ürün kararı çıkmaz.

### 31.8 Ölçüm aracı düzeltildi — ve GİZLİ BİR BAŞARI ortaya çıktı

Denetimin ardından `backtest.py` iki noktada düzeltildi:

1. **Eşleştirilmiş bootstrap.** İlk denetimde her yöntem ayrı örnekle
   bootstrap edilmişti; bu, farkın varyansını `var(A)+var(B)` yapar. Doğrusu
   `var(A−B)` ve yöntemler aynı oyunculara uygulandığı için çok daha küçük.
   (Düzeltme hükmü değiştirmedi ama aralıkları daralttı.)
2. **Lig içi AUC eklendi.** İlk-N yalnızca lig başına 15-20 oyuncuya bakıp
   geri kalanı atıyor. AUC tüm örneklemi kullanır ve belirgin biçimde daha
   keskin. İkisi de raporlanıyor: ilk-N *karar* için, AUC *yöntem kıyası* için.

**Yeni araç, eski aracın göremediği bir şeyi buldu:**

| Sonuç · kohort | SİSTEM − piyasa değeri | %95 GA | Ayırt edilebilir |
|---|---|---|---|
| Değer sıçraması · U23 | **+0,120** | [0,078 , 0,161] | ✅ |
| Değer sıçraması · tüm yaşlar | **+0,117** | [0,089 , 0,144] | ✅ |
| Lig terfisi · tüm yaşlar | **−0,110** | [−0,147 , −0,078] | ✅ (piyasa üstün) |

Ve `SİSTEM − dakika` lig terfisinde **+0,070 [0,024 , 0,120]** ile ayırt
edilebilir hale geldi.

**Yorum — projenin değer önerisi ilk kez istatistiksel destek buldu:**

- Sistem, **piyasanın ucuza gördüğü oyuncuyu bulmakta piyasadan iyi**
  (değer büyümesini fiyattan daha iyi öngörüyor).
- Sistem, **kimin transfer edileceğini öngörmekte piyasadan kötü** — ki bu
  beklenen: kulüpler itibara ve fiyata bakarak alıyor.

İkisi birlikte tam olarak wonderkid avının tanımı: *piyasa henüz fark
etmemişken değer kazanacak oyuncuyu bulmak.* "Gol" ve "dakika" tabanlarından
ayırt edilememesi hâlâ geçerli ve hâlâ mütevazı bir tablo — ama sistemin
piyasayı geçtiği kısım artık kanıtlı.

---

## 32. İki İyileştirme: Örneklem Havuzlama + Possession-Adjusted Savunma (29 Ağu 2026)

Denetimin (§31) ortaya çıkardığı iki soruna doğrudan cevap.

### 32.1 Değerlendirme örneklemi havuzlandı — ama YALNIZCA terfi sonucunda

Amaç güven aralıklarını daraltmaktı. Ama pencereler eşit değil, ölçüldü:

| Tahmin penceresi | Eşleşmiş | Değer sonucu ölçülebilir |
|---|---|---|
| 2022 → 2023/24 | 6.716 | **5.251 (%78)** |
| 2023 → 2024/25 | 3.225 | **721 (%22)** |

İkincisi Transfermarkt değerleme kapsamının çöküşü (§17.1) ve kalanlar
sistematik olarak daha değerli oyuncular. **Değer sonucuna eklemek, bilerek
kaçındığımız seçilim yanlılığını geri getirirdi.**

Bu yüzden: **terfi sonucu iki pencereden havuzlanıyor** (kendi verimiz,
TM'e bağımlı değil), **değer sonucu yalnızca 2022'de kalıyor**.
U23'te terfi örneklemi 1.545 → **2.502** (+%62).

**Bootstrap oyuncu bazlı yapıldı.** Havuzlamada aynı oyuncu iki satırda
görünebiliyor; satırları bağımsız saymak güven aralığını yapay olarak
daraltırdı.

### 32.2 Savunma metrikleri possession-adjusted hale getirildi

§30'da ölçülmüştü: ham savunma hacmi takım bağlamıyla kirli — takımın
savunma yoğunluğu (stoperde AUC 0,408) oyuncunun kendi metriğinden daha
güçlü anti-tahminci.

Gerçek possession verisi ücretsiz planda yok. Vekil: **takım pas hacmi**
(çok pas = çok topa sahip = az savunma fırsatı).

```
pAdj = ham_p90 × (takım_pas90 / ligin_medyan_pas90)        [0,5 – 2,0 arası kırpılı]
```

**Sonuç — altı karşılaştırmanın altısı da anlamlı** (eşli bootstrap):

| Metrik | Ham AUC | pAdj | Fark · %95 GA |
|---|---|---|---|
| top çalma (tüm) | 0,525 | 0,537 | +0,013 [+0,006 , +0,020] |
| kesme (tüm) | 0,491 | 0,500 | +0,009 [+0,004 , +0,015] |
| savunma aksiyonu (tüm) | 0,502 | 0,516 | +0,014 [+0,007 , +0,022] |
| **top çalma (stoper)** | 0,549 | **0,570** | +0,021 [+0,004 , +0,038] |
| **kesme (stoper)** | 0,460 | **0,482** | +0,022 [+0,004 , +0,039] |
| **savunma aksiyonu (stoper)** | 0,501 | **0,534** | +0,034 [+0,011 , +0,057] |

**Bu, projede istatistiksel olarak desteklenen ilk gerçek metrik
iyileştirmesidir.**

`roles.yaml`'da savunma metrikleri `_padj` sürümlerine geçirildi.
`duels` **değiştirilmedi** — hücum ikili mücadelelerini de içerdiği için
ayrıca doğrulanmadı; doğrulanmamış bir değişiklik yapmıyoruz.

### 32.3 Skor düzeyindeki etki: tutarlı ama tek tek sınanmadı

| Kıyas | Öncesi | Sonrası |
|---|---|---|
| SİSTEM − gol (değer) | −0,016 | −0,009 |
| SİSTEM − dakika (değer) | −0,036 | −0,029 |
| SİSTEM − piyasa (değer) | +0,121 | **+0,127** |
| SİSTEM − gol (terfi) | +0,005 | **+0,023** |
| SİSTEM − dakika (terfi) | +0,012 | **+0,030** |
| SİSTEM − piyasa (terfi) | −0,087 | −0,070 |

Altısı da sistem lehine kaydı. **Dürüstlük notu:** metrik düzeyindeki
iyileşme kanıtlı, skor düzeyindeki hareket bu iyileşmeyle tutarlı — ama
skor farklarının kendisi anlamlılık testinden geçirilmedi. Küçük hareketler,
büyük iddia yok.

## 33. Toplama Zincirinde İki Sessiz Kayıp (30 Ağu 2026)

Kullanıcı "istediğimiz veriyi çekmiş mi" diye sordu. Cevap: **hayır, sıfır
istek.** İki ayrı kusur çıktı — ikisi de sessizdi, ikisi de kota yakıyordu.

### 33.1 Kota sıfırlanmasına 47 saniye kala pes etti

Görev bilgisayar açılınca **02:59:13**'te çalıştı. Kota 00:00 UTC'de (yerel
**03:00**) sıfırlanıyor.

```
02:59:14  [kota]  bugun 100/100, kalan 0
02:59:14  Kota yetersiz (2 istek gerekiyor).
02:59:17  [ozet]  bu calistirmada 0 istek
```

47 saniye sonra 100 istek hazırdı; script çoktan sonraki adıma geçmişti.
Sezon sondası da aynı sebeple atlandı.

Bu bugüne özgü değil: **her sabah 03:00 civarı açılan bilgisayar aynı deliğe
düşer.** 1-2 Ağu 2026'da bir günlük kota internetsizlik yüzünden yanmıştı,
çözümü `Wait-Internet` olmuştu. Aynı mantık kotaya uygulandı.

`scripts/daily_run.ps1` → **`Wait-KotaSifirlama`**: kota doluysa VE
sıfırlanmasına 45 dk'dan az kaldıysa bekler. Uzaksa hiç beklemez. Beklemenin
maliyeti yok — kota gün içinde saat farketmeksizin geçerli.

### 33.2 Sezon sondası tazelik önbelleğini hiç yazmıyordu

`scripts/probe_season_access.py` `--gunluk` modunda `season_access.json`
dosyasının yaşına bakıp 30 günden tazeyse istek harcamamak üzere yazılmıştı.
`SONUC` yolu tanımlıydı, tazelik kontrolü yazılmıştı — **ama dosya hiçbir
zaman yazılmıyordu.** `main()` sonucu basıp `return 0` yapıyordu, o kadar.

Sonuç: tazelik kontrolü her gün boşa düşer, sonda **30 günde bir yerine her
gün** 2 istek yakardı. Ayda ~60 istek ≈ yarım günlük toplama. Bugüne kadar
fark edilmemesinin sebebi, sondanın ilk kez bugün çalışması.

Düzeltildi: `main()` artık sonucu yazıyor. Bugünün sonucu dosyaya kondu.

### 33.3 Sondanın cevabı: 2025 ve 2026 HÂLÂ KAPALI

```
--- sezon 2025 deneniyor (1 istek) ---
--- sezon 2026 deneniyor (1 istek) ---
Yeni sezon acilmamis - pencere hala 2022-2024.
```

Ücretsiz plan penceresi değişmedi. Sistem güncel sezonu göremiyor; 2022-2024
ile çalışmaya devam. 30 gün sonra tekrar sınanacak (artık gerçekten 30 gün
sonra — bkz. §33.2).

### 33.4 Kaçan çalışma telafi edildi

Zincir elle çalıştırıldı: **98 istek**, tamamlanan lig-sezon 55 → **56/64**,
34.220 oyuncu-lig-sezon, 114.273 rol skoru. Boylamsal yaş eğrisi yeniden fit
edildi (tepe 25 yaş, 5.404 geçiş — §26 ile aynı). Denetim: 32 kontrol / 27
geçti / 5 kaldı, hepsi bilinen açık maddeler.

## 34. Kadro Analizi Sayfası (30 Ağu 2026)

ADIM 6'da kalan son ürün maddesi. Keşif sayfası "kim iyi" diye sorar; bu
sayfa **"bize kim lazım"** diye sorar. İkisi aynı soru değil: ligin en iyi
ön liberosu, zaten iki tane ön liberosu olan takım için bir şey ifade etmez.

`src/scout/features/squad.py` + `app/views/Kadro_Analizi.py`

### 34.1 Kıyas tabanı neden takım seviyesinde

En kritik tasarım kararı bu. Bir takımın o roldeki en iyisini neyle
kıyaslayacağız?

| Taban | Sonuç |
|---|---|
| Ligin **oyuncu** medyanı | Takım-rol çiftlerinin **%88'i** "ortalama üstü" |
| Ligin **takım-en-iyilerinin** medyanı | **%50** üstte, %50 altta |

Oyuncu medyanı yedekleri de sayar ve tabanı aşağı çeker — her takım her
rolde iyi görünür, harita hiçbir şey söylemez. Doğru taban "ligin ortalama
takımının o roldeki en iyisi". `test_taban_yedekleri_saymaz` bu kararı
kilitliyor: yanlış tabanla oranın %85'i aşacağını da ayrıca doğruluyor.

### 34.2 Eşik neden ±8

±8 percentile içi "ortalama" sayılıyor. Bu bir **ölçüm değil, temkinli
varsayım** — tek sezonda bu genişlikteki farkların gürültüden ayırt
edilemeyeceğini varsayıyoruz. Küçük farklara "güçlü/boşluk" damgası vurmamak
için konuldu, ölçülerek kalibre edilmedi. Dosya başında böyle yazıyor.

### 34.3 Derinlik: 1 ve 0 farklı şeyler

*derinlik* = o rolde ligin oyuncu medyanının üstünde kaç oyuncumuz var.

- **1** → tek adama bağımlıyız
- **0** → en iyimiz bile lig medyanının altında; o rolde kimse yok

Sınamada Santos 2024'ün kalecisi tam bu vakaydı: takımın en iyi kalecisi
ama derinlik 0. "0" ilk bakışta "veri yok" diye okunuyor, arayüzde ayrıca
açıklandı.

### 34.4 Yaş profili dakika ağırlıklı

Kadro yenileme ihtiyacını oyuncu **sayısı** değil oynanan **dakika**
gösterir: on yedek genç olabilir ama sahada 33 yaşındakiler varsa kadro
yaşlıdır. Santos 2024: dakikaların **%42,8'i 31 yaş üstüne**, %13,8'i 23
yaş altına gidiyor.

Sayfa bunu **kıyas değil betimleme** olarak sunuyor — hangi oranın "doğru"
olduğunu ölçmedik.

### 34.5 "Kim kimin yerine oynar" — DOĞRULANMADI

Stil benzerliğine (§25, CLR) dayanıyor. Stil benzerliğinin iyi bir **yedek
bulma** ölçütü olduğu geriye dönük testte gösterilmedi — doğrulayabileceğimiz
bir sonuç değişkenimiz yok. Sayfada uyarı olarak duruyor: *fikir üretir,
karar vermez.*

Ligler arası kıyas da yapılmıyor: farklı ligdeki adayın skoru **kendi**
liginin kohortuna göre. Lig gücü düzeltmesi geriye dönük testte sonucu
kötüleştiriyordu (§23).

### 34.6 Sınamada çıkan iki kusur

1. **Modül ASCII, arayüz Türkçe.** `durum` alanı "guclu"/"bosluk" dönerken
   arayüz "güçlü"/"boşluk" arıyordu — grafik `KeyError` verecekti. Gösterim
   etiketleri artık tek bir `DURUM_ADI` sözlüğünde.
2. **Sütun çakışması.** `benzerler()` `player_features` satırlarını olduğu
   gibi döndürüyor — yaş, lig, mevki zaten içinde. Bunları ayrıca
   `player_natural_role`'den çekmek `age_season_end_x/_y` üretip
   `KeyError: ['age_season_end'] not in index` ile sayfayı kırıyordu.
   Tarayıcıda görüldü, düzeltildi: yalnızca `score` birleştiriliyor.

Her ikisi de yalnızca sayfa gerçekten açılıp tıklandığı için görüldü.
Testler modülü doğruluyor, arayüzü doğrulamıyor.

**14 yeni test** (`tests/test_squad.py`), toplam **86 test** geçiyor.

## 35. §34'ün İki Doğrulanmamış İddiası Ölçüldü — Biri Yanlış Çıktı (30 Ağu 2026)

Kadro Analizi'ni teslim ederken iki şeyi "ölçmedik" diye işaretlemiştim.
İkisi de aslında ölçülebilirmiş. `scripts/validate_squad.py`

### 35.1 ±8 eşiği YANLIŞTI — ölçüldü, 12'ye çıkarıldı

**Yöntem:** aynı takım + aynı rol + **aynı oyuncu**, ardışık iki sezon
(n=1.006). Kadro değişmediği için `fark` değerinin sezonlar arası oynaması
= gerçek gelişim + ölçüm gürültüsü. Gerçek gelişim ≥ 0 olduğundan bu bir
**üst sınır**.

| Eşik | Hiçbir şey değişmemiş vakaların kapsanan oranı |
|---|---|
| ±6 | %41 |
| **±8 (eskisi)** | **%51** |
| ±10 | %60 |
| **±12 (yenisi)** | **%67** |
| ±20 | %86 |

`|değişim|` medyanı 7,7 · %68 yüzdeliği **12,1**

Yani ±8 eşiği, hiçbir şeyin değişmediği vakaların **yarısına** "güçlü" veya
"boşluk" damgası vuruyordu. Ölçüt olarak "bant, değişmemiş vakaların ~%68'ini
(1 SD eşdeğeri) kapsamalı" seçildi → **12**.

Üst sınır olduğu için gerçek gürültü daha küçük olabilir; yani 12 **geniş
tarafta** hata yapıyor — var olan bir boşluğu kaçırır, olmayan bir boşluğu
uydurmaz. Projenin başka yerlerdeki duruşuyla aynı yönde (eksik veriden skor
üretmemek gibi): uydurmaktansa susmak.

Etkisi: örnek takımda "güçlü rol" 2→1, "boşluk" 5→4.
`test_esik_olculmus_degerde_kalir` değeri kilitliyor.

### 35.2 "Sonuç değişkeni yok" demiştim — vardı

Stil benzerliğinin yedek bulmaya yaradığını doğrulayamayacağımızı
söylemiştim. Doğrulanabilir bir sonuç değişkeni var: **kulüplerin kendi
davranışı.**

Bir rolün en iyisi takımdan ayrıldığında, yerine gelen oyuncu ligdeki
rastgele bir aynı-mevki oyuncusundan daha mı benzer stilde?

**n = 2.510 değişim.** Gelenin yüzdelik sırası **0,406**, %95 GA
[0,394 , 0,417] — 0,50 rastgele demek. **Anlamlı: kulüpler gerçekten
benzerini arıyor.**

### 35.3 Ama mevkiye göre çarpıcı biçimde değişiyor — kalecide TERSİNE dönüyor

| Mevki | n | Fark (+ = gelen daha benzer) | %95 GA |
|---|---|---|---|
| Stoper/bek | 608 | **+0,654** | [+0,600 , +0,711] |
| Orta saha | 710 | +0,140 | [+0,081 , +0,203] |
| Forvet | 1.055 | +0,061 | [+0,018 , +0,107] |
| **Kaleci** | 137 | **−0,170** | **[−0,273 , −0,072]** |

Kalecide güven aralığının tamamı negatif: kulüpler kaleci değiştirirken
ayrılanın yerine rastgeleden **daha farklı** stilde oyuncu alıyor. En olası
sebep, kaleci "stil" vektörünün (pas ve müdahale hacimleri) kalecilikte
anlamlı bir şey ölçmemesi.

Arayüz artık kaleci seçilince `st.error` ile **açıktan uyarıyor**. Sessizce
liste göstermek en kötü seçenekti: kullanıcı sayının olmadığı yerde sayı
görürdü. `test_kaleci_yedek_benzerligi_ters` bulguyu kilitliyor.

Savunma hattındaki +0,654 ise güçlü: araç orada kulüplerin gerçekten yaptığı
işi ölçüyor.

### 35.4 Sayfayı gerçekten çalıştıran testler eklendi

§34'teki iki kırık yalnızca tarayıcıda görülmüştü, 14 birim test yeşilken.
Modül doğruydu, sayfa yanlıştı — birim testi bunu yakalayamazdı.

`tests/test_kadro_sayfasi.py`, Streamlit `AppTest` ile sayfayı baştan sona
çalıştırıyor: takım değiştir, oyuncu değiştir, grafikler üretildi mi, kaleci
uyarısı gerçekten çıkıyor mu. **6 test.**

Toplam **97 test** geçiyor. Ham çıktı: `reports/validate_squad_2026-08-30.txt`

## 36. Anomali Taraması: İki Sessiz Kusur, Bir Yapısal Sınır (30 Ağu 2026)

Denetimin kalan 5 maddesine ek olarak veriyi kendi başıma taradım. Denetimin
sormadığı sorular sordum. Üç şey çıktı.

### 36.1 Skorsuz oyunculara UYDURMA doğal rol atanıyordu

`player_natural_role` şöyle üretiliyordu:

```sql
row_number() OVER (PARTITION BY player_id, league_id, season
                   ORDER BY score DESC)
```

Bir oyuncunun **hiçbir rolde** skoru yoksa (§21 kapsam eşiği hepsini
bastırmışsa) tüm değerler NULL olur ve `ORDER BY` karar veremez — sıralama
satır sırasına düşer. Kazanan, `roles.yaml`'de o mevkinin **ilk** rolü olur.

Kanıt, etiketlerin dağılımının tam olarak dosya sırası olması:

| Uydurma etiket | n | roles.yaml'de o mevkinin |
|---|---|---|
| Orta Saha - Regista | 916 | **1.** rolü |
| Forvet - Pres Yapan | 743 | **1.** rolü |
| Kaleci - Kurtaran | 334 | **1.** rolü |
| Bek - Hücumcu | 9 | **1.** bek rolü |

**2.002 oyuncu-sezon**, bunların **1.289'u 450+ dakika** — yani arayüzde
görünür durumda. Hepsi zaten bilinen bozuk liglerde (Segunda Liga, Liga Pro,
Superettan, Veikkausliiga).

Tutarsızlık şuydu: sayıyı üretmeyecek kadar az veri varken **rol adını**
üretiyorduk. Skoru bastırmak ama etiketi bırakmak aynı hatanın yarısı.

**Düzeltildi:** satır kalıyor (oyuncu listeden kaybolmasın), `role` ve
`role_name` NULL oluyor. Denetime kontrol eklendi.

*İyi haber:* geçerli skoru **olan** hiçbir oyuncuda yanlış rol seçilmemiş
(0 vaka) — `NULLS LAST` sıralaması doğru çalışıyor. Sorun yalnızca hepsi
NULL olan durumdaydı.

### 36.2 İki oyuncunun doğum tarihi gelecekte — yaşları −3,6

`Matheus Carvalho dos Santos` ve `Atska Ntonalnto`: sağlayıcı doğum tarihini
**2026-08** vermiş. Sezon sonu 2022 olduğu için yaş **−3,6** çıkıyordu.

`age_band` NULL kaldığı için kohortları kirletmiyordu, ama negatif yaş
takım ortalama yaşı, yaş eğrisi ve yaş filtreleri boyunca sessizce
taşınıyordu.

**Düzeltildi:** 14-60 dışındaki yaşlarda `age_season_end` ve `birth_date`
NULL bırakılıyor.

**Üst sınır bilerek geniş (60):** Buffon 44,9 · Fábio 44,3 · **Miura 56,8**
— bunlar gerçek. Miura, 56 yaşında Segunda Liga'da oynadı. Dar bir üst sınır
gerçek veriyi eleyecekti.

Denetimde "doğum tarihi eksik" 1 → 3'e çıktı. Bu bir gerileme değil: yanlış
bir değer artık *bilinen bir eksik*. Yanlış sayıdan iyidir.

### 36.3 YAPISAL: "doğal rol" genelci şablonu asla seçemez

Doğal rol = 14 rol skorunun **argmax**'ı. Genelci şablonlar (`fw_complete`,
`mf_box_to_box`) ötekilerin ölçtüğü işlerin ortalamasını ölçüyor:

| Şablon | Ötekilerin ortalamasıyla korelasyon | argmax olma oranı | Eşit dağılım beklentisi |
|---|---|---|---|
| `fw_complete` | **0,910** | **%3,7** | %20 |
| `mf_box_to_box` | 0,861 | %14,1 | %25 |

Bir ortalama, bileşenlerinin maksimumu neredeyse hiç olamaz. Yani **komple
bir forvet, sistemde "Bitirici" ya da "Pres Yapan" olarak etiketleniyor** —
futbol gerçeği değil, argmax'ın aritmetiği.

Bu **düzeltilebilir bir hata değil**, seçim kuralının doğal sonucu. Şablonu
çıkarmak bilgi kaybı olurdu (rol skorunun kendisi hâlâ anlamlı ve sabit rol
aramasında kullanılıyor). Denetime **UYARI** olarak eklendi ki görünür
kalsın.

### 36.4 Temiz çıkanlar

Aradım, sorun bulamadım — bunları da yazıyorum çünkü aranmamış olmakla temiz
çıkmak farklı şeyler:

| Kontrol | Sonuç |
|---|---|
| §32 possession katsayısı NULL olan 2.794 satır **skor üretiyor mu?** | **0** — kendi değişikliğim regresyon yaratmamış; hepsi zaten bastırılmış lig-sezonlarda |
| Lig-sezon başına ortalama skor 50 civarında mı? | Hepsi 45-55 arasında, sapan yok |
| Transfermarkt eşleşme oranı | En düşük lig %98,5 |
| Dakika/maç imkânsız değer | 0 |
| 44+ yaş kayıtları | Gerçek (Buffon, Fábio, Miura) — elenmedi |

**Denetim 35 kontrol · 29 geçti · 5 kaldı · 1 uyarı.** Kalan 5 madde bilinen
sağlayıcı eksikleri (bozuk lig-sezonlar) ve 3 kohortsuz oyuncu.

## 37. Proje Yeniden Yönlendirildi: Tablo Değil, İddia (30 Ağu 2026)

Kullanıcı hedefi yeniden tanımladı:

> *"Uygulama sadece veriyi önüne dökmesin, içinden bir anlam ve araştırma
> çıkarsın. Profesyonel bir scout ekibi gibi düşün."*
> *"Ahmet 2022-2024 arası çok iyi skor yapmış, ben bunu manuel kontrol
> edeyim, bu çocuk ne yapmış. Gerisi benim kendi izlem ve gözlemlerime
> dayansın."*

Ve bir kısıt: **ücretli veri yok.** Önce ücretsiz veriyle en doğrusu.

Tam plan `ROADMAP.md` Bölüm 7'de. Burada yalnızca planı değiştiren **bulgu**
ve **karar gerekçeleri**.

### 37.1 Aylardır yanlış bildiğimiz şey: 2025/26 verisi elimizdeydi

"Ücretsiz plan güncel sezonu vermiyor" doğru — ama eksik. Transfermarkt CC0
veri setini (204 MB, Temmuz 2026'dan beri diskte) yeniden inceledim.
**Hiç dokunmadığımız dört tablo** çıktı:

| Tablo | Satır | Ne var |
|---|---|---|
| `appearances` | **1.894.350** | Maç bazında dakika, gol, asist, kart — **2026-05-24'e kadar** |
| `game_lineups` | 3.179.016 | İlk 11 / yedek |
| `game_events` | 1.274.469 | Gol, kart, oyuncu değişikliği (dakikasıyla) |
| `games` | 88.958 | Sonuç, tur, tarih, diziliş, hakem |

`player_season` tablosunu kurarken yalnızca `players`, `transfers`,
`player_valuations`, `clubs` alınmış; geri kalanı hiç sorgulanmamış. Bir
yıldır "güncel sezon yok" varsayımıyla plan yapıyorduk.

### 37.2 Bunun neyi değiştirdiği: geriye dönük test → ileriye dönük pencere

Şimdiye kadarki bütün doğrulama **geriye dönük** testti: 2022'den 2023/24'ü
tahmin et, aynı veri havuzu içinde. Artık gerçekten **tutulmuş** bir pencere
var — modelin geliştirilmesinde hiç kullanılmamış 2025/26.

| Skorlanan sezon | U23 oyuncu | 2025/26 sonucu ölçülebilir | ≥900 dk |
|---|---|---|---|
| 2022 | 1.855 | 1.013 (%54,6) | 694 |
| 2023 | 1.258 | 555 (%44,1) | 317 |
| 2024 | 2.046 | 1.090 (%53,3) | 688 |

Düşük görünürlüklü liglerden gerçek terfi taban oranları:
Ligue 2 %27,2 · Eerste Divisie %22,1 · Serie B (BRA) %12,2 ·
Superettan %11,7 · Primera A (COL) %4,2.

### 37.3 Sonuç değişkeninin sınırı — cümleyi doğru kurmak

TM 14 birinci ligi ve Avrupa kupalarını izliyor. Bir oyuncunun TM'de kaydı
**yoksa** bu "başarısız oldu" demek değil — Kolombiya'da gayet iyi oynuyor
ama izlenmiyor olabilir.

Yani ölçtüğümüz şey **"iyi oldu mu" değil, "izlenen bir seviyeye sıçradı
mı"**. Wonderkid avı için doğru hedef bu; ama iddiayı böyle kurmak zorundayız.
Aksi hâlde Primera A'nın %4,2'sini "Kolombiya ligi kötü" diye okuruz, oysa
sadece görünmüyor.

### 37.4 Planın omurgası ve neden bu sırada

```
FAZ 1  gercek sonuc tablosu   (1-2 gun)   <- olcemezsen gelistiremezsin
FAZ 2  modeli egit            (3-4 gun)   <- FAZ 1 olmadan egitilemez
FAZ 3  emsal orani            (2 gun)     <- FAZ 1 olmadan hesaplanamaz
FAZ 4  scout dosyasi          (3 gun)     <- FAZ 2+3'un ciktisi
FAZ 5  hesap defteri          (1 gun)     <- FAZ 4'un iddialarini kaydeder
```

### 37.5 Modelin kabul kriteri: üç tabanı birden yenmek

Yeni modelin geçmesi gereken sınav, tutulan 2024→2025/26 penceresinde:

| Taban | Neden |
|---|---|
| Mevcut uzman ağırlıklı skor | Yeni, eskisinden iyi olmalı |
| Piyasa değeri | Piyasayı yenmek projenin tek gerçek iddiası (§31'de +0,120 GA [0,078 , 0,161] ile kanıtlanmıştı) |
| **Sadece dakika + yaş** | En aptal makul model. Bunu yenemeyen model hiçbir şey öğrenmemiştir |

Üçüncüsü kasıtlı olarak konuldu. §27'de "yükseliş sinyali" güçlü sanılmıştı;
ölçünce mevcut seviyenin gerisinde kaldı. Aynı hataya düşmemek için en basit
rakip baştan tanımlanıyor.

**Model reddedilirse uzman ağırlıklarıyla devam edilir ve bu yazılır.**
Model eğitmiş olmak için model kullanılmayacak.

### 37.6 Neden karmaşık model kullanılmayacak

U23'te ölçülebilir sonuç ~1.000 kişi. Ağaç ensemble'ı bu boyutta ezberler.
Ayrıca **scout dosyası katsayılara dayanacak** — "bu oyuncu neden öne
çıktı" sorusunun cevabı okunabilir olmalı. Açıklanamayan bir skor, saha
gözlemine yön veremez.

### 37.7 Emsal oranı — eksik olan profesyonel araç

Scout'un asıl sorduğu soru "kaç puan aldı" değil, **"bu profildekiler ne
oldu"**. Aynı yaş + benzer stil + benzer seviye + benzer lig gücündeki
geçmiş oyuncuların 2025/26 sonuçları:

> *"Bu profildeki 61 oyuncudan 14'ü (%23) üst ligde yer edindi.
> Ligin taban oranı %12. Bu profil tabanın iki katı."*

Tahmin değil, **taban oranı**. Emsal grubu 30 kişinin altındaysa oran
gösterilmez — küçük kohortta percentile üretmeme kuralının aynısı.

### 37.8 Dosyanın son bölümü: "NE İZLEMELİSİN"

Her scout dosyası, verinin **göremediğini** listeleyerek bitecek: fizik,
karakter, baskı altında karar, sakatlık geçmişi.

Bu satır kasıtlı. Sistem nerede kör olduğunu söylemezse kullanıcı nereye
bakacağını bilemez ve gözlemi sistemin tekrarı olur. Amaç tam tersi:
**gözlem, sistemin devamı olmalı.**

## 38. FAZ 1 — Gerçek Sonuç Tablosu (30 Ağu 2026)

`player_outcome`: skorladığımız her oyuncu-sezon için **sonradan ne olduğu**.
33.213 satır. `scripts/build_outcomes.py` + `src/scout/features/outcome.py`

Kurulurken **iki sessiz tuzak** çıktı. İkisi de tabloyu makul gösterirdi.

### 38.1 TUZAK 1 — TM'nin sezon etiketi takvim yılı liglerinde bir yıl kayık

TM `games` tablosundan ölçüldü:

| Lig | TM `season=2024` | Bizim 2024 |
|---|---|---|
| ES1 (La Liga) | 2024-08-15 → 2025-05-25 | aynı ✓ |
| **BRA1** | **2025-03-29 → 2025-12-07** | takvim 2024 ✗ |
| **ARG1** | **2025-01-24 → 2025-05-04** | takvim 2024 ✗ |
| **SE1** | **2025-03-29 → 2025-11-09** | takvim 2024 ✗ |

TM'nin `season` alanını kullanmak Brezilya, Arjantin ve İskandinavya için
**bir yıl kaydırırdı** — ve kimse fark etmezdi.

**Çözüm:** sezon etiketi hiç kullanılmıyor. Her şey **tarihe** dayanıyor.
Pencere, skorlanan sezonun bitiş tarihinden itibaren. Takvim uzlaşımı ne
olursa olsun çalışır.

### 38.2 TUZAK 2 — 31 lig "birinci lig" görünüyor, 14'ünde oyuncu kaydı var

| Lig | `games`'te maç | `appearances`'ta oyuncu |
|---|---|---|
| IT1 | 1.711 | 53.402 |
| **BRA1** | 557 | **0** |
| **ARG1** | 418 | **0** |
| **SE1** | 329 | **0** |
| **NO1** | 329 | **0** |

Bunları "izleniyor" saymak felaket olurdu: Brezilya Serie A'da kalmaya devam
eden oyuncu **"iz yok"** çıkardı ve model *"Brezilya Serie A oyuncuları
başarısız oluyor"* diye öğrenirdi.

Ölçüldü — yanlışlıkla izleniyor sayıldığında ortalama kademeleri:
Brezilya Serie A **0,26** · Arjantin **0,22** · Allsvenskan **0,29** ·
Eliteserien **0,34**. Hepsi Ligue 2'nin (0,75) altında. Futbolen saçma.

Veikkausliiga'nın 17 metriği hiç yayınlanmadığı hâlde 1.301 sahte skor
üretmesiyle (§21) **aynı sınıf hata: eksik veriyi sıfır saymak.**

**Çözüm:** izlenen lig listesi sabit değil, `appearances` tablosundan
türetiliyor. Sabit harita veriyle her çalıştırmada karşılaştırılıyor;
uyuşmazsa uyarı basılıyor.

### 38.3 TUZAK 3 — Sansürleme

İlk sürümde sonuç `max(yıl1, yıl2)` idi. Veri 2026-06-28'de bitiyor:

| Sezon | Gözlenebilir ay | 12 ay tam? | 24 ay tam? |
|---|---|---|---|
| 2022 | 38,7 | ✓ | ✓ |
| 2023 | 27,4 | ✓ | ✓ |
| **2024** | **14,7** | ✓ | **✗** |

Yani 2022 satırlarına **iki şans**, 2024 satırlarına **bir şans**. Model
bundan "eski sezonlar daha başarılı" diye öğrenirdi — tamamen ölçüm
artefaktı.

**Çözüm:** birincil sonuç **12 aylık** dilim (her sezonda tam ve
kıyaslanabilir). 24 aylık sonuç yalnızca penceresi tamamlanmış satırlarda
üretilir, aksi hâlde NULL.

**Düzeltmenin kanıtı:** Eerste Divisie terfi oranı sezonlar arası
21,0 / 21,7 / 13,8 → **15,8 / 13,7 / 14,9**. Sansür kalkınca stabil oldu.

### 38.4 Sonuç değişkeni

| Kademe | Tanım |
|---|---|
| 0 | İzlenen birinci ligde iz yok |
| 1 | Göründü, <450 dk |
| 2 | Rotasyon, 450-899 dk |
| 3 | **Yer edindi, ≥900 dk** |
| 4 | ≥900 dk, ilk-5 ligde |

Ve her satırda `kapsam`:
- **`tam`** — menşei izlenen bir lig; *kalmak* da görünür (9 lig)
- **`sicrama_only`** — menşei izlenmiyor; yalnızca 14 lige *sıçrayan* görünür

`sicrama_only` liglerde **kademe 0 "başarısız" demek DEĞİL.** Brezilya
Serie B'den Serie A'ya çıkmak gerçek bir sıçramadır ama göremiyoruz.
Bu yüzden model değerlendirmesi **lig içinde** yapılmak zorunda (§31'de
kurulan in-league AUC).

### 38.5 KABUL KRİTERİ GEÇTİ: kademe lig gücünü izliyor

Sisteme lig sıralamasını hiç söylemedik. Ortaya çıkan (kapsam `tam`):

| Lig | n | Ort. kademe | Yer edindi % |
|---|---|---|---|
| Premier League | 794 | **2,91** | 67,5 |
| Bundesliga | 702 | 2,84 | 63,7 |
| Serie A (İTA) | 831 | 2,84 | 64,9 |
| La Liga | 816 | 2,75 | 61,8 |
| Ligue 1 | 752 | 2,50 | 56,0 |
| Eredivisie | 1015 | 1,97 | 53,4 |
| Jupiler Pro League | 689 | 1,90 | 49,9 |
| Superliga (DAN) | 695 | 1,81 | 45,0 |
| Primeira Liga | 717 | 1,69 | 45,5 |

Futbol bilgisiyle birebir örtüşüyor. Sonuç değişkeninin **inşa doğrulaması**
budur.

Sıçrama oranları (`sicrama_only`, 450+ dk):
Ligue 2 %15,6 · Eerste Divisie %14,8 · Challenger Pro %13,5 ·
Serie B (İTA) %10,5 · Segunda Liga %10,2 · 3. Liga %7,7 ·
Serie B (BRA) %6,3 · Primera A %3,8

Sıçrayanların gittiği ligler: NL1 223 · IT1 170 · FR1 156 · BE1 144 ·
PO1 124 — hepsi menşeinden güçlü.

### 38.6 Bundan sonrası

`build_outcomes.py` günlük zincire eklendi. **23 yeni test** (`test_outcome.py`),
toplam **120 test** geçiyor.

FAZ 2 (model eğitimi) artık mümkün: eğitim 2022+2023, test 2024 → 12 aylık
pencere. Sansür düzeltildiği için üç pencere de kıyaslanabilir.

## 39. FAZ 2 — Model Eğitildi ve Üç Tabanı da Geçti (30 Ağu 2026)

`scripts/train_model.py` + `src/scout/model/ranker.py`

**Hedef:** `kademe >= 3` — izlenen bir birinci ligde ≥900 dk, "yer edindi".
**Bölme:** eğitim 2022+2023 (3.205 satır, %25,8 olumlu) · test 2024
(2.076 satır, %29,5 olumlu). U23, 450+ dk.

### 39.1 Tutulan pencere sonucu

| | Lig-içi AUC |
|---|---|
| **model** | **0,700** |
| piyasa değeri | 0,657 |
| dakika+yaş (en aptal model) | 0,634 |
| mevcut uzman ağırlıklı skor | 0,607 |

| Fark (eşli, oyuncu bazlı bootstrap) | %95 GA | |
|---|---|---|
| model − mevcut skor | **+0,094** [+0,058 , +0,133] | GEÇTİ |
| model − piyasa değeri | **+0,042** [+0,020 , +0,064] | GEÇTİ |
| model − dakika+yaş | **+0,068** [+0,033 , +0,102] | GEÇTİ |

**Hüküm: benimsendi.** `player_model_score` tablosu + `model_ranker.joblib`.

### 39.2 Neden lojistik regresyon, neden ağaç değil

1. n küçük — eğitimde 3.205 satır. Ağaç ensemble'ı bu boyutta ezberler.
2. **Scout dosyası katsayılara dayanacak** (FAZ 4). "Bu oyuncu neden öne
   çıktı" sorusunun cevabı okunabilir olmalı; açıklanamayan bir skor saha
   gözlemine yön veremez.

### 39.3 Neden lig-içi AUC

Taban oranlar uçuruma benziyor: kapsam `tam` %57 yer edinir, `sicrama_only`
%12 sıçrar. Havuzlanmış AUC bu farkı "model iyi ayırt ediyor" diye okur;
oysa model yalnızca **ligi tanımış** olur. `test_havuzlanmis_auc_lig_farkini_yetenek_sanir`
bunu sentetik veriyle gösteriyor: havuzlanmış 0,79, lig-içi 0,50.

### 39.4 Sızıntı: iki tanesi bulundu ve kapatıldı

**(a) Piyasa değeri kesme tarihi transfer penceresine giriyordu.**
Avrupa'da sezon bitişi 15 Haziran olarak tanımlı ama ligler ~25 Mayıs'ta
bitiyor. 15 Haziran'daki bir değerleme, tahmin etmeye çalıştığımız
transferi zaten yansıtıyor olabilir. Kesme bir ay geri çekildi.

Etkisi ölçüldü: piyasa değeri AUC **0,732 → 0,716** (eğitim). Sızıntı
gerçekti.

**(b) Değerlemesi olmayan oyuncu "0 €" sayılıyordu.** — *Kullanıcının
işaretiyle bulundu.*

| Kapsam | Değerlemesi eksik |
|---|---|
| `tam` | %0,3 – %7,7 |
| **`sicrama_only`** | **%38,6 – %56,0** |

Toplam %31,8, ve eksiklik **tam da en çok önemsediğimiz düşük görünürlüklü
liglerde** yoğunlaşıyor. `log1p(0) = 0` yazmak modele *"bu Brezilya Serie B
çocuğu 0 € eder"* demekti ve katsayısı en ağır değişken olduğu için hepsini
dibe itiyordu. Veikkausliiga'nın eksik metriği 0 saymasıyla (§21) aynı hata.

Düzeltme: `deger_var` göstergesi (**"bilinmiyor" ≠ "ucuz"**) + eksik değer
kendi lig-sezonunun medyanıyla dolduruluyor.

**Çarpıcı sonuç:** düzeltmeden sonra en güçlü değişken `deger_var` (+1,441)
oldu, `log_deger` +0,878'e düştü. **Transfermarkt'ın oyuncuya değer biçmiş
olması, biçtiği değerin kendisinden daha güçlü sinyal.** Bu kısmen bir
*görünürlük* göstergesi, salt *kalite* göstergesi değil — dosyada böyle
sunulmalı.

### 39.5 Test penceresine İKİ KEZ bakıldı

Dürüstlük kaydı: tutulan pencere iki kez açıldı.

1. İlk bakış — model üç tabanı geçti (fark: skor +0,098 · piyasa +0,038 ·
   basit +0,071)
2. §39.4(b)'deki kodlama hatası düzeltildikten sonra ikinci bakış
   (+0,094 · +0,042 · +0,068)

İkincisi bir **model araması değil**, bir veri kodlama hatasının
düzeltilmesiydi ve hüküm iki bakışta da aynı. Yine de kayda geçiyor:
model varyantları deneyip test sonucuna göre seçmek sızıntı olurdu.

### 39.6 İç açıcı olmayan ikincil bulgu

Piyasa değeri **verilmeden** eğitilen model:

| Pencere | model_saf | piyasa | Fark | %95 GA |
|---|---|---|---|---|
| Eğitim | 0,678 | 0,693 | −0,015 | [−0,041 , +0,013] |
| Test | 0,684 | 0,657 | +0,028 | [−0,014 , +0,069] |

**Futbol metriklerimiz tek başına piyasayı yenmiyor.** Eğitimde biraz
gerideydi, testte biraz önde — ikisinde de güven aralığı sıfırı kapsıyor,
yani ayırt edilemiyor.

Model ancak piyasa değeri **verildiğinde** kazanıyor: +0,042. Yani
katkımız "piyasanın yerine geçmek" değil, **"piyasanın üstüne bir şey
eklemek"**. Bu §31'deki bulgudan farklı bir soru — orada sonuç değişkeni
*değer büyümesi*ydi ve sistem piyasayı geçmişti. Burada sonuç *"izlenen bir
lige yerleşti mi"* ve piyasa bu soruda çok iyi.

Kullanıcı kararı (30 Ağu): piyasa değeri sistemin dışında tutulmayacak.
Zaten birincil modelde. `model_saf` yalnızca bu ikincil soruyu yanıtlamak
için tutuluyor.

### 39.7 Sınırlar

- Eğitim penceresi tek: 2022+2023. Yıllar arası kayma ölçülemedi.
- `deger_var` görünürlük taşıyor; düşük görünürlüklü ligdeki gerçek yeteneği
  cezalandırıyor olabilir. FAZ 3'ün emsal oranı bunu dengeleyebilir.
- Sonuç değişkeni yalnızca 14 Avrupa birinci ligini görüyor (§38.4).

**11 yeni test** (`test_ranker.py`), toplam **131 test** geçiyor.

## 40. FAZ 3 — Emsal Oranı (30 Ağu 2026)

`src/scout/features/emsal.py` + `scripts/build_emsal.py` → `player_emsal`

Amaç: modelin verdiği olasılığın yanına **sayılabilir, adı olan bir geçmiş**
koymak.

> *"Bu profildeki 40 oyuncudan 15'i izlenen bir birinci ligde yer edindi:
> %38 (%95 GA %24–%53). Ligin taban oranı %10. Güven aralığı tabanın
> ÜSTÜNDE — profil gerçekten ayırt ediyor."*

### 40.1 İlk sürüm YETERSİZDİ — kullanıcı itirazı üzerine kazıldı

İlk sürümde mesafe **stil** (CLR, 10 boyut) + seviye (2 boyut) idi. Yani
ağırlığın **%83'ü "nasıl oynuyor"** boyutundaydı. Oysa modelin en güçlü
değişkenleri `deger_var` (+1,44) ve `log_deger` (+0,88) ve bunlar mesafeye
**hiç girmiyordu.**

Yani **"benzer OYNAYANLARI"** buluyorduk, **"benzer DURUMDA olanları"**
değil.

Dört tanım ölçüldü (`scripts/emsal_tani.py` · 2024 hedef, havuz 2022+2023):

| Mesafe tanımı | AUC | Kalibrasyon hatası | Tabanı aşan |
|---|---|---|---|
| stil + seviye *(ilk sürüm)* | 0,560 | 0,0217 | %17,8 |
| stil + seviye + değer | 0,590 | 0,0255 | %15,7 |
| **model uzayı, katsayı ağırlıklı** | **0,662** | 0,0237 | %13,8 |
| model olasılığı komşuluğu | 0,663 | 0,0305 | %14,3 |

**Model uzayı seçildi.** Olasılık komşuluğu aynı ayırt etme gücünü veriyor
ama kalibrasyonu daha kötü **ve emsalleri yorumlanamaz kılıyor**: aynı
olasılığa sahip iki oyuncu bambaşka olabilir. Model uzayında komşu olanlar
gerçekten benzer — scout o 40 ismi açıp bakabilir.

**Stil benzerliği kaybolmadı, ayrı bir soru.** "Kim gibi oynuyor" sorusu
Profil sayfasındaki benzer oyuncu aramasında (§25) duruyor. Emsal oranı
"kim onun DURUMUNDAYDI" sorusunu yanıtlıyor.

### 40.2 Düzeltmenin etkisi

| | İlk sürüm | Düzeltilmiş |
|---|---|---|
| Lig-içi AUC | 0,576 | **0,662** |
| Mevcut skora göre fark | −0,032 [−0,078 , +0,010] · *ayırt edilemez* | **+0,057 [+0,008 , +0,105]** · *anlamlı* |
| Modele göre fark | −0,130 [−0,172 , −0,089] | −0,043 [−0,075 , −0,013] |
| Oran üretilen satır | %96 | **%99** |
| GA'sı tabanı aşan | %10,4 | %13,9 |

**En çarpıcı tek vaka.** C. Drakas (3. Liga 2024, model %79, gerçekleşen
kademe 4 — ilk-5 ligde yer edindi):

| | Emsal grubu |
|---|---|
| İlk sürüm | **0/40** — grup onu tamamen ıskalamıştı |
| Düzeltilmiş | **15/40 (%38, GA %24–%53)**, taban %10, tabanı aşıyor ✓ |

2024'te `sicrama_only` liglerde modelin ilk 10'unda **9'unun** güven aralığı
artık ligin tabanını aşıyor (ilk sürümde: 12'de 0).

### 40.3 Kalibrasyon

2024 hedefleri, emsaller **yalnızca 2022+2023'ten** (geleceğe bakış yok):

| Emsal dedi | Gerçekleşen | n |
|---|---|---|
| 0,018 | 0,062 | 856 |
| 0,175 | **0,189** | 354 |
| 0,439 | **0,438** | 397 |
| 0,710 | **0,698** | 400 |

Orta ve üst kovalarda neredeyse köşegen üzerinde. **En alt kova iyimser**
(0,018 diyor, 0,062 oluyor): 0/40 görmek "%0" demek değil. Cümle bunu
kurtarıyor çünkü **her zaman güven aralığı gösteriliyor** — 0/40 için
"%0 (GA %0–%9)".

### 40.4 k ödünleşmesi — büyük k SAHTE KESİNLİK üretir

`python scripts/build_emsal.py --k-taramasi`

| k | AUC | GA genişliği | Tabanı aşan |
|---|---|---|---|
| **40** | **0,662** | 0,199 | %13,9 |
| 80 | 0,627 | 0,148 | %14,6 |
| 150 | 0,564 | 0,128 | %14,7 |

Büyük k aralığı daraltıyor ve daha çok "anlamlı" üretiyor — **ama ayırt
etme gücü düşüyor.** Kesinliği bilgiyle karıştırmamak için **k=40**.
(k=20 hiç sonuç vermiyor: asgari emsal 30 kuralına takılıyor, beklenen.)

### 40.5 'kaldıraç' sıralama anahtarı DEĞİL

`oran / lig_taban` sezgisel görünüyor ama küçük payda etkisi taşıyor.
Ölçüldü: kaldıraca göre sıralayınca liste tabanı %3 olan liglerle
(Arjantin, Brezilya Serie B, Eliteserien) doluyor ve **ilk 12'nin 11'i
sonradan hiçbir izlenen lige çıkmamış.**

Kaldıraç bağlam için gösterilir; **sıralama modelin olasılığıyla yapılır.**
Karar `taban_ustunde` bayrağına bakar (GA alt sınırı > taban).

### 40.6 Hüküm

Emsal oranı **benimsendi**. Modeli geçmiyor (−0,043) ve geçmesi beklenmiyor;
ama artık **mevcut uzman skorunu anlamlı biçimde geçiyor** (+0,057) ve
kalibre. İki işi var:

1. Modelin olasılığına **sayılabilir, adları okunabilir** bir karşılık vermek
2. Ayırt edemediğinde bunu açıkça söylemek

**21 test** (`test_emsal.py`), toplam **152 test** geçiyor.
`build_emsal.py` günlük zincirde.

### 40.7 Kalan sınır

Vakaların %86'sında emsal oranının güven aralığı hâlâ ligin tabanını
kapsıyor — yani çoğu oyuncu için cevap "bu profil sıradan". Bu bir kusur
değil, n=40'ın dürüst sınırı: %12 tabanda %25'i ayırt etmek için birkaç yüz
emsal gerekir, o da emsal olmaktan çıkar. Veri büyüdükçe iyileşir.

## 41. FAZ 4 — Scout Dosyası: Veri Dökümü Değil, İddia (30 Ağu 2026)

`app/views/Scout_Dosyasi.py` + `src/scout/features/dosya.py` +
`app/_dosya_metin.py`

Projenin çıkış noktası buydu: *"uygulama sadece veriyi önüne dökmesin,
içinden bir anlam ve araştırma çıkarsın."*

### 41.1 Yedi bölüm

| Bölüm | Ne veriyor |
|---|---|
| **İDDİA** | Tek cümle, yanlışlanabilir |
| **KANIT** | Skoru taşıyan metrikler (waterfall özeti) + kapsam |
| **BAĞLAM** | Lig zorluğu, takım, yaşıtlarına göre dakika payı |
| **YÖRÜNGE** | Sezon sezon **+ sonradan gerçekten ne olduğu** |
| **EMSAL** | Bu profildekiler ne oldu (§40) |
| **RİSKLER** | Otomatik bayraklar |
| **NE İZLEMELİSİN** | Verinin göremediği |

Gerçek çıktı örneği (Lamine Yamal, La Liga 2024):

> **17,5 yaşında, La Liga'de yaşıtlarının %96'sı seviyesinde. Model, 12 ay
> içinde izlenen bir birinci ligde yer edinme olasılığını %97 veriyor;
> ligin tabanı %68.**
>
> Sonuç: İzleyen 12 ayda **ilk-5 ligde yer edindi** — ES1, 2270 dakika.

Son satır kullanıcının asıl istediği şey: *"bu çocuk ne yapmış?"* — artık
sistem cevaplıyor.

### 41.2 "Ne izlemelisin" neden var

Sistem nerede **kör** olduğunu söylemezse, kullanıcı nereye bakacağını
bilemez ve gözlemi sistemin **tekrarı** olur. Amaç tersi: gözlem sistemin
**devamı** olsun.

Mevkiye özgü kör noktalar, verinin gerçek sınırlarından türetildi:
- Stoper: *"veri yalnızca **müdahaleyi** sayıyor, doğru yerde durup
  müdahaleye gerek bırakmayanı ödüllendirmiyor"*
- Forvet: *"bitiricilik kalitesi — xG olmadan şut seçimi
  değerlendirilemiyor"*
- Orta saha: *"pasın kırıcılığı — hat arası mı, yan mı (mekânsal veri yok)"*

Artı her dosyada genel körlükler: fizik, karakter, baskı altında karar,
sakatlık geçmişi, sözleşme.

### 41.3 Riskler otomatik, ama "boş liste risk yok demek değil"

Yedi bayrak: küçük örneklem (<900 dk) · eksik metrik (kapsam <0,60) ·
bozuk lig verisi · **sonuç kısmen görünmez** · **piyasa değeri yok** ·
tek sezon · yaş sınırda (≥22,5).

İki tanesi bu projeye özgü ve önemli:

- **Sonuç kısmen görünmez** — menşe lig TM'de izlenmiyorsa kademe 0
  "başarısız" demek değil (§38.4). Düşük görünürlüklü her oyuncuda yanar.
- **Piyasa değeri yok** — `deger_var` modelin en güçlü değişkeni (+1,44);
  yoksa skor aşağı çekiliyor. Dosya bunu açıkça *"kalitesizlik değil,
  **görünmezlik** anlamına gelebilir"* diye yazıyor (§39.4).

### 41.4 src/ metin üretmiyor — bu sefer baştan doğru

§35.6'da bu ayrımı bir kez ihlal etmiştim ve sayfada Türkçe arayüzün
ortasında ASCII cümleler görünmüştü. Bu sefer:

- `src/scout/features/dosya.py` → **kod** üretir (`kucuk_orneklem`,
  `sonuc_gorunmez`, `fw_bitiricilik`…) ve eşikleri tutar
- `app/_dosya_metin.py` → Türkçe cümleleri kurar

`test_metin_uretmez` her risk ve kör nokta kodunun ASCII ve boşluksuz
olduğunu doğruluyor; `test_turkce_metin_ascii_sizintisi_yok` sayfayı
çalıştırıp "yasinda" gibi sızıntı arıyor.

### 41.5 Sayfayı gerçekten çalıştıran test bir hata daha buldu

Sorguda `e.n AS emsal_n` diye yeniden adlandırmıştım ama `emsal.cumle()`
ham `n` anahtarını bekliyor → `KeyError: 'n'`. **Birim testler yeşilken**
sayfa düşük görünürlük filtresinde çöküyordu.

Kadro Analizi'ndeki (§34.6) desenin aynısı: modül doğru, sayfa yanlış.
`tests/test_dosya_sayfasi.py` (7 test) bunu yakaladı.

### 41.6 Dışa aktarım

Dosya markdown olarak indirilebiliyor — sahaya telefonla gidilir.
İddia, yörünge, emsal, riskler ve kör noktalar tek dosyada.

**27 yeni test** (`test_dosya.py` 20 + `test_dosya_sayfasi.py` 7),
toplam **179 test** geçiyor.

### 41.7 Kalan: FAZ 5 (hesap defteri)

Dosya bir iddia üretiyor ama iddia henüz **kaydedilmiyor**. Sistem geçen
yıl ne dedi, ne oldu — bu soruyu yanıtlayacak defter FAZ 5'te.

## 42. FAZ 5 — Hesap Defteri (30 Ağu 2026)

`src/scout/model/defter.py` + `scripts/defter.py` +
`app/views/Hesap_Defteri.py` → `iddia_defteri` tablosu

Bir scout ekibini **ekip** yapan şey, iddiasının kaydının tutulmasıdır.
Bu faza kadar hiçbir iddiamız yazılı değildi, dolayısıyla **hiçbiri
yanlışlanamıyordu**.

### 42.1 İki bölüm — ve aradaki fark kritik

Kurarken hemen bir dürüstlük sorunuyla karşılaştım: **2022–2024
sezonlarının sonucu zaten biliniyor.** Bugün bu sezonlar için açılan bir
kayıt ileriye dönük tahmin değildir — model bu veriyle eğitildi (2022+2023)
ya da üzerinde sınandı (2024).

| Bölüm | Ölçüt | Ne işe yarar |
|---|---|---|
| **Geçmişe dönük** | Kayıt anında pencere kapalıydı | Kalibrasyon raporu — modelin **nerede** yanıldığı |
| **İleriye dönük** | Kayıt anında pencere açıktı | **Gerçek sicil** |

Ayrım koda gömüldü: `bolumle()` kayıt tarihi ile sezon bitişi arasındaki
farka bakıyor (≥365 gün → retrospektif). `test_pencere_kapaliyken_retrospektif`
ve `test_bir_gun_eksikte_prospektif` sınırı kilitliyor.

İkisini karıştırmak, geriye dönük testi *"sistem şu kadar isabetli"* diye
sunmak olurdu. Bu proje o hatayı bir kez yaptı (§31); tekrar etmiyoruz.
Arayüzde bu, sayfanın en görünür uyarısı:

> **Bu bir sicil DEĞİL, başarı iddiası DEĞİL.** … Buradaki sayılar yalnızca
> modelin **nerede yanıldığını** gösterir.

`test_retrospektif_sicil_diye_sunulmuyor` bu uyarının varlığını sınıyor.

### 42.2 İleriye dönük bölüm şu an BOŞ — ve bu normal

Elimizdeki en yeni sezon 2024 ve onun 12 aylık penceresi kapandı. 2025
ücretsiz API'de açıldığında (30 günde bir sınanıyor, §33.3) bölüm dolmaya
başlar.

Boş bölüm "bir şey çalışmıyor" gibi görünmesin diye sayfa **neden** boş
olduğunu yazıyor.

### 42.3 İlk kayıt hemen bir bulgu verdi

300 iddia kaydedildi (sezon × kapsam başına ilk 50). Kalibrasyon:

| Model dedi | Gerçekleşen | n |
|---|---|---|
| 0,568 | **0,650** | 60 |
| 0,648 | 0,500 | 60 |
| 0,740 | 0,617 | 60 |
| 0,881 | **0,833** | 60 |
| 0,930 | **0,900** | 60 |

**Nerede yanılıyor (sapma > 0 = model fazla umutlu):**

| Lig türü | n | Model dedi | Gerçekleşen | Sapma |
|---|---|---|---|---|
| **`sicrama_only`** | 150 | 0,674 | 0,580 | **+0,094** |
| `tam` | 150 | 0,833 | 0,820 | +0,013 |

**Model, düşük görünürlüklü liglerde ~9 puan fazla umutlu; izlenen liglerde
kalibre.** Yani tam da en çok önemsediğimiz yerde iyimser. Muhtemel sebep:
bu liglerde sonucun kendisi kısmen görünmez (§38.4) — model "yer edinmedi"
sayılan ama aslında kendi ülkesinde yükselen oyuncuları ceza olarak
öğreniyor.

Bu bulgu FAZ 4'teki risk bayrağını doğruluyor: düşük görünürlüklü ligde
model olasılığı bir üst sınır gibi okunmalı.

### 42.4 Senin seçimlerin

Shortlist ile defter kesiştiriliyor: senin seçtiklerinin model ortalaması
ve gerçekleşme oranı, defter geneliyle yan yana. Bir scout ekibinde asıl
öğrenme burada — sistem ve insan nerede ayrışıyor, ayrışınca kim haklı
çıkıyor.

Şu an boş (shortlist'te defterde kayıtlı oyuncu yok); Keşif sayfasından
işaretledikçe dolar.

### 42.5 Append-only

`defter.py --kaydet` yinelenen kayıt yazmaz, **geçmiş kaydı asla
güncellemez**. Bir iddianın değeri geri alınamamasından gelir. Günlük
zincire eklendi.

**20 yeni test** (`test_defter.py` 15 + `test_defter_sayfasi.py` 5),
toplam **199 test** geçiyor.

---

## FAZ 1–5 TAMAMLANDI

| Faz | Çıktı | Durum |
|---|---|---|
| 1 | `player_outcome` — gerçek sonuç tablosu | ✅ §38 |
| 2 | Model — üç tabanı da geçti | ✅ §39 |
| 3 | Emsal oranı — kalibre, mevcut skoru geçiyor | ✅ §40 |
| 4 | Scout dosyası — iddia + gerekçe + kör noktalar | ✅ §41 |
| 5 | Hesap defteri — iddia kaydı | ✅ §42 |

**Sırada ne var:** ileriye dönük defterin dolması 2025 sezonuna bağlı.
O açılana kadar en verimli işler: veri toplamayı tamamlamak (kalan
lig-sezonlar), ve §42.3'teki iyimserlik sapmasını düzeltmek — düşük
görünürlüklü liglerde model olasılığının kalibrasyonu.

## 43. FAZ 6 PLANI — Mevki Sıralaması ve "Sonra Ne Yaptı" Doğrulaması (30 Eyl 2026)

Kullanıcı hedefi (kendi sözleriyle özet): model 2022–24 verisiyle eğitilsin;
**her mevkiden** başarılı ve **yatırıma değer** oyuncuların sıralaması çıksın;
kullanıcı bu oyuncuların *şimdi* ne yaptığını (kaç maç, ne kadar verim)
kendisi incelesin. Pahalı, zaten bilinen oyuncular ilgi alanı **dışında**.

Bu bir yeniden yönlendirme: modelin işi artık "yer edinir mi" olasılığı
vermek değil, **"piyasanın değerinin altında fiyatlanan"** oyuncuyu mevki
mevki sıralamak. Aşağıdaki plan önce ölçtüklerime dayanıyor.

### 43.1 Planı şekillendiren üç ölçüm

**(a) Fiyat, sonucun en güçlü göstergesi.**

| Sezon-sonu değeri | n | "Yer edindi" |
|---|---|---|
| Değerleme yok | 1.680 | %4,8 |
| < 0,5M € | 1.173 | %14,7 |
| 0,5–2M | 1.224 | %32,4 |
| 2–5M | 651 | %51,8 |
| 5–15M | 629 | %64,4 |
| > 15M | 536 | %79,1 |

Model AUC'si 0,70 — ama bunun ne kadarı **sadece fiyat**? Modelin en güçlü
değişkenleri zaten `deger_var` ve `log_deger`. Kullanıcının ilgilendiği
*ucuz* bantta modelin ek bilgi katıp katmadığı **hiç ölçülmedi**. Bu, planın
en kritik sorusu: ölçülmezse "yatırıma değer" sıralaması aslında bir **fiyat
sıralaması** olur ve kullanıcıya zaten bildiği şeyi söyler.

**(b) Mevkiye göre örneklem çok dengesiz.**

| Mevki | n (tam+sıçrama) | Olumlu |
|---|---|---|
| Defans | 2.041 | 658 |
| Orta saha | 1.980 | 627 |
| Forvet | 1.630 | 473 |
| **Kaleci** | **242** | **56** |

Mevkiye göre lig-içi AUC (2024; model bu sezonu da görmüş → üst sınır):
defans 0,737 · kaleci 0,724 · orta saha 0,702 · forvet 0,691. Kaleci için
**ayrı model eğitmek mümkün değil** (242 satır); onlar için havuzlanmış model
+ geniş belirsizlik gerekir.

**(c) "Kaç puanla oynadı" sorusunun bir sınırı var.** API'den gelen *rating*
yalnızca 2022–2024 sezonlarında. Sonraki dönem (2025/26) için **yok**.
Elimizde olan, Transfermarkt CC0'dan: maç sayısı, dakika, gol, asist, kart,
ilk 11/yedek (`game_lineups`, henüz DB'ye alınmadı), değer yörüngesi,
transfer bedeli. Yani **"ortalama puan" yerine "dakika + gol/asist + değer
değişimi + ilk 11 oranı"** ölçülebilir. Kullanıcıya bu baştan söylenmeli.

### 43.2 Fazlar

#### FAZ 6.1 — Modeli tam veriyle yeniden eğit · ~0,5 gün
- 2023 sezonu 14 → 23 lige çıktı; **612 eğitim satırı** (çoğu Avrupa büyük
  ligleri) modelin görmediği durumda. `player_emsal` (5.893) ile
  `player_model_score` (5.281) arasındaki tutarsızlık da bunun sonucu:
  612 oyuncu Scout Dosyası'nda görünmüyor.
- **Sızıntı disiplini:** test penceresi (2024) bu kez **üçüncü** açılışta.
  Sebep model araması değil, eksik verinin tamamlanması — kayda geçirilecek.
- **Ek sağlamlık:** *kayan başlangıç* — (a) eğit 2022 → sırala 2023,
  (b) eğit 2022+2023 → sırala 2024. İki bağımsız geri test; sonuç
  ikisinde de tutarlıysa güven artar.
- **Kabul:** üç taban (mevcut skor, piyasa, dakika+yaş) yine geçilir ve
  `model_olasilik` tüm 5.893 satırda dolu.

#### FAZ 6.2 — Fiyat-koşullu değerlendirme · ~1 gün · **EN KRİTİK**
- Lig-içi AUC'yi **fiyat bandı içinde** ölç: değer yok / <0,5M / 0,5–2M /
  2–5M. Model, fiyatın söylediğinin ÜSTÜNE ne katıyor?
- **Piyasa-yalnız modeli** (sadece `log_deger`, `deger_var`, yaş, lig) kur;
  **`piyasa_ustu = model_olasilik − piyasa_olasiligi`** üret. Bu, tam olarak
  "yatırıma değer": *piyasa vasat diyor, oyun verisi güçlü diyor*.
- **Kabul:** ucuz bantta (değer yok + <2M) model, piyasa-yalnız modeli eşli
  bootstrap GA'sı sıfırı dışlayarak geçmeli.
- **Geçemezse:** dürüstçe yazılır — *"bu bantta oyun verisi fiyattan fazla
  bilgi vermiyor"* — ve sıralama başka bir kritere kaydırılır (ör. yaşa
  göre dakika payı, gelişim). Sonuç arayüze "başarı" diye değil olduğu gibi
  yansıtılır.
- **Önceden bilinen risk:** ucuz bandın çoğunluğu `deger_var=0`
  (1.680/3.500) ve orada taban oran %4,8. Bu grubun içinde ayırt etme
  gücü modelin *diğer* değişkenlerine bağlı; ayrı ölçülecek.

#### FAZ 6.3 — Mevki mevki sıralama · ~1 gün
- Mevki için ayrı model **yalnızca** ölçülüp üstünlüğü kanıtlanırsa
  benimsenir (lig-dışarıda-bırak CV, havuzlanmış modele karşı). Kanıt yoksa
  havuzlanmış model + **mevkiye özgü kalibrasyon** (isotonic/Platt).
- **Kaleci:** ayrı model yok; çıktı geniş güven aralığıyla ve "n=242"
  uyarısıyla verilir.
- Her mevki için: **top-K listesi** (K=20 varsayılan), model olasılığı,
  `piyasa_ustu`, güven aralığı, emsal oranı, risk bayrakları.
- **Kabul:** her mevkide lig-içi AUC ≥ taban (dakika+yaş) ve kalibrasyon
  hatası raporlanır; kaleci için açıkça "düşük güven" işaretlenir.

#### FAZ 6.4 — "Sonra ne yaptı" tablosu · ~1,5 gün
- `game_lineups` + `games` DB'ye alınır (bugüne dek dokunulmadı).
- Her oyuncu-sezon için sonraki 12 ay: **maç, ilk 11, dakika, gol+asist/90,
  değer değişimi (Δ€ ve Δ%), transfer (bedel, hedef lig), en çok oynadığı
  lig**. *Rating yok — bu kullanıcıya açıkça yazılır.*
- **Eşleştirilmiş kontrol:** top-K'yı *rastgele* oyuncularla değil; aynı
  lig-türü + mevki + yaş bandı + fiyat bandındaki **sıradan oyuncularla**
  kıyasla. Aksi halde "top-K daha çok oynadı" bulgusu yalnızca "daha iyi
  oyuncular daha çok oynar" der. Fark için bootstrap GA.
- Bu tablo kullanıcının manuel incelemesinin **ham materyali**: her satırda
  "model dedi X, gerçekte şu oldu" yan yana.
- **Kabul:** kontrol grubuna göre fark GA ile raporlanır; sıfırı
  kapsıyorsa öyle yazılır.

#### FAZ 6.5 — Arayüz: "Mevki sıralaması" sayfası · ~1 gün
- Filtre: mevki · lig türü (düşük görünürlük / izlenen) · **fiyat tavanı**
  (kaydırıcı; varsayılan ≤ 5M € veya değerleme yok) · yaş · sezon kesiti.
- Tablo: model olasılığı, `piyasa_ustu`, GA, emsal, **sonra ne yaptı
  sütunları**, risk bayrağı. CSV dışa aktarım. Satıra tıklayınca Scout
  Dosyası.
- Tarihsel sezon seçilince **"o gün bilinenlerle"** sıralama (as-of) ve
  yanında **gerçekleşen** — kullanıcının kendi testini yapacağı ekran bu.
- **Kabul:** `AppTest` ile her mevki/filtre kombinasyonu çökmeden açılır.

#### FAZ 6.6 — Düşük görünürlük iyimserliğini gider · ~1 gün
- §42.3'te ölçüldü: model bu liglerde ~9 puan fazla umutlu (sapma +0,094).
- Kapsam-koşullu kalibrasyon (Platt) dene; **yalnız** lig-dışarıda-bırak
  CV'de kalibrasyon hatasını iyileştiriyorsa benimse.

### 43.3 Sıra ve bağımlılık

```
6.1 yeniden eğit ──> 6.2 fiyat-koşullu ölçüm ──> 6.3 mevki sıralaması
                              │                        │
                              └── sonuç: model ucuz bantta  │
                                  ek bilgi veriyor mu?      │
6.4 sonra-ne-yaptı (bağımsız, paralel) ─────────────────────┤
                                                            v
                                          6.5 arayüz  ──>  6.6 kalibrasyon
```

**6.2'nin sonucu planın geri kalanını belirler.** Model ucuz bantta ek bilgi
veriyorsa tüm plan olduğu gibi sürer. Vermiyorsa 6.3–6.5 "oyun verisi
piyasadan fazlasını söylemiyor" gerçeğine göre yeniden kurulur.

Toplam ~6 iş günü. Ücretli veri yok.

### 43.4 Baştan kabul edilen sınırlar

1. **Rating yok** (sonraki dönem) → "kaç puan ortalamayla" ölçülemez;
   yerine dakika, gol+asist, ilk 11, değer değişimi.
2. **Sonuç kısmen görünmez**: TM 14 Avrupa birinci ligini oyuncu bazında
   izliyor. Brezilya/Arjantin/Kolombiya/İskandinav oyuncusu ülkesinde
   yükselirse **görmeyiz** (§38.4). Sıralamada düşük görünürlüklü liglerin
   `sonra ne yaptı` sütunu çoğunlukla boş olacak; bu "başarısız" değil.
3. **Kaleci örneklemi küçük** (242) → düşük güvenle sunulur.
4. **Ortalamaya dönüş**: bir sezonluk parlayan oyuncunun sonraki sezon
   düşmesi normal; kontrol grubu tam bunun için var.
5. **Ücretsiz sezon penceresi 2022–24**: güncel (2025/26) oyun verisi
   yok. "Şimdi ne yapıyor" yalnızca TM'den (dakika, gol, asist, değer)
   izlenir; pas, mücadele gibi zengin metrikler için güncel sezon yok.

### 43.5 Kullanıcı kararı gereken tek nokta

"Pahalı değil" tanımı: varsayılan **sezon-sonu değeri ≤ 5M € veya değerleme
yok**. Kaydırıcı ile değiştirilebilir; 6.2'de bantlar ayrı ayrı ölçüleceği
için hangi eşikte modelin gerçekten fark yarattığı **veriden** görülecek —
eşik gerekirse ona göre önerilecek.


## 44. FAZ 6.1 — Model Tam Veriyle Yeniden Eğitildi (30 Eyl 2026)

Eksik 612 eğitim satırı (2023'ün Avrupa büyük ligleri) tamamlandı; eğitim
havuzu 3.205 → **3.817**. `player_model_score` artık `player_emsal` ile aynı:
**5.893**. Scout Dosyası'nda gizli kalan 612 oyuncu görünür oldu.

### 44.1 Sonuçlar — iki BAĞIMSIZ pencere

| Pencere | model | piyasa | dakika+yaş | mevcut skor |
|---|---|---|---|---|
| **Kayan: 2022 → 2023** (yeni) | 0,741 | 0,715 | 0,639 | 0,589 |
| **Tutulan: 2022+23 → 2024** | 0,699 | 0,657 | 0,634 | 0,608 |

Fark (eşli, oyuncu bazlı bootstrap): kayan pencerede +0,151 / **+0,025** /
+0,103; tutulan pencerede +0,091 / **+0,042** / +0,066 (skor / piyasa /
dakika+yaş). **Üç taban iki pencerede de geçildi.** Piyasaya karşı marj küçük
ama iki pencerede de sıfırı dışlıyor.

### 44.2 Dürüstlük kaydı — tutulan pencere ÜÇÜNCÜ kez açıldı

1. İlk model · 2. eksik piyasa değeri kodlaması düzeltmesi (§39.5) ·
3. **eksik eğitim verisinin tamamlanması (bu)**. Hiçbirinde model varyantı
seçilmedi; hüküm üçünde de aynı. Model araması yapılmadığı için sızıntı yok,
ama üç bakış kayıtta.

### 44.3 6.2'yi öngören işaret (ÖNEMLİ)

Piyasa değeri **verilmeden** eğitilen model, piyasaya karşı:

| Pencere | Fark | %95 GA |
|---|---|---|
| Eğitim (LOLO CV) | −0,032 | [−0,061 , −0,004] |
| Kayan 2023 | **−0,051** | [−0,095 , −0,013] |
| Tutulan 2024 | +0,026 | [−0,016 , +0,068] |

İki pencerede **anlamlı biçimde kötü**, birinde ayırt edilemez. Yani oyun
verisi tek başına piyasayı yenmiyor; model ancak piyasayı da bilince
kazanıyor. Bu, kullanıcının ilgilendiği "piyasanın altında fiyatlanan"
sorusunu doğrudan etkiliyor ve FAZ 6.2'de fiyat bandı içinde ayrıca
ölçülecek. Erken uyarı: "yatırıma değer" sıralaması beklenenden zayıf
çıkabilir.

### 44.4 Katsayı kayması

`score` katsayısı +0,134 → **+0,061**, `score_age` ≈ 0. Rol skoru, daha çok
veriyle modelde giderek daha az ağırlık alıyor; `deger_var` (+1,42) ve
`log_deger` (+0,95) baskın. Rol skoru sıralamada hâlâ anlamlı ama modelin
asıl taşıyıcısı değil.

### 44.5 Defter

`iddia_defteri` (300 kayıt, 31 Ağu) **dokunulmadı** — append-only, eski model
olasılıkları olduğu gibi kalıyor. Yeni model olasılıkları yeni kayıtlarla
girer.

## 45. FAZ 6.2 — Fiyat-Koşullu Değerlendirme (30 Eyl 2026)

`scripts/fiyat_bandi.py` · soru: model AUC'sinin ne kadarı **sadece fiyat**?
Kullanıcı pahalı oyuncularla ilgilenmiyor; ucuz bantta modelin fiyatın
üstüne bir şey katıp katmadığı ölçülmemişti.

**Yöntem:** her fiyat bandı içinde lig-içi AUC; tahminciler *model*, *piyasa*
(yalnız değer+yaş), *basit* (dakika+yaş), *saf* (oyun verisi, piyasa yok);
eşli oyuncu-bazlı bootstrap. **Disiplin:** birincil kanıt = lig-dışarıda-bırak
CV (2022+23) ve kayan 2022→2023; 2024 yalnızca **önceden ilan edilmiş**
doğrulama (4. bakış, model seçimi yok).

### 45.1 Ana sonuç — UCUZ (≤5M € veya değerleme yok), üç pencerede

| Fark (AUC) | CV 2022+23 | Kayan 2023 | Tutulan 2024 |
|---|---|---|---|
| **model − piyasa** | +0,033 [+0,02 , +0,05] | +0,027 [+0,00 , +0,05] | **+0,043 [+0,02 , +0,06]** |
| **model − dakika+yaş** | +0,091 [+0,06 , +0,12] | +0,086 [+0,04 , +0,12] | +0,050 [+0,00 , +0,09] |
| **saf − dakika+yaş** | +0,025 [+0,00 , +0,04] | +0,028 [−0,00 , +0,06] | +0,063 [+0,03 , +0,09] |

**Model, ucuz bantta piyasayı üç pencerede de aynı yönde geçiyor** (sınırda
küçük bir marj: +0,03–0,04). Oyun verisi (piyasa olmadan) dakika+yaşın
üzerine **+0,03–0,06 AUC** ekliyor. Yani "yatırıma değer" sıralaması bir
fiyat sıralamasının kopyası **değil** — ama etki küçük ve dürüstçe öyle
sunulmalı.

### 45.2 Bant bant: etki yeknesak değil

| Bant | n (CV) | model − basit (CV / kayan) | Yorum |
|---|---|---|---|
| **< 0,5M** | 805 | **+0,082* / +0,160*** | oyun verisi burada en değerli |
| 0,5–2M | 865 | −0,001 / +0,010 | **model ≈ dakika+yaş** |
| 2–5M | 470 | −0,001 / +0,004 | **model ≈ dakika+yaş** |
| ≥ 5M | 782 | +0,062* / +0,100* | (ilgi dışı) |

**0,5–5M ara bantta model, dakika+yaştan ayırt edilemiyor.** Oyun
metriklerinin asıl katkısı en ucuz oyuncularda (piyasanın hiç fiyatlamadığı
yerde) ve en pahalılarda. Ara bantta fiyat ve oynama süresi neredeyse her
şeyi söylüyor.

### 45.3 KÖR NOKTA — "değerleme yok" grubu ölçülemiyor

En çok ilgilenilen grup (Transfermarkt'ın hiç değer biçmediği oyuncular):

| | n | olumlu |
|---|---|---|
| CV 2022+23 | 895 | **12 (%1,3)** — 28 lig-sezonun **22'sinde sıfır** olumlu |
| Kayan 2023 | 447 | yetersiz |
| Tutulan 2024 | 785 | 68 (%8,7) — ölçülebilir |

Sebep yapısal: bunlar TM'nin oyuncu bazında **hiç izlemediği** liglerin
oyuncuları (Kolombiya, Arjantin, Ekvador, İskandinavya…). Sonuç değişkenimiz
(izlenen bir birinci ligde ≥900 dk) bu grupta neredeyse **kör**. Tek ölçülebilen
pencere 2024'te model − dakika+yaş +0,077 [+0,01 , +0,16], saf − dakika+yaş
+0,121 [+0,04 , +0,22] — ama bu **tek pencere**.

**Sonuç:** "değerleme yok" grubu için sıralama **doğrulanmamıştır**; tek
pencere işareti olumlu ama iki pencerede ölçülemiyor. Bu, kullanıcı arayüzde
açıkça görmeli.

### 45.4 `piyasa_üstü` tanımına etkisi

Piyasa-yalnız model, değerlemesi olmayan oyuncuda **bilgisizdir** (sabit).
Dolayısıyla o grupta `model_olasilik − piyasa_olasiligi` ≈ modelin kendisi;
"piyasa altı fiyatlanma" **tanımlı değil**. Kural:
- değerlemesi **var** → `piyasa_ustu = model − piyasa` (gerçek karşılaştırma)
- değerlemesi **yok** → sıralama `model_olasilik` ile, satır **"piyasa
  referansı yok — doğrulanmamış"** işaretli

### 45.5 Bu plan için anlamı

1. **Plan geçerli**: ucuz bantta model piyasanın üstüne bilgi ekliyor;
   FAZ 6.3–6.5 sürer.
2. Beklenti **mütevazı olmalı**: +0,03–0,04 AUC, "kesin isabet" değil.
3. En sağlam alan **<0,5M**; **0,5–5M** ara bantta oyun verisi dakika+yaştan
   fazlasını söylemiyor — o bantta sıralama zayıf güvenle sunulacak.
4. **Yeni iş (6.2b):** "değerleme yok" grubunu doğrulamak için **ikinci
   bir sonuç değişkeni** gerekiyor — kendi verimizden (aynı oyuncunun
   sonraki sezon dakika/skor/lig-değişimi; Brezilya Serie A gibi TM'nin
   izlemediği ama bizim API verimizde olan ligler dahil). Bu, TM körlüğünü
   aşar.

### 45.6 Kayıt

Tutulan 2024 penceresi **dördüncü kez** açıldı (betimleyici, model seçimi
yok, önceden ilan edilmiş). 3 yeni test (`test_fiyat_bandi.py`); eksik
değerin "0 €" sanılmaması (`0 yok` ayrı bant) bir daha kilitlendi.

## 46. FAZ 6.2b — İkinci Sonuç Değişkeni: Kendi Verimizden (30 Eyl 2026)

`src/scout/features/outcome2.py` + `scripts/dogrula_ikinci_sonuc.py`

TM sonucu, TM'nin izlemediği liglerde kördü (§45.3). Aynı oyuncunun **sonraki
sezon** satırını kendi API verimizde aradık: 24 ligimizden birinde, orijinden
**daha üst seviyede ≥450 dk** oynadı mı? Model bu sonucu **hiç görmedi**
(TM sonucuyla eğitildi) → bağımsız doğrulama.

### 46.1 Üç tuzak baştan kapatıldı

1. **Sansür** (§38.3'ün dersi): sabit pencere, sezon bitişinden (90, 400] gün.
   2024 orijinleri gözlenemez (2025 kapalı) ve **dışlanır — sıfır sayılmaz.**
2. **Takvim**: sezon etiketi değil **tarih**. Brezilya B 2022 → Portekiz
   2022/23 aynı etiketli sezon ama tarihçe sonra; etiket kuralı bunu kaçırırdı.
3. **Seviye tanımı veriyle sınandı** (4 kaba kademe, elle): farklı seviyeye
   geçen U23'lerin **%74'ü yukarı** (tüm yaşlar %59; 444 yukarı · 154 aşağı).
   Tanım doğru yönde.

`tests/test_outcome2.py` — 11 test bu üçünü kilitliyor.

### 46.2 İki sonucun uyumu

`corr(y_TM, y2) = +0,26` (izlenen ligler, n=773). Orta: ikisi ilişkili ama
**aynı şeyi ölçmüyor** — birbirinin kör noktasını kısmen kapatıyorlar.

### 46.3 Model ikinci sonucu öngörüyor (LOLO CV, 2022+23, n=3.022, %13,2 olumlu)

| Kesit | n | Olumlu | model | piyasa | dk+yaş | saf | model−dk+yaş | model−piyasa |
|---|---|---|---|---|---|---|---|---|
| **Hepsi (T2–T4)** | 3.022 | 400 | **0,767** | 0,745 | 0,614 | 0,673 | +0,154* | **+0,021*** |
| Değer VAR | 2.130 | 363 | 0,755 | 0,728 | 0,621 | 0,677 | +0,133* | +0,027* |
| **Değer YOK (TM kör)** | 892 | **37** | 0,630 | 0,564 | 0,561 | 0,587 | +0,067 [−0,01 , +0,14] | +0,067 [−0,10 , +0,21] |
| Düşük görünürlük | 2.249 | 319 | 0,768 | 0,741 | 0,625 | 0,683 | +0,147* | +0,027* |
| **TM kör ligler** | 791 | 40 | **0,863** | 0,820 | 0,595 | 0,691 | +0,268* | +0,045 [−0,00 , +0,10] |
| Ucuz (≤5M/yok) | 2.810 | 338 | 0,750 | 0,725 | 0,616 | 0,668 | +0,134* | +0,025* |

(* = %95 GA sıfırı dışlıyor.)

### 46.4 Ne doğrulandı, ne doğrulanmadı

**Doğrulandı:** model **bağımsız bir sonucu**, hiç görmediği liglerde,
piyasanın **üstünde** öngörüyor (+0,021 [+0,01 , +0,04]); ucuz bantta da
(+0,025). Oyun verisi (piyasa olmadan) dakika+yaşın üzerine anlamlı bilgi
ekliyor (+0,059; TM kör liglerde +0,096). §45'teki bulgu **ikinci sonuç
değişkeniyle de tutuyor** — tek bir ölçüme bağımlı değil.

**Doğrulanmadı — "değerleme yok" grubu hâlâ kesinleşmedi:** yön olumlu
(model − dk+yaş +0,067, saf − dk+yaş +0,025) ama **yalnızca 37 olumlu**;
güven aralıkları sıfırı kapsıyor. Yetersiz güç, çürütme değil. Bu grup için
sıralama **"doğrulanmamış"** etiketi taşımaya devam edecek.

**Dikkat — TM kör ligler AUC 0,863:** çarpıcı ama muhtemelen piyasa
bilgisinden (piyasa tek başına 0,820); o liglerdeki değerli üst düzey
oyuncular ile değersiz olanların ayrımı kolay. Asıl ayrı sinyal **saf**
model (+0,096 dk+yaş üzerine). Bu sayıyı "model çok iyi" diye okumak yanlış.

### 46.5 Sınır

Yalnızca 2022 ve 2023 orijinleri (2024 gözlenemez). Seviye tanımı elle ve
kaba; yön dengesi (%74) makul ama tek tek lig sıralaması kanıtlanmadı.
24 ligimizin dışına (Türkiye, Rusya, MLS…) geçişler **görünmez**.

**Sonuç:** 6.3'e geçmek için engel yok. `deger yok` grubu güvenle doğrulanana
dek etiketli kalır.

## 47. FAZ 6.3 — Mevki Sıralaması (30 Eyl 2026)

`scripts/mevki_model.py` (model seçimi) · `scripts/build_ranking.py`
(`player_ranking` tablosu, 5.893 satır) · `scripts/train_model.py` (düzeltme)

### 47.1 Mevkiye özel model gerekli DEĞİL — kanıtla

Ön-ilanlı kural: bir varyant ancak havuzlanmış modeli (P), ilgili mevkide **ve
en az iki hedefte** (TM sonucu, ikinci sonuç y2) güven aralığı sıfırı
dışlayarak geçerse benimsenir. LOLO CV, 2022+2023, tutulan 2024'e dokunulmadı.

| Varyant | Sonuç |
|---|---|
| **X** havuzlanmış + mevki göstergeleri | fark yok; y2'de hepsinde **−0,007 [−0,01 , −0,00]** (anlamlı biçimde biraz kötü) |
| **S** mevkiye özel ayrı model | hiçbir mevkide P'yi geçemedi (S−P: def +0,003, orta −0,012, forvet +0,012; GA'lar sıfırı kapsıyor) |
| **U** birleşik hedef (y_TM **veya** y2) | üç hedefte de fark yok; kör noktayı kapatmadı |

**P (havuzlanmış, TM hedefi) kalıyor.** Sadeleşme: ayrı mevki modelleri
kurmaya, mevki kesişim kaymasına ya da hedef birleştirmeye gerek yok.
Kaleci (n=242) için zaten ayrı model mümkün değildi.

### 47.2 BULUNAN HATA: eksik değer, test kümesinin kendi medyanıyla dolduruluyordu

`_hazirla` eksikleri **df'in kendi medyanıyla** dolduruyordu. İki sorun:
1. Test kümesi için bu, test dağılımından bilgi sızdırır (küçük ama gerçek).
2. **Tek satırlık tahminde medyan o satırın kendisi olur** — eksik değer NaN
   kalır ve `0.0`'a düşer. `score_age` için ham 0 çok uç bir değerdir.

Eksik oranlar küçük (score_age %4,6 · minutes_agepct %4,5 · rating_pct %2,8),
bu yüzden **toplu sonuçları etkilemedi**: düzeltme sonrası CV (0,744) ve
kayan (0,741) AUC'leri üç haneye kadar aynı; tutulan pencere yeniden
açılmadı. Ama tam da yapacağımız iş — tek oyunculuk sıralama / Scout Dosyası
— bu hatadan etkilenirdi.

**Düzeltme:** `_hazirla(df, kolonlar, ref=EGITIM)` — eğitim medyanı; üretim
modeli medyanları `model_ranker.joblib` içine kaydediyor. `--kaydet-yalniz`
bayrağı, spesifikasyon değişmediğinde test penceresini açmadan kayıt sağlıyor.
4 test (`test_medyan.py`).

### 47.3 Sıralama tablosu: her tahmin DIŞARIDAN

Kullanıcı tarihsel bir sezonu seçip "gerçekte ne oldu" diye bakacak. Üretim
modeli bu sezonları görmüş (in-sample) → geçmiş sıralamalar olduğundan iyi
görünürdü. Bu yüzden `player_ranking`'de:

| Sezon | Tahmin türü |
|---|---|
| 2022, 2023 | lig-dışarıda-bırak CV (satır kendi ligini hiç görmemiş) |
| 2024 | 2022+2023 ile eğitilmiş model (zaman dışı) |
| 2025+ | üretim modeli (açılınca) |

Alanlar: `model_olasilik`, `piyasa_olasilik`, **`piyasa_ustu`** (yalnız
değerlemesi VAR ise), fiyat bandı, `ucuz`, `guven`, `tahmin_turu`.

**Güven etiketi** (6.2/6.2b bulgularının kodlanması; en kötümser kazanır):
`dusuk` (kaleci) > `dogrulanmamis` (değerleme yok) > `zayif` (0,5–5M) > `iyi`
(<0,5M, ≥5M). Dağılım: iyi 2.224 · zayıf 1.803 · doğrulanmamış 1.624 ·
düşük 242.

### 47.4 Mevki bazında sonuç (dışarıdan tahmin, lig-içi AUC)

| Mevki | n | model | piyasa | dk+yaş | saf | model − dk+yaş |
|---|---|---|---|---|---|---|
| Defans | 2.041 | 0,735 | 0,729 | 0,630 | 0,659 | **+0,106*** |
| Orta saha | 1.980 | 0,729 | 0,711 | 0,633 | 0,678 | **+0,098*** |
| Forvet | 1.630 | 0,728 | 0,697 | 0,664 | 0,697 | **+0,065*** |
| **Kaleci** | 242 | 0,824 | 0,764 | 0,817 | 0,843 | +0,004 [−0,10 , +0,10] |

Kalibrasyon hatası: forvet 0,018 · orta saha 0,018 · defans 0,032 ·
**kaleci 0,065** (üst dilimde model 0,67 diyor, gerçekleşen 0,62; orta
dilimlerde 0,31 → 0,17). **Kaleci için model dakika+yaştan ayırt edilemiyor**
ve kalibrasyonu belirgin biçimde kötü — `dusuk` etiketi hak ediyor.

### 47.5 Sağlama: top-20, dakika+yaş ile seçilen top-20'den daha mı iyi?

Ucuz bantta (≤5M/değerleme yok), mevki × sezon 12 hücre; top-20'nin
**gerçekten yer edinen oranı**:

| Seçim | Ortalama isabet |
|---|---|
| Taban (bant ortalaması) | %19,9 |
| Dakika+yaş ile top-20 | %35,0 |
| Oyun verisi (saf) ile top-20 | %40,8 |
| **Model ile top-20** | **%55,8** |

Model, dakika+yaş seçimini **12 hücrenin 11'inde** geçiyor (ort. +0,208).
Top-20 isabeti tabanın **1,9–3,6 katı** (her hücrede tabanın üstünde). Bu
"sadece çok oynayanı seçmek" değil.

**Ama** dürüst not: top-20'lerin çoğu `zayıf` bantta (0,5–5M). O bant için
AUC düzeyinde model ≈ dakika+yaş bulmuştuk (§45.2), top-20 düzeyinde ise
belirgin üstün. İkisi çelişmiyor — AUC tüm sıralamayı, top-20 yalnızca en
üst ucu ölçüyor — ama zayıf bant etiketi bu yüzden "sıralamanın **ortası**
belirsiz, **ucu** dolu" diye okunmalı.

### 47.6 Sınır
- Kaleci: n=242, kalibrasyon kötü, dakika+yaştan ayırt edilemiyor.
- Top-20 isabeti `y` (TM sonucu) ile; TM'nin kör olduğu `dogrulanmamis`
  grup için bu sayılar geçerli değil.
- Model olasılığı **sıralama** için; mutlak olasılık olarak yalnızca
  outfield mevkilerde kalibre.

**9 yeni test** (`test_ranking.py` 5 + `test_medyan.py` 4), toplam **222**.

## 48. FAZ 6.4 — "Sonra Ne Yaptı" + Eşleştirilmiş Kontrol (30 Eyl 2026)

`scripts/build_sonra.py` → `player_sonra` (36.881 satır) ·
`src/scout/model/kontrol.py` · `scripts/sonra_analiz.py`

### 48.1 player_sonra: her oyuncu-sezon için sezon bitişinden sonraki 12 ay

`mac_lig / ilk11_lig / dk_lig / gol+asist / ga90`, kupa dahil `mac_tum /
ilk11_tum`, **değer yörüngesi** (`deger_bas`, `deger_son`, `deger_oran`),
`kulup_degisti`, `bilinen_bedel`. `game_lineups` (1,36 milyon satır) DB'ye
alındı.

**Kapsam (U23, pencere tam):**

| | n | maç var | ilk 11 var | sonra değer var | kulüp değişti |
|---|---|---|---|---|---|
| İzlenen ligler (`tam`) | 2.350 | %82,6 | %82,2 | %77,9 | %22,4 |
| Düşük görünürlük | 3.867 | %25,7 | %32,7 | **%33,0** | %3,4 |

### 48.2 İKİ BULUNAN VERİ TUZAĞI

1. **`transfers` tablosu ciddi biçimde eksik.** Maç kayıtlarına göre kulüp
   değiştiren 350 U23'ten yalnızca **32'si (%9)** tabloda kayıtlı. İlk
   sürümdeki `transfer_var` (oran %4,3) "transfer olmadı" diye **yanlış bilgi**
   verirdi. Kulüp değişimi artık **maç kayıtlarından** türetiliyor (%22,4,
   iki tarafta görünenlerdeki %27'yle uyumlu); tablodan yalnızca `bilinen_bedel`
   ve **kısmi** olduğu belirtilerek.
2. Aynı tablo **2030'a kadar tarihli** kayıt içeriyor (sözleşme kaynaklı
   gelecek). Veri tarihiyle kırpılıyor.

Ayrıca kendi hatam: ilk sürümde geniş `except Exception` gerçek bir hatayı
"şema farkı" gibi maskeliyordu; yalnızca `BinderException/CatalogException`.

### 48.3 Rating YOK — kullanıcıya baştan söylendi

API rating'i yalnızca 2022–24. Sonraki dönem için ölçülebilen: dakika,
ilk 11, gol+asist, değer değişimi. "Kaç puanla oynadı" **ölçülemez.**

### 48.4 Yöntem: eşleştirilmiş kontrol

Tedavi: her (sezon, mevki) için **ucuz bantta** (≤5M/değerleme yok) model
top-K, tahminler **dışarıdan** (`player_ranking`). Kontrol: aynı sezon +
mevki + kapsam + `deger_var`; en yakın 5 oyuncu **yaş, log dakika, log
değer** üzerinden. Bu bilinçli olarak **muhafazakâr**: modelin en çok
dayandığı üç şeyi sabitler; geriye kalan fark, oyun metriklerinin katkısıdır.
"Top-K daha çok oynadı" bulgusu dakika farkından gelemez. Güven aralıkları
**oyuncu bazında kümelenmiş** bootstrap (aynı oyuncu birden çok sezonda
hedefte olabilir). `test_kontrol.py`: 11 test.

### 48.5 SONUÇ (K=20, tüm sezonlar, ucuz bant)

| Alt grup | Yer edindi | Birinci lig dk | İlk 11 | Gol+asist/90 | **Değer değişimi** |
|---|---|---|---|---|---|
| **HEPSİ** (n=240) | — | **+434** [+302 , +567]* | **+4,8** [+3,4 , +6,4]* | **+0,062** [+0,030 , +0,093]* | **+0,070 [−0,033 , +0,175]** |
| İzlenen ligler (132) | **+0,172*** [+0,085 , +0,258] | +401* | +4,7* | +0,054* | +0,069 [−0,078 , +0,211] |
| Düşük görünürlük (108) | **+0,178*** [+0,073 , +0,281] | +426* | +4,5* | +0,084* | +0,079 [−0,078 , +0,240] |
| Defans (60) | +0,223* | +422* | +4,5* | +0,035* | −0,011 [−0,188 , +0,159] |
| Orta saha (60) | +0,123 [−0,010 , +0,251] | +424* | +3,8* | +0,034 [−0,032 , +0,100] | +0,069 |
| Forvet (60) | +0,177* | +370* | +5,2* | **+0,149*** [+0,074 , +0,231] | +0,069 |
| Kaleci (60, düşük güven) | +0,208* | +544* | +6,1* | (yetersiz) | +0,125 |

(* = %95 GA sıfırı dışlıyor.)

### 48.6 NE DOĞRULANDI, NE DOĞRULANMADI

**Doğrulandı — model, eşleştirilmiş kontrole göre sonradan gerçekten daha
çok ve daha verimli oynayan oyuncuları seçiyor.** Aynı yaş, aynı dakika, aynı
fiyat: ortalama **+434 birinci lig dakikası, +4,8 ilk 11, +%17 yer edinme
olasılığı, +0,06 gol+asist/90.** Etki hem izlenen hem düşük görünürlüklü
liglerde, dört mevkide de aynı yönde. Forvette gol+asist/90 farkı en belirgin
(+0,149).

**Doğrulanmadı — "finansal yatırım değeri".** Değer değişimi (ln son/baş):
**+0,070 [−0,033 , +0,175]** — yani modelin seçtikleri **piyasa değerini
kontrolden anlamlı biçimde daha çok artırmadı** (ortalama ~%7, belirsiz).
Hiçbir alt grupta anlamlı değil. Kullanıcının "maddi yük de önemli" kaygısı
için bu kritik: **model sahada daha iyi oyuncular seçiyor; bu oyuncuların
piyasa değeri bunu (12 ayda) anlamlı biçimde yansıtmıyor.** Sebepler
olabilir: değer güncellemeleri gecikmeli, yalnızca %33–78'inde iki
değerleme var, 12 ay kısa.

### 48.7 Sınırlar (kullanıcıya gösterilecek)

- **Gol+asist/90 koşullu**: yalnızca ≥450 dk oynayanlar → seçilim etkisi.
- **Sonuçlar TM tabanlı**: izlenmeyen ligde oynamaya devam edenler "iz yok".
  Düşük görünürlük satırlarında dakika farkının bir kısmı "izlenen lige
  geçti mi" farkıdır, oyun kalitesi farkı değil.
- **2022/2023 tahminleri lig-dışı CV'den**: modeller başka liglerin *gelecek*
  sezonlarını görmüş olabilir. Temiz zaman-dışı yalnızca 2024 (aşağıda).
- Kontrol eşleşmesi gözlemlenebilir değişkenlere; gözlenmeyen (fizik, karakter)
  farklar kontrolsüz.
- Rating yok.


### 48.8 SAĞLAMA — K ve zaman dışı

Havuzlanmış sonuç 2022/23'ün lig-dışı CV tahminlerine dayanıyordu (modeller
başka liglerin *gelecek* sezonlarını görmüş olabilir). Temiz **zaman-dışı**
yalnızca 2024; K'yı da değiştirerek:

| Tedavi | n | Yer edindi | Birinci lig dk | İlk 11 | Gol+asist/90 | Değer değişimi (ln) |
|---|---|---|---|---|---|---|
| K=20, tüm sezonlar | 240 | +0,17* | +434* | +4,8* | +0,062* | +0,070 [−0,033 , +0,175] |
| K=20, **yalnız 2024** | 80 | **+0,126*** [+0,009 , +0,244] | **+262*** [+16 , +499] | +2,8* | +0,047 [−0,000 , +0,094] | +0,044 [−0,106 , +0,197] |
| K=50, tüm sezonlar | 450 | **+0,150*** [+0,101 , +0,197] | **+392*** [+303 , +483] | **+4,5*** | **+0,057*** [+0,030 , +0,084] | **−0,057** [−0,132 , +0,019] |
| K=50, **yalnız 2024** | 150 | **+0,193*** [+0,112 , +0,274] | **+407*** [+247 , +563] | **+4,8*** | **+0,049*** [+0,008 , +0,092] | **−0,072** [−0,170 , +0,034] |

**Dört kurulumun dördünde de** yer edinme, birinci lig dakikası ve ilk 11
farkı anlamlı ve aynı yönde. En konservatif tahmin (K=20, yalnız 2024, n=80)
en küçük etkiyi veriyor ama yine anlamlı; K=50'de (daha büyük örneklem) temiz
2024 sonucu **daha güçlü**. Yani havuzlanmış sonuç lig-dışı CV'nin bir
artefaktı değil.

**Değer değişimi hiçbir kurulumda anlamlı değil, ve K=50'de yön NEGATİF**
(−0,057 ve −0,072, ikisinde de GA sıfırı kapsıyor). Modelin sahada daha iyi
seçtiği oyuncuların piyasa değeri kontrolden **daha hızlı artmıyor**.

### 48.9 Kullanıcı için sonuç

Sistem iki farklı şey söyleyebilir; ikisi ayrı tutulmalı:

1. **"Bu oyuncu sahada yer edinir / daha çok oynar / daha verimli"** —
   **destekleniyor** (eşleştirilmiş kontrolle, 12 ay sonra, dört kurulumda).
2. **"Bu oyuncunun piyasa değeri artar / yatırım olarak kârlı"** —
   **desteklenmiyor.** Değer 12 ayda kontrolden anlamlı biçimde fazla
   artmıyor.

Kullanıcı maddi yükü önemsiyor: ucuz aldığı bir oyuncu sahada daha çok işe
yarıyor ama **yeniden satış değeri** avantajı bu veriyle gösterilemiyor.
"Yatırıma değer" ifadesi arayüzde **"sahada değer üretir"** olarak
okunmalı, **"değeri artar"** olarak değil.

### 48.10 Yöntemsel not
Hiç model seçimi yapılmadı; tahminler `player_ranking`'den (dışarıdan).
Tutulan 2024 penceresi bu fazda *yeniden eğitim için* açılmadı — yalnızca
2024'ün dışarıdan tahminleri sonuçla eşlendi (betimleyici).

**17 yeni test** (`test_kontrol.py` 11 + `test_sonra.py` 6).

## 49. FAZ 6.5 — "Mevki Sıralaması" Sayfası (30 Eyl 2026)

`src/scout/model/siralama.py` (mantık, metin üretmez) ·
`app/views/Mevki_Siralamasi.py` (ince arayüz) · `app/Home.py` (gezinme)

Kullanıcının testi burada gerçekleşiyor: tarihsel sezon seç → fiyat tavanı
koy → listenin üstünü incele → **"sonra gerçekte ne oldu"ya bak**.

### 49.1 Ne sunuyor

- **Dört sekme:** Defans · Orta saha · Forvet · Kaleci — her biri kendi
  top-N'i, özeti ve CSV'siyle ("her mevkiden sıralama").
- **Filtreler:** sezon · sıralama ölçütü · fiyat tavanı (0,25–20 M €) ·
  değerlemesizleri dahil et · lig türü · yaş · asgari dakika · güven etiketi.
- **Üç ölçüt:** *model olasılığı* (oyun verisi + piyasa) · ***piyasa üstü***
  (model − piyasa, yalnız değerlemesi olanlarda) · ***yalnız oyun verisi***
  (piyasa YOK — fiyattan bağımsız bir bakış).
- **Sonra sütunları:** sonuç (12 ay), birinci lig dakikası, ilk 11,
  gol+asist/90, değer Δ%, kulüp değişti.
- **Her listenin özeti:** *gerçekte yer edinen oran* + **%95 güven aralığı** +
  havuzun tabanı; aralık tabanı kapsıyor mu, sayfa açıkça yazıyor.

Örnek (2024, defans, ≤5M € veya değerleme yok, 30 oyuncu): gerçekte yer edinen
**%73** (GA %56–86), havuz tabanı **%23** → tabanın üstünde; ort. lig
dakikası 1.606. Sayfa aynı anda "listenin çoğu zayıf bantta" uyarısını da
veriyor.

### 49.2 Sayfanın kendi dürüstlük katmanı

Her açılışta iki sabit uyarı: (1) **Rating verisi yok** — sonraki dönem için
yalnız dakika, ilk 11, gol+asist, değer değişimi; (2) **"Yatırıma değer"
= sahada değer üretir, değeri artar DEĞİL** (§48.9). Ayrıca:

- `iz yok*` → izlenmeyen ligden gelenin sonucu **başarısız demek değil**
  (§38.4); `sonra_metni_kodu` bunu `iz_yok` ile `iz_yok_gorunmez` diye ayırıyor.
- Uyarılar listeye göre dinamik: çoğunluğu *doğrulanmamış*, *zayıf* ya da
  *kaleci* ise ilgili cümle çıkıyor (PLAN §45.3, §47.5).
- "Bu sayfa neyi söylemiyor?" açılır bölümü: fizik, karakter, sakatlık dahil
  körlükler.
- **`piyasa_ustu` olmayanlar listeden çıkarılıyor**, sona itilmiyor:
  değerlemesizde "piyasa altında fiyatlanma" tanımsız (§45.4).
- Eksik değer tavana sokulmuyor: "değerlemesizleri dahil et" ayrı seçenek
  (eksik 0 € değildir, §39.4).

### 49.3 Test sırasında düzeltilen iki tutarsızlık

1. **Çelişkili uyarı:** 20 oyunculu listede "oran yorumlanamaz" uyarısı çıkıyor,
   hemen üstünde ise güven aralığı "tabanın üstünde" diyordu. Wilson aralığı
   küçük örneği zaten hesaba katıyor. Uyarı *"aralığıyla birlikte okuyun"*
   diye yeniden yazıldı; varsayılan liste boyu 20 → **30**.
2. **ASCII sızıntısı** (§35.6'nın üçüncü tekrarı): veriden gelen
   `zaman-disi` / `lig-disi CV` arayüzde ham görünüyordu; Türkçe etikete
   eşlendi. Yazım da "56-86%" → "%56–86".

### 49.4 Test

18 mantık testi (`test_siralama.py`) + 7 sayfa testi
(`test_siralama_sayfasi.py`, `AppTest`: dört sekme, iki temel uyarı, kaleci
uyarısı, tüm sezon ve ölçütlerde çökmeme, aşırı sıkı filtrede boş liste).
Sayfa ayrıca gerçek tarayıcıda açılıp doğrulandı.

Toplam **264 test**.



## 50. FAZ 6.6 — Kapsam-Koşullu Kalibrasyon (30 Eyl 2026)

`src/scout/model/kalibrasyon.py` · `scripts/kalibrasyon_dene.py` ·
`scripts/build_ranking.py` (uygulama) · `data/kalibrator.json` ·
`tests/test_kalibrasyon.py` (8)

### 50.1 Önce ölçüyü düzelttik: +0,094 neydi?

§42.3'teki +0,094, defterin **ilk 50'lerinden** (sezon × kapsam) ve
2022/23 için **örneklem içi** üretim modelinden geliyordu. Dışarıdan
tahminlerin (`player_ranking`) tamamında tablo farklı:

| | n | tahmin | gerçek | sapma |
|---|---|---|---|---|
| Düşük görünürlük (`sicrama_only`) | 3.544 | 0,160 | 0,121 | **+0,039** iyimser |
| İzlenen (`tam`) | 2.349 | 0,503 | 0,589 | **−0,087** kötümser |

Sorun tek yönlü değil: model `kapsam`ı özellik olarak görmüyor. İki grubun
tabanı çok farklı (%12 / %59), lig-dışı tahminde bu farkı kısmen kaçırıyor.

### 50.2 Önceden yazılan kural ölçüyü yanlış seçmişti (açık kayıt)

Karar kuralı çalıştırmadan önce yazıldı: genel ECE'de anlamlı iyileşme,
Brier kötüleşmez, iki kapsamda ECE kötüleşmez. İlk koşuda sonuç **"ham"**
çıktı. Sebep: **genel ECE bu soruna kör.** Aynı olasılık kovasında izlenen
ligin kötümserliği ile düşük görünürlüğün iyimserliği birbirini götürüyor
(genel ECE 0,014, kapsam içi ECE'ler 0,089 / 0,063).

Kriter (1), planın asıl hedefi olan **koşullu ECE** ile değiştirildi
(kapsam içi ECE'lerin n-ağırlıklı ortalaması, lig-kümeli bootstrap).
Bu, sonucu gördükten sonra yapılan bir değişiklik. Bu yüzden **2024 teyidi
zorunlu sayıldı:** 2024'te koşullu ECE ve Brier iyileşmeseydi benimsenmeyecekti.

### 50.3 Sonuç

Kalibratör de dışarıdan: 2022/23'te her lig için yalnızca diğer liglerden
kuruldu, 2024'te 2022+23 CV'den.

| | koşullu ECE | Brier | havuz AUC | ECE tam | ECE düşük gör. |
|---|---|---|---|---|---|
| **CV 2022+23** ham | 0,074 | 0,1478 | 0,841 | 0,089 | 0,063 |
| CV global Platt | 0,080 | 0,1495 | 0,837 | 0,096 | 0,070 |
| **CV kapsam Platt** | **0,028** | **0,1403** | **0,859** | 0,029 | 0,027 |
| **2024** ham | 0,076 | 0,1431 | 0,839 | 0,108 | 0,056 |
| **2024 kapsam Platt** | **0,050** | **0,1372** | **0,852** | 0,052 | 0,050 |

Fark (kapsam − ham), lig-kümeli %95 GA:
- **CV:** koşullu ECE −0,046 [−0,065, −0,021]\*, Brier −0,0075 [−0,013, −0,003]\*
- **2024:** koşullu ECE −0,025 [−0,042, −0,005]\*, Brier −0,0059 [−0,011, −0,002]\*

Tek global Platt işe yaramıyor (hatta kötüleştiriyor): sorun genel
değil, **gruplar arası.** Kapsam × değerleme (4 grup) kapsamdan anlamlı iyi
değil, bu yüzden basit olan seçildi (2024'te `kd` koşullu ECE'de biraz iyi,
0,048 / 0,050, Brier'de kötü, 0,1386 / 0,1372; karar CV'den verildi,
değişmedi). **Benimsendi.**

Lig içi AUC'ler birebir aynı kaldı (Defans +0,106, Orta saha +0,098, Forvet
+0,065 dakika+yaşa karşı): kalibrasyon lig içinde sıralamayı değiştirmiyor.
Mevki kalibrasyon hataları 0,018–0,045'e indi.

Platt parametreleri (2022+23 CV): düşük görünürlük a=−0,64, b=0,93
(neredeyse sabit aşağı kaydırma); izlenen a=+0,39, b=0,67 (yukarı kaydırma
ve uçları sıkıştırma).

### 50.4 İKİ UYARI — benimsenen şey mükemmel değil

**1. İyimserlik zamanla azalıyor; sabit düzeltme en yeni sezonda fazla geliyor.**

| Düşük görünürlük, ilk 50 | ham sapma | kalibre sapma |
|---|---|---|
| 2022 | +0,198 | +0,054 |
| 2023 | +0,083 | −0,069 |
| 2024 | +0,038 | **−0,122** |

Liste tepesinde, en yeni sezonda **ham değer gerçeğe daha yakın.** Sayfa
iki değeri yan yana gösteriyor ("Model %" + "Ham %") ve bunu açıkça
söylüyor. Muhtemel sebep: TM'nin bu ligleri ve sıçramaları izleme kapsamı
zamanla artıyor. Yeni sezon eklendikçe kalibratör yeniden kurulmalı. 2025
açıldığında `kalibrator.json` 2022–24 ile yeniden üretilecek.

**2. Karma listede izlenen ligler öne çıkıyor. Bu bir ölçüm iyileşmesi,
keşif iyileşmesi DEĞİL.**

Ucuz bantta, iki kapsam karışıkken top-20 isabeti yükseliyor (2024:
%58,8 → %67,5). Ama bu kazancın kaynağı bileşim: listelerdeki izlenen
lig payı %41–70'ten **%86–91**'e çıkıyor, kapsam içinde isabet artmıyor.
Kalibre olasılık "sonucu **görünür** başarı" olasılığı. Görünürlüğü yüksek
olanı öne almak ölçülen isabeti artırıyor, ama projenin amacı olan düşük
görünürlüklü liglerdeki gizli yeteneği geri itiyor.

Önlem: karma havuzda listenin ≥%75'i izlenen liglerdense sayfa uyarıyor
(`UYARI_IZLENEN`) ve **Lig türü → Düşük görünürlük** seçimini öneriyor.
Tek kapsamlı görünümde sıralama kalibrasyondan hiç etkilenmiyor.

### 50.5 6.4 sonuçları yeni tedavi grubuyla yeniden koşuldu

Karma ucuz havuzda top-20 artık 212/240 izlenen ligden (düşük görünürlük
yalnızca 28, alt analiz için yetersiz). Ana bulgu korunuyor (K=20):

| | Yer edindi | Birinci lig dk | İlk 11 | G+A/90 | Değer değişimi |
|---|---|---|---|---|---|
| Önce (§48.5) | — | +434\* | +4,8\* | +0,062\* | +0,070 (ns) |
| **Sonra** | **+0,160\*** | **+394\*** | **+4,6\*** | **+0,061\*** | +0,042 (ns) |

"Sahada değer üretir, değeri artar değil" sonucu değişmedi.

### 50.6 Held-out sayacı

2024'e **5. bakış**, yalnızca kalibrasyon teyidi için. Model seçimi
değişmedi. Karar CV'den verildi; 2024 kuralı değiştirmedi, teyit etti.
(Teşhis sırasında 2024'ün kapsam sapmalarını bir tanı betiği de gösterdi.
Aynı bakışın parçası sayıldı.)

### 50.7 Kapsam dışı bırakılan

- **Scout dosyası / defter** (`player_model_score`) üretim modelinin
  örneklem içi olasılıklarını kullanıyor. Dışarıdan kurulan kalibratörü
  örneklem içi tahmine uygulamak tutarsız olurdu, bu yüzden dokunulmadı.
  `kalibrator.json` 2025+ tahminleri (gerçekten dışarıdan) için hazır.

Toplam **273 test**. Denetim 35 / 29 / 5 / 1 (değişmedi).


## 51. FAZ 7.0 — Tek Doğruluk Kaynağı + Zincir Tamamlama (1 Eki 2026)

`src/scout/model/tahmin.py` · `player_tahmin` tablosu · `tests/test_tahmin.py` (6)

### 51.1 Sorun: iki sayfa aynı oyuncu için iki farklı olasılık

| Kaynak | Ne | Kim okuyordu |
|---|---|---|
| `player_ranking` | dışarıdan (lig-dışı CV / zaman-dışı), kalibre | Mevki sıralaması |
| `player_model_score` | üretim modeli, **2022–24'ü eğitimde görmüş** | Scout dosyası, defter, emsal raporu |

Ölçülen fark (5.893 oyuncu-sezon): **ortalama 7, en fazla 27 puan**.
Örnek: 2024'ün en yüksek olasılığı sıralamada %93, dosyada %97.
İkinci sayı, cevabı bilen modelden geliyordu.

### 51.2 Kural

`build_ranking` artık `player_tahmin`'i de yazıyor: oyuncu-sezon başına tek
olasılık.
- Dışarıdan tahmin **varsa** o kullanılır (2022–24'ün tamamı).
- Yalnızca dışarıdan tahmini olmayan satırlar (sonucu bilinmeyen yeni
  sezonlar, 2025+) üretim modelinden gelir. Onlar zaten dışarıdan.
  Aynı kapsam kalibratörüyle (`kalibrator.json`) düzeltilir.
- Her satır kaynağını taşır: `tahmin_turu` = `lig-disi CV` |
  `zaman-disi` | `uretim` | `uretim_kalibresiz`.

Okuyanlar: Scout dosyası (olasılığın yanında kaynağı ve ham değeri de
gösterir), Hesap defteri, `defter.py`, `build_emsal.py`.
`player_model_score` yalnızca üretim modelinin iç çıktısı olarak kalır.
Hiçbir sayfa onu okumuyor.

### 51.3 Hesap defteri

- **Kayıt değişmez:** 7.0 öncesi 353 iddia olduğu gibi duruyor.
  Deftere `tahmin_turu` sütunu eklendi; eski satırlarda boş (= örneklem içi).
- **Geriye dönük kalibrasyon raporu artık defterin iddialarından değil,**
  `player_tahmin`'in 5.893 dışarıdan tahmininden hesaplanıyor. §42.3'teki
  "+0,094" ölçüsünün sorunu buydu: rapor, sezonu görmüş modelin
  iddialarını ölçüyordu.
- Yeni kural ilk çalıştığında **33 yeni (geriye dönük) iddia** kaydedildi:
  dışarıdan tahmine göre ilk-50'ler, üretim modelininkilerden farklı
  oyunculardan oluşuyor.
- Defter her `--kaydet`te `data/defter/iddia_defteri.csv`'ye aynalanıyor
  (git'te). Veritabanı yeniden üretilebilir, defter üretilemez.

### 51.4 Yeni bulgu: dışarıdan ölçünce

| Lig türü | n | Model dedi | Gerçekleşen | Sapma |
|---|---|---|---|---|
| İzlenen (`tam`) | 2.349 | 0,583 | 0,589 | −0,006 |
| Düşük görünürlük | 3.544 | 0,108 | 0,121 | −0,013 |

Kapsam kalibrasyonu (§50) tutuyor. Lig bazında en büyük sapma
**Premier League: model 0,790 dedi, gerçekleşen 0,670 (+0,121, n=230).**
Sebebi ölçülmedi. Kullanıcının odağı (ucuz/düşük görünürlük) dışında.
Kayıt altında, düzeltilmedi. Lig bazında kalibrasyon, 22 ligle aşırı
uyum riski taşır.

### 51.5 Günlük zincir

`daily_run.ps1`: `build_outcomes → build_sonra → build_ranking --sessiz →
build_emsal → defter --kaydet`. Önceden `build_sonra` ve `build_ranking`
zincirde yoktu. Veri güncellenince Mevki sıralaması **sessizce** eski
kalıyordu. `--sessiz` tanı raporunu atlar (17 sn).

### 51.6 Denetim: eski kalmayı içerikten yakalamak

DuckDB tablo zaman damgası tutmuyor. Dört yeni kontrol:
`player_tahmin` anahtarı tekil · her sıralama satırını kapsıyor ·
`player_ranking.kademe = player_outcome.kademe` (sonuç tablosu yenilenip
sıralama yenilenmediyse ayrışır) · sonucu bilinen sezonda üretim tahmini yok.

### 51.7 Test

`test_tahmin.py` (6), `test_defter.py` +3, `test_dosya_sayfasi.py` +1.
Sonuncusu sayfayı gerçekten çalıştırıp gösterilen olasılığın
`player_tahmin` ile aynı olduğunu sınıyor. Eski kaynakla kalsaydı %97 ≠ %93
ile kalırdı. Toplam **283 test**. Denetim 39 / 33 / 5 / 1 (5 = bilinen
sağlayıcı boşlukları).


## 52. FAZ 7.1 — Transfermarkt Tarihsel Tablo, 2012–2025 (1 Eki 2026)

`src/scout/features/tm_tarih.py` · `scripts/build_tm_tarih.py` ·
`tm_oyuncu_sezon` (92.958 oyuncu-lig-sezon, 26.297 oyuncu) ·
`tests/test_tm_tarih.py` (8)

### 52.1 Neden

API ücretsiz planı yalnızca 2022–2024'ü veriyor (Temmuz'da API bunu açıkça
söyledi; 2021'i yeniden denemek için istek harcanmadı). 2024 held-out'u beş
bakışla tükendi. Ham TM dosyasında (`2026-07-11`) hiç kullanılmamış
**2012–2021** ve **2025/26** var.

**Sınır:** TM yalnızca 14 birinci ligde oyuncu kaydı tutuyor. Düşük
görünürlüklü ligler bu dönemde yok. Bu tablo izlenen liglerdeki genç
oyuncular içindir.

### 52.2 Mühür (sonuçlara bakılmadan, kodda sabit)

| Sezon | Bölüm | Kullanım |
|---|---|---|
| 2012 | yalnız geçmiş | kadro verisi yok; yalnız "önceki sezon" bilgisi |
| **2013–2017** | geliştirme | özellik, model, kural seçimi |
| **2018–2021** | **mühürlü test** | **tek açılış (7.2).** 7.1'de sonuç oranı basılmadı |
| 2022–2024 | API dönemi | 7.4: API modeliyle aynı yıllarda karşılaştırma |
| 2025 | ileriye dönük | pencere açık; 7.5 defteri |

`test_muhur_degismedi` mührün sessizce kaydırılmasını engelliyor.
2019/20 ve 2020/21 COVID sezonları; test raporunda ayrı gösterilecek.

### 52.3 Özellikler (yalnız TM)

- **Süre:** dakika, maç, ilk 11, yedekten giriş, oyundan çıkış, tam maç
  (ilk 11 ve oyundan çıkmadı). Payları: dakika payı = dk / (90 × takımın
  lig maçı). Sezon içinde kulüp değiştirenlerde takım maçları toplanır.
- **Üretim:** gol, asist, sarı, kırmızı; G+A/90, kart/90.
- **Savunma bağlamı (kullanıcının sorusu üzerine):** oyuncu sahadayken
  takımın attığı ve yediği gol (`gf_on90`, `ga_on90`, artı-eksi) ve bunların
  **takımın sezon ortalamasına göre** farkı (`ga_on_goreli`, `pm_on_goreli`).
  Giriş: ilk 11 ise 0, değilse oyuna girdiği dakika. Çıkış: oyundan çıkış ya
  da kırmızı kart dakikası. Gol aralığı (giriş, çıkış].
- **Takım gücü:** takımın maç başı puanı, attığı ve yediği gol
  (sezonda birden çok kulüp varsa dakikayla ağırlıklı).
- **Mevki:** oyuncunun bugünkü mevkisi değil, **o sezon ilk 11'de en çok
  oynadığı mevki** (`game_lineups`): Stoper, Sol bek, Sağ bek, Ön libero,
  Merkez orta saha, 10 numara, kanatlar, Santrfor. 2013 sonrası %100 kadrodan.
- **Değer:** sezon bitişinden 1 ay önceki son değer (mevcut sistemle aynı kural).
- **Yörünge:** önceki sezonun 14 ligdeki dakikası ve dakika payı.
- **Sonuç:** mevcut sistemle aynı. Sezon bitişinden sonraki 12 ayda 14 ligdeki
  toplam lig dakikası; kademe, en çok oynanan ligin ilk-5 olup olmamasına
  göre. 2025 penceresi açık: sonuç NULL (0 değil).

### 52.4 Sağlamalar

| Sağlama | Sonuç |
|---|---|
| Baştan sona oynayan ilk 11'de sahadaki gol = maç skoru | **%99,95** (n=761.943) |
| Kendi kalesine gol: `club_id` lehine yazılan takım mı? | **%99,9** evet; işaret çevirme yok |
| **2022–24'te mevcut sistemle aynı oyuncu-sezonda kademe** | **%100,00** (n=13.478) |
| Sezon dakikası, TM ve API | korelasyon 0,936 |
| Kadro verisi kapsamı (maçların ilk 11'i) | 2013–2025 %97–100 |

U23 (≥450 dk) yaklaşık **760–890 oyuncu-sezon/yıl**. Geliştirme yıllarında
yer edinme tabanı %55–60. API havuzundan (%31) yüksek, çünkü burada herkes
zaten izlenen bir birinci ligde.

**2025'te değerleme kapsamı %73,4** (diğer yıllar %94–100). TM değerleri
2026-02-27'de bitiyor. 7.5'te `deger_var` göstergesi bu yüzden kritik.

### 52.5 İlk betimleyici bakış — yalnızca geliştirme yılları

U23, ≥450 dk, lig içi AUC (model değil, tek değişken; seçim 7.2'de):

| Mevki | n | dakika payı | sahadayken az gol yeme (takıma göre) | takım gücü | değer |
|---|---|---|---|---|---|
| Stoper | 574 | 0,656 | **0,622** | 0,677 | 0,656 |
| Sol bek | 348 | 0,709 | 0,553 | 0,683 | 0,726 |
| Sağ bek | 329 | 0,718 | 0,593 | 0,658 | 0,689 |
| Ön libero | 345 | 0,699 | 0,503 | 0,671 | 0,670 |
| Santrfor | 408 | 0,683 | 0,555 | 0,621 | 0,708 |

Stoperde "sahadayken takım ortalamasından az gol yemek" (0,622), API'nin
stoper rol skorundan (0,586, bkz. aşağıda) güçlü. Beklerde ve ön liberoda
asıl sinyal süre.

### 52.6 Kullanıcının sorusu: model yalnızca atak mı ölçüyor?

**Yapı olarak hayır:** API modelinde her oyuncu kendi mevkisinin rol
şablonlarıyla puanlanıyor. Stoper: ikili mücadele, top kesme, araya girme,
pas. Bek ve orta saha da kendi şablonlarıyla. Ama **ölçüm savunmada rol
skorunun zayıf olduğunu gösteriyor** (2022–24, lig içi AUC):

| | rol skoru | API reytingi | dakika payı | değer | model |
|---|---|---|---|---|---|
| Bek | **0,552** | 0,651 | 0,666 | 0,706 | 0,748 |
| Stoper | 0,586 | 0,690 | 0,648 | 0,710 | 0,741 |
| Orta saha | 0,635 | 0,666 | 0,642 | 0,693 | 0,729 |
| Forvet | 0,655 | 0,728 | 0,694 | 0,700 | 0,762 |

Model savunmada da çalışıyor, ama savunma istatistikleriyle değil reyting,
süre ve değerle. Sayısal müdahale verisi pozisyon almayı göremez (Scout
dosyasındaki "kör noktalar" bölümü bunu zaten söylüyor). 7.2'de savunma
bağlamı özelliklerinin bu boşluğu ne kadar kapattığı **mevki mevki**
raporlanacak.

### 52.7 Çalıştırma

Ham TM anlık görüntüsü değişmedikçe yeniden kurmaya gerek yok; günlük
zincirde değil. TM dosyası yenilendiğinde (`data/raw/transfermarkt/<tarih>/`)
en yeni klasör otomatik seçilir. Toplam **291 test**.


## 53. FAZ 7.2 — TM Modeli: Geliştirme ve Mühürlü Test (1 Eki 2026)

`src/scout/model/tm_model.py` · `scripts/tm_model.py` ·
`src/scout/model/egitim.py` (eğitim yardımcıları `train_model`'den taşındı;
`player_ranking` parmak izi 10 ondalığa kadar aynı) · `tests/test_tm_model.py` (7)

### 53.1 Kurulum

- **Nüfus:** U23, ≥450 lig dakikası, 14 izlenen lig. Hedef aynı:
  `y = kademe ≥ 3`, 12 ay.
- **Eğitim hattı aynı** (`egitim.py`: L2 lojistik, eğitim medyanıyla
  doldurma, C=1). Ölçü aynı (lig içi AUC, oyuncu kümeli eşli bootstrap).
- **Varyantlar:** `basit` (yaş + dakika payı) · `piyasa` (yaş + değer) ·
  `saf` (oyun verisi + savunma bağlamı, değer YOK) · `tam` (saf + değer) ·
  `tam_savsiz` (tam − savunma bağlamı) · `tam_mevki` (tam + savunma
  bağlamı × defans).
- Oyun verisi: dakika/ilk 11/tam maç/yedek payı, önceki sezon dakika payı,
  G+A/90 kohort yüzdeliği (lig-sezon-mevki, tüm yaşlar), kart/90, takım
  gücü, ilk-5 ligi. Savunma bağlamı: takıma göre artı-eksi ve yenen gol,
  `dk/(dk+900)` ile sıfıra çekilmiş (gürültülü).

### 53.2 Geliştirme kuralları (çalıştırmadan önce, betikte)

- **K1 savunma bağlamı tutulur** ⇔ `tam − tam_savsiz` defans alt grubunda
  hem LOLO hem kayan doğrulamada > 0 **ve** genelde anlamlı negatif değil.
- **K2 mevki etkileşimi benimsenir** ⇔ `tam_mevki`, `tam`'ı iki
  doğrulamada da GA sıfırı dışlayarak yener (projenin mevcut varyant kuralı).

### 53.3 MÜHÜRLÜ TEST HİPOTEZLERİ — test açılmadan yazıldı ve commit edildi

Seçilen model 2013–2017'nin tamamıyla eğitilir; 2018–2021 **bir kez**
tahmin edilir. `data/tm_tarih/muhur_acilis.json` yazılır; o dosya varken
betik ikinci kez test açmayı reddeder.

| | Hipotez | Başarı ölçütü |
|---|---|---|
| **H1** | Model, dakika+yaşı yener | lig içi AUC farkı, %95 GA > 0 |
| **H2** | Model, piyasayı yener | fark GA > 0 |
| H3 | Yalnız oyun verisi (saf) vs piyasa | **yön iddiası yok**; API döneminde fark anlamsızdı (§45). Raporlanır |
| **H4** | (savunma bağlamı tutulduysa) defansta model > savunma bağlamısız model | fark GA > 0 |
| **H5** | Ucuz bantta (≤5M / değersiz) sezon × mevki top-20 isabeti, dakika+yaşın top-20'sinden yüksek | ortalama yüksek ve hücrelerin çoğunda kazanır |

Ek olarak raporlanır (hipotez değil, 7.3'ün girdisi): sezon sezon AUC ve
kalibrasyon (ECE, sapma); 2019/20 ve 2020/21 COVID sezonları işaretli;
ince mevki bazında model − basit.

**Ne anlama gelecek:** H1 ve H2 tutarsa TM verisi izlenen liglerde, API'siz
ve 10 yıllık bağımsız bir dönemde, piyasanın ötesinde bilgi taşıyor demektir.
H2 tutmazsa model izlenen liglerde **piyasayı tekrar etmekten öteye
geçmiyor** demektir. Bu, projenin asıl iddiası olan "ucuz ve görünmez
oyuncu" için önemli bir uyarı olur. Sonuç ne çıkarsa çıksın yazılacak.

### 53.4 Geliştirme sonucu (2013–2017; test açılmadan)

Lig içi AUC, oyuncu kümeli eşli bootstrap (B=400).

| | basit | piyasa | **saf** | **tam** | tam − basit | tam − piyasa | saf − piyasa |
|---|---|---|---|---|---|---|---|
| LOLO (n=3.879) | 0,670 | 0,679 | 0,735 | 0,733 | +0,063* | +0,054* | +0,056* |
| Kayan 13–15→16–17 (n=1.522) | 0,694 | 0,688 | 0,740 | 0,739 | +0,046* | +0,052* | +0,052* |
| LOLO defans (n=1.251) | 0,695 | 0,689 | 0,754 | 0,749 | +0,054* | | |
| Kayan defans (n=481) | 0,723 | 0,660 | 0,720 | 0,722 | **−0,003** (ns) | | |

- **K1 savunma bağlamı: TUTULDU, ama zayıf.** Defansta `tam − tam_savsiz`
  +0,003 (LOLO) ve +0,006 (kayan); ikisi de anlamsız. Kural "iki
  doğrulamada pozitif ve genelde zarar yok" diyordu, "anlamlı" demiyordu.
  Kural gevşek kurulmuştu; bu açıkça kayıt altında. H4'ün tutmaması beklenmeli.
- **K2 mevki etkileşimi: REDDEDİLDİ** (+0,003, GA sıfırı içeriyor).
- **Seçilen: `tam`.**

**Dikkat çeken:** İzlenen liglerde TM oyun verisi piyasayı açıkça yeniyor
(saf − piyasa +0,05) ve değer, oyun verisine bir şey eklemiyor (saf ≈ tam).
API döneminde (§45) tersiydi. Fark muhtemelen nüfustan: burada herkes zaten
izlenen bir birinci ligde ve değerlemesi var. Kayan doğrulamada defansta
model dakika+yaşı yenemiyor. Bu, testte defans için kötümser bir beklenti.

### 53.5 MÜHÜRLÜ TEST SONUCU — 2018–2021, tek açılış (1 Eki 2026 13:20)

Hipotezler `467fba1`'de, açılıştan önce commit edildi. Açılış kaydı
`data/tm_tarih/muhur_acilis.json`. Tam çıktı
`reports/tm_muhurlu_test_2018_2021.txt`. n=3.097, olumlu %57,3. Eşli,
oyuncu kümeli bootstrap (B=1000).

| | Hipotez | Sonuç | Karar |
|---|---|---|---|
| **H1** | model > dakika+yaş | **+0,046** [+0,027, +0,064] | ✅ |
| **H2** | model > piyasa | **+0,057** [+0,042, +0,072] | ✅ |
| H3 | saf vs piyasa (yön iddiası yoktu) | **+0,058** [+0,042, +0,076] | oyun verisi piyasayı yeniyor |
| **H4** | defansta savunma bağlamı katkı | −0,005 [−0,019, +0,007] | ❌ |
| **H5** | ucuz bant top-20, dakika+yaştan iyi ve hücrelerin çoğunda | ort. 0,713 / 0,696, **5/12 kazandı** (2 berabere, 5 kaybetti) | ❌ |

AUC'ler: model 0,742 · saf 0,744 · basit 0,696 · piyasa 0,686.

**Sezon sezon (7.3'ün girdisi):**

| Sezon | n | olumlu | model | basit | piyasa | ECE | sapma |
|---|---|---|---|---|---|---|---|
| 2018 | 775 | %52,6 | 0,706 | 0,667 | 0,660 | 0,068 | **+0,063** |
| 2019 (COVID, ara) | 761 | %64,4 | 0,759 | 0,694 | 0,689 | 0,068 | **−0,056** |
| 2020 (seyircisiz) | 804 | %56,1 | 0,768 | 0,730 | 0,723 | 0,057 | +0,011 |
| 2021 | 757 | %56,3 | 0,731 | 0,691 | 0,670 | 0,038 | +0,017 |

Model dört sezonun dördünde de dakika+yaşı ve piyasayı yeniyor; COVID
sezonlarında da. Ama **kalibrasyon yıldan yıla ±6 puan oynuyor.** 2019/20'de
taban %64'e fırladı (muhtemelen ara ve 5 değişiklik kuralı gençlere daha çok
süre verdi; ölçülmedi). Sabit kalibrasyonun kırılganlığı (§50.4) bağımsız
10 yılda da görülüyor.

**Mevki mevki (model − basit):** Stoper **+0,070*** (n=537) ve Santrfor
**+0,083*** anlamlı. Diğerleri pozitif ama aralık geniş: Sağ bek +0,084,
10 numara +0,074, Merkez OS +0,058, Sol bek +0,040. Ön libero (+0,005),
Sağ kanat (−0,010) ve Sol kanat (+0,011) ayırt edilemiyor.

### 53.6 Ne öğrendik

1. **TM verisi izlenen liglerde gerçek ve bağımsız bir sinyal taşıyor.**
   10 yıl sonraki, hiç görülmemiş 4 sezonda model, piyasayı (+0,057) ve
   dakika+yaşı (+0,046) yeniyor. Geliştirmedeki etki büyüklüğü (+0,054 /
   +0,063) testte korundu: aşırı uyum yok.
2. **İzlenen liglerde piyasa değeri oyun verisine bir şey katmıyor**
   (saf 0,744 ≈ tam 0,742). API döneminde (§45) tersiydi. Ama orada nüfus
   düşük görünürlüklü ligleri içeriyordu. Burada herkes izlenen ligde ve
   değerlemesi var.
3. **Savunma bağlamı (artı-eksi) işe yaramadı (H4 ❌).** Geliştirmede de
   anlamsızdı ve K1 gevşek kurulduğu için tutuldu. Sonuç değişmedi: model
   onsuz da aynı. Yine de **stoperde model dakika+yaşı anlamlı yeniyor**
   (+0,070). Bu sinyal süre istikrarı, takım gücü ve geçmiş sezondan geliyor,
   artı-eksiden değil. Kullanıcının sorusunun cevabı netleşti: savunmada
   **ne** yaptığını ölçemiyoruz, **ne kadar güvenildiğini** ölçebiliyoruz.
4. **Liste tepesinde (H5 ❌) model, dakika+yaştan güvenilir biçimde iyi
   değil.** Ucuz bantta top-20 isabeti ortalamada ancak 1,7 puan yüksek ve
   12 hücrenin yalnızca 5'inde kazanıyor. Sebep: izlenen bir birinci ligde
   çok oynayan ucuz bir genç zaten büyük olasılıkla yer edinir. Dakika+yaşın
   top-20'si %70 isabet veriyor ve tepe doymuş durumda. Modelin üstünlüğü
   sıralamanın **bütününde** (AUC), **tepesinde** değil. API döneminin
   düşük görünürlüklü havuzunda (§47) bu tersiydi (11/12). Kullanıcı için
   anlamı: izlenen liglerde "listenin ilk 20'si" bir dakika listesinden
   çok farklı değil. Modelin değeri, düşük görünürlüklü liglerde ya da
   sıralamanın ortasında.
5. **Kalibrasyon yıldan yıla oynuyor.** 7.3 bu dört test yılını kullanamaz
   (mühür açıldı, artık geliştirme verisi değil). 7.3'ün kalibratör
   güncelleme kuralı 2013–2017 içinde seçilmeli, 2022–2024'te
   (TM satırları) sınanmalı.

Held-out sayacı: 2018–2021 **bir kez** açıldı. 2024 (API) için sayaç 5'te.


## 54. FAZ 7.3 — Kalibratör Zaman İçinde Nasıl Güncellenmeli? (1 Eki 2026)

`src/scout/model/zaman_kalibrasyon.py` · `scripts/kalibrasyon_kayma.py` ·
`kalibrasyon.py`'ye ağırlıklı Platt + kesişim kaydırması ·
`tests/test_zaman_kalibrasyon.py` (10)

### 54.1 Soru

Model iyi sıralıyor ama olasılık seviyesi oynuyor: TM mühürlü testinde
sezon sapması +0,063 / −0,056 / +0,011 / +0,017 (§53.5). API döneminde düşük
görünürlük iyimserliği 2022'den 2024'e azaldı (§50.4). Kalibratörü son
sezona göre mi, tüm geçmişe göre mi, ağırlıklı mı güncellemeli?

### 54.2 Kurulum

**İleri-zincir tahmin:** her sezon t için model (`tam`, §53) yalnızca
2013..t−1 ile eğitilir ve t'yi tahmin eder, yani üretimdeki durum.
Kurallar hedef sezon s için yalnızca s'den önceki sezonların tahmin ve
sonuçlarını kullanır. `test_gelecegi_gormez`, hedef sezonu ve sonrasını
bozmanın sonucu değiştirmediğini her kural için sınıyor.

Kurallar: `ham` · `tum_gecmis` (Platt, tüm geçmiş) · `son1` · `son2` ·
`son1_kesisim` (yalnız kesişim, tek parametre) · `agirlikli` (üstel,
yarılanma 1 sezon; önceden sabit).

**Karar kuralı (önceden):** geliştirme hedefleri 2015–2017. En düşük
log-kayıplı kural, `tum_gecmis`e karşı oyuncu kümeli %95 GA sıfırın
altındaysa seçilir; değilse `tum_gecmis`. Sınama 2022–2024 (TM).
**Açık kayıt:** 2022–24'ün TM taban oranları 7.1 sağlamasında basılmıştı.

### 54.3 Sonuç: hiçbir güncelleme kuralı işe yaramıyor

| | Geliştirme 2015–17 log-kayıp | Sınama 2022–24 log-kayıp | sınama ort. \|sapma\| |
|---|---|---|---|
| **ham** | **0,5871** | 0,6001 | 0,0027 |
| tum_gecmis | 0,5879 | 0,6001 | 0,0026 |
| son1 | 0,5886 | 0,6006 | 0,0058 |
| son2 | 0,5882 | 0,5998 | 0,0069 |
| son1_kesisim | 0,5888 | 0,6003 | 0,0068 |
| agirlikli | 0,5881 | 0,5999 | 0,0029 |

- Geliştirmede en iyisi `ham`. `tum_gecmis`e karşı fark −0,0009
  [−0,0023, +0,0005], anlamsız. Kural gereği **`tum_gecmis` seçildi**.
  Sınamada `tum_gecmis − ham` = −0,0000. Pratikte ikisi aynı.
- **"Son sezona göre düzelt" kuralları en kötüleri.** Geliştirmede sezon
  sapması −0,04 → +0,01..+0,05 diye yön değiştiriyor. Son sezonu izleyen
  kural bir sonraki yılı tahmin edemiyor, tepkiyi abartıyor.
- **Kayma bir eğilim değil, gürültü** (2019/20 COVID gibi tekil şoklar dahil).
  Geçmiş sezonlardan kestirilemiyor.
- **Asıl belirleyici, eğitim geçmişinin uzunluğu.** Modelin 1–4 sezonla
  eğitildiği geliştirme yıllarında sezon sapmaları ±0,04. 9–11 sezonla
  eğitildiği 2022–24'te ±0,005. Model ne kadar çok sezon görürse sezonlar
  arası şoklar o kadar ortalanıyor.

### 54.4 Ürüne yansıması

1. **API kalibratörü değişmiyor.** Kapsam Platt'ı "tüm geçmiş" ile kurulmaya
   devam ediyor (6.6). 2025 açıldığında 2022–24 ile yeniden kurulacak. Son
   sezona göre güncelleme yapılmayacak.
2. **API modeli yalnızca 2–3 sezonla eğitildi.** TM'nin 10 yılı bu kadar
   kısa geçmişte sezon düzeyinde **±4–6 puanlık, kestirilemeyen** sapma
   beklenmesi gerektiğini gösteriyor. Mevki sıralaması sayfasına eklendi:
   "%62 ile %58 arasındaki farka değil, listedeki yere güvenin."
3. §50.4'teki "düşük görünürlükte iyimserlik azalıyor" gözlemi üç sezona
   dayanıyor. Buradaki kanıt, bunun bir eğilim olarak okunmamasını, son
   sezona göre düzeltme yapılmamasını söylüyor.

Toplam **308 test**.


## 55. FAZ 7.4 — API Modeli vs TM Modeli, Aynı Oyuncular (1 Eki 2026)

`scripts/api_tm_karsilastir.py` · `reports/api_tm_karsilastirma_2022_2024.txt`

### 55.1 Soru ve kurulum

İzlenen liglerde API'nin oyun metrikleri (reyting, ikili mücadele, pas, top
kesme...) TM'nin bilmediği bir şey biliyor mu? Ücretli veriye geçme
kararının dayanağı bu.

- **Nüfus:** 2022–24, izlenen 9 lig, U23. İki tabloda da ≥450 dk olan
  **1.742** oyuncu-sezon (API'nin 2.349'undan; TM bağlantısı ve TM dakika
  filtresi). Kademe uyumu %100.
- **API:** `player_ranking`, kalibrasyon öncesi (2022/23 lig-dışı CV, 2024
  zaman-dışı). **TM:** ileri-zincir (§54).
- **Birleşik:** iki logitin ortalaması, **parametresiz**.
- Önceden yazılan okuma: birleşik − TM > 0 ise API, TM'nin üstüne bilgi katar.
- 2024 API tahminleri 6. kez kullanıldı; model seçimi yok.

### 55.2 Sonuç

| (lig içi AUC) | API | TM | Birleşik |
|---|---|---|---|
| tam (değer dahil) | 0,685 | **0,714** | 0,705 |
| saf (değersiz) | 0,674 | **0,716** | 0,709 |
| dakika+yaş | 0,644 | 0,648 | |
| piyasa | 0,664 | 0,667 | |

| Fark | Sonuç |
|---|---|
| **birleşik − TM** (ana okuma) | **−0,009** [−0,019, +0,001]: **API katkısı YOK** |
| API − TM | **−0,030*** [−0,046, −0,013] |
| API saf − TM saf | **−0,042*** [−0,066, −0,019] |

Sezon sezon API − TM: 2022 −0,029*, 2023 −0,011, 2024 −0,048*.
Mevki: **Defans −0,049*** (saf: **−0,090***), Orta saha −0,014, Forvet −0,020
(saf: +0,002). İnce mevkide API yalnızca 10 numara (0,811 / 0,781) ve sağ
kanatta (0,638 / 0,604) önde. n küçük, aralık yok.

### 55.3 Nasıl okunmalı — eşit bir yarış DEĞİL

1. **Eğitim verisi asimetrik.** TM modeli 9–11 sezon × 14 lig ile eğitildi.
   API modeli 2 sezon × 23 lig ile, çoğu düşük görünürlüklü havuzda. §54
   eğitim geçmişinin uzunluğunun belirleyici olduğunu gösterdi. Fark kısmen
   **veri kaynağından değil, geçmişin uzunluğundan** geliyor olabilir.
2. **Protokol farkı.** API 2022/23 lig-dışı (kendi ligini hiç görmemiş),
   TM ileri-zincir (aynı ligin önceki yıllarını görmüş). Ama 2024'te ikisi
   de zaman-dışı ve fark yine en büyük orada (−0,048*). Sonuç protokole
   bağlı görünmüyor.
3. **Ölçülen yalnızca izlenen ligler.** Düşük görünürlüklü liglerde TM verisi
   **yok**. Orada API tek kaynak ve 6.x'teki tüm bulgular (ucuz bantta
   11/12, eşleştirilmiş kontrolde +394 dk) geçerli.

### 55.4 Ne öğrendik

- **İzlenen liglerde API'nin olay sayımları TM'nin üstüne bilgi katmıyor.**
  İkisini birleştirmek yalnız TM'den iyi değil, hatta biraz geride.
- **Defansta fark en büyük** (saf −0,090). Bu, §52.6 ve §53.6 ile tutarlı:
  defans oyuncusunun **ne yaptığını** sayan metrikler (müdahale, top kesme)
  zayıf. **Ne kadar güvenildiğini** gösterenler (ilk 11 payı, tam maç,
  önceki sezon, takım gücü) güçlü. TM bunları zengin biçimde taşıyor.
- **Forvette** iki kaynak eşit (saf +0,002). Gol/asist her ikisinde de var.

### 55.5 Ücretli veri kararı için anlamı

Bu sonuç **"daha ayrıntılı olay sayımı satın al"** yönünde bir gerekçe
**vermiyor**. Ücretli API'nin aynı türden metrikleri (daha çok sezon dahil)
izlenen liglerde TM'den iyi olmayabilir. Değerli olabilecek iki şey:
1. **Düşük görünürlüklü liglerde daha fazla sezon.** Orada TM yok. §54'e
   göre geçmişin uzunluğu belirleyici ve API modelinin geçmişi yalnızca 2
   sezon. Ücretli planın asıl getirisi burada olur.
2. **API modeline TM tarzı "güven" özellikleri.** İlk 11 payı zaten var.
   Tam maç payı, önceki sezon dakika payı ve takım gücü eklenebilir. API
   oyuncu istatistiğinde yedek giriş/çıkış alanları var; takım gücü
   puan durumundan gelir (ek istek). **Uyarı:** API tarafında temiz sınav
   verisi kalmadı (2024 altı kez kullanıldı). Böyle bir değişiklik ancak
   2025 ileriye dönük defterle sınanabilir.


## 56. FAZ 7.5 — TM İleriye Dönük Defter: 2025/26 Havuzu (1 Eki 2026)

`src/scout/model/tm_defter.py` · `scripts/tm_defter.py` · `tm_iddia_defteri`
(DB) + **`data/defter/tm_iddia_defteri.csv` (git)** · `tests/test_tm_defter.py` (5)

### 56.1 Neden şimdi

API ücretsiz planı 2025'i açmıyor ve ne zaman açacağı bilinmiyor. TM ise
2025/26 sezonunu içeriyor ve TM modeli mühürlü testten geçti (§53). Sonuç
penceresi **2026-06-15 → 2027-06-15** açık. Bugün yazılan olasılık, sonucu
kimsenin bilmediği bir iddia. **Projenin ilk gerçek sicili.**

### 56.2 Kullanıcının isteğine göre: isim değil, havuz

Kullanıcı (1 Eki 2026): sistem tek bir isim vermesin; okyanustan bir havuz
çıkarsın, istatistikler liste üzerinden incelenebilsin, oyuncular takibe
alınabilsin. Güncel ayrıntılar Sofascore'da izlenecek. Bu yüzden deftere
2025/26'da izlenen 14 ligde ≥450 dk oynamış **tüm U23'ler (891)** yazıldı;
her biri lig × mevki ve mevki içindeki sırasıyla, kulübüyle ve güncel
kulübüyle. Arayüz (FAZ 8) havuzu buradan okuyacak.

### 56.3 Model ve kayıt

- Model `tam` (§53), 2013–2024'ün tamamıyla eğitildi (9.484 satır).
  **Kalibrasyon yok** (§54: 12 sezonla eğitilen modelde güncelleme kuralı
  ham'dan iyi değil).
- Aynı oyuncular için yalnız oyun verisi (`saf`), dakika+yaş ve piyasa
  olasılıkları da yazıldı; puanlamada karşılaştırma bunlarla.
- Sezon tamlığı doğrulandı: 14 ligde takım maç sayıları önceki yıllarla aynı.
- **Ekleme yalnız:** aynı (oyuncu, lig, sezon, model sürümü) ikinci kez
  yazılmıyor (sınandı). Model sürümü `tm_tam_v1`.

### 56.4 Değerleme boşluğu ve atılan ilk yazım (açık kayıt)

2025 havuzunun **%27'sinin (237) TM'de hiç değerlemesi yok.** Değerler
2026-02-27'de bitiyor ve bu oyuncuların büyük kısmı 2025'te yeni kulübüne
geçmiş: Wesley (Roma), Bonny (Inter), Alberto Costa (Porto), Baidoo (Lens).
Model bundan etkilenmiyor: değerleme göstergesinin katsayısı −0,005,
`tam` ile `saf` sıra korelasyonu 0,988.

**Ama "ucuz" tanımı etkilendi.** İlk yazımda API dönemindeki kural
(değersiz = düşük görünürlük = ucuz, §39.4) kullanıldı ve ucuz listesinin
tepesine Roma ve Inter oyuncuları çıktı. **İlk yazım (891 satır) dakikalar
içinde, commit edilmeden atıldı ve düzeltilmiş tanımla yeniden yazıldı.**
Sonuçlar 2027'ye kadar bilinemeyeceği için bu bir avantaj sağlamıyor.
Model olasılıkları değişmedi.

Yeni tanım: **ucuz = değerlemesi var ve ≤5M** (415 oyuncu). Değerlemesi
olmayanlar `deger_durumu = bilinmiyor` (237); ucuz da pahalı da sayılmıyor.

### 56.5 İleriye dönük hipotezler (sonuç bilinmeden yazıldı)

Puanlama yalnızca pencere kapandıktan sonra (2027-06-15+), yeni bir TM
anlık görüntüsüyle (`build_tm_tarih.py` ardından `tm_defter.py --puanla`).

| | Ölçüt | Beklenti (§53'e göre) |
|---|---|---|
| **P1** | model − dakika+yaş, lig içi AUC | > 0 (GA) |
| **P2** | model − piyasa | > 0 (GA) |
| P3 | kalibrasyon: ECE ve ortalama sapma | \|sapma\| ≤ 0,05 |
| P4 | ucuz bant, mevki top-20: model vs dakika+yaş | yön iddiası yok (§53 H5 tutmadı) |

Havuz özeti: 891 oyuncu · 14 lig · Orta saha 325, Forvet 277, Defans 256,
Kaleci 33 · ortalama olasılık 0,561.

### 56.6 Sınır

Bu sicil **yalnızca izlenen 14 ligi** kapsıyor. Projenin asıl hedefi olan
düşük görünürlüklü ligler için ileriye dönük sicil hâlâ API'nin 2025'i
açmasını bekliyor.


## 57. FAZ 8.0 — Laboratuvar Liderler: Metrik Aileleri (1 Eki 2026)

`app/_metrikler.py` (katalog) · `app/views/Laboratuvar.py` ·
`tests/test_laboratuvar_sayfasi.py` (11)

### 57.1 Kullanıcı isteği

"Lig lideri" ekranı beğenildi, ama bir metriğe bakarken **ilişkili
metrikler** de görünmeli: pas yüzdesine bakarken pas sayısı, pas sayısına
bakarken yüzde. Bir oran hacmi olmadan yanıltır: 3 ikilinin 3'ünü kazanmak
%100'dür.

### 57.2 Yapılan

- **Metrik kataloğu** (`app/_metrikler.py`): 8 aile (Pas ve oyun kurma, Gol
  ve şut, Çalım ve top taşıma, İkili mücadele, Savunma, Disiplin, Kaleci,
  Süre ve reyting), 46 metrik. Türkçe ad, biçim, yüzde ölçeği, "düşük olan
  iyi" bilgisi ve açıklama.
- **Liderler sekmesi:** kategori seçilir, sıralama metriği seçilir. Ailenin
  bütün metrikleri yan yana gelir, sıralanan metrik başta ▼ ile. Yön
  (faul/kart/yenen golde varsayılan "düşük önce"), mevki, sezon, lig, azami
  yaş, asgari dakika, oyuncu sayısı. Başka ailelerden ek sütun eklenebilir.
- Yaş 1 ondalık; mevki ve başlıklar Türkçe; ham kolon adı arayüze sızmıyor
  (testle korunuyor). Dağılım grafiği de aynı Türkçe adları kullanıyor.
  Önceki liste ~200 ham sütundu (`passes_p90_sh_agepct` gibi).

### 57.3 Bulunan veri tuzağı: API'nin "pass_accuracy" alanı YÜZDE DEĞİL

Kullanıcı ekranda pas yüzdesine baktığını düşünüyordu. Ölçüldü (PL 2022):

| Oyuncu | 90 dk'da pas | API "accuracy" |
|---|---|---|
| L. Dunk | 89,1 | 80 |
| Rúben Dias | 93,3 | 80 |
| W. Saliba | 69,4 | 62 |
| R. Varane | 51,7 | 41 |

Değer pas hacmini izliyor (korelasyon 0,66). Düzenli oynayanlarda kabaca
maç başına isabetli pas **sayısı**. Yedekten girenlerde tutarsız (R. Lewis:
maç başı 17 pas, değer 42). Sıralamanın tepesine çok pas atan stoperler
çıkıyordu. Ad artık "İsabetli pas/maç (API)", açıklamada ve sayfada "yüzde
değil" uyarısı var. **Gerçek pas isabeti yüzdesi ücretsiz veride yok**
(Sofascore'da var). Bu alan hiçbir modelde ya da rol şablonunda
kullanılmıyor; etkisi yalnızca bu ekrandı.

Toplam **324 test**.


## 58. FAZ 8.1 — Havuz Ekranı (1 Eki 2026)

`app/_havuz.py` (biçimlendirme + süzgeç, Streamlit'siz) ·
`app/views/Havuz.py` (sayfa, uygulamanın yeni giriş sayfası) ·
`app/views/Scout_Dosyasi.py` (`?pid=&lid=&sezon=` ile açılır) ·
`tests/test_havuz.py` (11)

### 58.1 Kullanıcı isteği

"Sistemin bana bir oyuncu ismi vermesini istemiyorum … okyanus içerisinde
bir havuz yaratmasını bekliyorum. İstatistikleri liste üzerinden
inceleyebildiğim …" Ayrıntılı güncel istatistik Sofascore'da izlenecek.

### 58.2 Yapılan

- **İki kaynak, tek ekran.** *2022–24 · geniş lig ağı* (API, 23 lig,
  düşük görünürlük dahil, 5.893 U23 oyuncu-sezon, dışarıdan tahmin) ve
  *2025/26 · Avrupa ligleri* (TM, 14 lig, 891 U23, §56 ileriye dönük
  defterdeki kayıt). İkisi ortak şemaya çevrilir (`api_hazirla`,
  `tm_hazirla`).
- **Havuz dilimi:** İlk %10 / %25 (varsayılan) / %50 / Hepsi.
- **Süzgeçler:** mevki, sezon, lig türü, lig, azami yaş, asgari dakika,
  fiyat tavanı (değeri bilinmeyen tavana takılmaz, ayrı kutucuk), isim
  arama (aksan ve Türkçe harf duyarsız: "ruben" → Rúben, "yildiz" →
  Yıldız).
- **İstatistik görünümü:** Liderler'deki aileler (API'de 8, TM'de 3: süre ve
  rol, üretim, takım katkısı), ek sütun eklenebilir. Sütun başlığından
  sıralanır. CSV indirilebilir.
- **Oyuncu kartı:** satıra tıklanınca açılır. Havuz puanı, model %,
  dakika, değer, **bugün nerede** (TM Temmuz 2026: kulüp + değer), 12 ay
  sonucu, yüzdelik profil (API: kendi lig+sezon+mevki havuzunda; TM: aynı
  mevkideki U23 havuzunda), "Scout dosyasında aç". `?oyuncu=<anahtar>` ile
  doğrudan açılır (8.2 takip listesi buradan dönecek).
- API ülke adları Türkçe (TM tarafıyla aynı dil).

### 58.3 Tasarım kararı: havuz puanı = GRUP İÇİ yüzdelik

Havuz puanı, model olasılığının oyuncunun kendi grubundaki yüzdeliğidir.
Grup: sezon × mevki × lig türü (TM'de sezon × mevki). Lig türü içinde
yüzdelik kalibrasyondan bağımsızdır (Platt monoton). Puan kullanıcı
süzgeçlerinden **önce** hesaplanır.

Neden olasılık değil: iki lig türünün taban oranı çok farklı (düşük
görünürlükte yer edinme %12, izlenende %59). Olasılıkla sıralanan bir
liste, kullanıcının asıl aradığı düşük görünürlüklü ligleri neredeyse
tamamen dışarıda bırakıyor. Karar ölçümden ÖNCE verildi. Aşağıdaki ölçüm
betimleyicidir; kuralı değiştirmedi.

| Sezon | Havuzda (ilk %25) | Düşük gör. payı: havuz | Aynı sayıda en yüksek olasılık | Bütün U23 |
|---|---|---|---|---|
| 2022 | 484 | %59,9 | %6,4 | %60,0 |
| 2023 | 476 | %57,8 | %3,2 | %57,8 |
| 2024 | 522 | %62,3 | %2,7 | %62,4 |

**Bedeli (dürüstlük için):** listenin tamamında 12 ayda yer edinme oranı
düşüyor: ilk %25'te havuz %49–53, olasılığa göre üst %70–71. Sebep
taban oranı farkı ve düşük görünürlükte sonucun kısmen görünmemesi ("iz
yok*"). Düşük görünürlüklü grubun **kendi içinde** havuz işini yapıyor:
ilk %25'te %29–37, ilk %10'da %39–46. Grubun tabanı %12, yani 2,5–4 kat.
Ekran bu yüzden iki sayıyı birlikte gösteriyor: sıralama havuz puanıyla,
seviye model %'siyle okunur.

**Held-out sayacı:** 2024'e 7. bakış. Yalnızca betimleyici: kompozisyon
ve oran. Model ya da kural seçimi yok.

### 58.4 Bulunan ve düzeltilen

- Kart profilinde katalogda olmayan iki metriğin (blocks_padj,
  duel_win_pct_sh) ham değeri "—" çıkıyordu. Ham sütunlar artık
  yükleniyor ve biçim taban metrikten alınıyor ("12 · %45"). Testle
  korunuyor.
- Uygulamanın giriş sayfası artık Havuz; Keşif ikinci sırada.

Toplam **335 test**.


## 59. FAZ 8.2 — Takip Listesi (1 Eki 2026)

`src/scout/takip.py` (depolama + append-only günlük) · `app/_takip_ui.py`
(ortak düğmeler) · `app/views/Takip.py` (yeni sayfa) · Havuz kartı ·
Hesap defteri "Senin seçimlerin" · `tests/test_takip.py` (13)

### 59.1 Kullanıcı isteği

"Oyuncuları takibe alabildiğim bir sistem istiyorum." Oyuncu Sofascore'da
izlenecek; bizim taraf listeyi, durumu ve notları tutar.

### 59.2 Yapılan

- **Kişi anahtarı = Transfermarkt kimliği** (`tm:<id>`; eşleşme yoksa
  `api:<id>`). API 2024 havuzundan eklenen oyuncu ile TM 2025/26
  havuzundaki aynı kişi **tek kayıt**. Takip sayfası iki havuz geçmişini
  birlikte gösteriyor (testle korunuyor).
- **Havuz kartı:** "Takibe al". Takipteyse durum (İzleniyor /
  İlgileniyorum / Öncelikli / Bıraktım), hızlı not, "Takip listesinde aç".
  Havuz tablosunda ★ sütunu.
- **Takip listesi sayfası:** bugünkü yaş, kulüp, değer (TM Temmuz 2026),
  ince mevki, son havuz puanı, eklerken model %, not sayısı ve son not.
  Satıra tıklanınca: durum, zaman damgalı not günlüğü, havuz geçmişi,
  "eklerken sistem ne diyordu", Havuzda aç / Scout dosyası, göz testi
  raporu (eski Shortlist formu buraya taşındı), listeden çıkar (onaylı).
  Liste ve notlar CSV olarak iniyor.
- **Eski "Shortlist & rapor" kaldırıldı.** `reports/shortlist.json` ve
  `scout_reports.json` hiç oluşmamıştı; taşınacak veri yoktu. Keşif ve
  Profil düğmeleri ("Takibe al"), Karşılaştırma'nın hazır listesi ve
  `scripts/defter.py` artık takip listesinden okuyor.

### 59.3 Defter bağlantısı: göz testi ancak sonuç bilinmiyorken sınanır

İki dosya var:
- `data/takip/takip.json`: güncel liste, atomik yazılır.
- `data/defter/takip_gunlugu.csv`: **append-only** olay günlüğü (ekle /
  durum / not / rapor / sil).

Her seçim, o andaki sistem iddiasını (model %, havuz puanı, değer) ve
`sonuc_gorunur` bayrağını taşır. Sonradan güncellenmez.

- **API 2022–24'ten seçim:** 12 aylık pencere kapalı ve sonuç Havuz'da
  ekranda. Bu seçim **göz testi sayılmaz**. Hesap defterinde "geriye
  dönük — döküm" kutusunda durur ve açıkça öyle yazılır.
- **TM 2025/26'dan seçim:** sonuç 15.06.2027'ye kadar bilinmiyor. Bu
  **gerçek sınav**. TM defteriyle aynı gün puanlanacak; sistemin aynı
  oyuncular için ne dediği de kayıtlı.

Neden: sonucu ekranda görürken "yer edindi" yazan oyuncuyu seçip sonra
"gözüm %100 tuttu" demek, defterin bütün disiplinini boşa çıkarır.
Silinen oyuncu günlükten silinmez: "bıraktım, sonra yıldızlaştı" da
öğretici bir kayıttır. Bu yüzden arayüz silmek yerine durumu "Bıraktım"
yapmayı öneriyor.

**Bekleyen iş (2027):** `tm_defter.py --puanla` çalıştığında takip
günlüğündeki ileriye dönük seçimler de aynı sonuçla puanlanacak (kullanıcı
ile sistem karşılaştırması). Puanlama kodu o zaman yazılacak; şu an
puanlanacak sonuç yok.

### 59.4 Bulunan ve düzeltilen

- **Seçim konumla saklanıyordu.** Süzgeç değişince aynı satır numarası
  başka oyuncunun kartını açardı. Tablo anahtarı artık satır kümesinin
  özetine bağlı; süzgeç değişince seçim sıfırlanıyor (Havuz ve Takip).
- **Bozuk takip dosyası** sessizce boş liste sayılmıyor. Sayılsaydı ilk
  kayıt kullanıcının listesini silerdi. Yüksek sesle duruyor (testli).
- "1 Eki 2026'den beri" → "Eklendi: 1 Eki 2026" (ek uyumu sayıya göre
  değişiyor).
- Testler ve tarayıcı denemesi `SCOUT_TAKIP_DIZIN` ile geçici dizinde
  çalıştı. Kullanıcının gerçek listesine hiç yazılmadı.

Toplam **348 test**.


## 60. FAZ 7.6 — Eşleşme Güveni Düzeltmesi: Sonuçlar Başka Kişinin Kariyerinden Ölçülüyordu (1 Eki 2026)

`src/scout/resolve/matcher.py` (`KABUL`, `kabul_disini_bosalt`) ·
`scripts/build_links.py` · `scripts/build_ranking.py` (`uretim_yukle`,
`guven_etiketi`) · `scripts/audit.py` (+2 kontrol) · Eşleşme kuyruğu ·
Mevki Sıralaması metinleri · `tests/test_matcher.py`, `tests/test_ranking.py`

### 60.1 Bulgu

8.3 için Transfermarkt profil bağlantısı denenirken görüldü: "T. Abed"
(Jong PSV) → *Abdul Fatawu*, "Diegão" → *Renato Veiga*, "K. Ruiz-Atil" →
*Dilane Bakwa*. `player_links` her API oyuncusu için **en iyi adayı**
`tm_id`'ye yazıyordu: C (belirsiz) ve D (reddedildi) dahil. §13.3 C'nin
"kullanılmıyor", D'nin "reddedildi" olduğunu söylüyor; `player_meta` buna
uyuyordu. Ama şu tüketiciler `tm_id` üzerinden bağlanıp güvene
**bakmıyordu**:

| Tüketici | Sonuç |
|---|---|
| `build_outcomes.py` | sonuç satırlarının **%26'sı** (9.723 / 36.881) başka kişinin kariyerinden |
| `train_model.py` (değer özelliği) | aynı satırlarda piyasa değeri başka kişinin |
| `build_sonra.py`, Scout dosyası, Havuz, Takip | "sonra", değer, "Şimdi", takip kimliği |

Model havuzunda (U23) 1.093 oyuncu-sezon; 1.027'si düşük görünürlükte
(grubun **%29'u**). İzlenen liglerde yalnız 66. Hata FAZ 1-6'nın ilk
sürümünden beri vardı. TM tarihi (§52–§56) etkilenmiyor; orada kimlik
TM'nin kendisi.

### 60.2 Düzeltme — yapısal

`tm_id` artık **yalnız kabul edilmiş** eşleşmede (A, B, manuel M) dolu.
Aday `aday_tm_id`'de; onu yalnız manuel onay kuyruğu kullanıyor. Filtreyi
her tüketiciye tek tek eklemek yerine kaynakta boşaltıldı: `tm_id`
üzerinden yapılan her JOIN kendiliğinden doğru oluyor, yeni kod aynı hatayı
yapamıyor. Denetime iki kontrol eklendi: kabul dışı eşleşmede `tm_id` boş;
hiçbir sonuç kabul dışı eşleşmeden ölçülmüyor. İkisi de geçiyor.

Zincir yeniden çalıştı (links → outcomes → sonra → üretim modeli → ranking
→ emsal). Model spesifikasyonu **değişmedi**; yalnız veri düzeldi
(`train_model.py --kaydet-yalniz`).

**Yan bulgu:** Ekvador 2023, 10 satırın altına düştüğü için lig-dışı CV
onu atladı. Boş kalan 6 satırı "üretim modeli" örneklem içi tahminle
doldurdu ve denetim bunu yakaladı. `uretim_yukle` artık yalnız sonuç
penceresi açık satırları alıyor. O 6 oyuncunun tahmini yok, havuzda da
yoklar.

Havuz: **5.893 → 4.794** oyuncu-sezon (düşük görünürlük 3.544 → 2.511).

### 60.3 Etki — aynı ölçüm, düzeltme öncesi / sonrası

Lig-içi AUC, dışarıdan tahmin. Fark sütunları eşli, oyuncu bazlı
bootstrap %95 GA.

| | Önce | Sonra |
|---|---|---|
| **2022–23 CV, hepsi** · model | 0,744 | **0,732** |
| model − dakika+yaş | +0,094* | +0,074* |
| saf (piyasasız) − piyasa | −0,032* | −0,013 [−0,04 , +0,02] |
| **2022–23 CV, düşük gör.** · model | 0,829 | **0,798** |
| model − dakika+yaş | +0,214* | +0,156* |
| **2022–23 CV, izlenen** · model | 0,718 | 0,715 |
| **2024, düşük gör.** · model | 0,742 | **0,688** |
| model − dakika+yaş | +0,102* | **+0,006 [−0,07 , +0,08]** |
| model − saf | +0,064* | −0,043 [−0,11 , +0,03] |
| saf − piyasa | −0,021 | **+0,111*** |
| **2024, izlenen** · model − dakika+yaş | +0,053* | +0,045* |
| Koşullu ECE, kalibre (CV / 2024) | 0,028 / 0,050 | 0,030 / 0,057 |

**Okuma:**
- İzlenen liglerde neredeyse hiçbir şey değişmedi.
- Düşük görünürlükte değer özelliğinin gücü kısmen **sahteydi**. Değer ve
  sonuç aynı yanlış kişiden geldiği için birbiriyle tutarlıydı. 2022–23'te
  model yine açıkça iyi. **En yeni sezonda (2024) düşük görünürlükte
  model, dakika+yaştan ayırt edilemiyor.** Piyasasız model piyasa
  modelini geçiyor.
- Birincil model önceden ilan edildiği gibi **tam model** kalıyor. 2024'e
  bakıp model değiştirmek, tutulan pencerede seçim olurdu. Sonuç ekranda
  söyleniyor (Mevki Sıralaması). Gerçek sınav ileriye dönük: API 2025
  açılırsa o sezon, yoksa TM defteri (yalnız izlenen ligler).

**Kalibrasyon:** karar kuralı (CV) yine **kapsam-koşullu Platt**'ı seçti.
Koşullu ECE: ham 0,086 → 0,030.

**Liste tepesi** (düşük görünürlük, sezon başına ilk 50, ham sıraya göre):

| | ham önce | ham sonra | kalibre önce | kalibre sonra |
|---|---|---|---|---|
| 2022 | +0,198 | +0,239 | +0,054 | +0,062 |
| 2023 | +0,083 | +0,100 | −0,069 | −0,085 |
| 2024 | +0,038 | **−0,037** | −0,122 | **−0,223** |

2024'te kalibre değer liste tepesinde ~22 puan kötümser; ham değer gerçeğe
daha yakın (§50.4'ün yönü aynı, büyüklüğü arttı).

**Mevki** (model − dakika+yaş): defans +0,106* → +0,087*, orta saha
+0,098* → +0,068*, **forvet +0,065* → +0,038 [−0,00 , +0,08]** (sınırda),
kaleci +0,004 → +0,003 (n 242 → 210).

**Fiyat bandı** (model − dakika+yaş, CV / kayan):

| Bant | Önce | Sonra |
|---|---|---|
| <0,5M | +0,082* / +0,158* | **+0,033 / +0,118*** |
| 0,5–2M, 2–5M | ≈0 / ≈0 | ≈0 / ≈0 |
| ≥5M | +0,063* / +0,100* | +0,056* / +0,094* |

En ucuz bantta *yalnız oyun verisi* (piyasasız) dakika+yaşın üstüne
bilgi katıyor: CV +0,063*, kayan +0,110*. Tam model katmıyor.

**Güven etiketi:** "iyi" için ölçüt, model − dakika+yaşın CV **ve**
kayanda anlamlı olmasıydı (§45.2). <0,5M artık CV'de anlamlı değil.
**Ölçüt aynı, veri düzeldi:** <0,5M "iyi"den "zayıf"a geçti. 2024
kullanılmadı. Dağılım: iyi 1.080 · zayıf 2.416 · doğrulanmamış 1.088 ·
düşük 210.

**API vs TM (§55):** sonuç değişmedi. API − TM −0,030* → −0,025*,
birleştirmek yine katkı vermiyor (−0,009). Rapor yeniden üretildi.

**Havuz (§58), ilk %25:**

| | Önce | Sonra |
|---|---|---|
| Havuzda (2022 / 2023 / 2024) | 484 / 476 / 522 | 414 / 384 / 409 |
| Düşük görünürlük payı | %58–62 | %50–54 (U23 tabanıyla aynı) |
| Olasılıkla seçilseydi düşük gör. payı | %3–6 | %0,2–4 |
| Yer edinme: havuz / olasılık-üst | %49–53 / %70–71 | %54–57 / %73–74 |
| Düşük gör. içinde: havuz / taban | %29–37 / %12 | %29–38 / %13–15 |

### 60.4 Geçersizleşen sayılar

Önceki API sonuçları (§38–§58) **silinmedi**; o günkü veriyle doğru
yazıldılar. Bu bölümle çeliştikleri yerde **§60 geçerlidir**. Özellikle
§45.1–45.2, §47.4, §50.2–50.4, §55 ve §58.3 tabloları. Hesap
defterindeki eski iddialar append-only kalıyor. Kabul dışı eşleşmeli
oyuncuların iddiaları artık sonuçsuz (sonuç ölçülemez).

**Held-out sayacı:** 2024'e **8. bakış**. Düzeltme öncesi/sonrası aynı
ölçüm, betimleyici. Model, kalibrasyon yöntemi ya da etiket ölçütü
2024'e göre seçilmedi.

### 60.5 Açık kalan

- Kabul dışı eşleşmeli 1.093 oyuncu-sezon havuzdan çıktı. Model onları
  değersiz oyuncu gibi tahmin edebilir. Sonucu ölçülemez ama "TM
  eşleşmesi yok" etiketiyle havuza geri alınabilirler (okyanus tamlığı).
  Ayrı bir adım; karar kullanıcıda.
- Manuel onay kuyruğunda 1.727 C kaydı var. Onaylandıkça kapsam artar.

Toplam **350 test**.


## 61. FAZ 8.3 — Sofascore ve Transfermarkt'a Tek Tık (1 Eki 2026)

`app/_havuz.py` (`sofascore_url`, `tm_url`) · `app/_takip_ui.py`
(`baglantilar`) · Havuz kartı · Takip detayı · Profil · testler (+4)

### 61.1 Yapılan

- **Sofascore:** Sofascore'un arama adresi **yok** (`/search?q=` → 404,
  denendi). DuckDuckGo `!ducky` ilk sonuca yönlendiriyor; `site:sofascore.com`
  ile sonuç Sofascore'a sınırlı. Sorgu: tam ad + kulüp.
- **Transfermarkt:** **yalnız kabul edilmiş eşleşmede** birebir profil
  (§60); değilse TM hızlı arama. "T. Abed" önce Abdul Fatawu'nun profiline
  gidecekti, şimdi "Tai Abed Kassus" araması.
- **Arama adı:** TM'deki tam ad > API ad+soyad > API kısa ad. Kısa ad
  ("T. Abed", "F. Esposito") aramayı bozuyor. Kulüp: bugünkü (TM) > o
  sezonki.
- Yerler: Havuz kartı, Takip listesi ayrıntısı, Profil (eski düz TM
  araması yerine).

### 61.2 Denendi — 9/9 doğru oyuncu sayfası

Pio Esposito (Inter), Kenan Yıldız (Juventus), **André Gomes** (FC
Alverca: aynı adlı ünlü orta saha varken doğru kişi, 2004 doğumlu kaleci;
kulübü Temmuz'dan sonra değişmiş olsa da), Vitor Reis, Sebastian Nanasi,
Eli Junior Kroupi, Élan Ricardo, Kelian Nsona, Oskar Siira Sivertsen.
Düşük görünürlüklü liglerden, havuzun tepesinden farklı liglerden seçildi.

**Sınır:** Bu bir arama motoru yönlendirmesi, kimlik eşleşmesi değil.
Örneklemdeki herkesin TM eşleşmesi doğrulanmıştı. Yalnız API adı olan
oyuncularda (eşleşmesiz) isabet denenmedi. Sofascore verisi çekilmiyor;
yalnız bağlantı veriliyor.

Toplam **353 test**.


## 62. FAZ 8.4 — Görsel Düzen: Daha Az Sayfa, Üstte Kararlar (1 Eki 2026)

### 62.1 Yapılan

- **13 sayfa → 11, üç grup.** *Scout* (Havuz → Takip listesi → Oyuncu →
  Karşılaştırma), *Analiz* (Keşif, Mevki sıralaması, Yükselenler, Kadro,
  Laboratuvar), *Sistem* (Hesap defteri, Veri). Menü tam açık: önceden
  "View 3 more" sayfaları gizliyordu (kullanıcının ekran görüntüsü).
- **Oyuncu** = eski *Oyuncu profili* + *Scout dosyası*. İkisi aynı
  oyuncu-sezona iki açıdan bakıyordu. Sekmeler: Scout dosyası · Profil ·
  Benzer oyuncular. Arama kutusu tüm oyuncu-sezonları kapsar;
  Havuz/Takip/Keşif `?pid=&lid=&sezon=` ile açar. Model iddiası olmayan
  oyuncu-sezonda (23 yaş üstü, eşleşmesiz) dosya sekmesi bunu söyler,
  diğer sekmeler çalışır.
- **Veri** = *Veri durumu* + *Eşleşme kuyruğu* (sekmeler; gövdeler
  `app/_veri_durumu.py`, `app/_eslesme.py`). "Bilinen eksikler" tablosu
  güncellendi: lig gücü ölçüldü ama uygulanmıyor, yaş eğrisi isteğe bağlı,
  yalnız doğrulanmış TM eşleşmesi (§60).
- **Kararlar sayfanın üstünde.** Keşif'te mevki + rol (kullanıcı "rol
  değiştiremiyorum" dedi: seçici çalışıyordu ama kenar çubuğunda 23 ligin
  altında kalıyordu). Mevki sıralaması filtreleri de üste alındı. Havuz
  ve Laboratuvar zaten böyleydi.
- **Ortak oyuncu başlığı** (`ui.oyuncu_basligi`): Havuz kartı, Takip
  ayrıntısı ve Oyuncu sayfası aynı ad + alt satır + rozet düzenini
  kullanıyor.

### 62.2 Bulunan ve düzeltilen

- Profil'deki TM bağlantısı `https://www.transfermarkt.com` önekini tam
  adresin önüne ekliyordu (bozuk bağlantı). Artık ortak bağlantı düğmeleri
  (§61) kullanılıyor.
- Profil'de mevki İngilizce görünüyordu ("Midfielder").

Testler: Scout dosyası testleri Oyuncu sayfasına taşındı (iddiası olmayan
oyuncu testi eklendi), Veri ve Keşif sayfa testleri. Toplam **353 test**.


## 63. FAZ 8.5 — Bakım (1 Eki 2026)

- `use_container_width=True` → `width="stretch"`: kalan **30 yer**
  (Streamlit 2025 sonu itibarıyla kaldırıyor). 8.1–8.4'te yazılan kod
  baştan yeni biçimdeydi. 11 sayfanın hepsi AppTest'te hatasız açılıyor,
  kullanımdan kaldırma uyarısı artık çıkmıyor.
- **ROADMAP §1–§2** güncel: tablo büyüklükleri, 75/75 lig-sezon, 353 test, 41
  denetim, "neye güvenebilirsin" tablosu (§60 sonrası sayılarla), mimari
  harita (model hattı, takip, havuz modülleri, 11 sayfa), günlük zincir
  sırası. Eski §1'deki 29 Ağustos denetimi §31'e işaret ediyor.
- **README:** denetim/test sayıları, script tablosu (model ve TM hattı).

FAZ 8 tamam: havuz (8.1), takip (8.2), Sofascore/TM geçişi (8.3), görsel
düzen (8.4), bakım (8.5). Arada FAZ 7.6 eşleşme düzeltmesi (§60).

Toplam **353 test**.


## 64. FAZ 8.6 — Google Stitch ile Tasarım Dili: "Saha Analitik" (2 Eki 2026)

`.streamlit/config.toml` (tema) · `app/_style.py` · `app/assets/logo*.svg` ·
`reports/tasarim/` (Stitch çıktıları, referans)

### 64.1 Süreç

Kullanıcı Google Stitch CLI'yi kurdu (0.11.0, kendi Google hesabı).
Stitch'te özel bir proje açıldı ("Scout - yetenek kesif") ve iki ekran
üretildi: **Havuz** ve **oyuncu kartı**. Stitch projeye bir de tasarım
sistemi kurdu: *Saha Analitik* — Linear'ın sakinliği + Sofascore'un veri
yoğunluğu, Inter + JetBrains Mono, renk yalnız durum bildirir.

**Öğrenilenler (CLI):**
- Uzun ve ayrıntılı istem ekran **üretmiyor**: `CLARIFICATION_REQUIRED`
  dönüyor, yalnız tasarım sistemi kuruluyor. Kısa ve odaklı istem
  çalışıyor.
- `stitch find screens` listesi boş dönüyor (CLI hatası). Ekran kimliği,
  görüntüsü ve HTML'i `generate` çıktısında var.
- Stitch istemde olmayan içerik uyduruyor: "Scout IQ", Opta, xG, fazladan
  oyuncular. **Yalnız görsel dil alındı**, içerik değil.

### 64.2 Uygulanan

- **Tema** (Streamlit'in kendi tema sistemi, CSS'ten sağlam): Inter +
  JetBrains Mono, birincil `#1D4ED8`, `#F8FAFC` zemin, 8px köşe, tablo
  başlığı `#F1F5F9`. **Lacivert gezinme paneli** `[theme.sidebar]`
  `#213145`; kenar çubuğundaki filtreler koyu zeminde okunur.
- **Logo** `st.logo` ile panelin en üstünde (önceden gezinmenin altına
  düşüyordu); panel daralınca yalnız "S".
- **KPI kutuları:** büyük mono değer, küçük büyük-harf mono etiket, 12px
  kart.
- **Rozetler:** mono, 5px köşe (Stitch "chip").
- **Oyuncu başlığı:** baş harf avatarı (FE, LY…).
- **Havuz kartı istatistik kutuları** (`ui.stat_kutulari`): `st.metric`
  dar sütunda değeri kesiyordu ("3.1…"). Havuz puanı ve model % altında
  ince doluluk çizgisi var.
- **Yüzdelik çubuk kademesi** (`ui.yuzdelik_renk`): <50 gri · 50–74 mavi ·
  ≥75 yeşil (Sofascore). Kırmızı-yeşil değil; değer her zaman yazılı (§10
  ilkesi korunuyor).

Testler: kart testi yeni kutulara göre güncellendi. Toplam **353 test**.
