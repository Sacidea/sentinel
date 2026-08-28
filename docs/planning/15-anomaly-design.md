# 15 — Anomali Tespit Tasarımı

Bu dosya "anomali nedir" sorusunu somut, kodlanabilir kurallara çevirir: baseline nasıl öğrenilir, hangi özellikler izlenir, Z-Score nasıl hesaplanır, warning/critical nasıl belirlenir. Anomali mantığı `domain/` katmanında saf/testedilebilir olarak yaşar (bkz. 03, 05).

## Genel Yaklaşım: İki Katman

1. **Katman 1 — Z-Score tabanlı (çekirdek, yorumlanabilir):** "Bu özellik, öğrenilmiş normalin kaç standart sapması uzağında?" Açıklanabilir: alarm çaldığında *neden* çaldığı nettir ("kurtosis, baseline'ın 5.2 sapması üstünde").
2. **Katman 2 — ML tabanlı (IsolationForest / PCA / River):** Z-Score tabanının üstüne eklenir; çok değişkenli/doğrusal olmayan örüntüleri yakalar. Katman 1 çalışmadan buna geçilmez.

Bu sıralama bilinçli: önce açıklanabilir taban, sonra ML zenginleştirmesi.

## Baseline (Normal Davranış Referansı)

**Strateji: Sabit başlangıç penceresi.**
- IMS testleri sağlıklı durumda başlar. Her `(machine_id, axis, metric)` için **ilk N snapshot** (varsayılan N=200, `.env`'de `BASELINE_WINDOW`) "normal" kabul edilir.
- Bu pencereden `mean` ve `std` hesaplanır ve `machine_baseline` tablosuna yazılıp **sabitlenir** (bir daha güncellenmez).
- Sonraki tüm snapshot'lar bu sabit baseline'a göre skorlanır.

**Neden sabit (kayan değil):** Veri run-to-failure — kayan pencere baseline'ı bozulan veriyle birlikte kaydırır, yavaş bozulmayı asla yakalayamaz ("baseline drift" / boiling frog). Kestirimci bakımın amacı tam da o yavaş bozulmayı görmek olduğu için baseline sabit kalmalı.

**Kritik doğrulama (spike + kalibrasyon, ADR-0006):**

- **Arıza çapanı (NASA, göz kararı değil):** Set 2 README: *“At the end of the test-to-failure experiment, outer race failure occurred in bearing 1.”* Incipient timestamp yok. Lead time son dosyaya göredir (index 983, `2004.02.19.06.22.39`; 10 dk aralık). RMS ~index 700 nitel gözlemdir; hesaba girmez. Ayrıntı: `ml/notebooks/ims_set2_spike.md`.
- **Sonuç:** `BASELINE_WINDOW=200` kirlenmiyor. 3.0/5.0 etiketlenmemiş `bearing_2`'de 13 erken alarm (index 351). **5.0/8.0** ile etiketsiz FP=0; bearing_1 lead **74.5 saat** (index 536→983). Tarama: `ml/notebooks/ims_set2_zscore_calibration.md`.
- **Sınır:** Eşikler yalnız Set 2'ye kalibre edildi. Set 1/3 veya başka dağılımda yeniden ölçülmeden kullanılmaz (overfitting).

**Soğuk başlangıç (cold start):** Baseline dolana kadar (ilk N snapshot) anomali skoru üretilmez; bu snapshot'lar yalnız baseline'ı beslemek için kullanılır. Event'lerde bu dönem `warming_up` olarak işaretlenebilir.

## İzlenen Özellikler

İki özellik **ayrı ayrı** izlenir (birleştirilmez):

| Özellik | Ne yakalar | Zamanlama |
|---|---|---|
| **Kurtosis** | Sinyaldeki ani darbeler (impulsiveness); yüzey çatlağı/pitting | **Erken** uyarı |
| **RMS** | Genel titreşim enerjisi/şiddeti | **Geç** ama kesin |

**Neden bu ikisi ve neden ayrı:** Farklı arıza evrelerini yakalarlar. Kurtosis erken çatlakta yükselir; ileri evrede bazen düşer (darbeler yüzeye yayılıp normalleşir) ama RMS yükselmeye devam eder. Biri diğerinin kör noktasını kapatır. Crest factor **skorlanmıyor** — RMS/kurtosis ile korelasyonlu, bağımsız sinyal katmıyor.

**Skorlama ≠ kayıt:** `domain/features.py` her pencere için dört özelliği de (RMS, kurtosis, crest factor, peak) çıkarır ve `VibrationFeatures` event'i hepsini taşır; `vibration_features` tablosuna yazılır. Z-Score yalnız yukarıdaki iki özelliğe uygulanır. Crest/peak kalibrasyon ve sonraki analiz (ML katmanı, 02) için saklanır.

**Kurtosis tanımı:** Pearson (dördüncü standartlaştırılmış moment) — normal dağılım için ≈ 3. Fisher/excess tanımı (normal = 0) kullanılmıyor; rulman izleme literatüründeki "sağlıklı ≈ 3, bozulmada yükselir" yorumu bu ölçeğe dayanıyor. Baseline zaten veriden öğrenildiği için eşikler ölçekten bağımsız, ama ham değerleri Grafana'da okurken bu tanım geçerli.

**Tanımsız durumlar:** Sessiz sensörde (RMS 0) crest factor, sabit sinyalde (std 0) kurtosis tanımsız; ikisi de sıfıra bölme yerine `0.0` döner — pipeline çökmez. NaN/inf içeren pencere ise özelliğe dönüşmez, hata fırlatır ve çağıran DLQ'ya yollar (bkz. 06, 07).

## Z-Score Hesabı

Her yeni snapshot'ın her özelliği için:
```
z = (value - baseline.mean) / baseline.std
```
- `baseline.std == 0` koruması: sıfıra bölme olmaz. Std sayısal olarak sıfırsa (≤ 1e-12) **o metrik atlanır** — epsilon eklenmez; aksi halde sabit sinyalde minik bir sapma sahte critical üretir.
- Std, baseline penceresinin **popülasyon** sapmasıdır (`ddof=0`): pencere "normal"in kendisi kabul edilir, örneklem tahmini değil.
- Z-Score **işaretli** tutulur ama eşik **mutlak değere** göre değerlendirilir (hem ani düşüş hem ani yükseliş anomali olabilir; özellikle kurtosis'in düşmesi ileri arıza işareti).

## Hareketli Ortalama (Gürültü Bastırma)

Tek bir snapshot'ın Z-Score'u gürültülü olabilir (anlık sıçrama). Yanlış pozitifi azaltmak için:
- Z-Score, son `MA_WINDOW` snapshot (varsayılan 5) üzerinde hareketli ortalamayla yumuşatılır.
- Alarm, **yumuşatılmış** Z-Score eşik aştığında çalar — tek bir gürültülü örnek tek başına alarm üretmez.
- MA penceresi dolmadan severity üretilmez (`warming_up` bittikten sonra da ilk `MA_WINDOW-1` skor `normal` kalır). Debounce (Telegram) ayrıdır ve application katmanındadır.
- Bu, "sürekli alarm veren sistem işe yaramaz" (05) ilkesinin somut önlemi.

## Warning / Critical Mantığı

| Seviye | Koşul (yumuşatılmış \|z\|) | Aksiyon |
|---|---|---|
| Normal | < `ZSCORE_WARNING` (5.0) | Sadece kaydet |
| **Warning** | ≥ 5.0 ve < `ZSCORE_CRITICAL` (8.0) | `anomaly.detected` + bildirim |
| **Critical** | ≥ 8.0 | `anomaly.detected` (critical) + bildirim |

- Eşikler `.env`'de (`ANOMALY_ZSCORE_WARNING/CRITICAL`). **IMS Set 2 kalibrasyonu 5.0/8.0** (ADR-0006); önceki 3.0/5.0 bu ölçekte etiketlenmemiş `bearing_2`'de yanlış pozitif üretti.
- Bu sayılar **yalnız Set 2** (984 dosya, bearing 1 dış bilezik, test sonu etiketi) üzerinde tarandı. Set 1, Set 3 veya başka bir makine/dağılım için aynı eşikler geçerli sayılmaz — overfitting riski; yeni sette `ims_set2_zscore_calibration.py` eşdeğeri yeniden çalıştırılmalıdır.
- **Herhangi bir** özellik (RMS *veya* kurtosis) eşiği aşarsa alarm çalar; `AnomalyDetected.metric` alanı hangisinin tetiklediğini belirtir.
- İki özellik aynı anda tetiklerse iki ayrı event yerine tek event'te en yüksek severity taşınır (event spam önleme).

## Alarm Gürültü Kontrolü (Debounce)

Bir rulman kritik bölgeye girince her snapshot alarm üretmemeli (Telegram spam).
- Aynı `(machine_id, axis, metric, severity)` için son bildirimden bu yana `ALARM_COOLDOWN` (varsayılan 60 sn playback zamanı) geçmeden yeni bildirim gönderilmez. Eksen seri kimliğinin parçasıdır; x ve y birbirini susturmaz.
- Kayıt (`anomaly_events`) yine de her tespitte yazılır; sadece *bildirim* debounce edilir. (Kayıt ≠ bildirim ayrımı.)

## Değerlendirme (05 ile bağlantılı)
- **Lead time (Set 2):** İlk warning ile NASA'nın duyurduğu arıza anı arasındaki süre. Duyuru testin sonudur; çapan son snapshot'tır (`02`: RUL etiketi = son dosya). Formül: `(n - 1 - ilk_warning_index) * 10 dk`. Index 700 kullanılmaz.
- **Yanlış pozitif (Set 2):** NASA'nın hasar duyurmadığı kanallarda (`bearing_2/3/4`), etiketli kanalın ilk uyarısından önceki alarmlar.
- Bu metrikler eşik/pencere kalibrasyonunu yönlendirir; başka sete taşınmaz (ADR-0006).

## Katman 2 — ML Entegrasyonu (özet, detay 02'de)
- `AnomalyDetector` port'u ardında IsolationForest / PCA (Hotelling T² + SPE) / River HalfSpaceTrees.
- Girdi: aynı dört özellik (RMS, kurtosis, crest, peak). FFT bantları henüz yok.
- Soğuk başlangıç Z-Score ile aynı `BASELINE_WINDOW`; **sonra freeze** (boiling frog — River da online güncellenmez).
- `anomaly_events.detector` alanı katmanı ayırt eder (`zscore` / `isolation_forest` / `pca` / `river`).
- Katman 1 ile 2 aynı snapshot'ta paralel çalışır; debounce anahtarına `detector` dahildir.
- **Kayıt ≠ bildirim:** `anomaly_events` tüm detector'ları yazar. Kafka/Telegram yalnız
  `zscore` ve `isolation_forest` (`NOTIFY_DETECTORS`). PCA (Set 2'de FP=3) ve River
  kayda gider, bildirime çıkmaz (ADR-0008).
- **Skor alanları (ADR-0009):** Z-Score `z_score` + `score_kind='zscore'`. IF
  `anomaly_score` + `if_score` veya `extent` (hangisi kazandıysa); `z_score` NULL.
  PCA `pca_t2`/`pca_spe`, River `river`. Event `schema_version=2`.
- Kapatma: `ML_LAYER_ENABLED=false`. Eşikler warmup eğitim skor niceliği (`ML_WARNING_QUANTILE=0.995`, `ML_CRITICAL_QUANTILE=0.999`; **yalnız Set 2 IF+zarf**, ADR-0008 — başka sette yeniden tarama). Isolation Forest ölçeklenmiş max-norm zarfı eğitim niceliğiyle (çarpan yok). FFT bantları yok (ADR-0007). Birim testler sentetik; Set 2 karnesi `ims_set2_ml_calibration.md`.

## Yeni Config Değişkenleri
```
BASELINE_WINDOW=200          # baseline için ilk kaç snapshot
MA_WINDOW=5                  # Z-Score hareketli ortalama penceresi
ALARM_COOLDOWN=60            # aynı alarm için bildirim debounce (sn, playback zamanı)
ANOMALY_ZSCORE_WARNING=5.0   # Set 2; ADR-0006 (3.0/5.0 elendi)
ANOMALY_ZSCORE_CRITICAL=8.0  # baska sete gecince yeniden olc
ML_LAYER_ENABLED=true        # IsolationForest + PCA + River
ML_WARNING_QUANTILE=0.995    # Set 2 IF (ADR-0008)
ML_CRITICAL_QUANTILE=0.999
```
