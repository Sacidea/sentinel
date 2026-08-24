# Grafana

Walking skeleton panosu kod olarak provision edilir (`docs/planning/13-pre-coding-checklist.md` adım 5).

- Datasource: `provisioning/datasources/timescaledb.yaml` (`uid: sentinel-timescaledb`)
- Dashboard: `provisioning/dashboards/json/vibration-features.json`

`make up` sonrası: http://localhost:3000 (varsayılan `admin` / `admin`) → klasör **Sentinel** → **Vibration Features**.

İskelet aşamasında RMS/kurtosis `0.0` görünür; amaç satırların simülatör → Kafka → processor → DB → Grafana zincirinde aktığını doğrulamaktır.
