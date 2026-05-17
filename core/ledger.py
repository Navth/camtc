"""Ledger - hash-chained block storage with snapshot support."""
import json
import os
from typing import List, Optional, Dict

from .block import Block
from .transaction import Transaction


class Ledger:
    def __init__(self, node_id: int, snapshot_dir: str = ""):
        self.node_id = node_id
        self.blocks: Dict[int, Block] = {}      # height -> Block
        self.height = 0
        self.snapshot_dir = snapshot_dir
        self.tier_heights: Dict[int, int] = {1: 0, 2: 0, 3: 0}
        self._tx_index: Dict[str, Transaction] = {}

    def append(self, block: Block) -> None:
        block.height = self.height
        self.blocks[self.height] = block
        self.height += 1
        self.tier_heights[block.tier] = self.tier_heights.get(block.tier, 0) + 1
        for tx in block.transactions:
            tx.committed_at = block.timestamp
            self._tx_index[tx.tx_id] = tx

    def get_block(self, height: int) -> Optional[Block]:
        return self.blocks.get(height)

    def get_transaction(self, tx_id: str) -> Optional[Transaction]:
        return self._tx_index.get(tx_id)

    def last_block_hash(self) -> bytes:
        if self.height == 0:
            return b"\x00" * 32
        return self.blocks[self.height - 1].hash()

    def snapshot(self) -> dict:
        return {
            "node_id": self.node_id,
            "height": self.height,
            "tier_heights": self.tier_heights,
            "last_hash": self.last_block_hash().hex(),
        }

    def save_snapshot(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.snapshot(), f)

    def load_snapshot(self, path: str) -> None:
        if not os.path.exists(path):
            return
        with open(path, "r") as f:
            data = json.load(f)
        self.height = data["height"]
        self.tier_heights = data.get("tier_heights", {1: 0, 2: 0, 3: 0})

    def get_all_transactions(self) -> List[Transaction]:
        txs = []
        for h in sorted(self.blocks.keys()):
            txs.extend(self.blocks[h].transactions)
        return txs

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "height": self.height,
            "tier_heights": self.tier_heights,
            "total_tx": len(self._tx_index),
        }
