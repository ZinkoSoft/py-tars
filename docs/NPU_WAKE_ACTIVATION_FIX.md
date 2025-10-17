# NPU Wake Activation Fix - Complete Solution

**Date**: 2025-10-10  
**Issue**: Wake-activation NPU service was falling back to CPU despite NPU being available  
**Status**: ✅ RESOLVED

---

## Problem Analysis

### Symptoms

```
tars-wake-activation-npu | 2025-10-10 15:30:07,213 W wake_activation.detector: NPU requested but not available, falling back to CPU
```

### Root Causes

1. **Container using wrong Dockerfile**
   - `compose.yml` was using generic `docker/specialized/wake-activation.Dockerfile`
   - This Dockerfile didn't include `rknn-toolkit-lite2` Python package
   - NPU availability check failed on import test

2. **Missing render group membership**
   - Container was privileged but didn't have render group (GID 992)
   - `/dev/dri/renderD129` requires render group access
   - NPU permission check failed

3. **Permission check didn't handle unnamed groups**
   - `npu_utils.py` only checked for named groups ("render", "video")
   - In containers, GID 992 exists but has no name
   - Permission validation incorrectly failed

---

## Solution

### 1. Fix compose.npu.yml - Use NPU-Specific Dockerfile

**File**: `ops/compose.npu.yml`

```yaml
wake-activation:
  # Use NPU-enabled Dockerfile
  build:
    context: ..
    dockerfile: apps/wake-activation/Dockerfile.npu
  image: tars/wake-activation:npu
  container_name: tars-wake-activation-npu
  privileged: true
  group_add:
    - "992"  # render group for NPU access
  devices:
    - "/dev/rknpu:/dev/rknpu"
    - "/dev/dri:/dev/dri"
    - "/dev/mali0:/dev/mali0"
```

**Changes**:
- ✅ Added `build` section pointing to `Dockerfile.npu`
- ✅ Added `group_add: ["992"]` for render group access
- ✅ Changed image name to `tars/wake-activation:npu`

### 2. Fix Dockerfile.npu - Correct File Paths

**File**: `apps/wake-activation/Dockerfile.npu`

**Problem**: COPY commands were using relative paths from wrong context

```dockerfile
# ❌ BEFORE (incorrect paths)
COPY wake_activation/ /app/wake_activation/
COPY scripts/ /app/scripts/
COPY tests/ /app/tests/

# ✅ AFTER (correct paths from build context root)
COPY apps/wake-activation/wake_activation/ /app/wake_activation/
COPY apps/wake-activation/pyproject.toml /app/
COPY apps/wake-activation/README.md /app/
```

**Additional fix**:
```dockerfile
# ❌ BEFORE
RUN chmod +x /app/entrypoint.sh /app/healthcheck.sh /app/scripts/*.py

# ✅ AFTER (scripts not copied, so removed from chmod)
RUN chmod +x /app/entrypoint.sh /app/healthcheck.sh
```

### 3. Fix npu_utils.py - Handle Unnamed Groups

**File**: `apps/wake-activation/wake_activation/npu_utils.py`

```python
# ✅ Enhanced permission check
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
    status_messages.append("❌ User not in render/video groups - run: sudo usermod -aG render,video $USER")
    perms_ok = False
```

**What changed**:
- Check for GID 992 even if "render" group name doesn't exist
- Show GID in success message for better debugging
- Handle KeyError gracefully for missing groups

---

## Verification

### Build and Deploy

```bash
# Rebuild with NPU support
docker compose -f ops/compose.yml -f ops/compose.npu.yml build wake-activation

# Restart service
docker compose -f ops/compose.yml -f ops/compose.npu.yml up -d wake-activation

# Check logs
docker logs tars-wake-activation-npu --tail 40
```

### Expected Output

