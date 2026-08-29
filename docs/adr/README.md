# Architecture Decision Records (ADR)

Önemli mimari kararların atomik, tarihli kayıtları. Her biri "neden bu kararı verdik" sorusunu ileride cevaplar. Yeni karar için `template.md`'yi kopyala.

| ADR | Karar | Durum |
|---|---|---|
| 0001 | Event-driven servis mimarisi (tam mikroservis değil) | Kabul edildi |
| 0002 | Apache Kafka (Redis Streams değil) | Kabul edildi |
| 0003 | NASA IMS Bearing veri seti (C-MAPSS değil) | Kabul edildi |
| 0004 | Chunk'lı snapshot + stateful reassembly | Kabul edildi |
| 0005 | Oynatma hızı `PLAYBACK_INTERVAL_SEC` ile (`PLAYBACK_SPEED` değil) | Kabul edildi |
| 0006 | Z-Score eşikleri 5.0/8.0 (IMS Set 2 kalibrasyonu) | Kabul edildi |
| 0007 | Katman 2 ML eşikleri kalibre değil; FFT bantları ertelendi | Kısmen yerini aldı ADR-0008 (eşik), ADR-0010 (FFT çıkarım), ADR-0012 (teshis) |
| 0008 | Katman 2 IF nicelik eşikleri 0.995/0.999 (IMS Set 2) | Kabul edildi |
| 0009 | Anomali skor alanları: `z_score` vs `anomaly_score`+`score_kind` (schema 2) | Kabul edildi |
| 0010 | FFT bant enerjisi çıkarılır, tespite girmez | Kabul edildi |
| 0011 | Ham-rFFT arıza teşhisi offline; canlı yok (otopsi) | Kabul edildi; yol ADR-0012 |
| 0012 | Ham-rFFT teşhis kapanır; sonraki adım envelope | Kabul edildi; uygulama ADR-0013 |
| 0013 | Envelope teşhisi offline; canlı yok | Kabul edildi |
