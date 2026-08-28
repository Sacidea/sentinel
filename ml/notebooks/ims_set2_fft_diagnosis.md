# IMS Set 2 FFT ariza teshisi (offline)

Canli `anomaly_events` yok. Kural: `diagnose_fft_bands` (ADR-0011).
Esikler Set 2: abs_z=12, dominance=3,
companion_z=8. Grafik: `ims_set2_fft_diagnosis.png`.

Dosya sayisi: **984**. Baseline ilk 200, gec son 50.

## Neden enerji-orani yetmedi

Son 50 dosyanin ortalamasinda **butun** rulmanlarda BPFO, BPFI/BSF'ten
onlarca kat buyuk. Kaplin bu ozellikte 'tum bantlari esit kaldirmiyor';
**yalniz BPFO kovasini** sisiyor. (b) yalniz `E_bpfo / max(E_bpfi, E_bsf)`
olursa bearing_4 da 'BPFO' olur — dunku tuzak.

Kalibre (b): enerji baskinligi **ve** en az bir diger karakteristigin
z >= 8 (gercek dis bilezikte BPFI de baseline'dan cikar;
kaplin BPFI'yi yerinde birakir). (a) aday bandin kendi baseline z'si
>= 12 (oran sismesini eker).

## Gec pencere (son 50) — kosul (a)/(b) ham sayilar

| Rulman | E_BPFO | E_BPFI | E_BSF | enerji baskinligi | z_BPFO | z_BPFI | z_BSF |
|---|---:|---:|---:|---:|---:|---:|---:|
| bearing_1 | 5.253e+05 | 2.832e+04 | 2.506e+04 | 18.5x | 107.5 | 51.2 | 34.9 |
| bearing_2 | 2.448e+05 | 8440 | 7950 | 29.0x | 16.3 | 1.9 | -0.4 |
| bearing_3 | 1.561e+06 | 8084 | 6882 | 193.1x | 33.5 | 0.5 | -0.7 |
| bearing_4 | 4.844e+05 | 3878 | 4275 | 113.3x | 159.4 | 0.9 | -0.2 |

## Teshis vs enerji-only tuzak

enerji-only = (a) z_BPFO + (b) enerji orani, **companion yok**.
Tam kural = ayni AND + companion z.

| Rulman | NASA | teshis | ilk | #BPFO | #enerji-only | #belirsiz | ok |
|---|---|---|---:|---:|---:|---:|---|
| bearing_1 | dis bilezik | bpfo | 956 | 19 | 99 | 765 | ok |
| bearing_2 | saglikli | uncertain | — | 0 | 33 | 784 | ok |
| bearing_3 | saglikli | uncertain | — | 0 | 69 | 784 | ok |
| bearing_4 | saglikli | uncertain | — | 0 | 88 | 784 | ok |

b1 ilk BPFO etiketi index 956 / 984 (gec donem teyidi; lead-time metrigi degil).

## bearing_4 (kaplin + oran sismesi) — ozellikle

Gec BPFO enerjisi 4.844e+05 (b1: 5.253e+05, ayni mertebe).
Enerji baskinligi 113.3x, z_BPFO=159 —
oran ve mutlak BPFO 'var' der. Bu yuzden enerji-only **88** snapshot'i BPFO sayar.
z_BPFI=0.9, z_BSF=-0.2 (companion esik 8) → companion yok → **belirsiz**.
Tam kuralda hic BPFO etiketi yok (n=0).

## Grid notu

Yalniz z_BPFO + enerji-D taramasi: b1'i yakalayan hicbir (Z, D) cifti
b2/3/4'u sifirlamadi (strict=0). Companion ile (abs_z=12, D=3,
companion_z=8) b1>0 ve etiketsiz=0.

Yalniz Set 2. Canli entegrasyon (`fault_type`, schema, migration) sonraki is.
