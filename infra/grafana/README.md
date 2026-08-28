# Grafana

Walking skeleton panosu kod olarak provision edilir (`docs/planning/13-pre-coding-checklist.md` adım 5).

- Datasource: `provisioning/datasources/timescaledb.yaml` (`uid: sentinel-timescaledb`)
- Dashboard: `provisioning/dashboards/json/vibration-features.json`

`make up` sonrası: http://localhost:3000 (varsayılan `admin` / `admin`) → klasör **Sentinel** → **Vibration Features**.

Anomali panosu `anomaly_events` okur: Katman 1 `z_score`, Katman 2 `anomaly_score` + `score_kind` (ADR-0009). Eski satırlarda `score_kind` NULL olabilir; grafik `COALESCE(anomaly_score, z_score)` kullanır.

BPFO panosu `fft_band_energy->>'bpfo'` okur (ADR-0010). Eski satırlarda JSONB NULL kalır; **teşhis/alarm yok**.

İskelet aşamasında RMS/kurtosis `0.0` görünür; amaç satırların simülatör → Kafka → processor → DB → Grafana zincirinde aktığını doğrulamaktır.
