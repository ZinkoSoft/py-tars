# X11 Docker Access Fix

## Problem
The TARS UI Docker container was unable to access the X11 display, resulting in errors:
- "Authorization required, but no authorization protocol specified"
- "Invalid MIT-MAGIC-COOKIE-1 key"
- "RuntimeError: Failed to initialize pygame video system"

This issue persisted after container restarts because Docker couldn't properly authenticate with the host's X server.

## Solution
The fix involves two changes:

### 1. Use Host Networking Mode
Changed `compose.non-stt-wake.yml` to use `network_mode: host` for the UI service. This:
- Simplifies X11 socket access (no need for volume mounts)
- Allows the container to directly access `localhost:1883` for MQTT
- Reduces network isolation but acceptable for local development

### 2. Disable X11 Access Control
Run `setup-x11-docker.sh` before starting containers. This script runs:
```bash
DISPLAY=:0 xhost +
```

This disables X11 access control, allowing any process on the local machine (including Docker containers) to connect to the X server.

## Usage

### Before Starting Containers
```bash
cd ops
./setup-x11-docker.sh
docker compose -f compose.non-stt-wake.yml up
```

### After System Restart
The `xhost +` setting is not persistent across reboots. You must run `setup-x11-docker.sh` again after restarting your system.

### Automatic Setup (Optional)
To make this permanent, add to your shell startup file (`~/.bashrc` or `~/.zshrc`):
```bash
# Enable X11 access for Docker
if [ -n "$DISPLAY" ]; then
    xhost +local:docker 2>/dev/null || true
fi
```

## Security Considerations

⚠️ **For local development only!**

The `xhost +` command disables X11 access control, which means:
- Any process on your machine can access your X display
- This is acceptable for single-user development machines
- **NOT recommended for production or multi-user systems**

### More Secure Alternative
For production, use `xhost +local:docker` instead of `xhost +`:
```bash
DISPLAY=:0 xhost +local:docker
```
This restricts access to local Docker containers only.

## Changes Made

1. **compose.non-stt-wake.yml**:
   - Added `network_mode: host` to UI service
   - Changed `MQTT_HOST` from `mqtt` to `localhost`
   - Updated Xauthority volume mount to use `${HOME}/.Xauthority`

2. **setup-x11-docker.sh**:
   - Simplified to just run `xhost +`
   - Removed complex Xauthority file generation (not needed with `xhost +`)
   - Added clear security warnings

## Verification

Check that the UI container is running without X11 errors:
```bash
docker compose -f compose.non-stt-wake.yml logs ui | grep -i "authorization\|error"
```

Should see no authorization errors, and UI should initialize pygame successfully.

## Troubleshooting

### Container still fails after fix
1. Ensure X server is running: `echo $DISPLAY` should show `:0` or similar
2. Re-run setup script: `./setup-x11-docker.sh`
3. Restart container: `docker compose -f compose.non-stt-wake.yml restart ui`

### "unable to open display" error
- Check that DISPLAY is set: `echo $DISPLAY`
- Verify X is running: `xdpyinfo -display :0 | head`

### Permission denied on X11 socket
- Check socket permissions: `ls -la /tmp/.X11-unix/`
- Re-run setup script with proper DISPLAY set

## Alternative Solutions Tried (Didn't Work)

1. ❌ **Custom Xauthority file**: Cookie mismatch issues
2. ❌ **Copying ~/.Xauthority**: Permission and format issues with Docker
3. ❌ **xhost +local:docker only**: Still had cookie validation failures
4. ✅ **xhost + with network_mode: host**: Works consistently

The combination of host networking and disabled access control provides the most reliable solution for local development.
