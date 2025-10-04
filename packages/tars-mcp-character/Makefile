# Makefile for tars-mcp-character

.PHONY: help install install-dev test test-unit test-integration test-cov lint format check clean

help:
	@echo "Available targets:"
	@echo "  install          - Install package dependencies"
	@echo "  install-dev      - Install package with dev dependencies"
	@echo "  test             - Run all tests (unit only, no integration)"
	@echo "  test-unit        - Run unit tests only"
	@echo "  test-integration - Run integration tests (requires MQTT)"
	@echo "  test-cov         - Run tests with coverage report"
	@echo "  lint             - Run linting (ruff)"
	@echo "  format           - Format code (black + ruff)"
	@echo "  check            - Run format + lint + test"
	@echo "  clean            - Remove generated files"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --ignore=tests/test_integration.py

test-unit:
	pytest tests/test_tools.py -v

test-integration:
	pytest tests/test_integration.py -v --run-mqtt

test-cov:
	pytest tests/ --cov=tars_mcp_character --cov-report=html --cov-report=term

lint:
	ruff check tars_mcp_character/ tests/

format:
	black tars_mcp_character/ tests/
	ruff check --fix tars_mcp_character/ tests/

check: format lint test

clean:
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
