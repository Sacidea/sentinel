# 11 — Risk Kaydı (Risk Register)

Projede ters gidebilecek durumlar, etki/olasılık ve önlemleri:

| # | Risk | Olasılık | Etki | Önlem |
|---|---|---|---|---|
| R1 | Kapsam şişmesi (tüm opsiyonel ML'i yetiştirememe) | Yüksek | Orta | Çekirdek/opsiyonel net ayrımı; opsiyoneller feda edilebilir |
| R2 | IMS verisinin boyutu/formatı beklenenden zor | Orta | Orta | Hafta 1'de erken keşifsel analiz; gerekirse alt-küme ile başla |
| R3 | Kafka kurulum/config karmaşıklığı zaman yer | Orta | Orta | KRaft mode (Zookeeper'sız); hazır compose imajı |
| R4 | Anomali tespiti çok fazla yanlış pozitif üretir | Orta | Yüksek | Eşik ayarı + lead time/FP metriğiyle iteratif kalibrasyon |
| R5 | Titreşim verisinde bozuk/NaN okuma pipeline'ı çökertir | Orta | Yüksek | Girdi validasyonu + DLQ (bkz. 06, 07) |
| R6 | Tüm stack tek makinede kaynak yetersizliği | Düşük | Orta | Bellek bütçesi (bkz. 08); gerekirse servisleri sırayla çalıştır |
| R7 | Antigravity'nin katman ihlali / karar değiştirmesi | Orta | Orta | AGENTS.md kuralları + kod review + ADR'ler |
| R8 | Telegram API rate-limit/erişim sorunu | Düşük | Düşük | pybreaker + retry; demo için log fallback |
| R9 | Chunk reassembly buffer'ı sızıntı/şişme (yarım snapshot birikimi) | Orta | Orta | MAX_PENDING_SNAPSHOTS sınırı + timeout ile zorla kapatma (bkz. 07) |
| R10 | Chunk'ların yanlış anahtarlanması (snapshot_id ile) reassembly'yi bozar | Orta | Yüksek | machine_id ile partition; AGENTS.md kuralı + entegrasyon testi |

**Kullanım:** Her hafta başında bu tabloyu gözden geçir; gerçekleşen riski "aktif", çözüleni "kapandı" işaretle.
