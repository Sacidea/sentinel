# IMS Set 2 envelope teshisi (offline)

> Ham-rFFT kapandi (ADR-0011/0012). Bu karne Hilbert envelope.
> Canli `fault_type` yok. Tutmazsa yine yazilmaz (ADR-0013).

Esikler (Set 2 kilit, `envelope.py`): abs_z=12,
dominance=3, companion_z=25.
Grafik: `ims_set2_envelope_diagnosis.png`.

Dosya sayisi: **984**. Baseline ilk 200, gec son 50.
Band-pass 2–10 kHz, sonra envelope spektrumu.

## Birincil — 4/4 tuttu

| Rulman | NASA | teshis | ilk | #BPFO | #enerji-only | #belirsiz | ok |
|---|---|---|---:|---:|---:|---:|---|
| bearing_1 | dis bilezik | bpfo | 959 | 20 | 449 | 764 | ok |
| bearing_2 | saglikli | uncertain | — | 0 | 87 | 784 | ok |
| bearing_3 | saglikli | uncertain | — | 0 | 6 | 784 | ok |
| bearing_4 | saglikli | uncertain | — | 0 | 172 | 784 | ok |

## Gec pencere (son 50) envelope enerjisi

| Rulman | E_BPFO | E_BPFI | E_BSF | enerji baskin | z_BPFO | z_BPFI | z_BSF |
|---|---:|---:|---:|---:|---:|---:|---:|
| bearing_1 | 4.736e+06 | 7.63e+04 | 4.701e+04 | 62.1x | 3015.5 | 61.3 | 35.2 |
| bearing_2 | 1.72e+05 | 6451 | 6226 | 26.7x | 120.4 | 1.8 | 1.1 |
| bearing_3 | 2.863e+04 | 1.302e+04 | 1.707e+04 | 1.7x | 3.8 | -0.7 | -1.3 |
| bearing_4 | 1.225e+05 | 6134 | 5216 | 20.0x | 176.7 | 5.6 | 2.9 |

## Esik taramasi (bu set, retune notu)

### companion_z (abs_z=12, D=3)

| companion_z | 4/4 | b1 | b2 | b3 | b4 | b1 #BPFO | etiketsiz # |
|---:|---|---|---|---|---|---:|---:|
| 8 | FAIL | bpfo | bpfo | uncertain | bpfo | 144 | 15 |
| 15 | FAIL | bpfo | uncertain | uncertain | bpfo | 33 | 5 |
| 20 | FAIL | bpfo | uncertain | uncertain | bpfo | 23 | 3 |
| 21 | FAIL | bpfo | uncertain | uncertain | bpfo | 22 | 1 |
| 25 | ok | bpfo | uncertain | uncertain | uncertain | 20 | 0 |
| 30 | ok | bpfo | uncertain | uncertain | uncertain | 18 | 0 |
| 40 | ok | bpfo | uncertain | uncertain | uncertain | 17 | 0 |
| 80 | ok | bpfo | uncertain | uncertain | uncertain | 14 | 0 |

b4 max companion z ~21; C=25 ilk 4/4. C=8 (ham-FFT kopyasi) b2/b4
false BPFO. abs_z bu sette 4/4 tasiyicisi degil (C=8 iken hicbiri).

### abs_z (D=3, C=25)

| abs_z | 4/4 | b1 | b2 | b3 | b4 | b1 #BPFO | etiketsiz # |
|---:|---|---|---|---|---|---:|---:|
| 0 | ok | bpfo | uncertain | uncertain | uncertain | 20 | 0 |
| 5 | ok | bpfo | uncertain | uncertain | uncertain | 20 | 0 |
| 8 | ok | bpfo | uncertain | uncertain | uncertain | 20 | 0 |
| 12 | ok | bpfo | uncertain | uncertain | uncertain | 20 | 0 |
| 20 | ok | bpfo | uncertain | uncertain | uncertain | 20 | 0 |
| 50 | ok | bpfo | uncertain | uncertain | uncertain | 20 | 0 |

Ham-FFT otopsi durur. Envelope canliya ancak Set 1 hold-out da
4/4 tutarsa yazilir (`ims_set1_envelope_diagnosis.md`).
