# ADR-0008: Katman 2 IF nicelik eşikleri 0.995 / 0.999 (IMS Set 2)

- **Durum:** Kabul edildi
- **Tarih:** 2026-08-26
- **İlgili:** ADR-0006 (Z-Score 5.0/8.0), ADR-0007 (FFT ertelemesi durur; eşik borcu kapanır)

## Bağlam

Katman 2 eşikleri birim testi yeşile çekmek için `max + 0.5 * yayılım` gibi çarpanlara
bağlıydı. ADR-0007 bunu kalibrasyon saymama kararıydı. Aynı Set 2 protokolü
(lead time = son dosyaya, etiketsiz FP = bearing_2/3/4 ve bearing_1 ilk uyarısından
önce) IsolationForest ve PCA için `ml/notebooks/ims_set2_ml_calibration.md` ile
koşuldu. 984 gerçek dosya; sentetik vektör yok.

## Karar

1. **Eşik = warmup eğitim skorunun niceliği.** `score > q`. 0.5 / 0.25 / 1e-3 yok.
2. **IsolationForest varsayılanı 0.995 / 0.999**, ölçeklenmiş max-norm zarf açık
   (`use_extent=True`). **Yalnız IMS Set 2** üzerinde tarandı; başka sete taşınmaz.
   Set 2 karnesi: bearing_1 ilk warning **447**, lead **89.3 saat**, etiketsiz **FP=0**.
   Critical 538 (Z-Score warning 536'ya yakın).
3. **0.90–0.99 nicelik seçilmez.** bearing_1 204–217'de (ısınma + ~15 dosya) çalar;
   127 saat lead sahte erken alarmdır; FP=0 pencere kısalığındandır.
4. **PCA aynı nicelikte etiketsiz FP=3** (`bearing_3` @ 236). Z-Score'un 3.0/5.0'ı
   eleme gerekçesi. Tespit ve `anomaly_events` kaydı durur (`detector='pca'`);
   Kafka/Telegram'a **çıkmaz**. Bildirim yalnız `zscore` ve `isolation_forest`
   (`NOTIFY_DETECTORS`).
5. **Bu nicelikler yalnız IMS Set 2'ye kalibre edilmiştir.** Set 1, Set 3 veya başka
   makine/dağılımda 0.995/0.999 geçerli sayılmaz — ADR-0006 ile aynı overfitting
   sınırı; yeni sette `ims_set2_ml_calibration.py` eşdeğeri yeniden çalıştırılmalıdır.
6. FFT hâlâ yok (ADR-0007). River taranmadı; kayıt edebilir, Telegram'a çıkmaz.

Kod: `DEFAULT_ML_WARNING_QUANTILE` / `DEFAULT_ML_CRITICAL_QUANTILE`; `config.py`,
`.env.example`, compose.

## Alternatifler

- **0.99 / 0.999:** Lead 127.7 saat, FP=0 — ısınma artığı; elendi.
- **IF zarfsız 0.995 / 0.999:** FP=0, lead 87.5 saat; critical 761 (geç). Zarf
  critical'i 538'e çeker.
- **IF 0.999 / 0.999:** Lead 74.2 saat (Z-Score ile neredeyse eşit), FP=1.
- **PCA'yı tamamen kapatmak:** Karşılaştırma için `detector='pca'` kaydı faydalı;
  Telegram yolu kapatıldı, skorlama durur.
- **PCA'yı Telegram'a almak:** FP=3; elendi.

## Sonuçlar

| Model | lead | vs Z-Score 74.5 saat | etiketsiz FP |
|---|---|---|---:|
| Z-Score 5.0/8.0 | 74.5 saat | referans | 0 |
| IF+zarf 0.995/0.999 | 89.3 saat | 14.8 saat daha erken | 0 |
| PCA 0.995/0.999 | 97.5 saat | 23.0 saat daha erken | 3 |

(+) IF, Z-Score ile aynı FP tanımında 0 kalır ve ~15 saat daha erken uyarır
(çok değişkenli zaman-alanı; FFT yok).
(−) Yalnız Set 2. 447, Z-Score 536'dan erken; "daha doğru arıza anı" kanıtı değil,
daha erken eşik aşımıdır. Set 1/3 veya başka veri **yeniden kalibrasyon** ister.
(−) PCA FP=3; Telegram'a gitmez, DB'de kalır.
(−) Birim testler hâlâ sentetiktir. Karnesi bu ADR + kalibrasyon markdown'ıdır.
