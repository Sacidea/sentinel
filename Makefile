# Sık kullanılan komutlar. `make <hedef>` ile çalıştır.
.PHONY: help up down logs test test-unit lint format type check install-hooks

help:            ## Bu yardımı göster
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

up:              ## Tüm stack'i ayağa kaldır (tek komut)
	@test -f .env || cp .env.example .env
	docker compose up -d --build

down:            ## Tüm stack'i durdur
	docker compose down

logs:            ## Servis loglarını takip et
	docker compose logs -f

test:            ## Tüm testleri çalıştır
	pytest

test-unit:       ## Yalnız birim testleri (hızlı, I/O yok)
	pytest -m unit

lint:            ## ruff ile lint
	ruff check .

format:          ## ruff ile formatla
	ruff format .

type:            ## mypy ile tip kontrolü
	mypy .

check: lint type test-unit  ## commit öncesi hızlı kontrol

install-hooks:   ## pre-commit hook'larını kur
	pre-commit install
