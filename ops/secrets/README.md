# MQTT Configuration Signing Keys

This directory contains Ed25519 key pairs used for cryptographic signing and verification of MQTT configuration updates.

## Files

- `signature_private_key.pem` - Private key used by config-manager to sign MQTT messages (DO NOT COMMIT)
- `signature_public_key.pem` - Public key used by services (STT, TTS, etc.) to verify signatures (DO NOT COMMIT)

## Generation

Generate new key pairs with:

```bash
cd py-tars
python3 << 'EOF'
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

# Generate Ed25519 key pair
private_key = Ed25519PrivateKey.generate()
public_key = private_key.public_key()

# Serialize private key
private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

# Serialize public key
public_pem = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

# Write to files
with open("ops/secrets/signature_private_key.pem", "wb") as f:
    f.write(private_pem)

with open("ops/secrets/signature_public_key.pem", "wb") as f:
    f.write(public_pem)

print("✓ Generated Ed25519 key pair")
EOF
```

## Docker Mount

These keys are mounted read-only into containers at `/etc/tars/secrets/`:

```yaml
volumes:
  - ./secrets:/etc/tars/secrets:ro
```

## Key Loading Priority

Services attempt to load keys in this order:

1. `/run/secrets/signature_*_key.pem` (Docker secrets mount)
2. `/etc/tars/secrets/signature_*_key.pem` (volume mount) ← **Current method**
3. `CONFIG_SIGNATURE_*_KEY_B64` (base64-encoded environment variable)
4. `CONFIG_SIGNATURE_*_KEY` (plain PEM environment variable)

## Security

- **Private key** (`signature_private_key.pem`): 
  - Only config-manager needs access
  - Used to sign MQTT configuration messages
  - DO NOT share or commit to version control

- **Public key** (`signature_public_key.pem`):
  - All services (STT, TTS, Router, LLM) need read access
  - Used to verify configuration message signatures
  - Safe to share within trusted infrastructure, but still excluded from git

## Rotation

To rotate keys:

1. Generate new key pair (see generation script above)
2. Restart config-manager to load new private key
3. Restart all services to load new public key
4. Verify MQTT live updates work in logs

No database changes or .env updates required with the file-based approach.
