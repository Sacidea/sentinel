# ADR-0009: Anomali skor alanlarının ayrılması (`schema_version` 1 → 2)

- **Durum:** Kabul edildi
- **Tarih:** 2026-08-28
- **İlgili:** ADR-0006 (Z-Score 5.0/8.0), ADR-0008 (IF nicelik 0.995/0.999)

## Bağlam

`AnomalyDetected.z_score` Katman 1 sapması (`(x-μ)/σ`) için tasarlandı. Katman 2
IsolationForest aynı alana `-decision_function` (~0.01) veya ölçeklenmiş max-norm
zarfı (~8) yazıyordu. Grafana/Telegram ikisini 5.0/8.0 cetvelinde okuyordu;
`0.014 warning` ile `8.65 critical` aynı sütunda karşılaştırılamaz hale geldi.

## Karar

1. **`schema_version` 2.** `AnomalyDetected`'a `anomaly_score: float | None` ve
   `score_kind` eklenir. Üretici (stream-processor) v2 yazar.
2. **`z_score` yalnız Katman 1.** `detector='zscore'` → `z_score` dolu,
   `anomaly_score` NULL, `score_kind='zscore'`.
3. **Katman 2 `z_score` yazmaz.** IF/PCA/River `anomaly_score` + `score_kind`
   doldurur; `z_score` NULL. IF'de zarf kazanırsa `extent`, aksi halde `if_score`.
4. **`score_kind` değerleri.** İstenen üçlü (`zscore` / `if_score` / `extent`)
   IF ile Z-Score'u ayırır. Aynı tabloya yazan PCA ve River için
   `pca_t2` / `pca_spe` / `river` eklenir — aksi halde PCA `if_score` diye yalan
   söyler. Severity hâlâ detector niceliğinden gelir; bu alanlar etikettir.
5. **Timescale `002_score_kind.sql`.** `anomaly_score` ve `score_kind` nullable.
   Mevcut satırlar NULL kalır. `z_score` NOT NULL kalkar (Katman 2 NULL yazar).
   `docker-entrypoint-initdb.d` yalnız boş volume'da çalışır; canlı DB'ye SQL
   ayrıca uygulanır.
6. **v1 Kafka kalıntısı (geriye uyum).** `anomaly_score` ve `score_kind` opsiyonel
   (`None` varsayılan). Eski gövde bu anahtarları taşımaz; parse kırılmaz.
   `score_kind` yoksa `detector`'dan türetilir (`zscore` / `if_score` / `pca_*` /
   `river`). v1 IF skoru `z_score` alanındadır; `reported_score()` oraya düşer.
   Yeni üretici v2 yazar (`z_score` Katman 2'de NULL).

Kod: `libs/contracts` `ANOMALY_SCHEMA_VERSION=2`; notifier
`format_alert_text`; Grafana `COALESCE(anomaly_score, z_score)`.

## Alternatifler

- **`z_score` adını koruyup IF skorunu oraya yazmak:** Canlı log karışıklığının
  kaynağı; elendi.
- **Tek `score` + `score_kind`:** Katman 1 okuyucuları (`z_score` sütunu) kırar;
  v1 satırlarıyla COALESCE daha ucuz.
- **PCA/River'ı Literal'dan çıkarmak:** PCA zaten `anomaly_events`'e yazıyor;
  `if_score` etiketi yanlış olur.

## Sonuçlar

(+) IF warning `if_score=0.014` ile zarf `extent=8.65` aynı sütunda Z-Score
sanılmaz.
(+) Eski satırlar okunur (`z_score` dolu, yeni sütunlar NULL).
(−) v1 üretici + v2 consumer: `score_kind` türetilir; v2 üretici + v1 consumer
`anomaly_score`'u yok sayar — notifier birlikte deploy edilmeli.
(−) Grafana tek eksende IF skoru ile zarfı hâlâ karıştırabilir; legend
`score_kind` ile ayrılır, ortak ölçek iddiası yoktur.
