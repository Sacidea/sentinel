# 10 — Yol Haritası, Git/CI ve Definition of Done

## 3 Haftalık Yol Haritası

### Hafta 0.5 — Proje İskeleti (Önce Bu!)
- Monorepo, `pyproject.toml`, ruff+mypy+pre-commit
- `libs/contracts` event şemaları (kod öncesi sözleşmeler)
- `docker-compose.yml` iskeleti (Kafka KRaft, TimescaleDB, Redis)
- `.env.example`, `Makefile`, boş katmanlı servis iskeletleri
- `.github/workflows/ci.yml`
- **Walking Skeleton'ı yürüt** (uçtan uca minimal boru bağlantısı — bkz. 13). İş mantığı yazmadan önce bu tamamlanmalı.

### Hafta 1 — Ingestion
- IMS indir, keşifsel analiz
- Simulator: domain + Kafka publisher + testler
- `sensor.vibration.raw`'a yazma, consumer ile doğrulama

### Hafta 2 — İşleme + Anomali + Bildirim
- Stream-processor domain: features + detectors — **önce birim testleri**
- Isolation Forest + PCA (AnomalyDetector port'u ardında)
- River online adaptasyon
- TimescaleDB repository + migration
- Notifier: Celery + Telegram + pybreaker
- Uçtan uca entegrasyon testi
- Idempotency + DLQ (bkz. 07)

### Hafta 3 — Görselleştirme + Doküman + Cila
- Grafana dashboard (kod olarak)
- (Opsiyonel) FastAPI + WebSocket
- `docs/architecture.py`, ADR'ler
- README (5 dk kurulum), sonuç grafikleri
- CI yeşil, kapsam raporu
- (Zaman kalırsa) RUL, autoencoder, MLflow

## Git & CI
- `main` her zaman çalışır; `feat/*`, `fix/*` branch'leri PR ile birleşir.
- Conventional Commits.
- CI (GitHub Actions): her push'ta ruff + mypy + pytest; kırmızıysa merge yok.

## Definition of Done (Her Görev İçin)
Bir görev şu koşullar sağlanmadan "bitti" sayılmaz:
- [ ] İlgili `domain/` mantığı için birim testleri yazıldı ve geçiyor
- [ ] `ruff check` ve `ruff format --check` temiz
- [ ] `mypy` (domain için strict) hatasız
- [ ] Yeni env değişkeni varsa `.env.example` güncellendi
- [ ] Yeni event/şema varsa `libs/contracts` ve ilgili doküman güncellendi
- [ ] Katman ihlali yok (domain'de I/O importu yok)
- [ ] CI yeşil
