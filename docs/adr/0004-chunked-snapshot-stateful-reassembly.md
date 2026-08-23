# ADR-0004: Chunk'lı Snapshot ve Stateful Reassembly

- **Durum:** Kabul edildi
- **Tarih:** 2025 (planlama)

## Bağlam
IMS snapshot'ları 20.480 noktalık bloklar. Bunları Kafka'ya nasıl yayınlayacağımıza dair üç seçenek vardı: (a) örnek bazlı (her nokta ayrı mesaj), (b) tüm snapshot tek mesaj, (c) snapshot'ı birkaç chunk'a bölmek.

## Karar
Snapshot **8 chunk**'a bölünerek yayınlanır (`snapshot_id`, `chunk_index`, `total_chunks` alanlarıyla). Stream-processor, chunk'ları bir **SnapshotReassembler** ile yeniden birleştirir. Bu, bilinçli olarak **stateful stream processing** tercihidir.

## Alternatifler
- **Örnek bazlı:** Saniyede ~20.480 mesaj/kanal — Kafka'yı gereksiz boğar, yine pencereye gruplama gerekir.
- **Tek mesaj/snapshot:** En basit, stateless; ancak akış hissi zayıf ve reassembly/stateful pratiği öğretmez.
- **Chunk + bağımsız alt-pencere (state yok):** Akış hissi verir, reassembly gerektirmez; ama "dağıtık mesaj birleştirme" becerisini göstermez.

## Sonuçlar
(+) Gerçek stateful stream processing + reassembly yeteneği. Tanecikli akış hissi.
(−) Stream-processor stateless olmaktan çıkar: reassembly buffer, timeout, duplicate/eksik chunk yönetimi, bellek koruması gerekir (bkz. planning/07). Uçtan uca gecikme, son chunk beklemesini içerir (bkz. planning/08).

## Kritik Kısıt
Chunk'lar **`machine_id`** ile partition'lanır (`snapshot_id` ile değil). Aksi halde aynı snapshot'ın chunk'ları farklı instance'lara dağılır, reassembly çöker.

## Timeout Politikası
- Dinamik: `max(FLOOR, (600 / PLAYBACK_SPEED) * FACTOR)`.
- ≥ %50 chunk → kısmi işle (`is_complete=false`); < %50 → DLQ.
