# Config Şablonları

Bu klasördeki dosyalar, projeyi başlatırken repo köküne kopyalanacak hazır konfigürasyon şablonlarıdır. (Nokta ile başlayan dosyalar bazı dosya gezginlerinde gizli görünebilir.)

| Şablon | Hedef konum | Amaç |
|---|---|---|
| `.pre-commit-config.yaml` | repo kökü | Commit öncesi ruff + mypy + güvenlik kontrolleri |
| `pyproject.toml` | repo kökü | ruff/mypy/pytest ortak ayarları |
| `Makefile` | repo kökü | `make up/test/lint/check` kısayolları |
| `.env.example` | repo kökü | Tüm env değişkenlerinin sırsız listesi |
| `.gitignore` | repo kökü | Python/secret/veri/model dışlamaları |
| `.github/workflows/ci.yml` | repo kökü | GitHub Actions CI hattı |

**Not:** `rev:` sürümleri (pre-commit) ve paket sürümleri, proje başlarken güncel sürümlerle yenilenmeli.
