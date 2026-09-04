# IMS Set 1 envelope teshisi (hold-out)

> Set 2 envelope esikleri kilit (abs_z=12, D=3, C=25). Retune yok.
> Canli `fault_type` yok (ADR-0013).

Hilbert 2–10 kHz, sonra ayni BPFO/BPFI/BSF kovalar.
Grafik: `ims_set1_envelope_diagnosis.png`.

NASA 1st_test: 8 kanal (rulman basina X/Y). Birincil protokol **X**
(Set 2 tek ivmeolcer analogu). Y ayri rapor.

Dosya sayisi: **2156**. Baseline ilk 200, gec son 50.

Beklenti: b3=`bpfi` (ic bilezik), b4=`bsf` (makara), b1/b2=`uncertain`.

## Birincil (X) — 4/4 TUTMADI

| Rulman | NASA | teshis | ilk | #BPFO | #BPFI | #BSF | #e-only | #belirsiz | ok |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| bearing_1 | saglikli | uncertain | — | 0 | 0 | 0 | 5 | 1956 | ok |
| bearing_2 | saglikli | bpfo | 2155 | 1 | 0 | 0 | 17 | 1955 | FAIL |
| bearing_3 | ic bilezik | uncertain | — | 0 | 0 | 0 | 0 | 1956 | FAIL |
| bearing_4 | makara | bpfo | 2117 | 27 | 0 | 0 | 29 | 1929 | FAIL |

Donuk esik X teshisleri: {'bearing_1': 'uncertain', 'bearing_2': 'bpfo', 'bearing_3': 'uncertain', 'bearing_4': 'bpfo'}.

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
| bearing_1 | 3.184e+04 | 1.216e+04 | 1.262e+04 | 2.5x | 2.5x | 8.2 | 3.0 | 2.7 |
| bearing_2 | 3.569e+04 | 1.148e+04 | 1.261e+04 | 2.8x | 2.8x | 20.0 | 8.1 | 7.7 |
| bearing_3 | 1.3e+05 | 1.313e+05 | 7.2e+04 | 1.0x | 1.0x | 69.4 | 83.9 | 43.8 |
| bearing_4 | 1.537e+05 | 3.578e+04 | 4.124e+04 | 3.7x | 0.3x | 71.3 | 24.5 | 31.0 |

hedef baskin = NASA bandinin (b3 BPFI, b4 BSF, sagliklilarda BPFO)
enerjisi / max(diger iki). enerji-only = (a) z + enerji orani,
**companion yok**.

## Hold-out (esik kilit, retune yok)

Asagidaki max z ve grid, Set 2 C=25'in bu sette ic bilezik/makara
ayirip ayirmadigini gosterir. Tutmazsa canli yok — esik kaydirma yok.

b3: max z_BPFI cok yuksek (~1257) ama gec pencerede E_BPFI ~ E_BPFO
(hedef baskin 1.0x) — 3x hakimiyet yok, kural BPFI diyemez.
b4: NASA makara; C=25 ile kural BPFO basar. C=8'de BSF olurdu ama
b2 false BPFO. Grid'de hicbir (C, abs_z) 4/4 yapmiyor.
Envelope Set 2 dis bilezigi ayirdi; Set 1 ic/makara yine imza.

| Rulman | max z_BPFO | max z_BPFI | max z_BSF |
|---|---:|---:|---:|
| bearing_1 | 20.3 | 6.8 | 9.3 |
| bearing_2 | 70.9 | 25.4 | 21.6 |
| bearing_3 | 459.8 | 1256.8 | 369.5 |
| bearing_4 | 103.9 | 62.6 | 160.5 |

Envelope Set 2'de dis bilezik vs kaplin (C=25). Bu hold-out ic
bilezik/makara icin ayni kurali dener; tutmazsa canli yok.


## Hold-out hassasiyet (retune degil)

Asagidaki tarama Set 2 esiklerini **degistirmez**. Yalniz bu sette hangi
C/abs_z 4/4 X-protokolunu tutardi — overfitting notu, yeni default degil.

### companion_z (abs_z=12, D=3) — X ekseni 4/4

| companion_z | 4/4 X | b1 | b2 | b3 | b4 |
|---:|---|---|---|---|---|
| 8 | FAIL | uncertain | bpfo | uncertain | bsf |
| 15 | FAIL | uncertain | bpfo | uncertain | bsf |
| 25 | FAIL | uncertain | bpfo | uncertain | bpfo |
| 40 | FAIL | uncertain | uncertain | uncertain | bpfo |
| 80 | FAIL | uncertain | uncertain | uncertain | uncertain |

### abs_z (D=3, C=25) — X ekseni 4/4

| abs_z | 4/4 X | b1 | b2 | b3 | b4 |
|---:|---|---|---|---|---|
| 0 | FAIL | uncertain | bpfo | uncertain | bpfo |
| 12 | FAIL | uncertain | bpfo | uncertain | bpfo |
| 20 | FAIL | uncertain | bpfo | uncertain | bpfo |
| 50 | FAIL | uncertain | bpfo | uncertain | bpfo |

Yalniz Set 1 envelope hold-out. Esikler Set 2 envelope (ADR-0013).
`fault_type` bu kurala, hold-out tutmadan, baglanmaz.
