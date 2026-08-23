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

**Kritik doğrulama (spike'ta):** İlk N snapshot'ın gerçekten sağlıklı bölgeye denk geldiği veri keşfinde doğrulanır. Rulman baştan sorunluysa baseline kirlenir — spike bunu yakalamalı.

**Soğuk başlangıç (cold start):** Baseline dolana kadar (ilk N snapshot) anomali skoru üretilmez; bu snapshot'lar yalnız baseline'ı beslemek için kullanılır. Event'lerde bu dönem `warming_up` olarak işaretlenebilir.

## İzlenen Özellikler

İki özellik **ayrı ayrı** izlenir (birleştirilmez):

| Özellik | Ne yakalar | Zamanlama |
|---|---|---|
| **Kurtosis** | Sinyaldeki ani darbeler (impulsiveness); yüzey çatlağı/pitting | **Erken** uyarı |
| **RMS** | Genel titreşim enerjisi/şiddeti | **Geç** ama kesin |

**Neden bu ikisi ve neden ayrı:** Farklı arıza evrelerini yakalarlar. Kurtosis erken çatlakta yükselir; ileri evrede bazen düşer (darbeler yüzeye yayılıp normalleşir) ama RMS yükselmeye devam eder. Biri diğerinin kör noktasını kapatır. Crest factor eklenmedi — RMS/kurtosis ile korelasyonlu, bağımsız sinyal katmıyor.

## Z-Score Hesabı

Her yeni snapshot'ın her özelliği için:
```
z = (value - baseline.mean) / baseline.std
```
- `baseline.std == 0` koruması: sıfıra bölme olmaz; std çok küçükse küçük bir epsilon eklenir veya o metrik atlanır (domain'de kontrol).
- Z-Score **işaretli** tutulur ama eşik **mutlak değere** göre değerlendirilir (hem ani düşüş hem ani yükseliş anomali olabilir; özellikle kurtosis'in düşmesi ileri arıza işareti).

## Hareketli Ortalama (Gürültü Bastırma)

Tek bir snapshot'ın Z-Score'u gürültülü olabilir (anlık sıçrama). Yanlış pozitifi azaltmak için:
- Z-Score, son `MA_WINDOW` snapshot (varsayılan 5) üzerinde hareketli ortalamayla yumuşatılır.
- Alarm, **yumuşatılmış** Z-Score eşik aştığında çalar — tek bir gürültülü örnek tek başına alarm üretmez.
- Bu, "sürekli alarm veren sistem işe yaramaz" (05) ilkesinin somut önlemi.

## Warning / Critical Mantığı

| Seviye | Koşul (yumuşatılmış \|z\|) | Aksiyon |
|---|---|---|
| Normal | < `ZSCORE_WARNING` (3.0) | Sadece kaydet |
| **Warning** | ≥ 3.0 ve < `ZSCORE_CRITICAL` (5.0) | `anomaly.detected` + bildirim |
| **Critical** | ≥ 5.0 | `anomaly.detected` (critical) + bildirim |

- Eşikler `.env`'de (`ANOMALY_ZSCORE_WARNING/CRITICAL`), kalibrasyonla ayarlanır.
- **Herhangi bir** özellik (RMS *veya* kurtosis) eşiği aşarsa alarm çalar; `AnomalyDetected.metric` alanı hangisinin tetiklediğini belirtir.
- İki özellik aynı anda tetiklerse iki ayrı event yerine tek event'te en yüksek severity taşınır (event spam önleme).

## Alarm Gürültü Kontrolü (Debounce)

Bir rulman kritik bölgeye girince her snapshot alarm üretmemeli (Telegram spam).
- Aynı `(machine_id, metric, severity)` için son bildirimden bu yana `ALARM_COOLDOWN` (varsayılan 60 sn playback zamanı) geçmeden yeni bildirim gönderilmez.
- Kayıt (`anomaly_events`) yine de her tespitte yazılır; sadece *bildirim* debounce edilir. (Kayıt ≠ bildirim ayrımı.)

## Değerlendirme (05 ile bağlantılı)
- **Lead time:** İlk warning ile veri setindeki bilinen arıza anı arasındaki süre. Ne kadar erken = o kadar iyi.
- **Yanlış pozitif:** Baseline sonrası, arıza bölgesi dışında çalan alarmlar.
- Bu metrikler eşik/pencere kalibrasyonunu yönlendirir.

## Katman 2 — ML Entegrasyonu (özet, detay 02'de)
- `AnomalyDetector` port'u ardında IsolationForest/PCA/River.
- Girdi: aynı çıkarılmış özellik vektörü (RMS, kurtosis, crest, FFT bantları).
- `anomaly_events.detector` alanı hangi katmanın bulduğunu ayırt eder (`zscore` / `isolation_forest` / `pca`).
- Katman 1 ile katman 2 aynı anda çalışabilir; farklı tespitler karşılaştırılabilir (hangisi daha erken/az yanlış pozitif).

## Yeni Config Değişkenleri
```
BASELINE_WINDOW=200          # baseline için ilk kaç snapshot
MA_WINDOW=5                  # Z-Score hareketli ortalama penceresi
ALARM_COOLDOWN=60            # aynı alarm için bildirim debounce (sn, playback zamanı)
```
(ANOMALY_ZSCORE_WARNING/CRITICAL zaten .env'de mevcut.)
