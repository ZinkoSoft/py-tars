Orange Pi 5 Max — NPU Activation & RKNN Quickstart (Ubuntu 24.04 Rockchip 6.1)

This guide gets the RK3588 NPU working on Orange Pi 5 Max running Ubuntu 24.04.3 LTS (rockchip kernel 6.1.x). It covers:
	•	Verifying the kernel rknpu driver
	•	Understanding DRM render nodes (/dev/dri/renderD*) vs legacy /dev/rknpu
	•	Creating a persistent /dev/rknpu symlink via udev
	•	Installing the RKNN runtime (librknnrt.so)
	•	Setting up the RKNN Lite2 Python API
	•	Running minimal smoke tests and a Mobilenet sample
	•	Version alignment tips & troubleshooting

TL;DR: On modern Rockchip kernels, the NPU appears as a DRM render node (e.g., /dev/dri/renderD129). We’ll add a udev rule to also expose /dev/rknpu for tooling that still expects it.

⸻

0) Prereqs
	•	Orange Pi 5 Max (RK3588)
	•	Ubuntu 24.04.x Rockchip kernel 6.1.x
	•	sudo privileges

Optional but recommended:
	•	git, git-lfs, curl
	•	Python 3.11 or 3.12 with venv

⸻

1) Confirm kernel & rknpu driver

uname -a
lsb_release -a || cat /etc/os-release

# rknpu driver (often built-in on 6.1 vendor kernels)
modinfo rknpu 2>/dev/null || echo "no rknpu module info (likely built-in)"

dmesg | grep -i rknpu | tail -n +50
ls -l /dev/dri

# Identify which render node is the NPU
for n in /dev/dri/renderD*; do
  echo "== $n =="
  cat /sys/class/drm/$(basename "$n")/device/of_node/name 2>/dev/null || true
done

Expected:
	•	rknpu messages in dmesg (e.g., Initialized rknpu 0.9.7 ...).
	•	Render nodes like renderD128, renderD129 where one prints npu (that’s the NPU node).

It’s normal not to see /dev/rknpu on newer kernels. The NPU lives at /dev/dri/renderDxxx.

⸻

2) Permissions: join the render group

Render nodes are gated by the render (and sometimes video) group.

sudo usermod -aG render,video "$USER"
# Re-login or spawn a subshell that picks up new groups
newgrp render

# Verify
id -nG | tr ' ' '\n' | grep -E '^(render|video)$'
ls -l /dev/dri/renderD*


⸻

3) Add a persistent /dev/rknpu symlink (udev)

Create a udev rule that finds the render node whose Device Tree name is npu (or legacy rknpu) and symlinks it as /dev/rknpu at boot.

sudo tee /etc/udev/rules.d/70-rknpu.rules >/dev/null <<'RULE'
# Symlink the Rockchip NPU render node as /dev/rknpu
SUBSYSTEM=="drm", KERNEL=="renderD*", ATTR{device/of_node/name}=="npu", \
  SYMLINK+="rknpu", GROUP="render", MODE="0660"

# Handle older DT name
SUBSYSTEM=="drm", KERNEL=="renderD*", ATTR{device/of_node/name}=="rknpu", \
  SYMLINK+="rknpu", GROUP="render", MODE="0660"
RULE

sudo udevadm control --reload
for n in /dev/dri/renderD*; do sudo udevadm trigger "$n"; done

# Check
ls -l /dev/rknpu
readlink -f /dev/rknpu   # typically -> /dev/dri/renderD129

Temporary (one-off) symlink if you don’t want udev yet:

sudo ln -sf "$(for n in /dev/dri/renderD*; do name=$(cat /sys/class/drm/$(basename "$n")/device/of_node/name 2>/dev/null); [ "$name" = "npu" ] && echo "$n"; done)" /dev/rknpu
ls -l /dev/rknpu


⸻

4) Install the RKNN runtime (librknnrt.so)

You need the board-side runtime so user-space (RKNN Lite2 / C API) can talk to the NPU.

