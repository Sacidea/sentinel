# Planlama Dokümanları — İndeks

Bu klasör, projenin planlama ve mühendislik standartlarını konu bazında ayrı dosyalara böler. Her dosya tek bir sorumluluğa sahiptir (tıpkı kodda olduğu gibi).

| # | Dosya | İçerik |
|---|---|---|
| 00 | `00-overview.md` | Bağlam, hedef, kapsam |
| 01 | `01-architecture.md` | Event-driven mimari, kullanılmayan desenler |
| 02 | `02-data-and-ml.md` | Veri kaynağı (IMS) + makine öğrenmesi planı |
| 03 | `03-service-design.md` | Katmanlı mimari, SOLID, event sözleşmeleri |
| 04 | `04-conventions.md` | İsimlendirme, config, kod kalitesi araçları |
| 05 | `05-testing-observability.md` | Test stratejisi, loglama, gözlemlenebilirlik |
| 06 | `06-security.md` | Secret yönetimi, bağımlılık taraması, validasyon |
| 07 | `07-resilience.md` | Hata yönetimi, DLQ, idempotency, retry |
| 08 | `08-nfr-sla.md` | Fonksiyonel olmayan gereksinimler, performans bütçesi |
| 09 | `09-repo-structure.md` | Detaylı repo/dizin yapısı |
| 10 | `10-roadmap-and-dod.md` | 3 haftalık yol haritası, Git/CI, Definition of Done |
| 11 | `11-risk-register.md` | Risk kaydı ve önlemler |
| 12 | `12-rejected-alternatives.md` | Elenen alternatifler ve gerekçeleri |
| 13 | `13-pre-coding-checklist.md` | Walking skeleton, spike, definition of ready |
| 14 | `14-data-model.md` | TimescaleDB şema, hypertable, cagg, sıkıştırma, retention |
| 15 | `15-anomaly-design.md` | Baseline, izlenen özellikler, Z-Score/MA, warning/critical |

**İlgili klasörler:**
- `../adr/` — Architecture Decision Records (atomik karar kayıtları)
- `../../templates/` — Hazır config dosyası şablonları (pre-commit, pyproject, CI vb.)
- `../../AGENTS.md` — AI kodlama ajanı talimatları
