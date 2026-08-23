# AGENTS.md — AI Kodlama Ajanı Talimatları

> Bu dosya, Antigravity/Claude gibi AI kodlama ajanlarının bu repoda çalışırken uyacağı kuralları içerir. (Claude Code'daki `CLAUDE.md` ile aynı işlevi görür.) Ajan, kod üretmeden önce bu dosyayı ve `docs/planning/` altındaki ilgili bölümü okumalıdır.

## Altın Kurallar

1. **Katman ihlali yapma.** `domain/` katmanına `import aiokafka`, `import psycopg`, `import requests` gibi I/O bağımlılıkları koyma. Domain saf ve I/O'suz kalmalı.
2. **Sır gömme.** Token, şifre, host gibi değerleri koda yazma. Hepsi `config.py` (pydantic-settings) üzerinden env'den okunur.
3. **Sözleşmeleri kopyalama.** Event modelleri yalnızca `libs/contracts` içinde tanımlanır. Servisler buradan import eder, kendi kopyasını oluşturmaz.
4. **Servisler birbirini doğrudan çağırmaz.** İletişim Kafka event'leri üzerinden. Bir servisten diğerine HTTP/fonksiyon çağrısı ekleme.
5. **Chunk anahtarlaması `machine_id` iledir, `snapshot_id` ile DEĞİL.** Ham veri 8 chunk'a bölünür; aynı rulmanın chunk'ları aynı partition'a gitmeli ki reassembly tek instance'ta çalışsın. Reassembly saf mantığı `domain/`'de, state/timeout `application/`'da (bkz. planning/03, 07).
6. **Test-önce mantığı.** `domain/` içindeki her fonksiyon için birim testi yaz. Anomali tespit mantığı test edilmeden "bitti" sayılmaz.
7. **Kararları sessizce değiştirme.** Kafka yerine Redis, Isolation Forest yerine LSTM gibi bir değişiklik gerekiyorsa önce gerekçesiyle öner; `docs/adr/` altındaki kararları geçersiz kılma.

## Kod Standartları
- Python 3.11+; tüm public fonksiyonlar type hint içerir; `domain/` `mypy --strict` geçer.
- Formatlama/lint: `ruff`. `print()` yerine `structlog`.
- İsimlendirme: `docs/planning/04-conventions.md`.

## Bir Görevi Bitirmeden Önce (Definition of Done)
`docs/planning/10-roadmap-and-dod.md` içindeki DoD kontrol listesini uygula: testler geçiyor, ruff+mypy temiz, ilgili doküman güncel.

## Nereye Bakmalı
- Mimari: `docs/planning/01-architecture.md`
- Servis iç yapısı & SOLID: `docs/planning/03-service-design.md`
- Event şemaları: `docs/planning/03-service-design.md` + `libs/contracts`
- Config şablonları: `templates/`
