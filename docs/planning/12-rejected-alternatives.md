# 12 — Elenen Alternatifler

| Konu | Alternatif | Seçilen | Gerekçe (detay) |
|---|---|---|---|
| Veri seti | C-MAPSS, CWRU | NASA IMS Bearing | Ham titreşim + run-to-failure (02) |
| Akış omurgası | Redis Streams | Apache Kafka | Partition/replay + standart (01) |
| Depolama | Vanilla PostgreSQL | TimescaleDB | Zaman serisi optimizasyonu (01/03) |
| Görselleştirme | Streamlit | Grafana | IIoT/SCADA standardı |
| Mimari stil | Tam mikroservis | Event-driven servis | 3 haftalık ROI (01) |
| ML çekirdek | LSTM / CNN | Isolation Forest + PCA + River | Az sekans, yorumlanabilirlik (02) |
| Z-Score eşiği | Klasik 3.0/5.0 | 5.0/8.0 (Set 2) | Etiketsiz FP 13→0, lead ~74.5 saat (ADR-0006) |
| Lint/format | black+flake8+isort | ruff | Tek araç, hızlı (04) |
| Servis içi yapı | Düz (tek dosya) | Katmanlı (ports & adapters) | SOLID + test (03) |

Bu kararlar `docs/adr/` altında atomik ADR'ler olarak da tutulur.
