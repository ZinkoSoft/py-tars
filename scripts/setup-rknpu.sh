#!/usr/bin/env bash
# setup-rknpu.sh — Orange Pi 5 Max (RK3588) NPU bring-up helper
# - Creates persistent /dev/rknpu symlink to the DRM render node
# - Adds the current user to render,video groups
# - Installs RKNN runtime (librknnrt.so) from URL or local path
# - (Optional) Creates a Python venv and installs rknn-toolkit-lite2
#
# Usage examples:
#   bash setup-rknpu.sh                                   # udev + groups + runtime (download)
#   bash setup-rknpu.sh --runtime-path /path/librknnrt.so  # install from local file
#   bash setup-rknpu.sh --force-runtime                    # overwrite existing /usr/lib/librknnrt.so
#   bash setup-rknpu.sh --venv --venv-dir "$HOME/venvs/rknn"   # also prep a venv with rknn-toolkit-lite2
#
# Flags:
#   --runtime-url URL     Download RK3588 aarch64 runtime from URL (default: Rockchip rknpu2 repo blob)
#   --runtime-path PATH   Install runtime from a local file instead of downloading
#   --no-udev             Skip installing udev rule
#   --no-runtime          Skip runtime installation
#   --no-groups           Skip adding user to render,video groups
#   --force-runtime       Overwrite /usr/lib/librknnrt.so if it already exists
#   --venv                Create Python venv and install rknn-toolkit-lite2
#   --venv-dir DIR        Where to create the venv (default: $HOME/venvs/rknn)
#   --pip PKG             Package spec to pip install in the venv (default: rknn-toolkit-lite2)
#   -h | --help           Show help

set -Eeuo pipefail

RUNTIME_URL_DEFAULT="https://github.com/rockchip-linux/rknpu2/raw/master/runtime/RK3588/Linux/librknn_api/aarch64/librknnrt.so"
RUNTIME_URL="$RUNTIME_URL_DEFAULT"
RUNTIME_PATH=""
DO_UDEV=1
DO_RUNTIME=1
DO_GROUPS=1
FORCE_RUNTIME=0
DO_VENV=0
VENV_DIR="$HOME/venvs/rknn"
PIP_PKG="rknn-toolkit-lite2"

usage() {
  sed -n '1,80p' "$0" | sed -n '1,80p' | grep -E "^#" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --runtime-url)   RUNTIME_URL="${2:?}"; shift 2;;
    --runtime-path)  RUNTIME_PATH="${2:?}"; shift 2;;
    --no-udev)       DO_UDEV=0; shift;;
    --no-runtime)    DO_RUNTIME=0; shift;;
    --no-groups)     DO_GROUPS=0; shift;;
    --force-runtime) FORCE_RUNTIME=1; shift;;
    --venv)          DO_VENV=1; shift;;
    --venv-dir)      VENV_DIR="${2:?}"; shift 2;;
    --pip)           PIP_PKG="${2:?}"; shift 2;;
    -h|--help)       usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

