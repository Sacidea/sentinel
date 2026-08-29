-- Sentinel — TimescaleDB şema (migration 003)
-- ADR-0014: dataset sütunu Set 1 / Set 2 serilerini ayırır.
-- docker-entrypoint-initdb.d yalnız boş volume'da çalışır; mevcut DB için
-- bu dosya psql ile ayrıca uygulanır (idempotent).

ALTER TABLE IF EXISTS vibration_features
    ADD COLUMN IF NOT EXISTS dataset TEXT NOT NULL DEFAULT 'unknown';

ALTER TABLE IF EXISTS anomaly_events
    ADD COLUMN IF NOT EXISTS dataset TEXT NOT NULL DEFAULT 'unknown';

ALTER TABLE IF EXISTS machine_baseline
    ADD COLUMN IF NOT EXISTS dataset TEXT NOT NULL DEFAULT 'unknown';

ALTER TABLE IF EXISTS machine_baseline
    DROP CONSTRAINT IF EXISTS machine_baseline_pkey;

ALTER TABLE IF EXISTS machine_baseline
    ADD PRIMARY KEY (dataset, machine_id, axis, metric);

CREATE INDEX IF NOT EXISTS idx_vf_dataset_machine_axis_time
    ON vibration_features (dataset, machine_id, axis, time DESC);

CREATE INDEX IF NOT EXISTS idx_ae_dataset_machine_time
    ON anomaly_events (dataset, machine_id, occurred_at DESC);
