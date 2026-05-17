"""SHA-256 Merkle tree for transaction hashing."""
import hashlib
from typing import List, Optional


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def merkle_root(hashes: List[bytes]) -> bytes:
    if not hashes:
        return sha256(b"")
    if len(hashes) == 1:
        return hashes[0]

    level = list(hashes)
    while len(level) > 1:
        next_level = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else left
            next_level.append(sha256(left + right))
        level = next_level
    return level[0]


def merkle_proof(hashes: List[bytes], index: int) -> List[tuple[bytes, str]]:
    """Generate a Merkle proof for the leaf at `index`. Returns list of (hash, direction) pairs."""
    if not hashes or index >= len(hashes):
        return []

    proof = []
    level = list(hashes)
    idx = index

    while len(level) > 1:
        next_level = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else left
            next_level.append(sha256(left + right))

        sibling_idx = idx ^ 1
        if sibling_idx < len(level):
            if idx % 2 == 0:
                proof.append((level[sibling_idx], "right"))
            else:
                proof.append((level[sibling_idx], "left"))

        idx = idx // 2
        level = next_level

    return proof


def verify_merkle_proof(root: bytes, leaf_hash: bytes, proof: List[tuple[bytes, str]]) -> bool:
    current = leaf_hash
    for h, direction in proof:
        if direction == "right":
            current = sha256(current + h)
        else:
            current = sha256(h + current)
    return current == root
