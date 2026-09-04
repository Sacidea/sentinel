# 05 — Test Stratejisi ve Gözlemlenebilirlik

## Test Piramidi
| Katman | Kapsam | Araç | Örnek |
|---|---|---|---|
| Birim (çoğunluk) | Saf `domain/`, I/O yok | pytest | `calculate_rms`, `z_score` doğru mu |
| Entegrasyon | Gerçek Kafka/DB'ye karşı adapter | pytest + testcontainers | Producer yazıyor, consumer okuyor mu |
| Sözleşme | Event şema uyumluluğu | pytest | `AnomalyDetected` beklenen alanları içeriyor mu |

**Öncelik:** `domain/` birim testleri. Anomali mantığını bilinen girdilerle (örn. yapay titreşim sıçraması) test etmek şart.

**Gerçekçi hedef:** `domain/` %90+ kapsam; `infrastructure/` birkaç kritik entegrasyon testi. Her adapter'ı %100 test etmek 3 haftayı aşar.

## Gözlemlenebilirlik
- **structlog** ile JSON log; `print()` yasak.
- Her event bir **correlation_id** (event_id) taşır → bir pencerenin simülatörden bildirime yolculuğu tek ID ile izlenir.
- Seviyeler: DEBUG (geliştirme), INFO (akış), WARNING (anomali), ERROR (işlenemeyen hata).
- (Stretch) Kafka consumer lag + işlenen mesaj sayısı Grafana'da.


## Reassembler Test Senaryoları (Kod Yazmadan Önce Listele)

Stateful reassembly (ADR-0004), sistemin en riskli bileşenidir. Aşağıdaki senaryolar, implementasyondan önce belirlenmiş test kapsamıdır. Hepsi `domain/` (saf mantık) veya `application/` (state/timeout) seviyesinde test edilebilir.

### Mutlu yol
| # | Senaryo | Beklenen |
|---|---|---|
| T1 | 8 chunk sırayla (0..7) gelir | Tam snapshot işlenir, `is_complete=true`, `chunks_received=8` |
| T2 | 8 chunk karışık sırayla gelir (örn. 3,0,7,1...) | Yine tam işlenir; sıra önemli değil, `chunk_index` seti kontrol edilir |

### Eksik / timeout
| # | Senaryo | Beklenen |
|---|---|---|
| T3 | 6/8 chunk gelir, timeout dolar | Kısmi işle, `is_complete=false`, `chunks_received=6` |
| T4 | 4/8 chunk gelir (tam eşik %50), timeout | Kısmi işlenir (eşiğe eşit dahil) |
| T5 | 3/8 chunk gelir (eşik altı), timeout | DLQ'ya gider, işlenmez |
| T6 | 1/8 chunk gelir, timeout | DLQ'ya gider |
| T7 | 0 chunk (snapshot hiç başlamadı) | Buffer'da kayıt yok, hiçbir şey olmaz |

### Duplicate / hatalı
| # | Senaryo | Beklenen |
|---|---|---|
| T8 | Aynı `chunk_index` iki kez gelir | İkinci yok sayılır (idempotent), çift sayılmaz |
| T9 | `total_chunks` mesajlar arası tutarsız (biri 8 biri 4 der) | Şema/tutarlılık hatası → DLQ, buffer kirlenmez |
| T10 | Geç gelen chunk (snapshot zaten timeout'la kapandı) | Yok sayılır veya geç-gelen olarak loglanır, kapanmış snapshot yeniden açılmaz |

### State / bellek
| # | Senaryo | Beklenen |
|---|---|---|
| T11 | Aynı anda birden fazla `snapshot_id` birikir | Her biri bağımsız tamponlanır, karışmaz |
| T12 | `MAX_PENDING_SNAPSHOTS` aşılır | En eski yarım snapshot zorla kapatılır (kısmi/DLQ), yeni gelen kabul edilir |
| T13 | Graceful shutdown, tamponda yarım snapshot var | Kısmi işlenir veya DLQ'ya yazılır, sessizce kaybolmaz |

### Timeout hesabı
| # | Senaryo | Beklenen |
|---|---|---|
| T14 | PLAYBACK_INTERVAL_SEC çok küçük (örn. 0,1 sn) | `reassembly_timeout` TIMEOUT_FLOOR'a iner, sıfır/negatif olmaz |
| T15 | PLAYBACK_INTERVAL_SEC büyük (örn. 600 sn) | Timeout formülle büyür, erken kapatma olmaz |

**Öncelik:** T1-T8 çekirdek (bunlar geçmeden reassembler "bitti" sayılmaz). T9-T15 dayanıklılık senaryolarıdır. Bu testlerin sürekli kırılması, stateful reassembly yaklaşımının bu proje için fazla karmaşık olduğuna ve chunk'ların bağımsız işlenmesine (reassembly'siz) geçmenin daha uygun olabileceğine işarettir.
