# Sentinel

Gerçek zamanlı endüstriyel titreşim anomali tespiti ve kestirimci bakım sistemi.

Fabrika rulmanlarından gelen titreşim verisini canlı bir akış olarak işleyerek, makine arızalanmadan önce istatistiksel ve makine öğrenmesi tabanlı erken uyarı üretir. Anomaliler Telegram üzerinden bildirilir ve canlı bir Grafana panosunda görselleştirilir.

> **Durum:** Çalışır durumda. İki farklı NASA IMS veri setinde (Set 1 ve Set 2) uçtan uca test edildi; dört detektörlü anomali tespiti canlı akışta çalışıyor. Tespit katmanı, tek sette kalibre edilip diğer sette hold-out testiyle doğrulandı.

## Öne Çıkan Sonuç: Tespit Genelleşiyor (hold-out doğrulaması)

Z-Score tabanlı tespit katmanı **yalnızca Set 2'de kalibre edildi** (eşikler 5.0/8.0), ardından **hiçbir yeniden kalibrasyon yapılmadan** Set 1'de test edildi. Sonuç: aynı eşiklerle üç farklı arıza tipini, sıfır yanlış pozitifle yakaladı.

| Arıza tipi | Veri seti | Bearing/eksen | Lead time (arıza öncesi) | Erken yanlış pozitif |
|---|---|---|---:|---:|
| Dış bilezik (BPFO) | Set 2 | bearing_1 | 74.5 saat | 0 |
| İç bilezik (BPFI) | Set 1 | bearing_3 / x | **166.0 saat** | 0 |
| İç bilezik (BPFI) | Set 1 | bearing_3 / y | 54.2 saat | 0 |
| Bilye/makara (BSF) | Set 1 | bearing_4 / x | **119.2 saat** | 0 |
| Bilye/makara (BSF) | Set 1 | bearing_4 / y | 114.7 saat | 0 |

Lead time, ilk `critical` uyarının arıza sonuna göre kaç saat önce geldiğini gösterir (dosya index ekseni, dosyalar 10 dakika aralıklı). Sağlıklı rulmanlarda (bearing_1/2) arızalı kanalların ilk uyarısından önce hiç alarm yok (erken FP = 0).

**Neden önemli:** Tek veri setinde kalibre edilen bir tespit sistemi, ikinci bir veri setinde üç farklı arıza tipini yeniden kalibrasyonsuz yakaladı. Bu, genelleme sınırının hold-out testiyle doğrulandığı anlamına gelir — çoğu benzer çalışmanın atladığı bir adım.

**Çift eksenin katkısı:** İç bilezik arızasında x ekseni (166 saat) arızayı y ekseninden (54 saat) çok daha erken gördü — çift eksenli izlemenin ölçülebilir getirisi.

## Ne Yapar

- **Ingestion:** NASA IMS Bearing verisi, kontrollü hızda canlı akışa dönüştürülür (asyncio simülatör → Kafka). Simülatör hem tek eksenli (Set 2, 4 kanal) hem çift eksenli (Set 1, 8 kanal) veriyi otomatik algılayarak işler. Her snapshot 8 chunk'a bölünür; stream-processor bunları `(dataset, machine_id, axis)` bazında yeniden birleştirir.
- **İşleme:** Her titreşim penceresinden sinyal özellikleri (RMS, kurtosis, crest factor, peak) ve FFT bant enerjileri (BPFO/BPFI/BSF) çıkarılır.
- **Anomali tespiti — dört detektör, canlı:**
  - **Z-Score / hareketli ortalama** — baseline'a göre sapma (yorumlanabilir, birincil bildirim katmanı; iki sette de genelleşen katman)
  - **Isolation Forest** — ağaç tabanlı, ölçeklenmiş zarf skoru
  - **PCA + Hotelling's T²** — çok değişkenli süreç izleme
  - **River (HalfSpaceTrees)** — çevrimiçi/artımlı öğrenme
  - Her detektörün skoru `score_kind` ile ayrı etiketlenir; baseline her `(dataset, machine_id, axis)` için ayrı öğrenilir.
- **Bildirim:** Anomaliler Telegram'a iletilir (Celery + circuit breaker). Yalnız `zscore` ve `isolation_forest` yayımlanır; PCA/River kayda geçer ama bildirilmez.
- **Görselleştirme:** TimescaleDB + Grafana ile canlı pano, dataset filtresiyle (set1 / set2).

