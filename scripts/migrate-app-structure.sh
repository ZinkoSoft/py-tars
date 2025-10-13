#!/bin/bash
# migrate-app-structure.sh
# Helper script to migrate an app to standardized structure
#
# Usage: ./scripts/migrate-app-structure.sh <app-name>
# Example: ./scripts/migrate-app-structure.sh wake-activation

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <app-name>"
    echo "Example: $0 wake-activation"
    exit 1
fi

APP_NAME="$1"
APP_DIR="apps/${APP_NAME}"
PACKAGE_NAME=$(echo "${APP_NAME}" | tr '-' '_')

echo "=========================================="
echo "Migrating app: ${APP_NAME}"
echo "Package name: ${PACKAGE_NAME}"
echo "=========================================="

# Verify app exists
if [ ! -d "${APP_DIR}" ]; then
    echo "Error: App directory ${APP_DIR} does not exist"
    exit 1
fi

cd "${APP_DIR}"

echo ""
echo "Step 1: Analyzing current structure..."
tree -L 2 > structure-before.txt || ls -R > structure-before.txt
echo "✓ Current structure documented in structure-before.txt"

echo ""
echo "Step 2: Creating new directory structure..."
mkdir -p "src/${PACKAGE_NAME}"
mkdir -p tests/unit
mkdir -p tests/integration
mkdir -p tests/contract
echo "✓ Created src/ and tests/ directories"

echo ""
echo "Step 3: Manual file migration needed"
echo "Please manually move source files to src/${PACKAGE_NAME}/"
echo "Then run: ./scripts/migrate-app-structure.sh ${APP_NAME} continue"
echo ""
echo "Next steps after moving files:"
echo "  1. Create pyproject.toml from template"
echo "  2. Create Makefile from template"
echo "  3. Create README.md"
echo "  4. Create .env.example"
echo "  5. Test with: pip install -e . && make check"

if [ "$2" == "continue" ]; then
    echo ""
    echo "Step 4: Creating pyproject.toml..."
    if [ ! -f "pyproject.toml" ]; then
        cat > pyproject.toml <<EOF
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "tars-${APP_NAME}"
version = "0.1.0"
description = "${APP_NAME} service for TARS"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "asyncio-mqtt>=0.16.2",
    "paho-mqtt<2.0",
    "orjson>=3.10.7",
    "pydantic>=2.6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "black>=24.0",
    "ruff>=0.5",
    "mypy>=1.10",
    "types-orjson>=3.6",
]

[project.scripts]
tars-${APP_NAME} = "${PACKAGE_NAME}.__main__:main"

[tool.setuptools]
package-dir = {"" = "src"}
packages = ["${PACKAGE_NAME}"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = ["-v", "--strict-markers"]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "contract: MQTT contract tests",
]
EOF
        echo "✓ Created pyproject.toml"
    else
        echo "⚠ pyproject.toml already exists, skipping"
    fi

    echo ""
    echo "Step 5: Creating Makefile..."
    if [ ! -f "Makefile" ]; then
        cat > Makefile <<EOF
# Makefile for ${APP_NAME}
PACKAGE_NAME := ${PACKAGE_NAME}
SRC_DIR := src/\$(PACKAGE_NAME)
TEST_DIR := tests
PYTHON := python3

.PHONY: help fmt lint test check build clean install install-dev

help:
	@echo "Available targets:"
	@echo "  make fmt         - Format code"
	@echo "  make lint        - Lint and type-check"
	@echo "  make test        - Run tests"
	@echo "  make check       - Run all checks (CI gate)"
	@echo "  make build       - Build package"
	@echo "  make clean       - Remove artifacts"
	@echo "  make install     - Install in editable mode"
	@echo "  make install-dev - Install with dev dependencies"

fmt:
	@echo "🎨 Formatting code..."
	@ruff check --fix \$(SRC_DIR) \$(TEST_DIR) || true
	@black \$(SRC_DIR) \$(TEST_DIR)
	@echo "✅ Formatting complete"

lint:
	@echo "🔍 Linting code..."
	@ruff check \$(SRC_DIR) \$(TEST_DIR)
	@echo "🔍 Type checking..."
	@mypy \$(SRC_DIR)
	@echo "✅ Linting complete"

test:
	@echo "🧪 Running tests..."
	@pytest \$(TEST_DIR) -v --cov=\$(SRC_DIR) --cov-report=term-missing --cov-report=xml
	@echo "✅ Tests complete"

check: fmt lint test
	@echo "✅ All checks passed!"

build:
	@echo "📦 Building package..."
	@\$(PYTHON) -m build
	@echo "✅ Build complete"

clean:
	@echo "🧹 Cleaning artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf dist/ build/ .coverage coverage.xml htmlcov/
	@echo "✅ Clean complete"

install:
	@echo "📥 Installing package..."
	@pip install -e .
	@echo "✅ Installation complete"

install-dev:
	@echo "📥 Installing package with dev dependencies..."
	@pip install -e ".[dev]"
	@echo "✅ Installation complete"
EOF
        echo "✓ Created Makefile"
    else
        echo "⚠ Makefile already exists, skipping"
    fi

    echo ""
    echo "Step 6: Creating .env.example..."
    if [ ! -f ".env.example" ]; then
        cat > .env.example <<EOF
# MQTT Configuration
MQTT_URL=mqtt://user:pass@localhost:1883

# ${APP_NAME} Configuration
# Add app-specific environment variables here
EOF
        echo "✓ Created .env.example"
    else
        echo "⚠ .env.example already exists, skipping"
    fi

    echo ""
    echo "Step 7: Documenting changes..."
    tree -L 2 > structure-after.txt || ls -R > structure-after.txt
    echo "✓ New structure documented in structure-after.txt"

    echo ""
    echo "=========================================="
    echo "Migration template created!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "  1. Review and update pyproject.toml with app-specific dependencies"
    echo "  2. Create/update README.md with MQTT topics"
    echo "  3. Run: pip install -e ."
    echo "  4. Run: make check"
    echo "  5. Update Dockerfile if needed"
    echo ""
fi
