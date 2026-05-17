"""Ethereum Anchoring Layer — submits state roots to EVM smart contract."""
import hashlib
import time
from typing import List, Optional

from ..core.block import Block


class AnchorEntry:
    def __init__(self, index: int, merkle_root: bytes, block_height: int,
                 epoch: int, commit_cert_hash: bytes, timestamp: float):
        self.index = index
        self.merkle_root = merkle_root
        self.block_height = block_height
        self.epoch = epoch
        self.commit_cert_hash = commit_cert_hash
        self.timestamp = timestamp


class EthereumAnchorSimulator:
    """Simulates Ethereum anchoring (works without a real Ethereum node)."""

    def __init__(self, async_mode: bool = True):
        self.entries: List[AnchorEntry] = []
        self.async_mode = async_mode
        self._anchor_count = 0
        self._pending: List[Block] = []

    def _to_bytes32(self, data: bytes) -> bytes:
        return data.ljust(32, b"\x00")[:32]

    def anchor_block(self, block: Block) -> AnchorEntry:
        """Submit a committed block's state root to the simulated Ethereum contract."""
        merkle_root = self._to_bytes32(block.merkle_root)
        commit_cert_hash = self._to_bytes32(block.hash())

        entry = AnchorEntry(
            index=self._anchor_count,
            merkle_root=merkle_root,
            block_height=block.height,
            epoch=block.epoch,
            commit_cert_hash=commit_cert_hash,
            timestamp=time.time(),
        )
        self.entries.append(entry)
        self._anchor_count += 1
        return entry

    async def anchor_block_async(self, block: Block):
        """Async anchoring — simulates ~12s Ethereum confirmation."""
        import asyncio
        await asyncio.sleep(0.01)  # Simulated short delay for demo
        return self.anchor_block(block)

    def verify_anchor(self, index: int, merkle_root: bytes) -> bool:
        if index >= len(self.entries):
            return False
        return self.entries[index].merkle_root == self._to_bytes32(merkle_root)

    def get_anchors(self) -> List[dict]:
        return [
            {
                "index": e.index,
                "merkle_root": e.merkle_root.hex()[:16],
                "block_height": e.block_height,
                "epoch": e.epoch,
                "timestamp": e.timestamp,
            }
            for e in self.entries
        ]

    def stats(self) -> dict:
        return {
            "total_anchors": self._anchor_count,
            "pending": len(self._pending),
        }
