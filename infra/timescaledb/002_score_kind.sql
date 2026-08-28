-- Sentinel — TimescaleDB şema (migration 002)
-- ADR-0009: skor alanlarını ayır. z_score yalnız Katman 1 (Z-Score).
-- Katman 2 IF/PCA/River anomaly_score + score_kind yazar; z_score NULL kalır.
-- docker-entrypoint-initdb.d yalnız boş volume'da çalışır; mevcut DB için
-- bu dosya psql ile ayrıca uygulanır (idempotent).

ALTER TABLE IF EXISTS anomaly_events
    ADD COLUMN IF NOT EXISTS anomaly_score DOUBLE PRECISION;

ALTER TABLE IF EXISTS anomaly_events
    ADD COLUMN IF NOT EXISTS score_kind TEXT;

-- 001_init z_score'u NOT NULL açtı. Katman 2 artık yazmaz.
ALTER TABLE IF EXISTS anomaly_events
    ALTER COLUMN z_score DROP NOT NULL;
