# İleriye Dönük Defter 2025/26 · Puanlama Planı (mühürlü)

**Yazıldığı tarih:** 30 Ekim 2026 · **Sonuç penceresi:** 2026-06-15 → 2027-06-15
**Durum:** sonuçlar **bilinmiyor**; bu belge sonuç gelmeden yazıldı ve commit edildi.
Puanlama bu belgeye göre, **bir kez** yapılır (GELISTIRME FAZ 9.2–9.3, FAZ 15).

---

## 1. Puanlanan şey

| | |
|---|---|
| Defter | `data/defter/tm_iddia_defteri.csv` (git), **891 satır** |
| Mühür | `data/defter/tm_2025_muhur.json`: SHA-256 `951378f8…c6c6`, kayıt commit'i `db45049` (1 Eki 2026) |
| Model | `tm_tam_v1` (PLAN §53, 2013–2024 ile eğitilmiş `tam`, kalibrasyon yok, §54) |
| Nüfus | 2025/26'da izlenen 14 ligde ≥ 450 lig dakikası olan U23'ler |
| Karşılaştırma olasılıkları | Aynı satırlarda kayıtlı `saf`, `basit` (dakika+yaş), `piyasa` |

**Kayıtlı tahminler puanlanır, yeniden hesaplanmaz.** Defter append-only'dir. Sonradan
yeni bir model ya da yeni bir veri sürümüyle aynı oyuncular için hesaplanan olasılıklar
bu puanlamaya **girmez**.

## 2. Sonuç tanımı (geliştirmedekiyle aynı, §52)

