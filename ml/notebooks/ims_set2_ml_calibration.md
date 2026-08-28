# IMS Set 2 IsolationForest / PCA kalibrasyonu

Kaynak: NASA Ames PCoE / University of Cincinnati IMS, Set No. 2 README.
Kayit: `2004.02.12.10.32.39` -> `2004.02.19.06.22.39` (984 dosya,
10 dk aralik). **Gercek Set 2 dosyalari; sentetik vektor yok.**
Ariza ani: "At the end of the test-to-failure experiment, outer race
failure occurred in bearing 1." — son dosya (index 983); baslangic timestamp'i yok.
Lead time = (son index - ilk warning) * 10 dk.
BASELINE_WINDOW=200. Ozellikler: rms, kurtosis, crest, peak
(`extract_features`, ayni tanim).
Esik: warmup egitim skorlarinin niceligi; carpan (0.5/0.25/1e-3) yok.
`score > nicelik`.

FP: NASA'nin hasar duyurmadigi kanallar (bearing_2/3/4) uzerinde,
etiketli kanalin (bearing_1) ilk uyarisindan onceki alarm sayisi.

Z-Score referansi (ADR-0006, 5.0/8.0): lead 74.5 saat (index 536), etiketsiz FP=0.

## IsolationForest (skor + olceklenmis max-norm zarf, nicelik)

| Wq / Cq | b1 ilk W | b1 ilk C | lead (son dosya) | etiketsiz FP |
|---|---:|---:|---|---:|
| 0.9/0.99 | 204 | 217 | 129.8 saat | 0 |
| 0.95/0.99 | 205 | 217 | 129.7 saat | 0 |
| 0.99/0.995 | 217 | 447 | 127.7 saat | 0 |
| 0.99/0.999 | 217 | 538 | 127.7 saat | 0 |
| **0.995/0.999** | **447** | **538** | **89.3 saat** | **0** |
| 0.999/0.999 | 538 | 538 | 74.2 saat | 1 |

## IsolationForest (yalniz decision_function niceligi, zarf yok)

| Wq / Cq | b1 ilk W | b1 ilk C | lead (son dosya) | etiketsiz FP |
|---|---:|---:|---|---:|
| 0.9/0.99 | 204 | 217 | 129.8 saat | 0 |
| 0.95/0.99 | 205 | 217 | 129.7 saat | 0 |
| 0.99/0.995 | 217 | 458 | 127.7 saat | 0 |
| 0.99/0.999 | 217 | 761 | 127.7 saat | 0 |
| 0.995/0.999 | 458 | 761 | 87.5 saat | 0 |
| 0.999/0.999 | 761 | 761 | 37.0 saat | 1 |

## PCA Hotelling T2 / SPE (nicelik)

| Wq / Cq | b1 ilk W | b1 ilk C | lead (son dosya) | etiketsiz FP |
|---|---:|---:|---|---:|
| 0.9/0.99 | 204 | 205 | 129.8 saat | 2 |
| 0.95/0.99 | 205 | 205 | 129.7 saat | 1 |
| 0.99/0.995 | 205 | 398 | 129.7 saat | 0 |
| 0.99/0.999 | 205 | 458 | 129.7 saat | 0 |
| 0.995/0.999 | 398 | 458 | 97.5 saat | 3 |
| 0.999/0.999 | 458 | 458 | 87.5 saat | 6 |

## Ilk alarm index (secilen 0.995 / 0.999)

| Model | bearing_1 | bearing_2 | bearing_3 | bearing_4 |
|---|---:|---:|---|---:|
| IF+zarf | 447 | 711 | 537 | 635 |
| IF skor | 458 | - | 537 | 635 |
| PCA | 398 | 430 | 236 | 432 |
| Z-Score 5/8 | 536 | 828 | 902 | 702 |

PCA 0.99/* satirlarinda FP=0, cunku b1 205'te calar ve FP penceresi 200-205'e coker
(diger kanallar daha gec). Bu 0 FP, Z-Score'daki "etiketsiz sessizlik" degildir.

## Z-Score ile karsilastirma

| Model | b1 ilk alarm | lead | vs Z-Score | etiketsiz FP |
|---|---:|---|---|---:|
| Z-Score 5.0/8.0 | 536 | 74.5 saat | referans | 0 |
| IF+zarf 0.995/0.999 | 447 | 89.3 saat | 14.8 saat daha erken | 0 |
| IF skor 0.995/0.999 | 458 | 87.5 saat | 13.0 saat daha erken | 0 |
| PCA 0.995/0.999 | 398 | 97.5 saat | 23.0 saat daha erken | 3 |

0.90-0.99 nicelikleri b1'i 204-217'de (warmup+~15 dosya) caldirir. Lead 127+ saat
"daha iyi" gorunur; FP penceresi kapanir. Bu, ariza oncesi yakalama degil,
egitim zarfinin hemen disidir. Secime girmez.

## Secim: IF 0.995 / 0.999 + zarf (ADR-0008)

- IsolationForest + olceklenmis max-norm zarf, egitim niceligi 0.995/0.999:
  etiketsiz FP=0; bearing_1 ilk warning 447; lead 89.3 saat (index 447 -> 983).
  Critical 538 (Z-Score warning 536 ile neredeyse ayni dosya).
- Zarf acik: critical 538 vs zarfsiz 761 (gec). Warning 447 vs 458 (yakin).
- PCA ayni nicelikte etiketsiz FP=3 (`bearing_3` @ 236). Z-Score'un 5.0/8.0
  eleme gerekcesini (etiketsiz erken alarm) karsilamiyor; varsayilan canli
  katmanda durur ama "Z-Score'dan iyi" sayilmaz.
- 0.999/0.999 IF+zarf lead 74.2 saat (Z-Score ile neredeyse esit) ama FP=1.
- Bu sayilar yalniz Set 2; Set 1/3 yeniden tarama ister.
- River bu taramada yok.

## Test ayrimi

| Nerede | Veri |
|---|---|
| `tests/unit/test_ml_detectors.py` | Sentetik vektor (7 test) |
| `tests/integration/test_week2_pipeline.py` | Fake port, sentetik chunk |
| `ml/notebooks/ims_set2_ml_calibration.py` | Gercek 984 Set 2 dosyasi |

"X test gecti" Set 2 karnesi degildir. Bu dosya kalibrasyon karnesidir.
