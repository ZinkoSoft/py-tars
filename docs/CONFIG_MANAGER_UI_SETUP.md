# Config Manager UI Setup Guide

## Setting the API Token for UI-Web

The Config Manager API requires authentication via an API token. By default, it uses your MQTT password.

### Quick Setup (Browser Console)

1. Open the UI-Web interface: http://localhost:5010
2. Open browser Developer Tools (F12)
3. Go to the **Console** tab
4. Run this command:

```javascript
localStorage.setItem('api_token', 'change_me')
```

5. Refresh the page
6. The Config drawer should now load successfully

### Default Token

By default, the API token is set to your **MQTT password**. Check your `.env` file:

```bash
MQTT_PASS=change_me  # This is your API token
```

### Custom API Token

If you want to use a different token instead of the MQTT password:

1. Set the `API_TOKENS` environment variable in your `.env` file:

```bash
API_TOKENS='my-secret-token:admin-user:admin'
```

2. Update the token in the browser console:

```javascript
localStorage.setItem('api_token', 'my-secret-token')
```

3. Restart the config-manager service:

```bash
cd ops
docker compose restart config-manager
```

### Token Format for API_TOKENS

Format: `token:name:role[,token2:name2:role2,...]`

**Roles**:
- `admin` - Full access (read + write + user management)
- `config.write` - Read and write configuration
- `config.read` - Read-only access

**Example**:
```bash
API_TOKENS='abc123:admin-token:admin,def456:readonly:config.read'
```

### Testing the Connection

After setting the token, test the API:

```bash
# From command line
curl -H "X-API-Token: change_me" http://localhost:8081/api/config/services

# Should return: {"services":["stt-worker",...]}
```

In the UI, you should see:
- Config drawer loads without errors
- Service tabs appear
- Configuration forms are editable

### Troubleshooting

**Problem**: "Authentication required" error in UI

**Solution**:
1. Check browser console (F12)
2. Verify localStorage has the token:
   ```javascript
   localStorage.getItem('api_token')
   ```
3. If null, set it again:
   ```javascript
   localStorage.setItem('api_token', 'change_me')
   ```
4. Refresh the page

**Problem**: "Insufficient permissions" error

**Solution**:
- Your token may have read-only access
- Check the token role in `API_TOKENS`
- Use a token with `admin` or `config.write` role

**Problem**: Config drawer shows "Failed to load services"

**Solution**:
1. Check config-manager is running:
   ```bash
   docker compose ps config-manager
   ```
2. Check config-manager logs:
   ```bash
   docker compose logs config-manager --tail=20
   ```
3. Verify the token in the logs:
   ```
   Created admin API token from MQTT password.
   Use X-API-Token header with value: change_me
   ```

### Persistent Setup

The token is stored in browser `localStorage`, so it persists across page refreshes. However, it's per-browser, so you'll need to set it on each device/browser you use.

### Security Notes

- **Development**: Using MQTT password as token is convenient
- **Production**: Generate a strong random token with `openssl rand -base64 32`
- **HTTPS**: In production, always use HTTPS to protect the token in transit
- Never commit tokens to version control
