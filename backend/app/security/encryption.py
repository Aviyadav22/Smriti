"""Field-level encryption using AES-256-GCM.

Provides symmetric encryption/decryption for sensitive database fields
(e.g., PII, API keys) using the ``cryptography`` library.
"""

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_NONCE_SIZE: int = 12  # 96 bits, recommended for AES-GCM


def _get_key() -> bytes:
    """Derive the AES-256 key from the application's encryption_key setting.

    The ``settings.encryption_key`` is expected to be a 64-character hex
    string (32 bytes / 256 bits) or a base64-encoded 32-byte key.

    Returns:
        A 32-byte key suitable for AES-256.

    Raises:
        ValueError: If the configured key cannot be decoded to 32 bytes.
    """
    raw = settings.encryption_key

    # Try hex decoding first (64-char hex string → 32 bytes)
    try:
        key = bytes.fromhex(raw)
        if len(key) == 32:
            return key
    except ValueError:
        pass

    # Try base64 decoding
    try:
        key = base64.b64decode(raw)
        if len(key) == 32:
            return key
    except ValueError:
        pass

    raise ValueError(
        "encryption_key must be a 64-character hex string or "
        "base64-encoded 32-byte key"
    )


def encrypt_field(plaintext: str) -> str:
    """Encrypt a string field using AES-256-GCM.

    The output is a base64-encoded concatenation of
    ``nonce (12 bytes) + ciphertext + tag (16 bytes)``.

    Args:
        plaintext: The value to encrypt.

    Returns:
        Base64-encoded encrypted string.
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(_NONCE_SIZE)

    # AESGCM.encrypt returns ciphertext + tag concatenated
    ciphertext_with_tag = aesgcm.encrypt(
        nonce, plaintext.encode("utf-8"), None
    )

    # Concatenate nonce + ciphertext + tag and base64-encode
    encrypted = nonce + ciphertext_with_tag
    return base64.b64encode(encrypted).decode("utf-8")


def decrypt_field(ciphertext: str) -> str:
    """Decrypt a string field encrypted with ``encrypt_field``.

    Args:
        ciphertext: Base64-encoded encrypted string (nonce + ciphertext + tag).

    Returns:
        The decrypted plaintext string.

    Raises:
        ValueError: If decryption fails (wrong key, tampered data, etc.).
    """
    key = _get_key()
    aesgcm = AESGCM(key)

    try:
        raw = base64.b64decode(ciphertext)
    except ValueError as exc:
        raise ValueError(f"Invalid base64 ciphertext: {exc}")

    if len(raw) < _NONCE_SIZE + 16:
        raise ValueError(
            "Ciphertext too short: must contain at least nonce + tag"
        )

    nonce = raw[:_NONCE_SIZE]
    encrypted_data = raw[_NONCE_SIZE:]

    try:
        plaintext_bytes = aesgcm.decrypt(nonce, encrypted_data, None)
    except (ValueError, OverflowError, InvalidTag) as exc:
        raise ValueError(f"Decryption failed: {exc}") from exc

    return plaintext_bytes.decode("utf-8")
