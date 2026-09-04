# IMS Set 2 Z-Score esik kalibrasyonu

Kaynak: NASA Ames PCoE / University of Cincinnati IMS, Set No. 2 README.
Kayit: `2004.02.12.10.32.39` -> `2004.02.19.06.22.39` (984 dosya,
10 dk aralik).
Ariza ani: "At the end of the test-to-failure experiment, outer race
failure occurred in bearing 1." — son dosya (index 983); baslangic timestamp'i yok.
Lead time = (son index - ilk warning) * 10 dk.
RMS egri gozlemi (~index 700) sadece nitel; bu hesaba girmez.
MA=5, BASELINE_WINDOW=200.

FP: NASA'nin hasar duyurmadigi kanallar (bearing_2/3/4) uzerinde,
etiketli kanalin (bearing_1) ilk uyarisindan onceki alarm sayisi.

## Esik taramasi

| W / C | b1 ilk W | b1 ilk C | lead (son dosya) | etiketsiz FP |
|---|---:|---:|---|---:|
| 3/5 | 534 | 536 | 74.8 saat | 13 |
| 5/8 | 536 | 554 | 74.5 saat | 0 |
| 8/12 | 554 | 597 | 71.5 saat | 0 |
| 10/15 | 575 | 612 | 68.0 saat | 0 |
| 12/20 | 597 | 648 | 64.3 saat | 0 |
| 15/25 | 612 | 693 | 61.8 saat | 0 |
| 20/30 | 648 | 702 | 55.8 saat | 0 |

## Ilk alarm index (3.0/5.0 vs 5.0/8.0)

| Esik | bearing_1 | bearing_2 | bearing_3 | bearing_4 |
|---|---:|---:|---:|---:|
| 3/5 | 534 | 351 | 889 | 652 |
| 5/8 | 536 | 828 | 902 | 702 |

## Secim: 5.0 / 8.0 (ADR-0006)

- 3.0/5.0: etiketsiz FP=13 (bearing_2 ilk alarm 351); lead 74.8 saat.
- 5.0/8.0: etiketsiz FP=0; bearing_1 ilk warning 536; lead 74.5 saat
  (index 536 -> 983).
- Daha yuksek esikler FP'yi iyilestirmez, lead time'i kisaltir.
- Bu sayilar yalniz Set 2 icindir; Set 1/3 veya baska veri setinde
  esikler yeniden olculmelidir.

