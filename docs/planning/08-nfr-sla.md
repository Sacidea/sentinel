# 08 — Fonksiyonel Olmayan Gereksinimler (NFR) ve Performans Bütçesi

Sayısal hedefler olmadan "gerçek zamanlı" iddiası ölçülemez. Bu projede gerçekçi, geliştirme ölçeğinde hedefler:

## Performans Hedefleri
| Metrik | Hedef | Not |
|---|---|---|
| Uçtan uca gecikme (event → bildirim) | < 2 sn* | Simülatör yayınından Telegram'a. *Chunk reassembly beklemesi dahil: son chunk gelene veya timeout'a kadar. Timeout PLAYBACK_INTERVAL_SEC'e bağlı (bkz. 07, ADR-0005). |
| Özellik çıkarım süresi (1 pencere) | < 50 ms | 20.480 nokta üzerinde RMS+kurtosis+FFT |
| Throughput | ≥ 50 pencere/sn | Tek stream-processor instance |
| Consumer lag | ~0 (sabit kalmalı) | Lag sürekli artıyorsa işleme yavaş demektir |

## Güvenilirlik
- Bir servis çökerse diğerleri çalışmaya devam eder (Kafka tampon görevi görür).
- Servis yeniden başladığında en son commit'li offset'ten devam eder (veri kaybı yok).

## Ölçeklenebilirlik (tasarımda hazır, uygulamada değil)
- `sensor.vibration.raw` 4 partition'lıdır (1 partition = 1 rulman). Stream-processor consumer group'una **en fazla 4** aktif instance eklenebilir; her biri bir rulmanı paralel işler.
- Başlangıçta tek instance çalışır; `docker compose up --scale stream-processor=N` (N≤4) ile ölçeklenme gösterilebilir.
- 4'ten fazla instance eklenirse fazlası boşta bekler (Kafka: aktif consumer ≤ partition sayısı). Topic/partition tablosu: bkz. 01.

## Kaynak Bütçesi (geliştirme makinesi)
- Tüm stack (`docker compose up`) tek bir dizüstünde çalışabilmeli: Kafka + TimescaleDB + Redis + 3 servis + Grafana. Bellek hedefi < 4 GB.

## Sağlık Kontrolleri (Health Checks)
- Her servis basit bir sağlık sinyali verir (Kafka bağlantısı canlı mı). Docker `healthcheck` ile compose'a bağlanır.
