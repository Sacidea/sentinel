# IMS Set 1 Z-Score hold-out (Set 2 5.0/8.0 kilit)

Kaynak: NASA Ames PCoE / University of Cincinnati IMS, 1st_test README.
Kayit: `2003.10.22.12.06.24` -> `2003.11.25.23.39.56` (2156 dosya,
resmi aralik 10 dk; lead = dosya index farki,
wall-clock degil — isim tarihleri arasinda bosluk olabilir).
NASA: bearing_3 ic bilezik, bearing_4 makara (bilye); bearing_1/2 saglikli.
Incipient timestamp yok — ariza capani **son dosya** (Set 2 ile ayni protokol).
Lead time = (son index - ilk critical) * 10 dk.
Ilk warning ayri kolon; lead hesabina girmez (istek: ilk critical).
MA=5, BASELINE_WINDOW=200.
Esik **kilit**: warning=5 / critical=8 (ADR-0006, yalniz Set 2
kalibrasyonu). Set 1'e retune **yok**. ML yok.
Ham dosya index'i; canli DB/Kafka/wall-clock yok. x ve y ayri seri.
Birincil protokol **X** (Set 2 tek ivmeolcer analogu); Y ayri satir.

FP: saglikli kanallar (bearing_1/2, her eksen) uzerinde, arizali grubun
(bearing_3/4, herhangi bir eksen) **ilk uyarisindan** onceki alarm.

## Set 2 karnesi formati (5.0/8.0 kilit, tarama yok)

| W/C | b3x W | b3x C | lead C b3x | b4x W | b4x C | lead C b4x | saglikli FP |
|---|---:|---:|---|---:|---:|---|---:|
| 5/8 | 755 | 1159 | 166.0 saat | 399 | 1440 | 119.2 saat | 0 |

## 5.0 / 8.0 — kanal karnesi

| Rulman | eksen | NASA | ilk W | ilk C | lead (ilk C, son dosya) |
|---|---|---|---:|---:|---|
| bearing_1 | x | saglikli | - | - | N/A (saglikli) |
| bearing_1 | y | saglikli | - | - | N/A (saglikli) |
| bearing_2 | x | saglikli | 2134 | 2155 | N/A (saglikli) |
| bearing_2 | y | saglikli | 2152 | - | N/A (saglikli) |
| bearing_3 | x | ic bilezik | 755 | 1159 | 166.0 saat |
| bearing_3 | y | ic bilezik | 1829 | 1830 | 54.2 saat |
| bearing_4 | x | makara | 399 | 1440 | 119.2 saat |
| bearing_4 | y | makara | 523 | 1467 | 114.7 saat |

## Erken FP (saglikli, arizalidan once)

Arizali grubun ilk uyarisi (b3/b4, min x/y): **399**
(index 200..399 arasi sayilir; warmup haric).
Saglikli toplam erken alarm: **0**.

| Rulman | eksen | ilk alarm | erken FP sayisi | arizalidan once? |
|---|---|---:|---:|---|
| bearing_1 | x | - | 0 | hayir |
| bearing_1 | y | - | 0 | hayir |
| bearing_2 | x | 2134 | 0 | hayir |
| bearing_2 | y | 2152 | 0 | hayir |

## Arizali kanallar — ilk uyari vs son dosya

Son dosya index: **2155** (`2003.11.25.23.39.56`).

| Rulman | eksen | ilk W | ilk C | lead W | lead C |
|---|---|---:|---:|---|---|
| bearing_3 | x | 755 | 1159 | 233.3 saat | 166.0 saat |
| bearing_3 | y | 1829 | 1830 | 54.3 saat | 54.2 saat |
| bearing_4 | x | 399 | 1440 | 292.7 saat | 119.2 saat |
| bearing_4 | y | 523 | 1467 | 272.0 saat | 114.7 saat |

## Hold-out yorumu (esik degismez)

- Bu karne **secim tablosu degil**. 5.0/8.0 Set 2'de kaldi (ADR-0006);
  Set 1'e uydurmak overfitting olur.
- Saglikli erken FP (b1/b2, arizali ilk uyaridan once): 0.
- b4/x ilk warning 399; ilk critical 1440 (119.2 saat).
  Warning-critical boslugu buyuk olabilir; esik yine degistirilmedi.
- b3/x critical lead 166.0 saat; b3/y 54.2 saat (eksenler karismaz).
- Lead time yalniz NASA'nin hasar duyurdugu rulmanlar (b3, b4) icin
  son dosyaya gore raporlanir; sagliklida 'lead' anlamsizdir.
- Canli esik, detector veya event semasi bu hold-out ile degismez.

