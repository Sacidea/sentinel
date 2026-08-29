# IMS Set 1 FFT ariza teshisi (hold-out)

> Ham-rFFT siniri: Set 2 kaplin/b4, bu sette ic bilezik/makara.
> 4/4 tutmadi. Canli yok; sonraki deneme envelope (ADR-0012).

Set 2 esikleri **kilit**: abs_z=12, dominance=3, companion_z=8.
Retune yok. Kural: `diagnose_fft_bands` (ADR-0011).
Canli `anomaly_events` yok. Grafik: `ims_set1_fft_diagnosis.png`.

NASA 1st_test: 8 kanal (rulman basina X/Y). Birincil protokol **X**
(Set 2 tek ivmeolcer analogu). Y ayri rapor.

Dosya sayisi: **2156**. Baseline ilk 200, gec son 50.

Beklenti: b3=`bpfi` (ic bilezik), b4=`bsf` (makara), b1/b2=`uncertain`.

## Birincil (X) — 4/4 TUTMADI

| Rulman | NASA | teshis | ilk | #BPFO | #BPFI | #BSF | #e-only | #belirsiz | ok |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| bearing_1 | saglikli | uncertain | — | 0 | 0 | 0 | 0 | 1956 | ok |
| bearing_2 | saglikli | bsf | 2135 | 0 | 0 | 4 | 0 | 1952 | FAIL |
| bearing_3 | ic bilezik | uncertain | — | 0 | 0 | 0 | 0 | 1956 | FAIL |
| bearing_4 | makara | uncertain | — | 0 | 0 | 0 | 0 | 1956 | FAIL |

Donuk esik X teshisleri: {'bearing_1': 'uncertain', 'bearing_2': 'bsf', 'bearing_3': 'uncertain', 'bearing_4': 'uncertain'}.

## Y ekseni (ayni esik, ayri karne)

| Rulman | NASA | teshis | ilk | #BPFO | #BPFI | #BSF | #belirsiz | ok |
|---|---|---|---:|---:|---:|---:|---:|---|
| bearing_1 | saglikli | uncertain | — | 0 | 0 | 0 | 1956 | ok |
| bearing_2 | saglikli | uncertain | — | 0 | 0 | 0 | 1956 | ok |
| bearing_3 | ic bilezik | uncertain | — | 0 | 0 | 0 | 1956 | FAIL |
| bearing_4 | makara | uncertain | — | 0 | 0 | 0 | 1956 | FAIL |

## Gec pencere (son 50) — X

| Rulman | E_BPFO | E_BPFI | E_BSF | BPFO baskin | hedef baskin | z_BPFO | z_BPFI | z_BSF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bearing_1 | 1.099e+04 | 6675 | 9355 | 1.2x | 1.2x | 2.5 | 1.6 | 3.1 |
| bearing_2 | 1.559e+04 | 1.1e+04 | 3.918e+04 | 0.4x | 0.4x | 6.4 | 4.5 | 30.1 |
| bearing_3 | 2.7e+04 | 2.653e+04 | 3.893e+04 | 0.7x | 0.7x | 8.0 | 12.2 | 18.1 |
| bearing_4 | 1.68e+04 | 6601 | 1.031e+04 | 1.6x | 0.6x | 3.2 | 6.1 | 10.7 |

hedef baskin = NASA bandinin (b3 BPFI, b4 BSF, sagliklilarda BPFO)
enerjisi / max(diger iki). enerji-only = (a) z + enerji orani,
**companion yok**.

## Neden tutmadi (imza, esik degil)

Gec pencerede b3'te E_BSF > E_BPFI (hedef baskin 0.7x). NASA ic
bilezik ama uc kova rFFT'de BPFI hakim degil — companion olsa da
(a)+(b) BPFI diyemez. enerji-only hedef de 0.
b4'te z_BSF gec ortalama 10.7 (<12) ve E_BPFO > E_BSF; makara
kovasi 3x baskin degil.
b2 (NASA saglikli) en yuksek z_BSF'i tasiyor; kural 4 snapshot
BSF basar — false positive.
Asagidaki grid'de hicbir (C, abs_z) 4/4 yapmiyor: C=40 b2 false
BSF'i kapatir ama b3/b4 hala belirsiz. abs_z=0 b4'u yanlis BPFO
yapar. Bu yuzden Set 2 esigi kaydirmak Set 1'i kurtarmaz.

| Rulman | max z_BPFO | max z_BPFI | max z_BSF |
|---|---:|---:|---:|
| bearing_1 | 5.6 | 6.7 | 16.3 |
| bearing_2 | 14.1 | 30.8 | 126.1 |
| bearing_3 | 32.7 | 73.4 | 66.8 |
| bearing_4 | 9.8 | 19.4 | 19.5 |

Set 2 yalniz dis bilezik + kaplin ayirdi. Set 1 ic bilezik/makara
ayni uc kovada ayri degil; canli `fault_type` kilitlenmez.


## Hold-out hassasiyet (retune degil)

Asagidaki tarama Set 2 esiklerini **degistirmez**. Yalniz bu sette hangi
C/abs_z 4/4 X-protokolunu tutardi — overfitting notu, yeni default degil.

### companion_z (abs_z=12, D=3) — X ekseni 4/4

| companion_z | 4/4 X | b1 | b2 | b3 | b4 |
|---:|---|---|---|---|---|
| 5 | FAIL | uncertain | bsf | uncertain | uncertain |
| 7 | FAIL | uncertain | bsf | uncertain | uncertain |
| 8 | FAIL | uncertain | bsf | uncertain | uncertain |
| 10 | FAIL | uncertain | bsf | uncertain | uncertain |
| 15 | FAIL | uncertain | bsf | uncertain | uncertain |
| 40 | FAIL | uncertain | uncertain | uncertain | uncertain |

### abs_z (D=3, C=8) — X ekseni 4/4

| abs_z | 4/4 X | b1 | b2 | b3 | b4 |
|---:|---|---|---|---|---|
| 0 | FAIL | uncertain | bsf | uncertain | bpfo |
| 12 | FAIL | uncertain | bsf | uncertain | uncertain |
| 20 | FAIL | uncertain | bsf | uncertain | uncertain |
| 50 | FAIL | uncertain | bsf | uncertain | uncertain |

Yalniz Set 1 hold-out. Esikler Set 2'de kalir (ADR-0011 otopsi).
Teshis envelope'a (ADR-0012); `fault_type` bu kurala baglanmaz.
