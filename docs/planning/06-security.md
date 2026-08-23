# 06 — Güvenlik

Kapsam abartılmadan, temel güvenlik önlemleri:

## Secret Yönetimi
- Telegram bot token, DB şifresi, hiçbir sır **koda veya git'e** girmez.
- Tüm sırlar env üzerinden (`.env`, git-ignored). `.env.example` yalnız anahtar isimlerini içerir, değer içermez.
- (Stretch) `docker compose` için Docker secrets veya `.env` dosyası; production simülasyonu istenirse Vault/SOPS notu.

## Bağımlılık Güvenliği
- `pip-audit` veya `uv`'nin denetimi CI'da çalışır — bilinen açıklı paketleri yakalar.
- Bağımlılıklar sabitlenir (lock dosyası); "en son sürüm" belirsizliği yok.
- Dependabot/Renovate (stretch) — otomatik güvenlik güncellemeleri.

## Girdi Doğrulama
- Kafka'dan gelen her mesaj `libs/contracts` pydantic modeliyle **doğrulanarak** parse edilir. Şemaya uymayan mesaj DLQ'ya gider (bkz. 07-resilience), sessizce çökertmez.
- Sayısal alanlarda NaN/inf kontrolü (titreşim verisinde bozuk okuma olabilir).

## En Az Yetki
- DB kullanıcısı yalnız gerekli tablolara erişir (yazan servis INSERT, Grafana yalnız SELECT).
- Container'lar root olarak çalışmaz (Dockerfile'da non-root user).

## Loglama Hijyeni
- Log'lara secret veya ham kişisel veri yazılmaz. (Bu projede kişisel veri yok ama alışkanlık önemli.)
