"""Cryptography functions for configuration management.

Provides:
- AES-256-GCM encryption for database secrets
- Ed25519 signatures for MQTT message authentication
- HMAC-SHA256 for LKG cache integrity verification
- Key generation and rotation support
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
import uuid
from typing import Any

import orjson
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# ===== AES-256-GCM Encryption =====


def encrypt_secret(plaintext: str, key_base64: str) -> str:
    """Encrypt secret using AES-256-GCM.

    Args:
        plaintext: Secret value to encrypt
        key_base64: Base64-encoded 32-byte key

    Returns:
        Base64-encoded nonce + ciphertext

    Raises:
        ValueError: If key is invalid
    """
    key = base64.b64decode(key_base64)
    if len(key) != 32:
        raise ValueError("Key must be 32 bytes for AES-256")

    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    # Return base64(nonce + ciphertext)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_secret(encrypted_base64: str, key_base64: str) -> str:
    """Decrypt secret using AES-256-GCM.

    Args:
        encrypted_base64: Base64-encoded nonce + ciphertext
        key_base64: Base64-encoded 32-byte key

    Returns:
        Decrypted plaintext

    Raises:
        ValueError: If key is invalid or decryption fails
    """
    key = base64.b64decode(key_base64)
    if len(key) != 32:
        raise ValueError("Key must be 32 bytes for AES-256")

    aesgcm = AESGCM(key)
    encrypted = base64.b64decode(encrypted_base64)
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]
    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext_bytes.decode()


async def encrypt_secret_async(plaintext: str, key_base64: str) -> str:
    """Async wrapper for encrypt_secret (offloads to thread pool)."""
    return await asyncio.to_thread(encrypt_secret, plaintext, key_base64)


async def decrypt_secret_async(encrypted_base64: str, key_base64: str) -> str:
    """Async wrapper for decrypt_secret (offloads to thread pool)."""
    return await asyncio.to_thread(decrypt_secret, encrypted_base64, key_base64)


# ===== Ed25519 Signatures =====


def generate_ed25519_keypair() -> tuple[str, str]:
    """Generate Ed25519 keypair for MQTT signing.

    Returns:
        Tuple of (private_key_pem, public_key_pem)
    """
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return private_pem.decode(), public_pem.decode()


def sign_message(message: bytes, private_key_pem: str) -> str:
    """Sign message with Ed25519 private key.

    Args:
        message: Message bytes to sign
        private_key_pem: PEM-encoded private key

    Returns:
        Base64-encoded signature
    """
    private_key_obj = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    if not isinstance(private_key_obj, ed25519.Ed25519PrivateKey):
        raise ValueError("Invalid Ed25519 private key")

    signature = private_key_obj.sign(message)
    return base64.b64encode(signature).decode()


def verify_signature(message: bytes, signature_b64: str, public_key_pem: str) -> bool:
    """Verify Ed25519 signature.

    Args:
        message: Message bytes that were signed
        signature_b64: Base64-encoded signature
        public_key_pem: PEM-encoded public key

    Returns:
        True if signature is valid, False otherwise
    """
    try:
        public_key_obj = serialization.load_pem_public_key(public_key_pem.encode())
        if not isinstance(public_key_obj, ed25519.Ed25519PublicKey):
            return False

        signature = base64.b64decode(signature_b64)
        public_key_obj.verify(signature, message)
        return True
    except Exception:
        return False


async def sign_message_async(message: bytes, private_key_pem: str) -> str:
    """Async wrapper for sign_message (offloads to thread pool)."""
    return await asyncio.to_thread(sign_message, message, private_key_pem)


async def verify_signature_async(message: bytes, signature_b64: str, public_key_pem: str) -> bool:
    """Async wrapper for verify_signature (offloads to thread pool)."""
    return await asyncio.to_thread(verify_signature, message, signature_b64, public_key_pem)


# ===== HMAC-SHA256 =====


def sign_cache(data: dict[str, Any], hmac_key_base64: str) -> dict[str, Any]:
    """Sign LKG cache with HMAC-SHA256.

    Args:
        data: Cache payload to sign
        hmac_key_base64: Base64-encoded HMAC key

    Returns:
        Signed cache with signature field
    """
    key = base64.b64decode(hmac_key_base64)
    payload = orjson.dumps(data, option=orjson.OPT_SORT_KEYS)
    signature = hmac.new(key, payload, hashlib.sha256).hexdigest()
    return {
        "payload": data,
        "signature": signature,
        "algorithm": "hmac-sha256",
    }


def verify_cache(signed_data: dict[str, Any], hmac_key_base64: str) -> dict[str, Any] | None:
    """Verify and extract LKG cache data.

    Args:
        signed_data: Signed cache with signature
        hmac_key_base64: Base64-encoded HMAC key

    Returns:
        Payload if signature is valid, None if tampered
    """
    try:
        key = base64.b64decode(hmac_key_base64)
        payload = orjson.dumps(signed_data["payload"], option=orjson.OPT_SORT_KEYS)
        expected_sig = hmac.new(key, payload, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected_sig, signed_data["signature"]):
            return signed_data["payload"]
        return None  # Tampered cache
    except (KeyError, ValueError, TypeError):
        return None


async def sign_cache_async(data: dict[str, Any], hmac_key_base64: str) -> dict[str, Any]:
    """Async wrapper for sign_cache (offloads to thread pool)."""
    return await asyncio.to_thread(sign_cache, data, hmac_key_base64)


async def verify_cache_async(
    signed_data: dict[str, Any], hmac_key_base64: str
) -> dict[str, Any] | None:
    """Async wrapper for verify_cache (offloads to thread pool)."""
    return await asyncio.to_thread(verify_cache, signed_data, hmac_key_base64)


# ===== Key Generation =====


def generate_master_key() -> tuple[str, str]:
    """Generate AES-256 master key for encryption.

    Returns:
        Tuple of (key_base64, key_id)
    """
    key = os.urandom(32)  # 256 bits for AES-256
    key_base64 = base64.b64encode(key).decode()
    key_id = str(uuid.uuid4())
    return key_base64, key_id


def generate_hmac_key() -> tuple[str, str]:
    """Generate HMAC key for cache signing.

    Returns:
        Tuple of (key_base64, key_id)
    """
    key = os.urandom(32)  # 256 bits for HMAC-SHA256
    key_base64 = base64.b64encode(key).decode()
    key_id = str(uuid.uuid4())
    return key_base64, key_id


def detect_key_rotation(current_key_id: str, db_key_id: str) -> bool:
    """Detect if encryption key has been rotated.

    Args:
        current_key_id: Key ID from environment
        db_key_id: Key ID stored in database

    Returns:
        True if rotation detected (IDs don't match)
    """
    return current_key_id != db_key_id
