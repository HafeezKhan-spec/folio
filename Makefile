.PHONY: api web test

VENV := .venv/bin

api:
	$(VENV)uvicorn folio.main:app --host 127.0.0.1 --port 8000

web:
	cd frontend && npm run dev -- --host 127.0.0.1 --port 5173

test:
	$(VENV)pytest