SUDO=""
if [[ $EUID -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then SUDO="sudo"; else echo "[!] Please run as root or install sudo"; exit 1; fi
fi

log()  { echo -e "\033[1;32m[+] $*\033[0m"; }
warn() { echo -e "\033[1;33m[!] $*\033[0m"; }
err()  { echo -e "\033[1;31m[✗] $*\033[0m" >&2; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || { err "Missing command: $1"; exit 1; }; }

require_cmd bash
require_cmd grep
require_cmd uname

ARCH=$(uname -m)
if [[ "$ARCH" != "aarch64" ]]; then
  warn "Non-aarch64 arch ($ARCH) detected; this script targets aarch64.";
fi

# Detect the NPU render node by reading the DT name from sysfs
detect_npu_node() {
  local node name
  shopt -s nullglob
  for node in /dev/dri/renderD*; do
    name=$(cat "/sys/class/drm/$(basename "$node")/device/of_node/name" 2>/dev/null || true)
    if [[ "$name" == "npu" || "$name" == "rknpu" ]]; then
      echo "$node"; return 0
    fi
  done
  return 1
}

NPU_NODE=$(detect_npu_node || true)
if [[ -z "${NPU_NODE:-}" ]]; then
  warn "Could not auto-detect NPU render node. Ensure rknpu is initialized (check dmesg). Proceeding with udev rule anyway."
else
  log "Detected NPU render node: $NPU_NODE (-> $(readlink -f "$NPU_NODE"))"
fi

if (( DO_UDEV )); then
  log "Installing udev rule for /dev/rknpu symlink..."
  $SUDO tee /etc/udev/rules.d/70-rknpu.rules >/dev/null <<'RULE'
# Symlink the Rockchip NPU render node as /dev/rknpu
SUBSYSTEM=="drm", KERNEL=="renderD*", ATTR{device/of_node/name}=="npu",   SYMLINK+="rknpu", GROUP="render", MODE="0660"
SUBSYSTEM=="drm", KERNEL=="renderD*", ATTR{device/of_node/name}=="rknpu", SYMLINK+="rknpu", GROUP="render", MODE="0660"
RULE
  $SUDO udevadm control --reload
  # Trigger existing nodes (no-op if not present yet)
  shopt -s nullglob
  for n in /dev/dri/renderD*; do $SUDO udevadm trigger "$n" || true; done
  if [[ -e /dev/rknpu ]]; then
    log "/dev/rknpu -> $(readlink -f /dev/rknpu)"
  else
    warn "/dev/rknpu not present yet (node appears when rknpu render device is created)."
  fi
fi

if (( DO_GROUPS )); then
  TARGET_USER="${SUDO_USER:-$USER}"
  log "Adding $TARGET_USER to 'render' and 'video' groups..."
  $SUDO usermod -aG render,video "$TARGET_USER"
  log "Group changes apply after re-login. Tip: run 'newgrp render' to apply in current shell."
fi

if (( DO_RUNTIME )); then
  if [[ -f /usr/lib/librknnrt.so && $FORCE_RUNTIME -eq 0 ]]; then
    log "Runtime already present at /usr/lib/librknnrt.so; skipping (use --force-runtime to overwrite)."
  else
    if [[ -n "$RUNTIME_PATH" ]]; then
      log "Installing runtime from local path: $RUNTIME_PATH"
      $SUDO install -m0644 "$RUNTIME_PATH" /usr/lib/librknnrt.so
    else
      require_cmd curl
      log "Downloading runtime from: $RUNTIME_URL"
      $SUDO curl -fsSL -o /usr/lib/librknnrt.so "$RUNTIME_URL"
      $SUDO chmod 0644 /usr/lib/librknnrt.so
    fi
    $SUDO ldconfig || true
    if command -v file >/dev/null 2>&1; then file /usr/lib/librknnrt.so || true; fi
    if command -v strings >/dev/null 2>&1; then strings /usr/lib/librknnrt.so 2>/dev/null | grep -i 'librknnrt version' -m1 || true; fi
  fi
fi

# Verify runtime loads via Python (if present)
if command -v python3 >/dev/null 2>&1; then
  log "Verifying runtime load with Python ctypes..."
  python3 - <<'PY' || true
import ctypes, sys
try:
    ctypes.CDLL('librknnrt.so')
    print('librknnrt: OK')
except OSError as e:
    print('librknnrt: ERROR ->', e)
    sys.exit(1)
PY
else
  warn "python3 not found; skipping ctypes verification."
fi

if (( DO_VENV )); then
  require_cmd python3
  log "Creating venv: ${VENV_DIR}"
  python3 -m venv "$VENV_DIR"
  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"
  python -m pip install --upgrade pip
  log "Installing '${PIP_PKG}' into venv..."
  python -m pip install "${PIP_PKG}"
  python - <<'PY'
try:
    from rknnlite.api import RKNNLite
    print('rknn-toolkit-lite2 import: OK')
except Exception as e:
    print('rknn-toolkit-lite2 import: ERROR ->', e)
PY
fi

log "Done. If you were just added to 'render', log out/in or run: newgrp render"
if [[ -e /dev/rknpu ]]; then log "/dev/rknpu -> $(readlink -f /dev/rknpu)"; fi

# basic: udev + groups + runtime (download)
# bash setup-rknpu.sh

# install runtime from your local repo copy (recommended) and overwrite existing
# bash setup-rknpu.sh --runtime-path ~/git/rknn-toolkit2/rknpu2/runtime/Linux/librknn_api/aarch64/librknnrt.so --force-runtime

# also prep a Python venv for RKNN
# bash setup-rknpu.sh --venv --venv-dir ~/venvs/rknn