```
✅ NPU Detection Success:
2025-10-10 15:39:48,180 I wake_activation.detector: NPU available, using NPU acceleration for wake detection

✅ RKNN Runtime Loaded:
W rknn-toolkit-lite2 version: 2.3.2
I RKNN: [15:39:48.321] RKNN Runtime Information, librknnrt version: 2.3.2
I RKNN: [15:39:48.321] RKNN Driver Information, version: 0.9.7
I RKNN: [15:39:48.323] RKNN Model Information, version: 6, target: RKNPU v2, target platform: rk3588

✅ Model Loaded Successfully:
D RKNN: Total Internal Memory Size: 9KB
D RKNN: Total Weight Memory Size: 100.875KB

✅ Wake Detector Ready:
2025-10-10 15:39:48,328 I wake-activation: Wake detector ready (threshold=0.15, retrigger=0.50s); consuming audio at 16000 Hz
```

### Manual NPU Check

```bash
# Verify group membership
docker exec tars-wake-activation-npu bash -c "id && python -c 'import os; print(\"Groups:\", os.getgroups())'"

# Expected output:
uid=1000(tarsuser) gid=1000(tarsuser) groups=1000(tarsuser),29(audio),44(video),992(render)
Groups: [1000, 29, 44, 992]

# Check NPU availability
docker exec tars-wake-activation-npu python -c "from wake_activation.npu_utils import check_npu_availability; print(check_npu_availability()[1])"

# Expected output:
✅ NPU render node found: /dev/dri/renderD129
✅ librknnrt.so runtime library available
✅ rknn-toolkit-lite2 Python API available
✅ RKNPU kernel driver detected in dmesg
✅ User is in render group (GID 992)
🎉 NPU is ready for wake word acceleration!
```

---

## Key Learnings

### 1. Docker Group Mapping

When using `group_add` in docker-compose, the GID is added to the container's groups list, but:
- The group name might not exist in the container
- You need to handle unnamed GIDs in permission checks
- Use `os.getgroups()` to see actual numeric GIDs

### 2. Build Context Matters

When `context: ..` (parent directory), all COPY paths are relative to parent:
```dockerfile
context: ..  # Project root
dockerfile: apps/wake-activation/Dockerfile.npu

# Must use full paths from context
COPY apps/wake-activation/wake_activation/ /app/
```

### 3. Multi-Stage Dockerfiles

For NPU services, maintain separate Dockerfiles:
- `Dockerfile` - Standard CPU version
- `Dockerfile.npu` - NPU-enabled with rknn-toolkit-lite2

Benefits:
- CPU containers stay lightweight
- NPU containers get specialized dependencies
- Clear separation of concerns

---

## Remaining Issue: Audio Fan-Out Permissions

```
2025-10-10 15:39:48,328 W wake-activation.audio: Audio fan-out connection error [Errno 13] Permission denied
```

**Cause**: Container user (`tarsuser` UID 1000) can't access `/tmp/tars/audio-fanout.sock`

**Solution**: Will need to either:
1. Run container as root user
2. Change socket permissions in STT service
3. Share common GID between services

This is a **separate issue** from NPU detection and doesn't affect NPU functionality.

---

## Summary

✅ **NPU Detection**: Fixed - now properly detects and uses NPU  
✅ **RKNN Runtime**: Loaded successfully on RK3588 NPU cores  
✅ **Wake Model**: Loaded on NPU (100.875KB weight memory)  
✅ **Performance**: Wake detection now using NPU acceleration  
⚠️ **Audio Socket**: Separate permission issue (not NPU-related)

**Impact**: Wake-word detection should now be faster and more power-efficient using dedicated NPU hardware instead of CPU.

---

**Related Documentation**:
- `docs/NPU_VS_CPU_INT8_DEEP_DIVE.md` - Why NPU excels for small models
- `apps/wake-activation/NPU_ACCELERATION.md` - Wake activation NPU guide
- `apps/wake-activation/Dockerfile.npu` - NPU-enabled Dockerfile
