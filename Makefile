.PHONY: install dev migrate migrate-new run run-sample ui api test test-cov lint format clean

install:
	pip install -e ".[dev]"

dev:
	pip install -e ".[dev]"
	playwright install chromium

migrate:
	alembic upgrade head

migrate-new:
	alembic revision --autogenerate -m "$(name)"

run:
	marketsignal run --config configs/competitors.ai-agent.yaml

run-sample:
	marketsignal run --use-sample-dataset

ui:
	streamlit run src/marketsignal/ui/streamlit_app.py

api:
	uvicorn marketsignal.api.main:app --reload --port 8000

test:
	pytest

test-cov:
	pytest --cov=marketsignal --cov-report=term-missing

lint:
	ruff check src tests

format:
	ruff format src tests

clean:
	rm -rf data/raw/* data/normalized/* data/reports/* data/evals/* data/chroma/* data/*.db
	find . -type d -name "__pycache__" -exec rm -rf {} +
