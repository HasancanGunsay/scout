# Scout · Profesyonel Seviye Geliştirme Planı

**Tarih:** 30 Ekim 2026 · **Kapsam:** veri, lig genişlemesi, model, mühendislik, ürün
**Önceki sürüm:** [27 Temmuz 2026 denetimi](docs/arsiv/GELISTIRME_2026-07-27.md) (arşiv; maddelerinin
çoğu FAZ 1–8'de kapandı)

> Bu dosya **ne yapılacağını** söyler. Ne yapıldığı ve neden ROADMAP.md'de, ölçümler
> PLAN.md'de. Buradaki her faz kullanıcı onayıyla başlar. ROADMAP §5'te reddedilmiş
> fikirler burada **yeniden önerilmez**.

---

## 0. Özet: üç bulgu planı belirliyor

Bu plan yazılmadan önce sistemin gerçek durumu ölçüldü (30 Ekim 2026):

| # | Bulgu | Anlamı |
|---|---|---|
| **1** | **Transfermarkt veri setinin güncellemeleri durdu.** Bakımcının duyurusu: veri 6 Temmuz 2026'da kesiliyor, toplama hattı Temmuz ortasından beri çalışmıyor, yeniden başlama tarihi yok ([kaynak](https://github.com/dcaribou/transfermarkt-datasets)). | Sonuç ölçümü (kademe), piyasa değeri, sözleşmeler ve **891 tahminlik 2025/26 defterinin Haziran 2027 puanlaması** bu kaynağa dayanıyor. Tek kaynak riski. **P0.** |
| **2** | **API kotasının %98'i boşta.** Günlük zincir 2/100 istek harcıyor. Ücretsiz pencerede (2022–24) oyuncu istatistiği veren **55 lig** henüz alınmadı; aralarında **TFF 1. Lig**, Championship, 2. Bundesliga, Avusturya, İsviçre, Hırvatistan, Sırbistan, Polonya var. | Lig başına 3 sezon ≈ 156 istek (ölçüm: 3.806 oyuncu sayfası / 75 lig-sezon ≈ 51 + takım listesi). Ücretsiz ve hemen başlatılabilir. |
| **3** | **Düşük görünürlüklü liglerde güncel sezon verisi yok.** API ücretsiz katmanı 2025+'ı vermiyor; TM yalnız 14 birinci lig. | Bugün bir 1. Lig oyuncusunun bu sezonki dakikasını sistem bilemiyor. En büyük ürün açığı. Ücretsiz yol: resmi federasyon / lig siteleri (önce fizibilite). |

**"Profesyonel seviye"nin tanımı.** Beş ölçüt; her faz en az birine hizmet ediyor:

1. **Güncel veri:** hedef liglerde bu sezonun dakikası ve gol katkısı bilinir.
2. **Geniş kapsam:** Türk kulüplerinin gerçekten transfer yaptığı pazarlar kapsanır.
3. **Kanıtlanmış doğruluk:** ileriye dönük sınav önceden yazılmış kurallarla puanlanır.
4. **Sağlam işletim:** kaynak bozulunca sistem bunu fark eder ve söyler; build'ler yarım kalmaz.
5. **Karar desteği:** sistem "kim iyi" değil, "bu kulübün bu kısıtlarla kimi alması mantıklı" sorusunu yanıtlar.

---

## 1. Değişmeyen ilkeler

- **Ücretsiz veri varsayılan.** Ücretli seçenekler yalnızca açık bir **karar noktası** olarak
  maliyet-fayda tablosuyla sunulur (FAZ 11.3); onaysız eklenmez.
- **Kullanım koşullarına uyulur.** Sofascore, FotMob, FBref ve Transfermarkt sitesinden
  kazıma yapılmaz (ToS ve ROADMAP §5). Resmi federasyon sitelerinde önce koşullar okunur.
- **Test seti disiplini.** API 2024 tükendi (8 bakış), TM 2018–21 açıldı. Yeni model
  seçimleri yalnız geliştirme sezonlarında yapılır; gerçek sınav ileriye dönük defterdir.
- **Her değişiklik ölçülür, reddedilen yazılır.** PLAN.md'ye yeni bölüm; ROADMAP §5'e reddedilenler.
- **Faz faz onay.** Her fazın sonunda sonuç + "devam / dur" önerisi.

---

## 2. Yol haritası: genel bakış

| Faz | Başlık | Ölçüt | Öncelik | Efor | Maliyet |
|---|---|---|---|---|---|
| **9** | Veri dayanıklılığı ve kaynak katmanı | 3, 4 | **P0** | 1–1,5 hafta | 0 |
| **10** | Lig genişlemesi (ücretsiz API penceresi) | 2 | **P0** (arka planda) | ~5 hafta takvim, ~3 gün iş | 0 |
| **11** | Güncel sezon verisi (resmi kaynaklar) | 1 | P1 | 1–2 hafta + fizibilite | 0 (ücretli seçenek ayrı karar) |
| **12** | Model derinliği | 3, 5 | P1 | 2–3 hafta | 0 |
| **13** | Mühendislik ve işletim | 4 | P1 (paralel) | 1,5–2 hafta | 0 |
| **14** | Ürün: transfer planlama ve rapor | 5 | P2 | 2 hafta | 0 |
| **15** | İleriye dönük sınav (Haziran 2027) | 3 | takvime bağlı | 2–3 gün | 0 |

Önerilen takvim §9'da.

---

## 3. FAZ 9 · Veri dayanıklılığı ve kaynak katmanı (P0)

**Neden önce bu:** Bulgu 1. Sistem bugün tek bir dış veri setinin sürmesine güveniyor ve
o veri seti durdu. Bunu fark eden bir kontrol yoktu; 30 Ekim'deki elle yapılan inceleme yakaladı.

### 9.1 Kaynak tazelik denetimi · ✅ TAMAM (30 Eki 2026, PLAN §65)
- `audit.py`'ye her kaynak için tazelik kontrolü:
  - TM anlık görüntü yaşı. Örnek eşik: oyun sezonu içinde 21 günden eski ise uyarı.
  - Son maç tarihi ile bugün arasındaki fark.
  - API sezon erişimi: `probe_season_access.py` ayda bir otomatik çalışır, 2025 açılırsa haber verir.
- **Veri** sayfasında kaynak başına "son güncelleme · beklenen sıklık · durum" kartı.
- **Kabul:** TM duraklaması bugün çalıştırılınca kırmızı görünür; test ile güvenceye alınmış.

### 9.2 2025/26 defterinin puanlama planını şimdi mühürle · ✅ TAMAM (PLAN §65)
Puanlama Haziran 2027'de. Kuralları sonuç gelmeden yazmak, projenin en güçlü yanının devamı.
- `docs/defter_2025_puanlama.md`:
  - Hipotezler: model > dakika+yaş, model > piyasa, kalibrasyon ECE eşiği, mevki alt grupları.
  - Ölçüler, bootstrap ayarı.
  - **Hangi kaynaktan ölçüleceği ve kaynak yoksa ne yapılacağı** (9.3).
- Commit edilir. Puanlama betiği bu dosyanın commit kimliğini rapora yazar.
- **Kabul:** dosya commit'li; betik sahte veriyle uçtan uca çalışıyor (test).

### 9.3 Sonuç kaynağı için yedek plan · ✅ PLAN YAZILDI (karar 1 Mart 2027)
TM devam etmezse 2025/26 sonuçlarını (2026/27 dakikaları) ölçecek yol gerekir. Seçenekler,
dürüst değerlendirmeyle:

| Seçenek | Ücret | Kapsam | Sorun |
|---|---|---|---|
| TM veri seti geri gelir | 0 | tam | Kontrolümüzde değil. **Mart 2027'ye kadar bekle, ayda bir kontrol (9.1)** |
| API-Football, 2026 sezonu (ücretli 1 ay) | ücretli | 14 ligin hepsi | Kural gereği karar noktası; tek seferlik maliyet |
| Resmi lig siteleri (FAZ 11 adaptörleri) | 0 | lig lig | 14 ligin her biri ayrı iş; yalnız birkaç lig gerçekçi |
| dcaribou hattını kendimiz çalıştırmak | 0 | tam | **Transfermarkt sitesini kazımak demek.** ToS ve ROADMAP §5 nedeniyle **önerilmez** |

- **Karar tarihi:** 1 Mart 2027. O gün TM hâlâ duruyorsa kullanıcıya seçenek sunulur.
- **Kabul:** karar kuralı 9.2 dosyasında yazılı.

### 9.4 Kaynak katmanı (adaptörler) ve kişi kaydı · ✅ TAMAM (30 Eki 2026, PLAN §66)
Bugün API ve TM, özellik ve sonuç kodunun içine gömülü. Yeni lig ya da kaynak eklemek her
seferinde çekirdeğe dokunmayı gerektiriyor.
- `src/scout/sources/`: her kaynak aynı sözleşmeyi uygular.
  - Tablolar: `oyuncu_sezon`, `mac_katilim` (maç bazında dakika/gol/kart), `deger`, `sozlesme`.
  - Her satırda `kaynak`, `kaynak_surum`, `cekilme_tarihi` alanları.
- **Kişi kaydı (`kisi`):** her kaynağın oyuncu kimliği tek bir kişiye bağlanır. Bugünkü
  `player_links` API↔TM ikilisinin N kaynağa genellemesi. KABUL kuralı (§60) aynen korunur:
  yalnız A/B/manuel eşleşme kişiye bağlanır.
- **Kabul:**
  - Mevcut sonuçlar birebir aynı (`player_ranking` parmak izi değişmez).
  - 353 test geçer.
  - Yeni kaynak eklemek tek bir adaptör dosyası + eşleştirme kuralı ile mümkün.

### 9.5 Atomik build ve build kaydı · ✅ TAMAM (PLAN §65)
Eski P1-2 hâlâ açık: zincir yarıda kalırsa tablolar karışık sürümde kalır.
- Zincir yeni bir DuckDB dosyasına yazar; denetim geçerse eskisinin yerine **taşınır**
  (atomik değiştirme). Geçmezse eski veritabanı yerinde kalır, arayüz eskiyi gösterir.
- `build_kaydi` tablosu: build kimliği, başlangıç ve bitiş, adım süreleri, kaynak sürümleri,
  denetim sonucu. Arayüz "veri şu build'den" bilgisini gösterir.
- **Kabul:** zincirin ortasında hata simüle edilince arayüz tutarlı eski veriyi gösteriyor.

---

## 4. FAZ 10 · Lig genişlemesi: ücretsiz API penceresi (P0, arka planda)

**Neden:** Bulgu 2. Kota boşta ve Türk kulüplerinin oyuncu aldığı pazarların çoğu kapsam dışında.
Veri 2022–24'e ait, yani güncel scouting için değil, şunlar için değerli:
- **Taban oranları:** örneğin "1. Lig'den Süper Lig'e kaç oyuncu sıçrıyor?"
- **Modelin daha çok ligle eğitilmesi:** §54'e göre eğitim geçmişinin genişliği belirleyici.
- **Lig gücü köprüleri** (12.2).

**Maliyet hesabı:** lig-sezon başına ≈ 52 istek. Günde ≈ 95 boş istek ile günde ≈ 1,8 lig-sezon.

### Dalga 1 · Türkiye bağlamı ve Türk kulüplerine oyuncu akışı olan pazarlar

| Lig (API id) | Sezon | Neden |
|---|---|---|
| **TFF 1. Lig (204)** | 2022–24 | Kullanıcının asıl bağlamı; 1. Lig → Süper Lig taban oranı |
| Avusturya Bundesliga (218) | 2022–24 | Genç ve ucuz oyuncu ihracı yüksek |
| İsviçre Super League (207) | 2022–24 | Aynı |
| Hırvatistan HNL (210) | 2022–24 | Balkan pazarı |
| Sırbistan Super Liga (286) | 2022–24 | Balkan pazarı |
| Polonya Ekstraklasa (106) | 2022–24 | Orta Avrupa |
| Romanya Liga I (283) | 2022–24 | Orta Avrupa |

21 lig-sezon ≈ 1.100 istek ≈ **12 gün** (otomatik, arka planda).

### Dalga 2 · Avrupa ikinci ligleri
Championship (40), 2. Bundesliga (79), Segunda División (141), Avusturya 2. Liga (219).
12 lig-sezon ≈ **7 gün**.

### Dalga 3 · Uzak pazarlar (değer/maliyet en yüksek, görünürlük en düşük)
MLS (253), J1 (98), Şili (265), Peru (281), Uruguay (268), Mısır (233), Fas (200),
Güney Afrika (288). Sezon kapsamı lig lig farklı (`coverage_api_all.csv`). ≈ **10 gün**.

**Bilerek dışarıda:**
- **TM'nin zaten izlediği birinci ligler** (Süper Lig, Yunanistan, İskoçya, Rusya, Ukrayna):
  §55'e göre izlenen liglerde API olay verisi TM'nin üstüne bilgi katmıyor. Süper Lig yalnız
  köprü ölçümü için gerekirse alınır.
- **Kadın ligleri:** ürün kapsamı dışında.

### Her dalga için kabul kriterleri
1. Lig-sezonlar tam (`league_complete`); denetim temiz; kohortsuz oyuncu yok.
2. Mevki etiketleri ve null davranışı yeni liglerde kontrol edildi (ROADMAP §8 tuzakları).
3. Lig başına **taban oran** raporu (kaç oyuncu izlenen bir lige sıçradı).
4. Model, **önceden yazılmış kuralla** genişletilmiş veriyle yeniden değerlendirildi
   (yalnız lig-dışı CV; 2024'e bakılmaz). Kural: yeni ligler eklendikten sonra eski liglerdeki
   CV AUC'si anlamlı düşmüyorsa genişletilmiş model üretime alınır.

---

## 5. FAZ 11 · Güncel sezon verisi: resmi kaynaklar (P1)

**Neden:** Bulgu 3. Ekim 2026'daki kulüp transfer çalışmasında bir 1. Lig oyuncusunun bu sezonki dakikası elle
aranmak zorunda kalındı. Profesyonel bir sistemde bu otomatik gelir.

### 11.1 TFF adaptörü: fizibilite (önce bu, kod sonra)
TFF'nin sitesindeki maç sayfaları resmi maç raporlarını yayımlıyor: kadrolar, oyuncu
değişiklikleri ve dakikaları, goller, kartlar. Süper Lig, 1. Lig ve 2. Lig kapsanıyor.
- **Kontrol listesi:**
  - Kullanım koşulları (robots.txt yok, 30 Ekim'de 404).
  - Sayfa yapısının sezonlar boyunca kararlılığı.
  - Kimlik yapısı (oyuncu ve maç kimlikleri).
  - Bir maçtan dakika çıkarmanın doğruluğu (elle 10 maçla karşılaştır).
- **Kibar erişim:** düşük hız, önbellek, yalnız gerekli sayfalar.
- **Geçme kriteri:** 10 maçın 10'unda dakika ve olaylar elle sayılanla aynı; koşullar engel değil.
  Geçmezse: dur, bulguyu yaz.

### 11.2 TFF adaptörü: uygulama
- `sources/tff.py` → `mac_katilim` tablosuna, TM `appearances` ile aynı şemada.
- Kişi kaydına bağlama (9.4). TFF oyuncu kimliği, ad + doğum tarihi + kulüp ile mevcut kişilere eşleşir.
- Günlük zincire eklenir (yalnız yeni maçlar).
- **Kabul:**
  - Bu sezonun 1. Lig maçları sistemde.
  - Havuz ve oyuncu kartında "bu sezon" sütunu.
  - Kulüp çalışmasında elle doğrulanan dakikalarla örnek kontrol tutuyor.

### 11.3 Karar noktası: ücretli API (varsayılan değil)
Ücretsiz kuralı bilinçli bir karar; bu tablo yalnız kararın bilgiyle verilmesi için.

| | Ücretsiz yol (FAZ 11.1–11.2) | API ücretli plan |
|---|---|---|
| Güncel sezon | Yalnız adaptör yazılan ligler (TFF) | Tüm hedef ligler, aynı şema |
| Metrik derinliği | Dakika, gol, kart, değişiklik | + pas, ikili mücadele, rating, şut |
| Bakım | Site yapısı değişirse kırılır | Düşük |
| 9.3 yedek sonuç kaynağı | Kısmi | Tam |
| Maliyet | 0 | Aylık abonelik (güncel fiyat kontrol edilmeli) |

Öneri: önce 11.1–11.2. Ücretli plan, 9.3 karar tarihinde (1 Mart 2027) yedek sonuç kaynağı
gerekirse tek aylık olarak değerlendirilir.

### 11.4 Başka ligler için aynı desen (opsiyonel)
Öncelikli pazarlarda resmi lig ya da federasyon sitesi benzer maç raporu veriyorsa aynı
adaptör deseni uygulanır. Her lig ayrı fizibilite (11.1 kontrol listesi). Sıra Dalga 1 listesine göre.

---

## 6. FAZ 12 · Model derinliği (P1)

Her madde aynı protokolle değerlendirilir: geliştirme sezonlarında lig-dışı + kayan
doğrulama, **önceden yazılmış kabul kuralı**, sonra ileriye dönük defter. Kabul edilen her
değişiklik yeni bir `model_surumu` alır. Eski defter kayıtları değişmez (append-only).

### 12.1 Takım gücü: Elo
Bugün takım gücü sezon puan ortalaması (`takim_ppg`): gecikmeli ve ligler arası
karşılaştırılamaz.
- TM `games` (2012–26) ve API fikstürlerinden **kendi Elo hesabımız**. Ligler arası bağı
  Avrupa kupası maçları kurar.
- ClubElo (ücretsiz servis) çapraz kontrol için. **Not:** 30 Ekim'de 502 hatası veriyordu.
- **Kabul:** Elo özelliği, TM modelinde `takim_ppg`'nin yerine konduğunda geliştirme CV'sinde
  AUC farkı ≥ 0 ve GA sıfırı dışlamıyorsa bile **yorumlanabilirlik** için tutulabilir. Kural
  önceden yazılacak: "zarar vermiyorsa ve ligler arası karşılaştırma sağlıyorsa kabul".

### 12.2 Lig gücü: köprü oyuncular, genişletilmiş liglerle
`league_strength.py` köprü oyuncu yöntemi doğru yöntem (lig içi ortalamalar yapısal olarak sabit).
FAZ 10 ile köprü sayısı artacak.
- **Kullanım alanı (ROADMAP §4 kararı korunur: skora uygulanmaz):**
  - Arayüzde "bu ligde 0,30 G+A/90 ≈ şu ligde ~X" çevirisi.
  - Transfer planlamada (FAZ 14) lig farkı uyarısı.
- **Kabul:** köprü sayısı lig çifti başına ≥ 30 olmayan çiftlerde katsayı gösterilmez.

### 12.3 Çoklu ufuk ve sonuç tanımları
- **24 ay ufku:** geç patlayan oyuncular.
- **"Daha güçlü lige sıçradı mı":** 12.1 ve 12.2 ile lig gücü farkı.
- **Süre modeli** (survival): "ne zaman" sorusu.
- Birincil sonuç **değişmez** (kademe ≥ 3, 12 ay). Bunlar ek göstergelerdir; ileriye dönük
  defterin hipotezleri birincil sonuca göre yazılmıştır.

### 12.4 Oyuncu bazında belirsizlik
Arayüz bugün nokta olasılık gösteriyor. Bootstrap ile oyuncu bazında aralık gösterilir:
"%62 [%54, %69]". §54'e uygun olarak sıralamadaki yerin aralığı da verilir.

### 12.5 Kaleciler
Model kalecide dakika+yaştan ayırt edilemiyor (+0,003). Kaleci olasılığı arayüzde
"bilgi taşımıyor" etiketiyle gösterilir ya da hiç gösterilmez. Ayrı model ancak yeni veriyle denenir.

### 12.6 Mevki bazlı kalibrasyon kontrolü
Mevki × lig türü hücrelerinde ECE raporu. Kötü hücreler arayüzde işaretlenir.
Kalibratör yalnız önceden yazılan kural sağlanırsa bölünür (§50 ve §54 dersi: fazla parametre kaymayı kovalar).

---

## 7. FAZ 13 · Mühendislik ve işletim (P1, diğer fazlara paralel)

### 13.1 Paketleme ve komut satırı
- `pyproject.toml` + `uv.lock` (bağımlılıklar sabit sürümle).
- `scout` komutu (ör. Typer):
  - `scout zincir` (günlük zincir), `scout denetim`, `scout plan` (kota/ETA),
  - `scout rapor <oyuncu>`, `scout defter puanla`.
- `daily_run.ps1` yalnızca `scout zincir` çağırır; mantık Python'da.

### 13.2 Herkese açık repoda CI
Bugün 37 test dosyasının 11'i yerel veritabanına bağlı; GitHub'da çalışmaz.
- Küçük, sentetik bir **fikstür veritabanı** (`tests/fixtures/`, birkaç yüz satır, gerçek
  veri içermez, lisans sorunu yok).
- Gerçek veri isteyen testler `@pytest.mark.veri` ile işaretlenir; CI onları atlar, yerelde koşar.
- GitHub Actions: ruff + pytest (fikstürle), her push'ta.
- **Kabul:** repo sayfasında yeşil CI rozeti; yerelde 353+ test.

### 13.3 Veri sözleşmeleri
- Kaynak ve ana tablolar için şema doğrulama (ör. pandera): tip, aralık, benzersizlik, null oranı.
- Denetim kontrollerinin bir kısmı sözleşmeye taşınır. Hata mesajı hangi kaynağın hangi
  alanının bozulduğunu söyler.

### 13.4 Zincir orkestrasyonu
- Python içinde basit bir adım grafiği: bağımlılıklar, yeniden deneme, adım süresi, kaldığı yerden devam.
- Ağır bir orkestratör (Airflow, Dagster) **gerekmiyor**: tek makine, günde bir çalışma.
  Yük gerekçesi doğarsa yeniden değerlendirilir.

### 13.5 Model kaydı
- Her eğitim: model dosyası + `meta.json` (özellik listesi, eğitim sezonları, veri parmak izi,
  CV sonuçları, kod commit'i) + otomatik değerlendirme raporu (`reports/model/<surum>.md`).
- Üretimdeki sürüm tek yerden okunur; arayüz ve defter sürümü gösterir.

### 13.6 Performans
- `load_features()` tüm tabloyu çekiyor (eski borç). FAZ 10 ile satır sayısı ~2 katına çıkacak.
- Sayfa başına sütun seçimi ve arayüz için hazır görünümler (`ui_*` tabloları build sonunda).
- **Kabul:** en ağır sayfa < 2 sn açılıyor (ölçülür).

### 13.7 Veri lisansları belgesi
`DATA_LICENSES.md`:
- API-Football: yeniden dağıtım yok; ham veri repoda değil.
- Transfermarkt veri seti: CC0.
- TFF: adaptör yazılırsa koşulların özeti.
- Repoya giren türetilmiş dosyaların (defterler) gerekçesi.

### 13.8 Teknik borç (eski listeden açık kalanlar)
- `scripts/` içindeki probe ve explore betikleri → `scripts/arsiv/`.
- Radar metrik listesi Profil ve Karşılaştırma'da iki kez tanımlı → ortak modül.
- GIL çökmesi (eski P1-3): tekrar ederse `faulthandler` çıktısı saklanır.
- Kod ve tanımlayıcılar Türkçe-ASCII kalır. Toplu İngilizceleştirme fayda/maliyet olarak
  **yapılmaz**; herkese açık giriş için İngilizce README yeterli.

---

## 8. FAZ 14 · Ürün: transfer planlama ve rapor (P2)

Kulüp transfer çalışması (Ekim 2026, isimsiz; ayrıntısı git dışında) sistemin asıl değerinin **kısıtlar altında karar** olduğunu
gösterdi. O iş elle ve sistemin dışında yapıldı; bu faz onu sisteme taşır. Belirli bir kulübe
özel değil, **kulüp profili** ile genel.

### 14.1 Kulüp profili
`config/kulupler/<kulup>.yaml`:
- Lig ve yabancı kontenjan kuralları (toplam, yaş şartlı kontenjan, sezona göre değişim).
- Harcama limiti.
- Mevcut kadro (yaş, mevki, sözleşme bitişi, uyruk).
- Hedef pencereler.

**Lig kuralları ayrı dosyada** (`config/lig_kurallari.yaml`, sezon bazlı); TFF 1. Lig ve
Süper Lig ile başlar.

### 14.2 Kadro ihtiyaç analizi
- Mevki başına yaş profili, sözleşme bitişleri, dakika dağılımı (11.2 verisiyle güncel).
- "İlk 11'de 33+ yaşında iki stoper", "tek kaynaktan gol" gibi otomatik bulgular.
- Kullanıcı ihtiyaç listesini onaylar ya da düzeltir.

### 14.3 Aday süzgeci ve kontenjan hesabı
- Havuzdan mevki, bütçe ve sözleşme bitişine göre adaylar.
- Her aday için hangi kontenjan yerini kullanacağı (yerli, yabancı, genç yabancı).
- Paket hesabı: seçilen adaylarla kontenjan ve bütçe tutuyor mu?

### 14.4 Durum doğrulama listesi
Veri gecikmeli olduğundan her aday için "son kontrol" alanı: kulüp, sözleşme, kaynak bağlantısı,
kontrol tarihi. Kulüp çalışmasında 47 adaydan 19'u bu adımda elendi; adım ürünün parçası olmalı.

### 14.5 Rapor üreticisi uygulamada
Kulüp çalışmasının rapor betikleri (git dışında) genelleştirilir:
- Oyuncu raporu ve genel rapor tek tıkla.
- Markdown ve PDF dışa aktarma.
- İzleme formu (teknik / taktik / fizik / mental) uygulamada doldurulur ve takip kaydına yazılır.

### 14.6 Göz testi geri bildirim döngüsü
- Yapılandırılmış izleme raporları birikir.
- ≥ 30 rapordan sonra: sistemin olasılığı ile göz testi notu ne kadar örtüşüyor, nerede ayrışıyor?
- Bu, eski P3 "kişisel tercih modeli"nin ölçülebilir ilk adımı.

### 14.7 Uyarılar
- Takip listesinde sözleşmesi 6 ay içinde bitenler.
- Son 4 haftada dakikası sıçrayanlar (11.2 verisiyle).
- Kaynak tazelik uyarıları (9.1).

**Bilerek yapılmayacak:** herkese açık çok kullanıcılı yayın. API-Football verisi yeniden
dağıtılamaz; uygulama yerel ya da özel kalır. Portfolyo sitesi yalnız yöntem ve sonuç gösterir.

---

## 9. FAZ 15 · İleriye dönük sınav (Haziran 2027)

- 15 Haziran 2027 sonrasında 9.2'deki mühürlü planla **bir kez** puanlama.
- Sonuç ne çıkarsa çıksın PLAN.md'ye, ROADMAP'e ve portfolyo sitesine yazılır.
- Takip listesindeki "sonuç görünmezken yapılan" seçimler de aynı gün puanlanır (§59).

---

## 10. Önerilen takvim

| Hafta | İş (paralel) | Arka planda |
|---|---|---|
| 1 | 9.1 tazelik denetimi · 9.2 defter puanlama planı (commit) · 13.1 paketleme | **10 Dalga 1 başlar** (TFF 1. Lig önce) |
| 2 | 9.4 kaynak katmanı · 9.5 atomik build | Dalga 1 sürer |
| 3 | 13.2 CI + fikstür DB · 13.3 veri sözleşmeleri | Dalga 1 biter → kabul raporu |
| 4 | 11.1 TFF fizibilite → karar | Dalga 2 |
| 5–6 | 11.2 TFF adaptörü (fizibilite geçerse) · 12.1 Elo | Dalga 2 biter, Dalga 3 |
| 7–8 | 12.2 lig gücü · 12.4 belirsizlik · 13.5 model kaydı | Dalga 3 |
| 9–10 | 14.1–14.4 transfer planlama | — |
| 11–12 | 14.5–14.7 rapor ve uyarılar · 13.6 performans | — |
| 1 Mart 2027 | **9.3 karar noktası:** TM hâlâ duruyorsa sonuç kaynağı seçimi | — |
| Haziran 2027 | **FAZ 15** ileriye dönük sınav | — |

Takvim tahmindir; her fazın sonunda kullanıcı onayıyla yeniden bakılır.

---

## 11. Bu planın reddettikleri

| Fikir | Neden reddedildi |
|---|---|
| Sofascore / FotMob / FBref / Transfermarkt sitesi kazıma | Kullanım koşulları; FBref ayrıca teknik olarak denendi ve başarısız (ROADMAP §5) |
| Derin öğrenme / büyük topluluk modelleri | n küçük; §53–§55'te sinyalin kaynağı basit "güven" özellikleri |
| xG modeli | Şut konumu verisi yok. StatsBomb açık verisiyle model eğitilebilir ama bizim oyunculara uygulanamaz |
| Serbest rol kümeleme | Mekânsal veri olmadan ayrık rol yapısı yok (ROADMAP §5) |
| Lig gücünü skora uygulamak | Geriye dönük testte sonucu kötüleştirdi (§23); yalnız bağlam olarak (12.2) |
| Yeni sayfa eklemek | 11 sayfa yeterli; yeni işlevler mevcut sayfalara (Havuz, Takip, Oyuncu) eklenir; transfer planlama tek yeni sayfa |
| Maç görüntüsü analizi | Ayrı proje (MacAnaliz); Scout'a ancak olgunlaşınca çıktı dosyasıyla bağlanır |
