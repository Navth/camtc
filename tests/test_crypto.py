"""Unit tests for crypto modules."""
import unittest

from camtc.crypto.signatures import generate_keypair, sign, verify
from camtc.crypto.merkle import sha256, merkle_root, merkle_proof, verify_merkle_proof
from camtc.crypto.encryption import generate_key, encrypt, decrypt
from camtc.crypto.vrf import vrf_evaluate, vrf_verify, vrf_output_to_float


class TestSignatures(unittest.TestCase):
    def test_sign_verify(self):
        sk, vk = generate_keypair()
        data = b"hello world"
        sig = sign(sk, data)
        self.assertTrue(verify(vk, data, sig))

    def test_invalid_signature(self):
        sk, vk = generate_keypair()
        sig = sign(sk, b"original")
        self.assertFalse(verify(vk, b"tampered", sig))


class TestMerkle(unittest.TestCase):
    def test_root_single(self):
        h = sha256(b"a")
        self.assertEqual(merkle_root([h]), h)

    def test_proof_verification(self):
        hashes = [sha256(f"tx{i}".encode()) for i in range(7)]
        root = merkle_root(hashes)
        proof = merkle_proof(hashes, 3)
        self.assertTrue(verify_merkle_proof(root, hashes[3], proof))

    def test_empty(self):
        root = merkle_root([])
        self.assertEqual(len(root), 32)


class TestEncryption(unittest.TestCase):
    def test_encrypt_decrypt(self):
        key = generate_key()
        plaintext = b"sensitive data"
        ct, nonce = encrypt(plaintext, key)
        pt = decrypt(ct, nonce, key)
        self.assertEqual(pt, plaintext)


class TestVRF(unittest.TestCase):
    def test_evaluate_verify(self):
        sk, vk = generate_keypair()
        alpha = b"seed-input"
        output, proof = vrf_evaluate(bytes(sk), alpha)
        self.assertTrue(vrf_verify(bytes(vk), alpha, output, proof))

    def test_output_range(self):
        sk, vk = generate_keypair()
        output, _ = vrf_evaluate(bytes(sk), b"test")
        f = vrf_output_to_float(output)
        self.assertGreaterEqual(f, 0.0)
        self.assertLess(f, 1.0)


if __name__ == "__main__":
    unittest.main()
