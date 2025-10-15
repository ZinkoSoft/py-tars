"""NPU availability detection and runtime utilities for wake activation."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def check_npu_availability() -> tuple[bool, str]:
    """Check if NPU hardware and runtime are available.

    Returns:
        Tuple of (is_available, status_message)
    """
    status_messages = []

    # Check for NPU device node
    rknpu_device = Path("/dev/rknpu")
    renderD129 = Path("/dev/dri/renderD129")  # Primary NPU device on RK3588

    if rknpu_device.exists():
        status_messages.append("✅ /dev/rknpu device found")
        device_available = True
    elif renderD129.exists():
        status_messages.append(f"✅ NPU render node found: {renderD129}")
        device_available = True
    else:
        # Check for DRM render nodes (modern approach)
        render_nodes = list(Path("/dev/dri").glob("renderD*"))
        npu_render_node = None

        for node in render_nodes:
            try:
                of_node_name = Path(f"/sys/class/drm/{node.name}/device/of_node/name")
                if of_node_name.exists():
                    name = of_node_name.read_text().strip()
                    if name in ("npu", "rknpu"):
                        npu_render_node = node
                        break
            except Exception:
                continue

        if npu_render_node:
            status_messages.append(f"✅ NPU render node found: {npu_render_node}")
            device_available = True
        else:
            # List available devices for debugging
            available_devices = (
                [str(p) for p in Path("/dev/dri").glob("renderD*")]
                if Path("/dev/dri").exists()
                else []
            )
            status_messages.append(
                f"❌ No NPU device nodes found (/dev/rknpu or renderD129). Available: {available_devices}"
            )
            device_available = False

    # Check for RKNN runtime library
    try:
        import ctypes

        ctypes.CDLL("librknnrt.so")
        status_messages.append("✅ librknnrt.so runtime library available")
        runtime_available = True
    except OSError:
        status_messages.append("❌ librknnrt.so not found - install RKNN runtime")
        runtime_available = False

    # Check for RKNN Lite2 Python API
    try:
        from rknnlite.api import RKNNLite  # noqa: F401

        status_messages.append("✅ rknn-toolkit-lite2 Python API available")
        api_available = True
    except ImportError:
        status_messages.append("❌ rknn-toolkit-lite2 not installed")
        api_available = False

    # Check kernel driver
    try:
        result = subprocess.run(["dmesg"], capture_output=True, text=True, timeout=5)
        if "rknpu" in result.stdout.lower():
            status_messages.append("✅ RKNPU kernel driver detected in dmesg")
        else:
            status_messages.append("⚠️  No RKNPU driver messages in dmesg")
    except Exception:
        status_messages.append("⚠️  Could not check kernel driver status")

    # Check permissions
    if device_available:
        # Root user always has access
        if os.getuid() == 0:
            status_messages.append("✅ Running as root (full device access)")
            perms_ok = True
        else:
            user_groups = os.getgroups()
            render_gid = None
            video_gid = None

            try:
                import grp

                # Try to get render/video group IDs by name
                try:
                    render_gid = grp.getgrnam("render").gr_gid
                except KeyError:
                    # Render group doesn't exist by name, check for common render GID (992)
                    if 992 in user_groups:
                        render_gid = 992

                try:
                    video_gid = grp.getgrnam("video").gr_gid
                except KeyError:
                    pass
            except Exception:
                pass

            if render_gid and render_gid in user_groups:
                status_messages.append(f"✅ User is in render group (GID {render_gid})")
                perms_ok = True
            elif video_gid and video_gid in user_groups:
                status_messages.append(f"✅ User is in video group (GID {video_gid})")
                perms_ok = True
            else:
                status_messages.append(
                    "❌ User not in render/video groups - run: sudo usermod -aG render,video $USER"
                )
                perms_ok = False
    else:
        perms_ok = False

    # Overall availability
    is_available = device_available and runtime_available and api_available and perms_ok

    status = "\n".join(status_messages)
    if is_available:
        status += "\n🎉 NPU is ready for wake word acceleration!"
    else:
        status += "\n❌ NPU not available - falling back to CPU"

    return is_available, status


def get_npu_info() -> dict | None:
    """Get NPU information and capabilities.

    Returns:
        Dictionary with NPU info, or None if not available
    """
    try:
        from rknnlite.api import RKNNLite

        # Try to initialize RKNN to get capability info
        rknn = RKNNLite()

        info = {
            "device": "RK3588 NPU",
            "cores": 3,  # RK3588 has 3 NPU cores
            "supported_formats": ["rknn"],
            "api_version": "rknn-toolkit-lite2",
        }

        # Check available cores
        available_cores = []
        for core in [1, 2, 4]:  # Test individual cores
            try:
                ret = rknn.init_runtime(core_mask=core)
                if ret == 0:
                    available_cores.append(core)
                    rknn.release()
            except Exception:
                continue

        if available_cores:
            info["available_cores"] = available_cores
            info["core_mask_auto"] = 0  # Auto-select cores
            info["core_mask_all"] = 7  # All 3 cores (1+2+4)

        return info

    except Exception as e:
        logger.debug(f"Could not get NPU info: {e}")
        return None


def log_npu_status() -> bool:
    """Log NPU availability status.

    Returns:
        True if NPU is available, False otherwise
    """
    is_available, status = check_npu_availability()

    logger.info("NPU Status Check:")
    for line in status.split("\n"):
        logger.info(f"  {line}")

    if is_available:
        info = get_npu_info()
        if info:
            logger.info("NPU Capabilities:")
            for key, value in info.items():
                logger.info(f"  {key}: {value}")

    return is_available


if __name__ == "__main__":
    """Run NPU availability check as standalone script."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    print("RK3588 NPU Availability Check")
    print("=" * 40)

    is_available, status = check_npu_availability()
    print(status)

    if is_available:
        print("\nNPU Capabilities:")
        info = get_npu_info()
        if info:
            for key, value in info.items():
                print(f"  {key}: {value}")
        else:
            print("  Could not retrieve NPU capabilities")

    print(f"\nOverall Status: {'✅ READY' if is_available else '❌ NOT AVAILABLE'}")
