# IMS domain-invariant IsolationForest (Set 2 egitim -> Set 1 test)

Offline hold-out. Canli Kafka/DB yok. Canli IF, nicelik veya ADR-0008 **degismez**.
Referans: `ims_set2_ml_calibration.py` (IF+zarf, 0.995/0.999).

Set 2: `data/ims` (`2004.02.12.10.32.39` -> `2004.02.19.06.22.39`,
984 dosya, 4 kanal x). `data/ims/2nd_test` bossa `data/ims` kullanilir.
Set 1: `data/ims_set1/1st_test` (`2003.10.22.12.06.24` -> `2003.11.25.23.39.56`,
2156 dosya, 8 kanal x/y). NASA: b3 ic bilezik, b4 makara; b1/b2 saglikli.
Dosya index'i; wall-clock degil. Lead = (son index - ilk C) * 10 dk.

Ozellik: rms, kurtosis, crest, peak (`extract_features`). FFT IF vektorune girmez.
Egitim: Set 2 warmup (ilk 200 * 4 rulman = 800 vektor).
Tek orman + Set 2'den donmus nicelik esigi; Set 1'de yeniden egitim yok.
IF: n_estimators=64, contamination=0.01,
random_state=0 (kalibrasyon notebook), RobustScaler, zarf acik,
Wq/Cq=0.995/0.999. Set 1 skorlama index 200'den.

## Iki kosu

1. **Ham:** Set 2 ham 4-vektorde egit, ayni modeli Set 1 ham 4-vektorde skorla.
2. **Domain-invariant:** her (dataset, rulman, eksen) kendi ilk 200'unden
   mean/std; `(x-mean)/std`. Set 2 kendi baseline'i, Set 1 kendi baseline'i.
   IF normalize Set 2 warmup'ta egitilir, normalize Set 1'de test edilir.

Dogrulama: mutlak alarm sayisi degil - ilk uyari index'i, siralama
(arizali sagliklidan once mi), erken FP (arizali ilk uyaridan once saglikli).

## Set 1 ozet (yan yana)

| Kosul | b3 | b4 | b1 | b2 | siralama | bosluk | erken FP |
|---|---:|---:|---:|---:|---|---|---:|
| ham | 1549 | 338 | - | 2155 | evet | 302.8 saat | 0 |
| normalize | 259 | 243 | 282 | 354 | evet | 6.5 saat | 0 |

## Kanal karnesi (ham vs normalize, yan yana)

| Rulman | eksen | NASA | ham W | ham C | norm W | norm C |
|---|---|---|---:|---:|---:|---:|
| bearing_1 | x | saglikli | - | - | 282 | - |
| bearing_1 | y | saglikli | - | - | 524 | 557 |
| bearing_2 | x | saglikli | 2155 | - | 354 | 2152 |
| bearing_2 | y | saglikli | - | - | 565 | 2153 |
| bearing_3 | x | ic bilezik | 1549 | 1559 | 259 | 262 |
| bearing_3 | y | ic bilezik | 1870 | 1829 | 304 | 1827 |
| bearing_4 | x | makara | 1441 | 1438 | 243 | 421 |
| bearing_4 | y | makara | 338 | 501 | 244 | 501 |

## Set 1 karneleri (ayri)

### Ham transfer

Ilk arizali alarm (b3/b4, min x/y): **338**.
Ilk saglikli alarm (b1/b2, min x/y): **2155**.
Siralama (arizali sagliklidan once mi): **evet (1817 dosya / 302.8 saat once)**.
Erken FP (saglikli, arizali ilk uyaridan once, warmup haric): **0**.

| Rulman | eksen | NASA | ilk W | ilk C | lead C (son dosya) |
|---|---|---|---:|---:|---|
| bearing_1 | x | saglikli | - | - | N/A (saglikli) |
| bearing_1 | y | saglikli | - | - | N/A (saglikli) |
| bearing_2 | x | saglikli | 2155 | - | N/A (saglikli) |
| bearing_2 | y | saglikli | - | - | N/A (saglikli) |
| bearing_3 | x | ic bilezik | 1549 | 1559 | 99.3 saat |
| bearing_3 | y | ic bilezik | 1870 | 1829 | 54.3 saat |
| bearing_4 | x | makara | 1441 | 1438 | 119.5 saat |
| bearing_4 | y | makara | 338 | 501 | 275.7 saat |

| Rulman | NASA | ilk alarm (min x/y) |
|---|---|---:|
| bearing_1 | saglikli | - |
| bearing_2 | saglikli | 2155 |
| bearing_3 | ic bilezik | 1549 |
| bearing_4 | makara | 338 |

### Domain-invariant (z-norm)

Ilk arizali alarm (b3/b4, min x/y): **243**.
Ilk saglikli alarm (b1/b2, min x/y): **282**.
Siralama (arizali sagliklidan once mi): **evet (39 dosya / 6.5 saat once)**.
Erken FP (saglikli, arizali ilk uyaridan once, warmup haric): **0**.

| Rulman | eksen | NASA | ilk W | ilk C | lead C (son dosya) |
|---|---|---|---:|---:|---|
| bearing_1 | x | saglikli | 282 | - | N/A (saglikli) |
| bearing_1 | y | saglikli | 524 | 557 | N/A (saglikli) |
| bearing_2 | x | saglikli | 354 | 2152 | N/A (saglikli) |
| bearing_2 | y | saglikli | 565 | 2153 | N/A (saglikli) |
| bearing_3 | x | ic bilezik | 259 | 262 | 315.5 saat |
| bearing_3 | y | ic bilezik | 304 | 1827 | 54.7 saat |
| bearing_4 | x | makara | 243 | 421 | 289.0 saat |
| bearing_4 | y | makara | 244 | 501 | 275.7 saat |

| Rulman | NASA | ilk alarm (min x/y) |
|---|---|---:|
| bearing_1 | saglikli | 282 |
| bearing_2 | saglikli | 354 |
| bearing_3 | ic bilezik | 259 |
| bearing_4 | makara | 243 |

## Hold-out yorumu (esik degismez)

- Beklenti (ham IF saglikli b2'yi erken/cok yakalar; z-norm arizaliyi ayirir)
  **tutmadi**. Esik retune yok; asagisi gozlem.
- Ham: b1 sessiz, b2 yalniz 2155 (test sonu). Arizali ilk 338 (b4). Siralama boslugu 302.8 saat; erken FP=0.
- Normalize: b3=259, b4=243, b1=282, b2=354 (hepsi warmup+kisa pencere). Siralama evet ama bosluk 6.5 saat. Erken FP=0 tanim icindir
  (saglikli, arizalidan *sonra* calar; ayirim kucuk).
- Normalize 'daha erken lead' warmup-kenari: ADR-0008'in eledigi 204-217
  sahte erken ile ayni sinif. Mutlak olcek z-norm ile silinince her kanal
  kucuk sapmada aykiri gorunur.
- Ham kosuda mutlak RMS/peak Set 2 ormanina tasiyor; saglikli Set 1 bu
  bulutta kaliyor, arizali (ozellikle b4/y) cikiyor. Bu, z-norm'un
  cozmesi beklenen 'domain kaymasi'nin bu ciftte felaket olmadigini gosterir.
- Bu karne secim tablosu degil. 0.995/0.999 Set 1'e uydurulmadi.
- Per-kanal canli IF (her seri kendi warmup ormani) bu deney degil;
  burada **tek** Set 2 ormani Set 1'e tasindi.
- Canli detector, event semasi veya ADR-0008 bu hold-out ile degismez.

