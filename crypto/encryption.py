"""AES-256-GCM encryption for sensitive transaction payloads."""
import os
import nacl.utils
import nacl.secret


def encrypt(plaintext: bytes, key: bytes) -> tuple[bytes, bytes]:
    """Encrypt plaintext with AES-256-GCM. Returns (ciphertext, nonce)."""
    box = nacl.secret.SecretBox(key)
    nonce = nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE)
    ciphertext = box.encrypt(plaintext, nonce)
    return ciphertext.ciphertext, nonce


def decrypt(ciphertext: bytes, nonce: bytes, key: bytes) -> bytes:
    """Decrypt AES-256-GCM ciphertext."""
    box = nacl.secret.SecretBox(key)
    combined = nonce + ciphertext
    return box.decrypt(combined)


def generate_key() -> bytes:
    return nacl.utils.random(32)
