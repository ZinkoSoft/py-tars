# X11 Docker Access Fix

## Problem
The TARS UI Docker container was unable to access the X11 display, resulting in errors:
- "Authorization required, but no authorization protocol specified"
- "Invalid MIT-MAGIC-COOKIE-1 key"
- "RuntimeError: Failed to initialize pygame video system"

This issue persisted after container restarts because Docker couldn't properly authenticate with the host's X server.

## Solution
The fix creates a Docker-accessible Xauthority file that containers can read without permission issues.

### 1. Use Host Networking Mode
`compose.non-stt-wake.yml` uses `network_mode: host` for the UI service. This:
- Simplifies X11 socket access (no need for complex volume mounts)
- Allows the container to directly access `localhost:1883` for MQTT
- Reduces network isolation but acceptable for local development

### 2. Create Docker-Accessible Xauthority File
Run `setup-x11-docker.sh` before starting containers. This script:
1. Allows X11 access from Docker: `xhost +local:docker`
2. Creates a world-readable Xauthority file at `/tmp/.docker-xauth/Xauthority`
3. Copies X11 auth cookies from your personal `.Xauthority` file

This approach is more secure than `xhost +` (which disables all access control) while still allowing Docker containers to authenticate properly.

## Usage

### Quick Start (Recommended)
Use the convenience script that handles everything:
```bash
./ops/start-ui.sh
```

Or for a specific compose file:
```bash
./ops/start-ui.sh ops/compose.yml
```

### Manual Method
```bash
# 1. Setup X11 access
cd ops
./setup-x11-docker.sh

# 2. Start containers with XAUTHORITY environment variable
XAUTHORITY=/tmp/.docker-xauth/Xauthority docker compose -f compose.non-stt-wake.yml up
```

### After System Restart
The X11 settings and Xauthority file are not persistent across reboots. You must run `setup-x11-docker.sh` again after restarting your system.

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

This solution uses `xhost +local:docker` which:
- ✅ Only allows local Docker containers to access X display
- ✅ More secure than `xhost +` (which allows ALL local processes)
- ⚠️ Still not recommended for multi-user or production systems

The world-readable Xauthority file at `/tmp/.docker-xauth/Xauthority`:
- Is only readable by users on your local machine
- Contains auth cookies specific to your X session
- Is automatically regenerated on each run of `setup-x11-docker.sh`

## Changes Made

1. **compose.non-stt-wake.yml**:
   - Uses `network_mode: host` for UI service (already configured)
   - `MQTT_HOST` set to `localhost` (for host networking)
   - Updated `XAUTHORITY` default to `/tmp/.docker-xauth/Xauthority`
   - Mounts `/tmp/.docker-xauth` directory (read-only)
   - Changed `/tmp/.X11-unix` to read-write mode

2. **setup-x11-docker.sh**:
   - Runs `xhost +local:docker` to allow Docker container access
   - Creates `/tmp/.docker-xauth/Xauthority` with copied auth cookies
   - Sets file permissions to 644 (world-readable)
   - Provides clear instructions for starting containers

3. **start-ui.sh** (new):
   - Convenience script that runs setup and starts docker compose
   - Automatically sets XAUTHORITY environment variable
   - Usage: `./ops/start-ui.sh [compose-file]`

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

## How It Works

The solution creates a clean authentication path:

1. **Host**: X server runs with normal security
2. **setup-x11-docker.sh**: 
   - Runs `xhost +local:docker` → X server allows Docker containers
   - Extracts auth cookies from `~/.Xauthority` → creates `/tmp/.docker-xauth/Xauthority`
   - Makes file world-readable (644) → Docker container can read it
3. **Docker container**:
   - Mounts `/tmp/.docker-xauth` volume
   - Sets `XAUTHORITY=/tmp/.docker-xauth/Xauthority` env var
   - SDL/pygame reads auth cookies and authenticates with X server
   - ✅ UI displays successfully

## Alternative Solutions Tried

1. ❌ **Mount ~/.Xauthority directly**: Permission denied (file is 600, container can't read)
2. ❌ **xhost + alone**: Too permissive, security risk
3. ❌ **Complex cookie regeneration**: Fragile, breaks on session changes
4. ✅ **World-readable copy in /tmp with xhost +local:docker**: Reliable and reasonably secure
