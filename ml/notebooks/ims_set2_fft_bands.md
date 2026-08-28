# IMS Set 2 FFT bant enerjisi (BPFO/BPFI/BSF)

Teshis yok. `extract_features` rfft gucu: temel+2.+3. harmonik, ±5 Hz.
Rexnord ZA-2115 merkezleri: BPFO=236, BPFI=297, BSF=278 Hz. Grafik:
`ims_set2_fft_bands.png`.

Dosya sayisi: **984**. Erken pencere ilk 200, gec son 50.

## BPFO (dis bilezik) erken vs gec ortalama

| Rulman | erken mean | gec mean | gec/erken |
|---|---:|---:|---:|
| bearing_1 | 1.186e+04 | 5.253e+05 | 44.30 |
| bearing_2 | 3.169e+04 | 2.448e+05 | 7.73 |
| bearing_3 | 7.796e+04 | 1.561e+06 | 20.03 |
| bearing_4 | 9963 | 4.844e+05 | 48.62 |

## Yorum

bearing_1 BPFO gec/erken **44.30** (erken 1.186e+04 → gec 5.253e+05).
NASA etiketi dis bilezik; b1 bu bantta run sonunda belirgin yukselir
(grafikte ~index 850+). Etiketsiz kanallar da sona dogru enerji alir
(kaplinli mil; teshis degil): bearing_2 7.73, bearing_3 20.03, bearing_4 48.62.
En dusuk artis bearing_2. Oran, erken ortalamasi kucuk olan kanalda
(bearing_4) sisirilir; mutlak gec seviyede b3 en yuksek.

Bu tarama alarm uretmez; yalniz ozellik dogrulamasi (ADR-0010).
