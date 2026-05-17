"""Ed25519 signature creation and verification using PyNaCl."""
import nacl.signing
import nacl.exceptions


def generate_keypair(seed: bytes | None = None) -> tuple[nacl.signing.SigningKey, nacl.signing.VerifyKey]:
    if seed is not None:
        sk = nacl.signing.SigningKey(seed)
    else:
        sk = nacl.signing.SigningKey.generate()
    return sk, sk.verify_key


def sign(sk: nacl.signing.SigningKey, data: bytes) -> bytes:
    return sk.sign(data).signature


def verify(vk: nacl.signing.VerifyKey, data: bytes, signature: bytes) -> bool:
    try:
        vk.verify(data, signature)
        return True
    except (nacl.exceptions.BadSignatureError, Exception):
        return False


def vk_to_bytes(vk: nacl.signing.VerifyKey) -> bytes:
    return bytes(vk)


def vk_from_bytes(b: bytes) -> nacl.signing.VerifyKey:
    return nacl.signing.VerifyKey(b)


def sk_to_bytes(sk: nacl.signing.SigningKey) -> bytes:
    return bytes(sk)


def sk_from_bytes(b: bytes) -> nacl.signing.SigningKey:
    return nacl.signing.SigningKey(b)
