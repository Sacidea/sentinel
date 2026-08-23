# 07 — Dayanıklılık ve Hata Yönetimi

Streaming bir sistemde en çok ihmal edilen ama en kritik alan. "Mutlu yol" kolay; asıl mühendislik hataların yönetiminde.

## Idempotency (Tekrar İşleme Güvenliği)
- Kafka "at-least-once" teslim garantisi verir → aynı mesaj birden fazla gelebilir.
- Her event `event_id` (UUID) taşır. Notifier, aynı `event_id` için ikinci kez bildirim göndermez (kısa süreli bir "görülen ID" seti veya DB unique constraint).
- DB yazımında `machine_id + occurred_at` üzerine unique index → çift kayıt engellenir (`ON CONFLICT DO NOTHING`).

## Dead Letter Queue (DLQ)
- Parse edilemeyen / şema doğrulamasından geçemeyen / işlenirken kalıcı hata veren mesajlar `*.dlq` topic'ine yazılır.
- Böylece bir bozuk mesaj tüm consumer'ı sonsuz döngüye sokup akışı durdurmaz.
- DLQ periyodik incelenir (bu projede manuel; production'da otomatik alarm).

## Retry Politikası
- **Geçici hatalar** (DB bağlantısı düştü, Telegram 5xx): üstel geri çekilme (exponential backoff) ile sınırlı sayıda retry.
- **Kalıcı hatalar** (şema hatası, 400): retry yok → doğrudan DLQ.
- Celery task'larında `max_retries` ve `retry_backoff` ayarlanır.

## Circuit Breaker (Telegram)
- `pybreaker`: Telegram API art arda başarısız olursa devre "açılır", bir süre çağrı yapılmaz, worker kaynakları korunur. Yarı-açık durumda tekrar denenir.

## Graceful Shutdown
- Her servis SIGTERM'de: yeni mesaj almayı durdurur, işlenmekte olanı bitirir, offset'i commit eder, bağlantıları kapatır. Docker `stop_grace_period` ile uyumlu.

## Consumer Offset Yönetimi
- Offset, mesaj **başarıyla işlendikten sonra** commit edilir (at-least-once). İşleme başarısızsa commit edilmez → mesaj tekrar denenir (idempotency bunu güvenli kılar).


## Chunk Reassembly Hata Yönetimi (Stateful)

Snapshot'lar 8 chunk halinde geldiği için (bkz. 03), yeni hata modları:

### Eksik / Geç Chunk (Timeout)
- İlk chunk geldikten sonra dinamik bir timeout başlar:
  `reassembly_timeout = max(TIMEOUT_FLOOR, (600 / PLAYBACK_SPEED) * TIMEOUT_FACTOR)`
  (600 = nominal snapshot aralığı sn; taban ve çarpan `.env`'de ayarlanır.)
- Timeout dolduğunda:
  - **≥ %50 chunk (≥4/8):** kısmi işle, `is_complete=false`, `chunks_received` işaretle.
  - **< %50 chunk:** DLQ'ya at (güvenilir özellik çıkarılamaz).

### Duplicate Chunk
- Kafka at-least-once → aynı `chunk_index` tekrar gelebilir. Reassembler idempotenttir: aynı index ikinci kez gelirse yok sayılır.

### Bellek Koruması (Buffer Bloat)
- Çok sayıda yarım snapshot birikirse tampon şişer. `MAX_PENDING_SNAPSHOTS` sınırı; aşılırsa en eski yarım snapshot timeout kuralıyla zorla kapatılır (kısmi işle veya DLQ).

### Graceful Shutdown Etkisi
- Servis kapanırken tampondaki yarım snapshot'lar: eldeki chunk'larla kısmi işlenir veya DLQ'ya yazılır — sessizce kaybolmaz.
