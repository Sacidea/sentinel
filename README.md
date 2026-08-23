# Sentinel

Gerçek zamanlı endüstriyel titreşim anomali tespiti ve kestirimci bakım sistemi.

Fabrika rulmanlarından gelen titreşim verisini canlı bir akış olarak işleyerek, makine arızalanmadan önce istatistiksel ve makine öğrenmesi tabanlı erken uyarı üretir. Anomaliler bir bildirim kanalına iletilir ve canlı bir panoda görselleştirilir.

> **Durum:** Planlama ve tasarım aşaması tamamlandı; implementasyon başlangıç aşamasında. Tüm mimari ve tasarım kararları `docs/` altında belgelenmiştir.

## Ne Yapar

- **Ingestion:** NASA IMS Bearing titreşim veri seti, kontrollü hızda canlı bir akışa dönüştürülür (asyncio simülatör → Kafka).
- **İşleme:** Her titreşim penceresinden sinyal özellikleri (RMS, kurtosis, crest factor, FFT bant enerjisi) çıkarılır.
- **Anomali tespiti:** İki katman — (1) baseline'a göre Z-Score / hareketli ortalama (yorumlanabilir), (2) Isolation Forest / PCA / River (makine öğrenmesi).
- **Bildirim:** Anomali olayları Telegram üzerinden iletilir (Celery + circuit breaker).
- **Görselleştirme:** TimescaleDB + Grafana ile canlı pano.

## Mimari

Event-driven, gevşek bağlı servis mimarisi. Servisler birbirini doğrudan çağırmaz; iletişim Kafka event'leri üzerindendir.

```
Simulator ──► Kafka (sensor.vibration.raw) ──► Stream Processor ──┬──► TimescaleDB ──► Grafana
                                                                  │
                                          Kafka (anomaly.detected)◄┘──► Notifier ──► Telegram
```

Detaylar: [`docs/planning/01-architecture.md`](docs/planning/01-architecture.md)

## Teknoloji Yığını

| Katman | Teknoloji |
|---|---|
| Dil | Python 3.11+ (asyncio) |
| Akış omurgası | Apache Kafka (aiokafka) |
| Sinyal işleme | NumPy, SciPy, Pandas |
| Makine öğrenmesi | scikit-learn, PyOD, River |
| Depolama | TimescaleDB (PostgreSQL) |
| Bildirim | Celery + Redis + Telegram Bot API + pybreaker |
| Görselleştirme | Grafana |
| Konteyner | Docker + Docker Compose |
| Kod kalitesi | ruff, mypy, pre-commit, pytest |

## Dokümantasyon

Tüm planlama ve tasarım kararları konu bazında ayrı dosyalarda:

- **[Planlama dokümanları](docs/planning/README.md)** — mimari, veri modeli, anomali tasarımı, test stratejisi, güvenlik, dayanıklılık, yol haritası (16 dosya)
- **[Karar kayıtları (ADR)](docs/adr/README.md)** — önemli mimari kararların gerekçeli kayıtları
- **[AGENTS.md](AGENTS.md)** — AI kodlama ajanları için proje kuralları

Başlıca dosyalar:

| Konu | Dosya |
|---|---|
| Mimari | [`01-architecture.md`](docs/planning/01-architecture.md) |
| Veri kaynağı & ML | [`02-data-and-ml.md`](docs/planning/02-data-and-ml.md) |
| Servis tasarımı & SOLID | [`03-service-design.md`](docs/planning/03-service-design.md) |
| Veri modeli | [`14-data-model.md`](docs/planning/14-data-model.md) |
| Anomali tasarımı | [`15-anomaly-design.md`](docs/planning/15-anomaly-design.md) |
| Yol haritası | [`10-roadmap-and-dod.md`](docs/planning/10-roadmap-and-dod.md) |

## Kurulum (planlanan)

> Servisler henüz implemente ediliyor. Hedeflenen akış:

```bash
# 1. Ortam değişkenlerini hazırla
cp templates/.env.example .env
# .env içindeki TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID alanlarını doldur

# 2. Tüm stack'i ayağa kaldır
make up          # docker compose up -d --build

# 3. Testler
make test        # veya: make test-unit
```

Konfigürasyon şablonları (`pre-commit`, `pyproject.toml`, `Makefile`, CI) `templates/` altındadır.

## Veri Kaynağı

NASA IMS Bearing Dataset — 20 kHz örnekleme ile gerçek ivmeölçer (titreşim) sinyali, run-to-failure test verisi. Seçim gerekçesi: [`docs/adr/0003-ims-over-cmapss.md`](docs/adr/0003-ims-over-cmapss.md)

## Yol Haritası

- **Hafta 0.5:** Proje iskeleti, walking skeleton, contracts
- **Hafta 1:** Ingestion (simülatör → Kafka)
- **Hafta 2:** İşleme, anomali tespiti, bildirim
- **Hafta 3:** Görselleştirme, dokümantasyon

Detay: [`docs/planning/10-roadmap-and-dod.md`](docs/planning/10-roadmap-and-dod.md)

## Lisans

Belirlenecek.
