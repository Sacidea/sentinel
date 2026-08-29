# Sentinel

Gerçek zamanlı endüstriyel titreşim anomali tespiti ve kestirimci bakım sistemi.

Fabrika rulmanlarından gelen titreşim verisini canlı bir akış olarak işleyerek, makine arızalanmadan önce istatistiksel ve makine öğrenmesi tabanlı erken uyarı üretir. Anomaliler Telegram üzerinden bildirilir ve canlı bir Grafana panosunda görselleştirilir.

> **Durum:** Çalışır durumda. Gerçek NASA IMS Set 2 verisiyle uçtan uca test edildi; dört detektörlü anomali tespiti canlı akışta çalışıyor.

## Sonuçlar (NASA IMS Set 2, gerçek veri)

Set 2'de arızalanan rulman **bearing_1** (dış bilezik arızası, NASA etiketli). Sistem bu rulmanı, arızadan **çok önce** ve düşük yanlış pozitif oranıyla yakaladı.

**Katman karşılaştırması (984 gerçek Set 2 dosyası):**

| Detektör | bearing_1 ilk alarm | Lead time (arıza öncesi) | Yanlış pozitif |
|---|---:|---|---:|
| Z-Score (5.0/8.0) | index 536 | 74.5 saat | 0 |
| **Isolation Forest (seçilen)** | **index 447** | **89.3 saat** | **0** |
| PCA (Hotelling's T²) | index 398 | 97.5 saat | 3 |

Isolation Forest, Z-Score'a göre ~15 saat daha erken uyardı, aynı sıfır yanlış pozitifle. PCA daha erken ama 3 yanlış pozitif ürettiği için birincil katman seçilmedi (detay: `docs/adr/0008-*`).

**Anomali dağılımı:** Tespit edilen anomalilerin **%97.5'i arızalı bearing_1'de** yoğunlaştı; sağlıklı rulmanlarda (bearing_2/3/4) yanlış pozitif oranı çok düşük — sistem doğru rulmanı ayırt ediyor.

## Ne Yapar

- **Ingestion:** NASA IMS Bearing titreşim verisi, kontrollü hızda canlı akışa dönüştürülür (asyncio simülatör → Kafka). Her snapshot 8 chunk'a bölünür; stream-processor bunları `machine_id` bazında yeniden birleştirir (stateful reassembly).
- **İşleme:** Her titreşim penceresinden sinyal özellikleri (RMS, kurtosis, crest factor, peak) çıkarılır.
- **Anomali tespiti — dört detektör, canlı:**
  - **Z-Score / hareketli ortalama** — baseline'a göre sapma (yorumlanabilir, birincil bildirim katmanı)
  - **Isolation Forest** — ağaç tabanlı, ölçeklenmiş zarf skoru
  - **PCA + Hotelling's T²** — çok değişkenli süreç izleme
  - **River (HalfSpaceTrees)** — çevrimiçi/artımlı öğrenme
  - Her detektörün skoru `score_kind` ile ayrı etiketlenir (`zscore`, `if_score`/`extent`, `pca_t2`, `river`).
- **Bildirim:** Anomaliler Telegram'a iletilir (Celery + circuit breaker). Yalnız `zscore` ve `isolation_forest` yayımlanır; PCA/River kayda geçer ama bildirilmez.
- **Görselleştirme:** TimescaleDB + Grafana ile canlı pano (RMS, kurtosis trendleri).

## Mimari

Event-driven, gevşek bağlı servis mimarisi. Servisler birbirini doğrudan çağırmaz; iletişim Kafka event'leri üzerindendir.

```
Simulator ──► Kafka (sensor.vibration.raw) ──► Stream Processor ──┬──► TimescaleDB ──► Grafana
                                                                  │
                                    Kafka (anomaly.detected) ◄────┴──► Notifier ──► Telegram
```

Kafka topic'leri: `sensor.vibration.raw` (4 partition = 4 rulman), `sensor.vibration.features`, `anomaly.detected`, `anomaly.dlq`. Detay: [`docs/planning/01-architecture.md`](docs/planning/01-architecture.md)

## Teknoloji Yığını

| Katman | Teknoloji |
|---|---|
| Dil | Python 3.11+ (asyncio) |
| Akış omurgası | Apache Kafka (aiokafka, KRaft mode) |
| Sinyal işleme | NumPy, SciPy, Pandas |
| Makine öğrenmesi | scikit-learn, River |
| Depolama | TimescaleDB (PostgreSQL, hypertable) |
| Bildirim | Celery + Redis + Telegram Bot API + pybreaker |
| Görselleştirme | Grafana |
| Konteyner | Docker + Docker Compose |
| Kod kalitesi | ruff, mypy, pytest |

## Kurulum

```bash
# 1. Ortam değişkenlerini hazırla
cp .env.example .env
# .env içindeki TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID alanlarını doldur

# 2. Altyapıyı ayağa kaldır (Kafka, TimescaleDB, Redis, Grafana)
docker compose up -d --build

# 3. NASA IMS verisini `data/` altına yerleştir
#    Set 2 (tek eksen): data/ims veya data/ims/2nd_test
#      → DATASET_PATH=/data/ims  DATASET_NAME=set2
#    Set 1 (çift eksen): data/ims_set1/1st_test
#      → DATASET_PATH=/data/ims_set1/1st_test  DATASET_NAME=set1
#    (indirme: https://phm-datasets.s3.amazonaws.com/NASA/4.+Bearings.zip)

# 4. Testler
pytest
```

Grafana panosu `http://localhost:3000` adresinde çalışır.

## Dokümantasyon

Tüm planlama ve tasarım kararları konu bazında ayrı dosyalarda:

- **[Planlama dokümanları](docs/planning/README.md)** — mimari, veri modeli, anomali tasarımı, test stratejisi, güvenlik, dayanıklılık, yol haritası
- **[Karar kayıtları (ADR)](docs/adr/README.md)** — önemli mimari kararların gerekçeli kayıtları
- **[AGENTS.md](AGENTS.md)** — AI kodlama ajanları için proje kuralları

## Veri Kaynağı

NASA IMS Bearing Dataset — 20 kHz örnekleme ile gerçek ivmeölçer (titreşim) sinyali, run-to-failure test verisi. Seçim gerekçesi: [`docs/adr/0003-ims-over-cmapss.md`](docs/adr/0003-ims-over-cmapss.md)

## Bilinen Sınırlamalar ve Gelecek İş

Bunlar bilinçli kapsam kararlarıdır, ADR'lerde kayıtlıdır:

- **FFT bant enerjisi** hesaplanır (`bpfo`/`bpfi`/`bsf`, ZA-2115 merkezleri) ve
  `fft_band_energy` JSONB'ye yazılır. **Teşhis/alarm yok** — Z-Score/IF vektörüne
  girmez (ADR-0010). Ham-rFFT ve envelope teşhis denendi: ikisi de Set 2'de 4/4,
  Set 1 hold-out tutmadı. Canlı `fault_type` yok (ADR-0011–0013).
- **Eşikler Set 2'ye kalibre.** Başka test setine (Set 1/3) geçilirse kalibrasyon scripti yeniden çalıştırılmalı.
- **River** çevrimiçi öğrenme detektörü kayda geçiyor ancak sistematik olarak taranmadı/kalibre edilmedi.

## Lisans

Belirlenecek.