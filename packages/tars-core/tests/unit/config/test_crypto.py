"""Unit tests for cryptography functions."""

import base64

import pytest

from tars.config.crypto import (
    decrypt_secret,
    encrypt_secret,
    generate_ed25519_keypair,
    generate_hmac_key,
    generate_master_key,
    sign_cache,
    sign_message,
    verify_cache,
    verify_signature,
)


class TestAESEncryption:
    """Test AES-256-GCM encryption and decryption."""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Test that encryption and decryption are reversible."""
        key, _ = generate_master_key()
        plaintext = "my secret password"

        encrypted = encrypt_secret(plaintext, key)
        decrypted = decrypt_secret(encrypted, key)

        assert decrypted == plaintext

    def test_different_ciphertexts_same_plaintext(self) -> None:
        """Test that encrypting the same plaintext produces different ciphertexts (random nonce)."""
        key, _ = generate_master_key()
        plaintext = "same secret"

        encrypted1 = encrypt_secret(plaintext, key)
        encrypted2 = encrypt_secret(plaintext, key)

        assert encrypted1 != encrypted2  # Different nonces
        assert decrypt_secret(encrypted1, key) == plaintext
        assert decrypt_secret(encrypted2, key) == plaintext

    def test_invalid_key_length_raises_error(self) -> None:
        """Test that invalid key length raises ValueError."""
        invalid_key = base64.b64encode(b"short").decode()
        with pytest.raises(ValueError, match="must be 32 bytes"):
            encrypt_secret("test", invalid_key)

    def test_wrong_key_fails_decryption(self) -> None:
        """Test that decryption with wrong key raises error."""
        key1, _ = generate_master_key()
        key2, _ = generate_master_key()
        plaintext = "secret"

        encrypted = encrypt_secret(plaintext, key1)

        with pytest.raises(Exception):  # cryptography raises InvalidTag
            decrypt_secret(encrypted, key2)


class TestEd25519Signatures:
    """Test Ed25519 signature generation and verification."""

    def test_sign_verify_roundtrip(self) -> None:
        """Test that signature verification succeeds for valid signatures."""
        private_key, public_key = generate_ed25519_keypair()
        message = b"Hello, TARS!"

        signature = sign_message(message, private_key)
        assert verify_signature(message, signature, public_key)

    def test_wrong_message_fails_verification(self) -> None:
        """Test that verification fails for different message."""
        private_key, public_key = generate_ed25519_keypair()
        message1 = b"original message"
        message2 = b"tampered message"

        signature = sign_message(message1, private_key)
        assert not verify_signature(message2, signature, public_key)

    def test_wrong_public_key_fails_verification(self) -> None:
        """Test that verification fails with wrong public key."""
        private_key1, _ = generate_ed25519_keypair()
        _, public_key2 = generate_ed25519_keypair()
        message = b"test message"

        signature = sign_message(message, private_key1)
        assert not verify_signature(message, signature, public_key2)

    def test_tampered_signature_fails_verification(self) -> None:
        """Test that tampered signature fails verification."""
        private_key, public_key = generate_ed25519_keypair()
        message = b"message"

        signature = sign_message(message, private_key)
        # Tamper with signature
        tampered_sig = signature[:-4] + "XXXX"

        assert not verify_signature(message, tampered_sig, public_key)


class TestHMACCacheSigning:
    """Test HMAC-SHA256 cache signing and verification."""

    def test_sign_verify_cache_roundtrip(self) -> None:
        """Test that cache verification succeeds for valid signature."""
        key, _ = generate_hmac_key()
        cache_data = {"service1": {"key": "value"}, "service2": {"another": "config"}}

        signed = sign_cache(cache_data, key)
        verified = verify_cache(signed, key)

        assert verified == cache_data

    def test_tampered_payload_fails_verification(self) -> None:
        """Test that tampered payload fails verification."""
        key, _ = generate_hmac_key()
        cache_data = {"service1": {"key": "value"}}

        signed = sign_cache(cache_data, key)
        # Tamper with payload
        signed["payload"]["service1"]["key"] = "tampered"

        assert verify_cache(signed, key) is None

    def test_tampered_signature_fails_verification(self) -> None:
        """Test that tampered signature fails verification."""
        key, _ = generate_hmac_key()
        cache_data = {"service1": {"key": "value"}}

        signed = sign_cache(cache_data, key)
        # Tamper with signature
        signed["signature"] = "0" * 64

        assert verify_cache(signed, key) is None

    def test_wrong_key_fails_verification(self) -> None:
        """Test that verification fails with wrong key."""
        key1, _ = generate_hmac_key()
        key2, _ = generate_hmac_key()
        cache_data = {"service1": {"key": "value"}}

        signed = sign_cache(cache_data, key1)
        assert verify_cache(signed, key2) is None


class TestKeyGeneration:
    """Test key generation functions."""

    def test_generate_master_key_format(self) -> None:
        """Test that generated master key has correct format."""
        key_base64, key_id = generate_master_key()

        # Verify base64 decoding works
        key_bytes = base64.b64decode(key_base64)
        assert len(key_bytes) == 32  # 256 bits

        # Verify UUID format
        assert len(key_id) == 36  # UUID string length
        assert key_id.count("-") == 4

    def test_generate_hmac_key_format(self) -> None:
        """Test that generated HMAC key has correct format."""
        key_base64, key_id = generate_hmac_key()

        key_bytes = base64.b64decode(key_base64)
        assert len(key_bytes) == 32

        assert len(key_id) == 36
        assert key_id.count("-") == 4

    def test_generate_ed25519_keypair_format(self) -> None:
        """Test that generated Ed25519 keys are valid PEM."""
        private_pem, public_pem = generate_ed25519_keypair()

        assert "-----BEGIN PRIVATE KEY-----" in private_pem
        assert "-----END PRIVATE KEY-----" in private_pem
        assert "-----BEGIN PUBLIC KEY-----" in public_pem
        assert "-----END PUBLIC KEY-----" in public_pem