Option A — from rknn-toolkit2 repo (keeps you aligned with your converter):

# Clone with submodules to fetch the rknpu2 runtime tree
cd ~/git
git clone https://github.com/airockchip/rknn-toolkit2.git
cd rknn-toolkit2
git submodule update --init --recursive

# Copy the aarch64 Linux runtime to a standard lib path
sudo install -m0644 rknpu2/runtime/Linux/librknn_api/aarch64/librknnrt.so /usr/lib/librknnrt.so
sudo ldconfig

# Verify
file /usr/lib/librknnrt.so
strings /usr/lib/librknnrt.so | grep -i "librknnrt version" -m1

Option B — direct download of a known-good blob:

sudo curl -L -o /usr/lib/librknnrt.so \
  https://github.com/rockchip-linux/rknpu2/raw/master/runtime/RK3588/Linux/librknn_api/aarch64/librknnrt.so
sudo chmod 0644 /usr/lib/librknnrt.so
sudo ldconfig

file /usr/lib/librknnrt.so
strings /usr/lib/librknnrt.so | grep -i "librknnrt version" -m1

Tip: Keep the runtime version in sync with the Toolkit you use to export .rknn models. If your model was built with 2.3.x, prefer librknnrt 2.3.x on the board.

⸻

5) Install RKNN Lite2 (Python API)

RKNN Lite2 provides an easy Python interface for inference.

# Python 3.12 or 3.11 both work (choose one)
python3 -m venv ~/venvs/rknn && source ~/venvs/rknn/bin/activate
pip install --upgrade pip
pip install rknn-toolkit-lite2

# Import check
python -c "from rknnlite.api import RKNNLite; print('RKNN Lite2 import OK')"


⸻

6) Smoke tests

6.1 Runtime loads

python3 - << 'PY'
import ctypes
ctypes.CDLL("librknnrt.so")
print("RKNN runtime loaded OK")
PY

6.2 RKNN Lite2 order of calls (load → init → inference)

# npu_smoke.py
from rknnlite.api import RKNNLite
r = RKNNLite()
# Must load a model BEFORE init_runtime
assert r.load_rknn('mobilenet_v1.rknn') == 0
print('init_runtime:', r.init_runtime(core_mask=RKNNLite.NPU_CORE_AUTO))
r.release()

6.3 Get a sample .rknn model (requires Git LFS; example path may vary by repo tag):

sudo apt-get update && sudo apt-get install -y git-lfs
cd ~/git/rknn-toolkit2
git lfs install
git lfs pull

# Locate a sample, e.g. Mobilenet
find rknpu2 -type f -path "*model/*RK3588*" -name "*.rknn" -print
# Copy one next to your smoke script
cp rknpu2/examples/rknn_mobilenet_demo/model/RK3588/mobilenet_v1.rknn ~/smoke-tests/npu_smoke_test/

6.4 Minimal inference

# npu_interface_test.py
from rknnlite.api import RKNNLite
import numpy as np

MODEL = 'mobilenet_v1.rknn'
r = RKNNLite()
assert r.load_rknn(MODEL) == 0
assert r.init_runtime(core_mask=RKNNLite.NPU_CORE_AUTO) == 0
x = np.zeros((1, 224, 224, 3), dtype=np.uint8)  # NHWC uint8 for many TFLite-converted models
(logits,) = r.inference([x])
print('Got', len((logits,)), 'tensor(s). First shape:', logits.shape)
r.release()


⸻

7) Version alignment & common warnings
	•	Toolkit vs Runtime mismatch: You may see a log like RKNN Model version: X not match with rknn runtime version: Y. In many cases it still works, but best practice is to match versions (e.g., Toolkit 2.3.2 ↔ librknnrt 2.3.2).
	•	Static vs dynamic shapes: Warning about RKNN_QUERY_INPUT_DYNAMIC_RANGE simply means the model is static-shape; it’s safe to ignore for static models.

Check versions