- **Olumlu (y = 1):** sonuç penceresinde (sezon bitişi 2026-06-15'ten sonraki 12 ay)
  izlenen 14 ligin herhangi birinde **≥ 900 lig dakikası** (kademe ≥ 3).
- İzlenen ligler `outcome.izlenen_ligler` ile veriden belirlenir (geliştirmede olduğu gibi).
- **Sansür:** yalnızca `pencere_tam` olan satırlar puanlanır. Pencere tamamlanmamış
  satır "olumsuz" sayılmaz.
- 14 lig dışına giden oyuncu, geliştirmedeki tanımla aynı biçimde **kademe 0**'dır
  ("izlenen bir seviyede yer edinmedi"; "başarısız" değil).

## 3. Hipotezler (PLAN §56.5'teki dört ölçüt; değiştirilmedi)

| | Ölçüt | Başarı | Not |
|---|---|---|---|
| **P1** | model − dakika+yaş, lig içi AUC farkı | %95 GA > 0 | §53 H1'in ileriye dönük tekrarı |
| **P2** | model − piyasa, lig içi AUC farkı | %95 GA > 0 | §53 H2'nin ileriye dönük tekrarı |
| P3 | kalibrasyon: ECE (10 eşit sayılı kova) ve ortalama sapma | \|sapma\| ≤ 0,05 | Bilgi amaçlı, §54'e göre kayma beklenir |
| P4 | ucuz bant (değerlemesi var, ≤ 5 M €), mevki top-20 isabeti: model vs dakika+yaş | yön iddiası yok | §53 H5 tutmamıştı |

**Ölçüm ayrıntısı (önceden sabit):**
- Lig içi AUC: lig-sezon içinde AUC, olumlu sayısıyla ağırlıklı (`ranker.lig_ici_auc`).
- Belirsizlik: oyuncu bazında eşli bootstrap, **B = 1000** (`ranker.esli_bootstrap`, `fark_ga`).
- Kaleciler P1–P3'e dahil, P4'ten hariç (geliştirmeyle aynı).

**Ek, betimleyici (hipotez değil):** lig, mevki ve yaş bandı kırılımları; ucuz /
bilinmiyor / pahalı bant ayrımı. Bunlardan "başarı" iddiası çıkarılmaz.

## 4. Bilinen koşul: tahminler eski piyasa değerleriyle yapıldı

Defter yazıldığında kullanılan Transfermarkt anlık görüntüsünde (2026-07-11) piyasa değerleri
**2026-02-27'de bitiyordu**. 5 Eylül sürümünde değerler 2026-06-12'ye kadar gidiyor; defterdeki
882 oyuncunun **761'inde** sezon sonu değeri farklı
(`reports/kaynak_karsilastirma_2026-07-11_2026-09-05.md`).

- Bu, **model** ve **piyasa** olasılıklarını aynı biçimde etkiler (ikisi de aynı eski değeri
  kullandı). P2 karşılaştırması bu yüzden simetriktir.
- `saf` (değersiz) ve `basit` olasılıkları etkilenmez.
- Değerleme hiç olmayan 237 oyuncu `deger_durumu = bilinmiyor`; P4'te ucuz sayılmaz (§56.4).
- Bu koşul puanlama raporunda açıkça yazılır. Tahminler "düzeltilmez".

## 5. Sonuç verisinin kaynağı ve yedek plan (FAZ 9.3)

Puanlama, sonuç penceresini **tamamen kapsayan** bir dakika kaynağı gerektirir
(2027-06-15'e kadar oynanan lig maçları).

| Durum | Ne yapılır |
|---|---|
| **A.** Transfermarkt açık veri seti güncellenmeye devam eder | Yeni anlık görüntü → `config/kaynaklar.yaml` → `build_tm_tarih.py` → `tm_defter.py --puanla`. Birincil yol |
| **B.** 1 Mart 2027'de TM veri seti hâlâ durmuş | Kullanıcıya seçenekler sunulur (aşağıda); seçim o tarihte PLAN.md'ye yazılır |
| **C.** Hiçbir kaynak pencereyi kapsamıyor | Puanlama **ertelenir**, kısmi veriyle "başarı" iddiası yapılmaz |

**B için seçenekler:**
1. Ücretli bir veri kaynağı, tek seferlik (ör. API-Football'un 2026 sezonu): 14 ligin tamamı.
   Kullanıcının ücretsiz kuralına istisna; karar kullanıcıda.
2. Resmi lig ve federasyon kaynakları (FAZ 11): yalnızca adaptörü yazılan ligler.

**Kısmi kapsam kuralı (önceden):** sonuç yalnızca bazı ligler için ölçülebiliyorsa:
- Puanlama yalnız o liglerdeki satırlarla yapılır.
- Kapsanan satır oranı raporlanır.
- P1/P2 sonucu **"kısmi"** etiketiyle yazılır, geliştirme testinin tekrarı sayılmaz.

Bir oyuncunun kapsanmayan bir lige gitmesi durumunda sonucu "bilinmiyor" sayılır,
kademe 0 sayılmaz.

**Kaynaklar arası eşdeğerlik şartı:** TM dışı bir kaynak kullanılırsa, önce 2025/26 sezonunun
(TM'de bilinen) dakikaları o kaynakla yeniden ölçülür. Oyuncu bazında kademe uyumu **≥ %97**
olmalı; altındaysa kaynak puanlama için kullanılmaz.

## 6. Prosedür

1. `docs/defter_2025_puanlama.md` ve `data/defter/tm_2025_muhur.json` bu commit'te.
2. Pencere kapanınca (2027-06-15 sonrası) kaynak seçimi (§5) → zincir → `audit.py` temiz.
3. `python scripts/tm_defter.py --puanla`:
   - defterin SHA-256'sını mühürle karşılaştırır, farklıysa **reddeder**;
   - pencere tam satır yoksa hiçbir şey yazmaz;
   - ilk puanlamada `data/defter/tm_2025_puanlama_acilis.json` yazar; dosya varken
     ikinci puanlamayı **reddeder**;
   - sonucu `reports/tm_defter_2025_puanlama.md`'ye yazar.
4. Sonuç ne çıkarsa çıksın PLAN.md'ye, ROADMAP'e ve portfolyo sitesine yazılır.

Bu kurallar `tests/test_defter_muhur.py` ile sınanır.
