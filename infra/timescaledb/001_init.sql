-- Sentinel — TimescaleDB şema (migration 001)
-- Plan: docs/planning/14-data-model.md

-- TimescaleDB uzantısını etkinleştir (imajda kurulu, sadece aktive ediyoruz)
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- =====================================================================
-- 1. vibration_features — ana zaman serisi (çıkarılan özellikler)
-- =====================================================================
CREATE TABLE IF NOT EXISTS vibration_features (
    time            TIMESTAMPTZ       NOT NULL,
    machine_id      TEXT              NOT NULL,
    axis            TEXT              NOT NULL,
    dataset         TEXT              NOT NULL DEFAULT 'unknown',
    snapshot_id     UUID              NOT NULL,
    rms             DOUBLE PRECISION,
    kurtosis        DOUBLE PRECISION,
    crest_factor    DOUBLE PRECISION,
    peak            DOUBLE PRECISION,
    fft_band_energy JSONB,
    is_complete     BOOLEAN           NOT NULL,
    chunks_received SMALLINT          NOT NULL
);

-- Hypertable'a çevir (zaman bazlı otomatik partition)
SELECT create_hypertable('vibration_features', 'time', if_not_exists => TRUE);

-- İndeksler (makine bazlı zaman sorguları için)
CREATE INDEX IF NOT EXISTS idx_vf_machine_time
    ON vibration_features (machine_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_vf_machine_axis_time
    ON vibration_features (machine_id, axis, time DESC);
CREATE INDEX IF NOT EXISTS idx_vf_dataset_machine_axis_time
    ON vibration_features (dataset, machine_id, axis, time DESC);

-- =====================================================================
-- 2. anomaly_events — anomali olayları (idempotency: event_id PK)
-- =====================================================================
CREATE TABLE IF NOT EXISTS anomaly_events (
    event_id     UUID              PRIMARY KEY,
    occurred_at  TIMESTAMPTZ       NOT NULL,
    machine_id   TEXT              NOT NULL,
    axis         TEXT,
    dataset      TEXT              NOT NULL DEFAULT 'unknown',
    metric       TEXT              NOT NULL,
    value        DOUBLE PRECISION  NOT NULL,
    z_score      DOUBLE PRECISION  NOT NULL,
    severity     TEXT              NOT NULL,
    is_complete  BOOLEAN           NOT NULL,
    detector     TEXT              NOT NULL,
    notified_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ae_machine_time
    ON anomaly_events (machine_id, occurred_at DESC);

-- =====================================================================
-- 3. machine_baseline — normal davranış referansı (Z-Score mean/std)
-- =====================================================================
CREATE TABLE IF NOT EXISTS machine_baseline (
    machine_id  TEXT              NOT NULL,
    axis        TEXT              NOT NULL,
    dataset     TEXT              NOT NULL DEFAULT 'unknown',
    metric      TEXT              NOT NULL,
    mean        DOUBLE PRECISION,
    std         DOUBLE PRECISION,
    updated_at  TIMESTAMPTZ,
    PRIMARY KEY (dataset, machine_id, axis, metric)
);