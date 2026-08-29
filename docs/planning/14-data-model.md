# 14 — Veri Modeli (TimescaleDB)

Bu dosya, koda başlamadan önce veri katmanını kâğıt üstünde tasarlar: tablolar, sütunlar, indeksler, hypertable/continuous aggregate/retention politikaları. TimescaleDB'yi seçme gerekçemiz (ADR yok ama 01/04'te belirtildi) bu özellikleri gerçekten kullanmaktı — burada nasıl kullanılacağı somutlaşıyor.

## Tasarım İlkeleri
- **Ham titreşim noktaları DB'ye YAZILMAZ.** 20 kHz × sürekli akış = devasa hacim; DB'nin işi bu değil. DB, çıkarılmış **özellikleri** (features) ve **anomali olaylarını** saklar. Ham veri Kafka'da (kısa retention) kalır.
- **Zaman serisi tabloları hypertable'dır**; zamana göre otomatik partition'lanır (chunk — Kafka chunk'ıyla karıştırma, bu TimescaleDB'nin iç partition'ı).
- **En az yetki:** yazan servis INSERT, Grafana yalnız SELECT (bkz. 06).

## Tablolar

### 1. `vibration_features` (hypertable) — ana zaman serisi
Stream-processor'ın her (kısmi veya tam) snapshot'tan çıkardığı özellikler.

| Sütun | Tip | Açıklama |
|---|---|---|
| `time` | `TIMESTAMPTZ NOT NULL` | Özelliğin ait olduğu an (event `occurred_at`) |
| `machine_id` | `TEXT NOT NULL` | `bearing_1..4` |
| `axis` | `TEXT NOT NULL` | `x` / `y` |
| `dataset` | `TEXT NOT NULL` | `set1` / `set2`; eski satırlar `unknown` (ADR-0014) |
| `snapshot_id` | `UUID NOT NULL` | İzlenebilirlik (chunk reassembly kaynağı) |
| `rms` | `DOUBLE PRECISION` | Kök ortalama kare |
| `kurtosis` | `DOUBLE PRECISION` | Basıklık (erken arıza göstergesi) |
| `crest_factor` | `DOUBLE PRECISION` | Tepe/RMS oranı |
| `peak` | `DOUBLE PRECISION` | Mutlak tepe genlik |
| `fft_band_energy` | `JSONB` | BPFO/BPFI/BSF bant gücü (ADR-0010; teşhis yok). Eski satırlar NULL. |
| `is_complete` | `BOOLEAN NOT NULL` | Kısmi snapshot'tan mı geldi (bkz. 07) |
| `chunks_received` | `SMALLINT NOT NULL` | Kaç chunk'tan hesaplandı |

**Hypertable:** `SELECT create_hypertable('vibration_features', 'time');`
**Chunk aralığı:** `chunk_time_interval => INTERVAL '1 day'` (playback hızlı olsa da veri hacmi düşük; 1 gün makul).
**Birincil erişim deseni:** "son N dakikada machine_id=X'in kurtosis trendi" → indeks buna göre.

**İndeksler:**
- Otomatik: `time DESC` (hypertable varsayılanı)
- `CREATE INDEX ON vibration_features (machine_id, time DESC);`  — makine bazlı zaman sorguları
- `CREATE INDEX ON vibration_features (machine_id, axis, time DESC);` — eksen ayrımı gerekiyorsa
- `CREATE INDEX ON vibration_features (dataset, machine_id, axis, time DESC);` — set ayrımı (ADR-0014)

### 2. `anomaly_events` — anomali olayları
`AnomalyDetected` event'inin kalıcı kaydı. Seyrek olay; hypertable şart değil ama tutarlılık için zamana göre indekslenir.

| Sütun | Tip | Açıklama |
|---|---|---|
| `event_id` | `UUID PRIMARY KEY` | Idempotency anahtarı (bkz. 07) |
| `occurred_at` | `TIMESTAMPTZ NOT NULL` | Anomali anı |
| `machine_id` | `TEXT NOT NULL` | |
| `axis` | `TEXT` | |
| `dataset` | `TEXT NOT NULL` | `set1` / `set2`; eski satırlar `unknown` (ADR-0014) |
| `metric` | `TEXT NOT NULL` | Hangi özellik tetikledi (örn. `kurtosis`) |
| `value` | `DOUBLE PRECISION NOT NULL` | Özelliğin değeri |
| `z_score` | `DOUBLE PRECISION` | Katman 1 sapması; Katman 2 NULL (ADR-0009, 002) |
| `anomaly_score` | `DOUBLE PRECISION` | Katman 2 tetikleyen skor; Katman 1 ve eski satırlar NULL |
| `score_kind` | `TEXT` | `zscore` / `if_score` / `extent` / `pca_t2` / `pca_spe` / `river` |
| `severity` | `TEXT NOT NULL` | `warning` / `critical` |
| `is_complete` | `BOOLEAN NOT NULL` | Kısmi veriden mi (güven göstergesi) |
| `detector` | `TEXT NOT NULL` | `zscore` / `isolation_forest` / `pca` — hangi model buldu |
| `notified_at` | `TIMESTAMPTZ` | Bildirim gönderildiyse zamanı (NULL = henüz değil) |

**İdempotency:** `event_id` PK olduğu için aynı event iki kez INSERT edilemez (`ON CONFLICT (event_id) DO NOTHING`). Bu, notifier'ın çift bildirim önlemesiyle (07) DB seviyesinde tekrar eder — savunma derinliği.

### 3. `machine_baseline` — normal davranış referansı
Anomali tespiti için "normal"in ne olduğunu tutar (detaylı mantık 15-anomaly-design'da gelecek; şema burada).

| Sütun | Tip | Açıklama |
|---|---|---|
| `machine_id` | `TEXT` | |
| `axis` | `TEXT` | |
| `dataset` | `TEXT` | `set1` / `set2`; eski satırlar `unknown` |
| `metric` | `TEXT` | Örn. `rms`, `kurtosis` |
| `mean` | `DOUBLE PRECISION` | Baseline ortalama |
| `std` | `DOUBLE PRECISION` | Baseline standart sapma (Z-Score paydası) |
| `updated_at` | `TIMESTAMPTZ` | En son ne zaman güncellendi |
| PK | `(dataset, machine_id, axis, metric)` | Her set×rulman×eksen×metrik için tek satır |

## Continuous Aggregate (Materialized, otomatik yenilenen)

Grafana'nın "son 24 saatin dakikalık ortalama kurtosis'i" gibi sorgularını her seferinde ham `vibration_features`'tan hesaplamak yerine, TimescaleDB otomatik önceden hesaplar. CQRS'in hafif hali — okuma optimizasyonunu yazma yolunu bozmadan verir (01'de bahsedilen).

```sql
CREATE MATERIALIZED VIEW vibration_features_1min
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 minute', time) AS bucket,
  machine_id,
  axis,
  avg(rms)       AS avg_rms,
  max(kurtosis)  AS max_kurtosis,
  avg(crest_factor) AS avg_crest
FROM vibration_features
GROUP BY bucket, machine_id, axis;
```
**Yenileme politikası:** `add_continuous_aggregate_policy` ile örn. her 1 dakikada bir güncellenir.

## Sıkıştırma (Compression)

Eski `vibration_features` verisi otomatik sıkıştırılır — TimescaleDB'nin öne çıkan, disk kullanımını ciddi azaltan özelliği.
```sql
ALTER TABLE vibration_features SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'machine_id, axis'
);
SELECT add_compression_policy('vibration_features', INTERVAL '7 days');
```

## Retention (Veri Yaşam Süresi)

Ham özellik verisi sonsuza dek tutulmaz; continuous aggregate zaten özetliyor.
```sql
SELECT add_retention_policy('vibration_features', INTERVAL '30 days');
```
`anomaly_events` daha uzun tutulur (olaylar değerli, hacim düşük) — retention koymayabilir veya çok uzun tutabiliriz.

## Migration Stratejisi
- Şema, `infra/timescaledb/` altında sıralı SQL dosyaları olarak tutulur (`001_init.sql`, `002_score_kind.sql`, …).
- Basit tutulur (Alembic gibi bir araç bu proje için fazla); docker-compose ilk açılışta bu SQL'leri çalıştırır.
- Her migration idempotent yazılır (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`).

## Erişim Rolleri (06-security ile uyumlu)
```sql
-- yazan servis (stream-processor, notifier)
GRANT INSERT, SELECT ON vibration_features, anomaly_events, machine_baseline TO sentinel_writer;
-- Grafana yalnız okur
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sentinel_reader;
```

## ER İlişkisi (kavramsal)
- `vibration_features` ve `anomaly_events`, `machine_id`+`axis` üzerinden mantıksal olarak ilişkili (FK zorunlu değil — zaman serisinde FK genelde kullanılmaz, performans için).
- `snapshot_id`, bir özelliğin hangi reassembly'den geldiğini izlemeye yarar (debugging).
