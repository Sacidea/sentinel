# IMS Set 2 spike bulguları

Atılabilir keşif; `extract_features` (Pearson kurtosis) ile ölçüldü. Grafik: `ims_set2_spike.png`.

## Format

- Dosya sayısı: **984**
- İlk / son: `2004.02.12.10.32.39` → `2004.02.19.06.22.39` (~6,8 gün, 10 dk aralık)
- Her dosya: **20480 satır × 4 sütun** (hepsi tutuyor; timestamp parse hatası 0)
- Simülatör beklentisiyle uyumlu: düz isimler, uzantısız, tab ayrımlı float

## Baseline penceresi (ilk 200 snapshot)

| Rulman | RMS mean | RMS std | son 50 RMS mean | kurtosis mean | kurtosis std | RMS \|z\|≥3 ilk index | kurtosis \|z\|≥3 ilk index |
|---|---:|---:|---:|---:|---:|---:|---:|
| bearing_1 | 0.0773 | 0.0012 | 0.2735 | 3.447 | 0.107 | 512 | 647 |
| bearing_2 | 0.0952 | 0.0010 | 0.1443 | 3.201 | 0.070 | 282 | 894 |
| bearing_3 | 0.1037 | 0.0024 | 0.1468 | 4.528 | 0.514 | 312 | 537 |
| bearing_4 | 0.0555 | 0.0007 | 0.1004 | 3.140 | 0.077 | 538 | 434 |

## Yorum

**İlk 200 sağlıklı.** Grafikte kesik çizginin solu düz; bearing_1 arızası ~700 civarında gözle görünür, sonda RMS > 0,7 / kurtosis ~17. Literatürdeki Set 2 “bearing_1 dış bilezik” öyküsü bu eğriyle uyumlu.

**`BASELINE_WINDOW=200` bu sette kirlenmiyor.** İlk |z|≥3, 200’ün oldukça sağında (bearing_1 RMS index 512 ≈ 85 saat sonra).

**Kalibrasyon uyarısı:** Sağlıklı RMS std’si çok küçük (~0,001). |z|≥3 mutlak olarak minik bir kayma; bearing_2 index 282’de 3σ’ya değiyor ama grafikte hâlâ “düz”. Canlı alarmı ham 3σ’ya bağlamak erken uyarı verir, yanlış pozitif de üretebilir. Mevcut `MA_WINDOW=5` bunu yumuşatır; eşik kalibrasyonu Set 2 üzerinde yapılmalı.

**bearing_3 kurtosis** baseline’da zaten ~4,5 (Gaussian 3 değil). Pearson ölçeği doğru; bu kanal daha darbeli başlıyor, arıza işareti değil.

## Sonuç (pipeline için)

- `data/ims` Set 2 ile doldurulabilir; simülatör sentetikten gerçeğe geçer.
- Baseline varsayımı Set 2 için tutulur.
- Z-Score eşikleri sentetik gürültüye göre değil bu ölçeğe göre ayarlanmalı.
