# 09 — Repo Yapısı

```
iiot-anomaly-detection/
├── AGENTS.md                     # AI ajan talimatları (CLAUDE.md karşılığı)
├── README.md
├── pyproject.toml                # workspace geneli araç config
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── Makefile
├── .github/workflows/ci.yml
├── libs/
│   └── contracts/                # paylaşılan event şemaları (pydantic)
│       ├── src/contracts/events.py
│       └── tests/
├── services/
│   ├── simulator/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/simulator/{domain,application,ports,infrastructure}/
│   │   │   ├── config.py  logging.py  __main__.py
│   │   └── tests/{unit,integration}/
│   ├── stream-processor/         # aynı iç yapı
│   │   └── src/stream_processor/
│   │       ├── domain/           # features.py, detectors.py (SAF)
│   │       ├── ports/            # MessageConsumer, ..., AnomalyDetector
│   │       └── infrastructure/   # kafka_consumer.py, timescale_repo.py, ml_detector.py
│   ├── notifier/                 # aynı iç yapı (telegram_notifier.py + pybreaker)
│   └── dashboard/                # opsiyonel FastAPI + WebSocket
├── ml/
│   ├── notebooks/                # keşifsel analiz
│   ├── training/                 # offline eğitim scriptleri
│   └── models/                   # eğitilmiş artefaktlar (git-lfs / .gitignore)
├── infra/
│   ├── grafana/                  # dashboard JSON (kod olarak)
│   └── timescaledb/              # şema/migration SQL
├── templates/                    # config şablonları (bu repoda docs amaçlı)
└── docs/
    ├── planning/                 # bu klasör
    ├── adr/                      # karar kayıtları
    └── architecture.py           # diagrams ile şema
```

`libs/contracts` ayrı paket → üç servis de aynı event tanımını import eder, kopyalamaz (DRY).
