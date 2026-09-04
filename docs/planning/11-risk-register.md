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
| R11 | 4 `machine_id` anahtarı murmur2 ile partition'lara eşit dağılmıyor | Gerçekleşti | Düşük (tek instance) | Ölçeklenmeye kadar kabul; bkz. "Bilinen Sınırlamalar" |

**Kullanım:** Her hafta başında bu tabloyu gözden geçir; gerçekleşen riski "aktif", çözüleni "kapandı" işaretle.

## Bilinen Sınırlamalar

### BS1 — Kafka partition dağılımı dengesiz (Hafta 3'te ele alınacak)

`bearing_1..4` anahtarlarının dördü de Kafka'nın varsayılan murmur2 partitioner'ı ile
`sensor.vibration.raw` topic'inin **partition 0**'ına düşüyor; diğer üç partition boş kalıyor.
Walking skeleton doğrulamasında ölçüldü ve hash hesabıyla teyit edildi.

- **Etkisi:** Tasarım kuralı bozulmuyor (aynı makinenin chunk'ları aynı partition'a gidiyor — ADR-0004
  ve AGENTS.md kuralı 5 sağlanıyor), ancak consumer paralelliği yok: 4 partition'a rağmen tek
  stream-processor instance'ı çalışabilir. Tek instance ile demo için sorun değil.
- **Ne zaman sorun olur:** Çoklu instance ile ölçeklenmeye geçildiğinde (Hafta 3 / ölçeklenme işi).
- **O zamanki çözüm:** Explicit partition ataması (anahtar → partition eşlemesini producer'da
  belirtmek) veya anahtar isimlendirmesinin/partition sayısının hash dağılımına göre seçilmesi.
- **Şu an aksiyon alınmıyor:** Öncelik iskeletin ve iş mantığının tamamlanması.