# Runtime version
strings /usr/lib/librknnrt.so | grep -i "librknnrt version" -m1

# Model’s embedded toolkit/compiler version (printed by RKNN when you load the model)
# or via your app logs

To fix mismatch: either upgrade runtime on the board to the version used by your converter, or re-export the model with the toolkit version you intend to run on the board.

⸻

8) After-reboot checklist

# 1) Permissions
id -nG | tr ' ' '\n' | grep -E '^(render|video)$'

# 2) Device nodes
ls -l /dev/dri/renderD*   # look for the NPU node
ls -l /dev/rknpu          # udev symlink should resolve to the NPU render node

# 3) Runtime present
python3 - << 'PY'
import ctypes
ctypes.CDLL('librknnrt.so')
print('OK')
PY


⸻

9) Troubleshooting
	•	No /dev/dri/renderD*: Ensure you’re on the vendor Rockchip 6.1 kernel and updated userland. Check dmesg for rknpu lines. Update to latest Ubuntu Rockchip kernel if needed.
	•	Permission denied opening device: Make sure your user is in the render group and your shell reflects it (newgrp render or re-login).
	•	OSError: librknnrt.so: cannot open: Copy the runtime into /usr/lib/ and run sudo ldconfig.
	•	invalid ELF header when loading librknnrt.so: You downloaded an HTML page or wrong arch. Re-download the aarch64 .so and verify with file.
	•	init_runtime fails: Most often permissions or missing runtime. Also confirm you called load_rknn() before init_runtime().
	•	Model incompatibility: Re-export the model using the same Toolkit version as the runtime installed on the board.

⸻

10) One-shot helper script (optional)

Put this in your repo as setup-rknpu.sh to install the udev rule, add your user to groups, and verify:

#!/usr/bin/env bash
set -euo pipefail

# 1) udev rule for /dev/rknpu
sudo tee /etc/udev/rules.d/70-rknpu.rules >/dev/null <<'RULE'
SUBSYSTEM=="drm", KERNEL=="renderD*", ATTR{device/of_node/name}=="npu", SYMLINK+="rknpu", GROUP="render", MODE="0660"
SUBSYSTEM=="drm", KERNEL=="renderD*", ATTR{device/of_node/name}=="rknpu", SYMLINK+="rknpu", GROUP="render", MODE="0660"
RULE
sudo udevadm control --reload
for n in /dev/dri/renderD*; do sudo udevadm trigger "$n"; done

# 2) add user to groups
sudo usermod -aG render,video "$USER"

# 3) optional: install runtime if provided via env var RKNK_SO
if [[ "${RKNPU_SO:-}" != "" ]]; then
  echo "Installing runtime from $RKNPU_SO"
  sudo install -m0644 "$RKNPU_SO" /usr/lib/librknnrt.so
  sudo ldconfig
fi

# 4) verify
echo "== Devices =="
ls -l /dev/dri/renderD* || true
ls -l /dev/rknpu || true

echo "== Runtime =="
python3 - <<'PY'
import ctypes, os
try:
    ctypes.CDLL('librknnrt.so')
    print('librknnrt: OK')
except OSError as e:
    print('librknnrt: ERROR ->', e)
print('rknpu ->', os.path.realpath('/dev/rknpu') if os.path.exists('/dev/rknpu') else 'missing')
PY

echo "Done. If you just added yourself to the render group, log out/in or run: newgrp render"

Make executable:

chmod +x setup-rknpu.sh

Run (optional with a specific runtime file):

./setup-rknpu.sh
# or
RKNPU_SO=~/git/rknn-toolkit2/rknpu2/runtime/Linux/librknn_api/aarch64/librknnrt.so ./setup-rknpu.sh


⸻

11) Where to go next
	•	Convert your own models with rknn-toolkit2 matching your board runtime.
	•	For streaming workloads (ASR, keyword spotting), decide static vs dynamic shapes at export time.
	•	For multi-core usage on RK3588, try NPU_CORE_0_1_2 in your runtime init.

Happy accelerating! 🚀
