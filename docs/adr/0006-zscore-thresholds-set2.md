# ADR-0006: Z-Score Eşikleri 5.0 / 8.0 (IMS Set 2 Kalibrasyonu)

- **Durum:** Kabul edildi
- **Tarih:** 2026-08-25

## Bağlam

Katman 1 varsayılanları klasik istatistikten geliyordu: warning `|z|≥3`, critical `|z|≥5`
(`.env` / `docker-compose` / `config.py`). Bu eşikler sentetik gürültü ve "3σ kuralı" için
makuldü; NASA IMS Set 2'nin sağlıklı bölgesinde değil.

Set 2 README (NASA Ames PCoE / University of Cincinnati IMS):

- Kayıt: 12 Şubat 2004 10:32:39 — 19 Şubat 2004 06:22:39; 984 dosya; 10 dk aralık.
- Arıza duyurusu: *"At the end of the test-to-failure experiment, outer race failure
  occurred in bearing 1."*
- Başka rulman için hasar duyurulmaz. Başlangıç (incipient) timestamp'i **yok**.

Bu yüzden lead time çapanı son dosyadır (index 983, `2004.02.19.06.22.39`) — `02-data-and-ml.md`
zaten RUL etiketini "son dosya = arıza anı" diye tanımlar. RMS eğrisinde ~index 700'de
görülen yükseliş göz kararıdır; NASA metninde yoktur, lead time hesabına girmez.

Ham `|z|≥3` (ve MA=5 ile yumuşatılmış 3.0 eşiği) etiketlenmemiş `bearing_2`'de index 351'de
çalar; spike grafiğinde kanal hâlâ düzdür. Canlı boru bu ölçekte yanlış pozitif üretir (R4).

## Karar

IMS Set 2 üzerinde, üretimdeki detector (`ZScoreDetector`, `MA_WINDOW=5`) ile tarama
(`ml/notebooks/ims_set2_zscore_calibration.md`):

| Eşik | Etiketsiz FP | bearing_1 ilk warning | Lead time (son dosyaya) |
|---|---:|---:|---|
| 3.0 / 5.0 | 13 (`bearing_2` @ 351) | 534 | 74.8 saat |
| **5.0 / 8.0** | **0** | **536** | **74.5 saat** |

**Seçilen varsayılan:** `ANOMALY_ZSCORE_WARNING=5.0`, `ANOMALY_ZSCORE_CRITICAL=8.0`.

FP tanımı: NASA'nın hasar duyurmadığı kanallarda (`bearing_2/3/4`), etiketli kanalın
(`bearing_1`) ilk uyarısından önceki alarm. Lead time: `(983 - ilk_warning) * 10 dk`.

3.0/5.0'a göre ~0.3 saat lead kaybı, etiketsiz FP 13→0. Daha yüksek eşikler (8/12 …)
FP'yi iyileştirmez, lead time'ı kısaltır.

Kod tek kaynak: `DEFAULT_ZSCORE_WARNING` / `DEFAULT_ZSCORE_CRITICAL` (`domain/detectors.py`);
`config.py`, `.env.example`, compose varsayılanları buradan/aynı değerlerden okunur.

## Alternatifler

- **3.0 / 5.0'ı korumak:** Klasik kural; Set 2 sağlıklı RMS std'si ~0.001 olduğu için
  mutlak olarak minik kaymalar 3σ'ya değer. `bearing_2` erken alarmı kabul edilemez.
- **8.0 / 12.0 veya daha sıkı:** Aynı FP=0, bearing_1 uyarısı 554'e kayar (~71.5 saat).
  Kazanılacak FP yok; erken uyarı kısılır.
- **Set'ten bağımsız evrensel eşik iddiası:** Set 1 (bearing 3/4, farklı kanal/std) ve
  Set 3 (bearing 3 dış bilezik, ~31 gün) aynı sayıların geçerli olduğunu göstermez.
  Kalibrasyon Set 2'ye özeldir.

## Sonuçlar

(+) Plan (`15-anomaly-design.md`) ile çalışan varsayılanlar aynıdır; 3.0/5.0 artık
dokümanda "eski klasik kural, Set 2'de elendi" olarak durur.
(+) Lead time NASA'nın duyurduğu arıza anına (test sonu) bağlıdır, eğriye bakarak
seçilmiş bir index'e değil.
(−) 5.0/8.0 **yalnız Set 2** üzerinde ölçülmüştür. Başka sete veya makineye geçilirse
yeniden tarama gerekir — aksi halde eşikler o dağılıma overfit kalır.
(−) NASA incipient an vermediği için "görünür bozulma" (~index 700) yalnızca nitel
gözlem olarak spike notunda kalır; metrik değildir.
