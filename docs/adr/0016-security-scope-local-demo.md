# ADR-0016: Guvenlik kapsami — yerel demo tehdit modeli

- **Durum:** Kabul edildi
- **Tarih:** 2026-09-04
- **İlgili:** [00-overview](../planning/00-overview.md) (kapsam disi: fabrika/HA/RBAC),
  [06-security](../planning/06-security.md),
  [10-roadmap-and-dod](../planning/10-roadmap-and-dod.md) (PR akisi)

## Baglam

Sentinel, 3 haftalik tek kisilik bir demo stack'idir. Tehdit modeli
**guvenilen tek makinede yerel calistirma**. Aga acik dagitim ve fabrika
ortami kapsam disidir (`docs/planning/00-overview.md`). mTLS / Kafka SASL /
Postgres SSL / Vault, tek komutla ayağa kalkan demo iddiasini bozar.

## Karar

1. **Uygulananlar (bu ADR):**
   - Sir yonetimi: `.env` git-ignore, `.env.example` placeholder,
     `detect-private-key` pre-commit, Telegram token yalniz env,
     httpx log kismi (bot token URL'de).
   - Girdi dogrulama: `libs/contracts` pydantic, NaN/inf reddi, DLQ.
   - Host portlari **loopback**: `127.0.0.1:5432/6379/9092/3000`.
     Ayni agdaki baska makine Kafka'ya sahte alarm basamaz.
     Localhost erisimi ayni kalir.
   - Varsayilan sifre uyarisi: `POSTGRES_PASSWORD` ve
     `GRAFANA_ADMIN_PASSWORD` `.env.example`'da doldurulmasi zorunlu
     (CHANGE_ME kalabilir, yorum acik). Grafana `GF_SECURITY_ADMIN_*`
     compose env ile ayarlanir. Gercek `.env` commit edilmez.
   - Bagimlilik kilidi: `uv.lock` (tekrar uretilebilirlik; 6 ay sonra
     aralik surum agaci kaymasin). CI `pip-audit`.

2. **Degerlendirildi, UYGULANMADI** (tehdit modeli disi; demo tek-komut
   iddiasini bozar):
   - mTLS
   - Kafka SASL
   - Redis AUTH
   - Postgres SSL
   - Vault / SOPS / Docker secrets
   - Ayrı okuma-yetkili DB kullanicisi (Grafana SELECT-only)
   - Non-root container (`USER` Dockerfile)

3. **main'e dogrudan push sapmasi:** `gh` CLI bu makinede yoktu;
   `feat/walking-skeleton` PR acilmadan `origin/main`'e merge edildi
   (2026-09-04, merge `1183c69`). CI kapi degil **rapor** olarak calisti.
   Plandaki PR akisi (`docs/planning/10-roadmap-and-dod.md`: feat/* PR,
   kirmiziysa merge yok) bilinçli sapma. Ilk `main` CI kosusu basarili
   idi (Actions run 33864742374). Sonraki isler tercihen PR ile.

## Disari acmadan once gerekenler

Demo'yu LAN/internete acmadan once, sirayla:

1. Host bind'i `127.0.0.1` birakma; veya ters proxy + ag politikasi.
2. Kafka SASL (veya ag izolasyonu); topic'e yazma yetkisi.
3. Redis AUTH; 6379'u host'ta acma.
4. Postgres SSL + Grafana `sslmode=require`; ayri readonly rol.
5. Grafana admin sifresi + anonymous kapat.
6. Container non-root `USER`.
7. Secret'lar Vault/SOPS; `CHANGE_ME` yasak.
8. mTLS servisler arasi (istege bagli, fabrika agi).

Bu liste demo kapsaminda **yapilmaz**; fabrika tehdit modeline geciste
ayri turdur.

## Alternatifler

- **Simdiden SASL/mTLS:** compose tek-komut kirilir, 00 kapsamini asar. Elendi.
- **Portlari acik birakmak:** ayni Wi-Fi'de sahte `anomaly.detected`. Elendi.
- **Lock dosyasiz aralik surum:** 6 ay sonra agac kayar. Elendi.

## Sonuclar

(+) Loopback + .env + kilit, demo tehdidine yeter.
(−) Fabrika/HA/RBAC hâlâ yok. 06-security stretch maddeleri (Vault,
    non-root, least-privilege DB) bilerek acik.
(−) PR kapisi bir kez atlandi; CI rapor idi.
