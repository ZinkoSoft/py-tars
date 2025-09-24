#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${PYTHON:-python3}"

info() {
  printf '\e[34m[run.tests]\e[0m %s\n' "$1"
}

create_venv() {
  if [[ ! -d "${VENV_DIR}" ]]; then
    info "Creating virtual environment at ${VENV_DIR}"
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  fi
  # shellcheck disable=SC1090
  source "${VENV_DIR}/bin/activate"
  info "Using Python $(python --version 2>/dev/null | tr -d '\n')"
}

install_requirements() {
  info "Upgrading pip/setuptools/wheel"
  pip install --upgrade pip setuptools wheel

  if [[ -f "${ROOT_DIR}/apps/router/pyproject.toml" ]]; then
    info "Installing router package (editable)"
    pip install -e "${ROOT_DIR}/apps/router"
  fi

  local requirements=(
    "apps/stt-worker/requirements.txt"
    "apps/tts-worker/requirements.txt"
    "apps/llm-worker/requirements.txt"
    "apps/memory-worker/requirements.txt"
    "apps/ui/requirements.txt"
    "apps/ui-web/requirements.txt"
    "server/stt-ws/requirements.txt"
  )

  for rel_path in "${requirements[@]}"; do
    local abs_path="${ROOT_DIR}/${rel_path}"
    if [[ -f "${abs_path}" ]]; then
      info "Installing dependencies from ${rel_path}"
      pip install --upgrade -r "${abs_path}"
    fi
  done

  info "Ensuring pytest tooling is available"
  pip install --upgrade pytest pytest-asyncio
}

run_tests() {
  local -a pytest_args
  if [[ $# -eq 0 ]]; then
    pytest_args=("-q")
  else
    pytest_args=("$@")
  fi

  export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"
  # Exclude wake-training from the root discovery; it's run separately below.
  local -a root_pytest_args=("${pytest_args[@]}")
  if [[ -d "${ROOT_DIR}/server/wake-training" ]]; then
    root_pytest_args+=("--ignore=server/wake-training")
  fi
  info "Running pytest at repo root: ${root_pytest_args[*]}"
  pytest "${root_pytest_args[@]}"
  # Run wake-training tests (isolated, with its own requirements)
  local WAKE_TRAINING_DIR="${ROOT_DIR}/server/wake-training"
  if [[ -d "${WAKE_TRAINING_DIR}" && -f "${WAKE_TRAINING_DIR}/requirements.txt" && -d "${WAKE_TRAINING_DIR}/tests" ]]; then
    info "Running wake-training tests in server/wake-training"
    pushd "${WAKE_TRAINING_DIR}" >/dev/null
  pip install --upgrade -r requirements.txt
  info "Setting PYTHONPATH=. for wake-training tests"
  PYTHONPATH=. pytest --maxfail=2 --disable-warnings -q tests
    popd >/dev/null
  fi
}

main() {
  create_venv
  install_requirements
  run_tests "$@"
}

main "$@"