## Mimari

Event-driven, gevşek bağlı servis mimarisi. Servisler birbirini doğrudan çağırmaz; iletişim Kafka event'leri üzerindendir.

```
Simulator ──► Kafka (sensor.vibration.raw) ──► Stream Processor ──┬──► TimescaleDB ──► Grafana
                                                                  │
                                    Kafka (anomaly.detected) ◄────┴──► Notifier ──► Telegram
```

Kafka topic'leri: `sensor.vibration.raw` (4 partition), `sensor.vibration.features`, `anomaly.detected`, `anomaly.dlq`. Detay: [`docs/planning/01-architecture.md`](docs/planning/01-architecture.md)

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

IMS dosyası yoksa simülatör **sentetik** titreşime geçer; Telegram `CHANGE_ME` ise bildirim log'a düşer (servis düşmez).

```bash
cp .env.example .env
docker compose up -d --build
```

Pano: [http://127.0.0.1:3000](http://127.0.0.1:3000) (`.env` → `GRAFANA_ADMIN_*`;
doldurulması zorunlu, ADR-0016). NASA IMS: Set 2 `data/ims`, Set 1 `data/ims_set1/1st_test`.
Set değiştirince `docker compose up -d --force-recreate stream-processor`.
Host portları yalnız loopback (`127.0.0.1`).

```bash
pytest -m unit
```

## Dokümantasyon

- **[Planlama dokümanları](docs/planning/README.md)** — mimari, veri modeli, anomali tasarımı, test stratejisi, güvenlik, dayanıklılık
- **[Karar kayıtları (ADR)](docs/adr/README.md)** — önemli mimari kararların gerekçeli kayıtları
- **[AGENTS.md](AGENTS.md)** — AI kodlama ajanları için proje kuralları
- **Analiz notebook'ları** — `ml/notebooks/` (Set 2 kalibrasyonu, FFT bant/teşhis, Set 1 hold-out karnesi)

## Veri Kaynağı

NASA IMS Bearing Dataset — 20 kHz örnekleme ile gerçek ivmeölçer (titreşim) sinyali, run-to-failure test verisi. Rexnord ZA-2115 rulman; karakteristik arıza frekansları BPFO=236 Hz, BPFI=297 Hz, BSF=278 Hz (**2×BSF**; temel BSF ~140 Hz, ADR-0015). Seçim gerekçesi: [`docs/adr/0003-ims-over-cmapss.md`](docs/adr/0003-ims-over-cmapss.md)

## Bilinen Sınırlamalar ve Gelecek İş

Bunlar bilinçli kapsam kararlarıdır, ADR'lerde kayıtlıdır:

- **Güvenlik:** Yerel demo tehdit modeli (güvenilen tek makine). Portlar loopback;
  mTLS/SASL/Vault yok. Ayrıntı: [ADR-0016](docs/adr/0016-security-scope-local-demo.md).
- **Teşhis:** ADR-0015 — belirginlik + yan bant yanlış etiket sorununu çözdü
  (Set 1 orta pencere: 0 yanlış) ama teşhis edilebilirliği çözmedi (arızalı
  kanallar orta pencerede %100 belirsiz). Doğru etiket Z-Score tespitinden
  290–900 snapshot sonra beliriyor; alarm-çapalı pencere bu çiftte çalışmaz.
  `fault_type` canlıda kapalı.
- **Tespit genelleşiyor, teşhis genelleşmiyor.** Z-Score tabanlı anomali *tespiti* iki sette, üç arıza tipinde yeniden kalibrasyonsuz çalışıyor. Arıza *tipi teşhisi* (ham-rFFT, envelope enerji, tepe belirginliği) denendi ve kapandı (ADR-0011–0013, ADR-0015). Canlı `fault_type` yok.
- **ML katmanı sete özgü kalibrasyon istiyor.** Isolation Forest / PCA, Set 2'de güçlü (89 saat lead), ancak Set 1'de yeniden kalibrasyon olmadan gürültülü. Z-Score'un göreli ölçüsü (baseline'dan kaç sigma) sayesinde daha iyi genelleştiği gözlendi — basit, ilkeye dayalı yöntemin genelleme avantajı.
- **Set 3 ile üçüncü hold-out** yapılmadı; kalibrasyonun tam genelliği ancak üçüncü bağımsız setle kesinleşir.

## Lisans

Belirlenecek.