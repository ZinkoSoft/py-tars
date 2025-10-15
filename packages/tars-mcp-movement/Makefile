.PHONY: help fmt lint test check install

help:
	@echo "Available targets:"
	@echo "  fmt     - Format code with black and ruff"
	@echo "  lint    - Run ruff and mypy linters"
	@echo "  test    - Run pytest tests"
	@echo "  check   - Run fmt + lint + test (CI gate)"
	@echo "  install - Install package with dev dependencies"

fmt:
	black tars_mcp_movement/ tests/
	ruff check --fix tars_mcp_movement/ tests/

lint:
	ruff check tars_mcp_movement/ tests/
	mypy tars_mcp_movement/

test:
	pytest tests/ -v --cov=tars_mcp_movement --cov-report=term-missing

check: fmt lint test

install:
	pip install -e ".[dev]"
