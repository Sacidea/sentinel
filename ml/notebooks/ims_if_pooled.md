# IMS IsolationForest havuzlu warmup (offline)

Canli IF, nicelik veya ADR-0008 **degismez**. Ham cache; Kafka yok.
Zarf niceligi havuz skorlarindan (800/1600), dar 200'den degil.
IF: n_estimators=64, contamination=0.01, zarf acik,
Wq/Cq=0.995/0.999. Set 1 rs=42 (canli default);
Set 2 rs=0 (ADR-0008 kalibrasyon).

## Iki kosu

1. **Per-kanal (canli):** her `(dataset, rulman, eksen)` kendi ilk 200'u.
2. **Havuzlu:** dataset'te tum kanallarin ilk 200'u birlesir
   (Set 1: 8*200=1600; Set 2: 4*200=800). Tek IF+zarf; kalan skorlanir.

Dogrulama: ilk uyari, siralama, bosluk, erken FP, critical sayisi.
Mutlak alarm sayisi tek basina karar degil.

## Set 1 ozet (yan yana)

| Kosul | b3 | b4 | b1 | b2 | siralama | bosluk | erken FP | b2/x C |
|---|---:|---:|---:|---:|---|---|---:|---:|
| per-kanal | 206 | 244 | 276 | 200 | hayir | - | 2 | 485 |
| havuzlu | 206 | 338 | 276 | 583 | evet | 11.7 saat | 0 | 0 |

## Set 1 karneleri

### Per-kanal (rs=42, n=2156)

Ilk arizali: **206**. Ilk saglikli: **200**.
Siralama: **hayir (saglikli 200, arizali 206)**.
Erken FP: **2**.

| Rulman | eksen | NASA | ilk W | ilk C | critical sayisi |
|---|---|---|---:|---:|---:|
| bearing_1 | x | saglikli | 276 | 282 | 67 |
| bearing_1 | y | saglikli | 542 | 512 | 160 |
| bearing_2 | x | saglikli | 235 | 200 | 485 |
| bearing_2 | y | saglikli | 200 | 218 | 149 |
| bearing_3 | x | ic bilezik | 214 | 230 | 1099 |
| bearing_3 | y | ic bilezik | 209 | 206 | 960 |
| bearing_4 | x | makara | 244 | 1438 | 238 |
| bearing_4 | y | makara | 885 | 957 | 21 |

| Rulman | NASA | ilk alarm (min x/y) |
|---|---|---:|
| bearing_1 | saglikli | 276 |
| bearing_2 | saglikli | 200 |
| bearing_3 | ic bilezik | 206 |
| bearing_4 | makara | 244 |

### Havuzlu 1600 (rs=42, n=2156)

Ilk arizali: **206**. Ilk saglikli: **276**.
Siralama: **evet (70 dosya / 11.7 saat once)**.
Erken FP: **0**.

| Rulman | eksen | NASA | ilk W | ilk C | critical sayisi |
|---|---|---|---:|---:|---:|
| bearing_1 | x | saglikli | 276 | 282 | 1 |
| bearing_1 | y | saglikli | 613 | 557 | 5 |
| bearing_2 | x | saglikli | 583 | - | 0 |
| bearing_2 | y | saglikli | 2152 | - | 0 |
| bearing_3 | x | ic bilezik | 412 | 416 | 381 |
| bearing_3 | y | ic bilezik | 206 | 739 | 244 |
| bearing_4 | x | makara | 421 | 1436 | 319 |
| bearing_4 | y | makara | 338 | 957 | 297 |

| Rulman | NASA | ilk alarm (min x/y) |
|---|---|---:|
| bearing_1 | saglikli | 276 |
| bearing_2 | saglikli | 583 |
| bearing_3 | ic bilezik | 206 |
| bearing_4 | makara | 338 |

## Set 2 (ADR-0008 referans: b1 W=447, lead 89.3 saat, FP=0)

Son dosya index 983; lead = (son - ilk W) * 10 dk.

| Kosul | b1 W | b1 C | lead W | etiketsiz FP | b2 ilk | b3 ilk | b4 ilk |
|---|---:|---:|---|---:|---:|---:|---:|
| per-kanal rs=0 | 447 | 538 | 89.3 saat | 0 | 711 | 537 | 635 |
| havuzlu 800 rs=0 | 945 | 934 | 6.3 saat | 1 | 979 | 537 | - |
| ADR-0008 IF+zarf | 447 | 538 | 89.3 saat | 0 | 711 | 537 | 635 |

## Hold-out yorumu (canli yok)

- Set 1 iyilesti ama Set 2 bozuldu. Canli havuzlama yok; ADR-0008 kilit.
- Set 1 b2/x critical: per-kanal 485 -> havuzlu 0.
- Set 1 havuzda b3 hâlâ 206 (warmup-kenari); b1 ilk alarm 276.
  Bosluk 11.7 saat — siralama evet ama Z-Score kadar temiz degil.
- Set 2 lead W: per-kanal 89.3 saat, havuzlu 6.3 saat (hedef 89.3 saat, ilk W 447).
- Set 2 etiketsiz FP: per-kanal 0, havuzlu 1.
- Havuz inlier'i genisletir: Set 1 dar-zarf FP'sini keser, Set 2 etiketli
  kanalin erken sapmasini yutar. Per-kanal Set 2 = ADR-0008 birebir.
- Esik retune yok. Canli `IsolationForestDetector` bu karne ile degismez.

