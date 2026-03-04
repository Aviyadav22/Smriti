"""Unit tests for AES-256-GCM field-level encryption."""

from unittest.mock import patch

import pytest

from app.security.encryption import decrypt_field, encrypt_field


# 32-byte key as 64-char hex string
_TEST_KEY_HEX = "a" * 64  # 32 bytes of 0xaa


@pytest.fixture(autouse=True)
def mock_settings():
    """Patch encryption key for all tests."""
    with patch("app.security.encryption.settings") as mock:
        mock.encryption_key = _TEST_KEY_HEX
        yield mock


class TestEncryptDecrypt:
    """Tests for encrypt_field and decrypt_field."""

    def test_round_trip(self):
        plaintext = "Sensitive PII data"
        encrypted = encrypt_field(plaintext)
        decrypted = decrypt_field(encrypted)
        assert decrypted == plaintext

    def test_encrypted_differs_from_plaintext(self):
        plaintext = "test data"
        encrypted = encrypt_field(plaintext)
        assert encrypted != plaintext

    def test_different_encryptions_produce_different_output(self):
        """Each encryption uses a random nonce, so outputs differ."""
        e1 = encrypt_field("same text")
        e2 = encrypt_field("same text")
        assert e1 != e2  # Different nonces

    def test_round_trip_unicode(self):
        plaintext = "Unicode: अनुच्छेद 21 — Right to Life"
        encrypted = encrypt_field(plaintext)
        decrypted = decrypt_field(encrypted)
        assert decrypted == plaintext

    def test_round_trip_empty_string(self):
        encrypted = encrypt_field("")
        decrypted = decrypt_field(encrypted)
        assert decrypted == ""

    def test_tampered_ciphertext_fails(self):
        encrypted = encrypt_field("test")
        # Tamper with the ciphertext
        tampered = encrypted[:-4] + "XXXX"
        with pytest.raises(ValueError):
            decrypt_field(tampered)

    def test_invalid_base64_fails(self):
        with pytest.raises(ValueError):
            decrypt_field("not-valid-base64!!!")

    def test_too_short_ciphertext_fails(self):
        import base64
        short = base64.b64encode(b"short").decode()
        with pytest.raises(ValueError, match="too short"):
            decrypt_field(short)


class TestKeyValidation:
    """Tests for key parsing."""

    def test_invalid_key_raises(self):
        with patch("app.security.encryption.settings") as mock:
            mock.encryption_key = "too-short"
            with pytest.raises(ValueError, match="encryption_key"):
                encrypt_field("test")

    def test_base64_key_works(self):
        import base64
        key_bytes = b"\x42" * 32
        b64_key = base64.b64encode(key_bytes).decode()
        with patch("app.security.encryption.settings") as mock:
            mock.encryption_key = b64_key
            encrypted = encrypt_field("base64 key test")
            decrypted = decrypt_field(encrypted)
            assert decrypted == "base64 key test"
