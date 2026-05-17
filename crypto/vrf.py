"""Simplified VRF (Verifiable Random Function) using Ed25519.

Implements a hash-based VRF: evaluate VRF on a seed using the private key,
producing a pseudorandom output and a proof that can be verified with the public key.
"""
import hashlib
import struct
from typing import Tuple

from .signatures import nacl


def _hash(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def vrf_evaluate(sk_bytes: bytes, alpha: bytes) -> Tuple[bytes, bytes]:
    """Evaluate VRF. Returns (output_hash, proof).

    Simplified construction: sign the alpha input, then derive the VRF output
    from the signature. The proof IS the signature.
    """
    sk = nacl.signing.SigningKey(sk_bytes)
    message = b"VRF:" + alpha
    signed = sk.sign(message)
    proof = signed.signature
    output = _hash(proof)[:32]
    return output, proof


def vrf_verify(vk_bytes: bytes, alpha: bytes, output: bytes, proof: bytes) -> bool:
    """Verify a VRF output against the public key and input."""
    vk = nacl.signing.VerifyKey(vk_bytes)
    message = b"VRF:" + alpha
    try:
        vk.verify(message, proof)
    except (nacl.exceptions.BadSignatureError, Exception):
        return False
    expected_output = _hash(proof)[:32]
    return output == expected_output


def vrf_output_to_float(output: bytes) -> float:
    """Convert a 32-byte VRF output to a float in [0, 1)."""
    value = int.from_bytes(output[:8], "big")
    return value / (2**64)


def is_eligible(vrf_float: float, threshold: float) -> bool:
    return vrf_float < threshold
