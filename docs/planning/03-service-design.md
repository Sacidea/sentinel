# 03 — Servis İç Mimarisi, SOLID ve Sözleşmeler

## Katmanlı Yapı (Ports & Adapters — hafif hexagonal)

Her servis aynı iç katmanlamayı kullanır:

```
src/<service>/
├── domain/          # Saf iş mantığı. I/O YOK (Kafka/DB/HTTP import edilmez).
├── application/     # Use case orkestrasyonu. Domain'i çağırır, port'larla I/O yapar.
├── ports/           # Soyut arayüzler (Protocol): MessageConsumer, MessagePublisher,
│                    # ReadingRepository, AnomalyDetector, Notifier ...
├── infrastructure/  # Port implementasyonları (adapter): KafkaConsumerAdapter,
│                    # TimescaleRepository, TelegramNotifier ...
├── config.py        # pydantic-settings
├── logging.py       # structlog
└── __main__.py      # Composition root: adapter oluştur → application'a enjekte et
```

**Neden işe yarıyor:**
- `domain/` I/O'suz olduğu için saf, hızlı birim testleri yazılır (anomali mantığının doğruluğu = projenin kalbi).
- `ports/infrastructure` ayrımı; Kafka'yı/DB'yi değiştirmeyi veya testte mock kullanmayı application'a dokunmadan mümkün kılar.

## SOLID — Somut Karşılıkları
- **S:** Özellik çıkarımı / skorlama / Kafka tüketimi / DB yazımı ayrı modüllerde. "Her şey tek dosyada" yasak.
- **O:** Yeni algoritma = `AnomalyDetector` implemente et; orkestrasyona dokunma.
- **L:** Tüm detector'lar `score(features) -> float` sözleşmesini sağlar; değiştirilebilir.
- **I:** Küçük odaklı port'lar; consumer sadece `MessageConsumer`'a bağımlı.
- **D:** application somut kütüphaneye değil `ports/`'a bağımlı; adapter'lar `__main__.py`'de enjekte edilir.

## Servisler Arası Sözleşmeler (Event Schemas)
Event modelleri `libs/contracts/` içinde pydantic olarak tanımlanır; tüm servisler buradan import eder (DRY).

| Topic | Model | Üreten | Tüketen |
|---|---|---|---|
| `sensor.vibration.raw` | `RawVibrationWindow` | simulator | stream-processor |
| `sensor.vibration.features` | `VibrationFeatures` | stream-processor | (analizciler) |
| `anomaly.detected` | `AnomalyDetected` | stream-processor | notifier |

**`AnomalyDetected` alanları (örnek, `schema_version=3`, ADR-0009 + ADR-0014):**
```
event_id: UUID
occurred_at: datetime      # UTC, tz-aware
machine_id: str
dataset: str               # set1 / set2; eski Kafka'da yok → "unknown"
metric: str
value: float
z_score: float | None      # yalnız Katman 1 (detector=zscore); v1'de her detector
anomaly_score: float | None  # Katman 2; v1'de yok (default None)
score_kind: Literal[...] | None  # v2+; v1'de yok, detector'dan türetilir
severity: Literal["warning", "critical"]
schema_version: int        # şema evrimi (1 → 2 skor alanları, 2 → 3 dataset)
```
`schema_version`, eski/yeni consumer'ların bir arada çalışmasını sağlar — gevşek bağlılığın somut karşılığı. v1 Kafka kalıntısında `anomaly_score`/`score_kind` anahtarı yoktur (opsiyonel); consumer `detector`'dan `score_kind` türetir, skoru `z_score`'dan okur.


## Ham Veri Akışı: Chunk'lı Snapshot (Stateful Reassembly)

**Tasarım kararı (ADR-0004):** Her 20.480 noktalık snapshot, **8 chunk**'a bölünerek yayınlanır. Bu, akış hissi verir ve bilinçli olarak **stateful stream processing + mesaj yeniden birleştirme (reassembly)** pratiğini içerir.

**`RawVibrationWindow` (chunk) şeması:**
```
snapshot_id: UUID          # aynı snapshot'ın chunk'larını bağlar
chunk_index: int           # 0 .. total_chunks-1
total_chunks: int          # 8
machine_id: str            # PARTITION ANAHTARI (snapshot_id DEĞİL!)
axis: Literal["x", "y"]
dataset: str               # set1 / set2; eski mesajda yoksa "unknown" (ADR-0014)
samples: list[float]       # bu chunk'ın ham noktaları (~2560)
occurred_at: datetime      # yayın anı (canlı zaman ekseni)
source_timestamp: datetime # orijinal dosya zaman damgası
schema_version: int
```

**KRİTİK — partition anahtarı:** Chunk'lar `machine_id`'ye göre anahtarlanır, `snapshot_id`'ye göre DEĞİL. Aksi halde aynı snapshot'ın chunk'ları farklı partition/instance'lara dağılır ve reassembly imkânsızlaşır. `machine_id` ile anahtarlandığında bir rulmanın tüm chunk'ları aynı partition → aynı stream-processor instance'ına gider; reassembly tek instance içinde çalışır (4 instance'a ölçeklense bile).

## SnapshotReassembler Bileşeni (stateful)

Stream-processor artık stateless değil; bir yeniden birleştirme katmanı içerir.

- **Saf mantık (`domain/`):** "Bu chunk seti tamam mı?" (`chunk_index` seti `0..total_chunks-1`'i kapsıyor mu), duplicate chunk tespiti, kısmi birleştirme — hepsi I/O'suz, test edilebilir.
- **State/orkestrasyon (`application/`):** `snapshot_id` → gelen chunk'lar tamponu; timeout zamanlayıcısı; tamamlanınca veya timeout'ta domain'e devretme.

**Tamamlanma/timeout davranışı (bkz. 07-resilience):**
- Tüm 8 chunk geldi → tam snapshot işlenir (`is_complete = true`).
- Timeout'ta ≥ 4/8 chunk (%50) → **kısmi işle**, `is_complete = false`, `chunks_received` işaretlenir.
- Timeout'ta < 4/8 chunk → **DLQ**'ya (güvenilir özellik çıkarılamaz).
- Duplicate `chunk_index` → idempotent yok say.

`VibrationFeatures` ve `AnomalyDetected` event'lerine `is_complete: bool` ve `chunks_received: int` alanları eklenir; böylece kısmi veriden gelen anomaliler ayırt edilebilir.
