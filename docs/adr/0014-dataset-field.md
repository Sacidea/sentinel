# ADR-0014: `dataset` alanı — Set 1 ve Set 2 aynı sistemde karışmaz

- **Durum:** Kabul edildi
- **Tarih:** 2026-08-29
- **İlgili:** ADR-0003 (IMS), ADR-0009 (`schema_version` 2 skor alanları)

## Bağlam

Set 2 tek eksen (`bearing_N`/`x`) ve Set 1 çift eksen aynı `machine_id` değerlerini
kullanır. Detector state ve `machine_baseline` `(machine_id, axis)` ile anahtarlanınca
Set 2'nin donmuş x baseline'ı Set 1 x'ini skorlar; y yeni key olduğu için ısınır.
İki seti aynı Kafka/Timescale/Grafana yığınında tutmak için kimlik `dataset` olmalı.

## Karar

1. **Event alanı `dataset: str`.** `RawVibrationWindow`, `VibrationFeatures`,
   `AnomalyDetected`. Eski gövdede yoksa `"unknown"`. `AnomalyDetected.schema_version`
   2 → 3; ham/özellik şemaları 1 → 2.
2. **Simülatör `DATASET_NAME`.** `set1` / `set2`. `DATASET_PATH` ile tutarlı
   (`1st_test`/`ims_set1` → set1, `/ims` veya `2nd_test` → set2).
3. **Tespit state `(dataset, machine_id, axis)`.** Z-Score, IsolationForest, PCA,
   River. `machine_baseline` PK `(dataset, machine_id, axis, metric)`.
4. **Timescale `003_dataset.sql`.** `ADD COLUMN IF NOT EXISTS`; mevcut satırlar
   `'unknown'`. `docker-entrypoint-initdb.d` yalnız boş volume'da çalışır; canlı
   DB'ye SQL ayrıca uygulanır (ADR-0009 `002_score_kind` dersi).
5. **Grafana `$dataset` değişkeni.** Paneller `WHERE dataset = '$dataset'`.

Partition anahtarı `machine_id` kalır (ADR-0004). `dataset` reassembly/tespit
ayrımı içindir, Kafka partition için değil.

## Alternatifler

- **Ayrı Kafka topic / consumer group / Postgres şema.** Daha ağır; aynı
  walking-skeleton yığınında iki seti karşılaştırmayı zorlaştırır.
- **`machine_id`'ye set öneki** (`set1_bearing_1`). Event/Grafana/NASA adlarını
  bozar; eksen hâlâ ayrı.

## Sonuçlar

Set değiştirince process restart + doğru `DATASET_NAME` ile baseline karışmaz.
Eski satırlar `unknown` kalır; yeni playback `set1`/`set2` yazar. Grafana'da
eski run'ı görmek için değişkeni `unknown` seç.
