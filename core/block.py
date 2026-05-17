"""Block model for CAMTC ledger."""
import time
from dataclasses import dataclass, field
from typing import List, Optional

from ..crypto.merkle import sha256, merkle_root
from .transaction import Transaction


@dataclass
class Block:
    height: int
    epoch: int
    tier: int                          # 1, 2, or 3
    transactions: List[Transaction] = field(default_factory=list)
    prev_hash: bytes = b"\x00" * 32
    proposer_vk: bytes = b""
    timestamp: float = field(default_factory=time.time)
    signature: bytes = b""

    commit_cert_hash: bytes = b""
    state_root: bytes = b""

    @property
    def tx_hashes(self) -> List[bytes]:
        return [tx.hash() for tx in self.transactions]

    @property
    def merkle_root(self) -> bytes:
        return merkle_root(self.tx_hashes)

    def hash(self) -> bytes:
        data = (
            str(self.height).encode()
            + str(self.epoch).encode()
            + str(self.tier).encode()
            + self.merkle_root
            + self.prev_hash
            + self.proposer_vk
            + f"{self.timestamp:.6f}".encode()
        )
        return sha256(data)

    def to_dict(self) -> dict:
        return {
            "height": self.height,
            "epoch": self.epoch,
            "tier": self.tier,
            "num_tx": len(self.transactions),
            "merkle_root": self.merkle_root.hex()[:16],
            "timestamp": self.timestamp,
            "tx_ids": [tx.tx_id for tx in self.transactions],
        }
