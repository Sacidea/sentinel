# 04 — İsimlendirme, Config ve Kod Kalitesi

## İsimlendirme
| Alan | Kural | Örnek |
|---|---|---|
| Python modül | `snake_case` | `feature_extraction.py` |
| Fonksiyon/değişken | `snake_case` | `calculate_rms()` |
| Sınıf | `PascalCase` | `KafkaConsumerAdapter` |
| Sabit | `UPPER_SNAKE` | `DEFAULT_WINDOW_SIZE` |
| Paket/klasör | `lower` | `contracts`, `infrastructure` |
| Kafka topic | `nokta.ayrık.küçük` | `sensor.vibration.raw` |
| Consumer group | `<servis>-<amaç>` | `stream-processor-features` |
| DB tablo | `snake_case` çoğul | `vibration_readings` |
| DB sütun | `snake_case` | `machine_id` |
| Env | `UPPER_SNAKE` prefix'li | `KAFKA_BOOTSTRAP_SERVERS` |
| Docker servis | `kebab-case` | `stream-processor` |
| Git branch | `<tip>/<açıklama>` | `feat/kafka-consumer` |
| Git commit | Conventional Commits | `feat: add kurtosis extractor` |

## Config Yönetimi (12-Factor)
- Tüm config env'den; kodda hardcoded değer/secret yok.
- Her servis `config.py` içinde `Settings(BaseSettings)` (pydantic-settings) tanımlar.
- Repo kökünde `.env.example` (bkz. `templates/`). Gerçek `.env` git'e girmez.
- Secret'lar (Telegram token, DB şifre) yalnız env'den.

## Kod Kalitesi
| Araç | Görev |
|---|---|
| ruff | lint + format (black/isort/flake8 yerine) |
| mypy | statik tip kontrolü (strict hedefi) |
| pre-commit | commit öncesi ruff + mypy |

- Tüm public fonksiyonlar type hint içerir; `domain/` `mypy --strict` geçer.
- Sihirli sayı yok; eşikler/pencere boyutları config veya adlı sabitlerde.
- Docstring *neden*i açıklar, *ne*yi değil.
