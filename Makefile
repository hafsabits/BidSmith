PY := .venv/bin/python
PIP := .venv/bin/pip
CLI := .venv/bin/bidsmith

.PHONY: setup db-up db-down init-db ingest fetch-sam api web test

setup:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e "backend[dev]"
	cd frontend && npm install
	@test -f .env || cp .env.example .env

db-up:
	docker compose up -d --wait db

db-down:
	docker compose down

init-db:
	$(CLI) init-db

ingest:
	$(CLI) ingest --profile all

fetch-sam:
	$(CLI) fetch-sam

api:
	.venv/bin/uvicorn bidsmith.api.main:app --reload --port 8000

web:
	cd frontend && npm run dev

test:
	.venv/bin/pytest backend/tests -q
