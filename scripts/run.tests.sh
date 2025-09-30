#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Place virtualenv one level above the script (repo root)
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv"
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

  if [[ -f "${REPO_ROOT}/packages/tars-core/pyproject.toml" ]]; then
    info "Installing tars-core package (editable)"
    pip install -e "${REPO_ROOT}/packages/tars-core"
  fi

  if [[ -f "${REPO_ROOT}/apps/router/pyproject.toml" ]]; then
    info "Installing router package (editable)"
    pip install -e "${REPO_ROOT}/apps/router"
  fi

  if [[ -f "${REPO_ROOT}/apps/wake-activation/pyproject.toml" ]]; then
    info "Installing wake activation package (editable)"
    pip install -e "${REPO_ROOT}/apps/wake-activation"
  fi

  if [[ -f "${REPO_ROOT}/apps/stt-worker/pyproject.toml" ]]; then
    info "Installing stt-worker package (editable)"
    pip install -e "${REPO_ROOT}/apps/stt-worker"
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
    local abs_path="${REPO_ROOT}/${rel_path}"
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
  info "Running pytest at repo root: ${pytest_args[*]}"
  pytest "${pytest_args[@]}"
}

main() {
  create_venv
  install_requirements
  run_tests "$@"
}

main "$@"
