# IMS IF Set 1: canli same-domain vs offline transfer otopsi

Canli IF/esik/ADR-0008 degismez. Ham dosya cache; Kafka yok.
Set 1 `vibration_features` 4312 satir = 2156 * 2 oynatma; ilk index ilk tur.

## Protokol farki (esik/pencere ayni, model degil)

| | Offline transfer (iyi gorunen) | Canli Set 1 (gurultulu) |
|---|---|---|
| Egitim | Set 2 havuz (4*200=800) | her kanal kendi 200 |
| Test | ayni orman, Set 1 ham | ayni kanalin geri kalani |
| RobustScaler | 800 noktalik genis bulut | 200 noktalik dar kanal bulutu |
| random_state | 0 (kalibrasyon notebook) | 42 (detector default) |
| BASELINE / Wq/Cq / zarf | 200 / 0.995/0.999 / acik | ayni |
| IF RAM seed | - | Yok; yalniz Z-Score `load_baselines` |

xy karismaz: anahtar `(dataset, machine_id, axis)`. Canli Z-Score ilk index
offline `ims_set1_zscore.md` ile birebir (b3x W=755, b4x W=399, b2x W=2134).

## Canli DB (set1, detector=isolation_forest)

bearing_2 x: 970 critical, **ilk index 200** (ilk skorlanan snapshot).
934/970 `score_kind=extent`. b2 y ilk W=200. b3 y ilk C=206. Saglikli,
arizali ile ayni warmup-kenarinda; b2 x, b3'ten 6 dosya **once**.
970 mutlak sayi: her critical snapshot kayda gider (debounce yalniz Telegram);
iki tam oynatma sayiyi siser. Metrik ilk index'tir, count degil.

## Offline tekrar: canli protokol (per-kanal, rs=42, zarf acik)

| Kosul | b3 | b4 | b1 | b2 | siralama | bosluk | erken FP |
|---|---:|---:|---:|---:|---|---|---:|
| transfer (Set 2 ormani) | 1549 | 338 | - | 2155 | evet | 302.8 saat | 0 |
| same-domain per-kanal | 206 | 244 | 276 | 200 | hayir | - | 2 |

| Rulman | eksen | NASA | ilk W | ilk C | critical sayisi | kazanan skor |
|---|---|---|---:|---:|---:|---|
| bearing_1 | x | saglikli | 276 | 282 | 67 | extent 66 / if_score 1 |
| bearing_1 | y | saglikli | 542 | 512 | 160 | extent 51 / if_score 109 |
| bearing_2 | x | saglikli | 235 | 200 | 485 | extent 467 / if_score 18 |
| bearing_2 | y | saglikli | 200 | 218 | 149 | extent 149 / if_score 0 |
| bearing_3 | x | ic bilezik | 214 | 230 | 1099 | extent 421 / if_score 678 |
| bearing_3 | y | ic bilezik | 209 | 206 | 960 | extent 609 / if_score 351 |
| bearing_4 | x | makara | 244 | 1438 | 238 | extent 4 / if_score 234 |
| bearing_4 | y | makara | 885 | 957 | 21 | extent 20 / if_score 1 |

Zarf kapali (ayni per-kanal, rs=42): b2/x ilk alarm 235; b2/x critical 18.

## Warmup darligi (RobustScaler IQR = scale_)

IQR tek basina suc degil (b2/x ~ Set 2 havuz). Fark: per-kanal 0.999 extent
niceligi 200 ornekte neredeyse max; bir sonraki snapshot asar. Havuzlu orman
800 cok-rulman noktasinda daha genis inlier; Set 1 saglikli mutlak RMS o
bulutta kalir.

- Set 2 havuz warmup IQR: `rms=0.001639, kurtosis=0.1323, crest_factor=0.6786, peak=0.054`
- Set 1 b2/x warmup IQR: `rms=0.001461, kurtosis=0.1226, crest_factor=0.7312, peak=0.093`
- Set 1 b3/x warmup IQR: `rms=0.001572, kurtosis=0.1065, crest_factor=0.6271, peak=0.1155`

## Kaynak (ne degil)

- **Degil:** farkli BASELINE_WINDOW veya nicelik. Ikisi de 200 / 0.995/0.999.
- **Degil:** x/y karisimi. Z-Score canli = offline karnesi.
- **Degil:** ilk 200'un ariza ile kirlenmesi. NASA saglikli baslar; Z-Score
  b2'yi 2134'e kadar sessiz tutar. IF b2 200'de calar cunku zarf, o kanalin
  dar warmup max-norm'unu asmayi 'critical' sayar.
- **Olan:** canli IF same-domain per-kanal + RobustScaler + extent.
  Offline 'iyi' sonuc **baska model**: Set 2'nin genis mutlak-olcek ormani.
  Same-domain'in cross-domain'den kotu gorunmesi ters degil: per-kanal
  200 ornekte overfit; havuzlu Set 2 ormani saglikli Set 1'i tesadufen
  inlier birakir.
- b2/x ilk critical 200 (warmup bitisi). Tek tur critical=485; canli 970 ~ iki oynatma.
- Canli IF'e tasinacak 'duzeltme' yok; bu otopsi. Esik retune yok.

