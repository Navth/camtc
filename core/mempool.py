"""Tiered mempool with three priority queues and batch assembly."""
import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional

from .transaction import Transaction


@dataclass
class QueueStats:
    size: int = 0
    max_batch: int = 0
    batch_wait_ms: int = 0


class TieredMempool:
    def __init__(
        self,
        tier1_batch: int = 5, tier1_wait_ms: int = 0,
        tier2_batch: int = 20, tier2_wait_ms: int = 2000,
        tier3_batch: int = 50, tier3_wait_ms: int = 10000,
    ):
        self.queues: dict[int, deque[Transaction]] = {
            1: deque(), 2: deque(), 3: deque(),
        }
        self.batch_sizes = {1: tier1_batch, 2: tier2_batch, 3: tier3_batch}
        self.batch_waits = {1: tier1_wait_ms, 2: tier2_wait_ms, 3: tier3_wait_ms}
        self._batch_timers: dict[int, float] = {1: 0, 2: 0, 3: 0}

    def enqueue(self, tx: Transaction) -> None:
        tier = tx.tier
        if tier not in self.queues:
            tier = 3
            tx.tier = 3
        self.queues[tier].append(tx)
        if self._batch_timers[tier] == 0:
            self._batch_timers[tier] = time.time()

    def dequeue_batch(self, tier: int) -> List[Transaction]:
        q = self.queues[tier]
        batch_size = self.batch_sizes[tier]
        batch = []
        while q and len(batch) < batch_size:
            batch.append(q.popleft())
        self._batch_timers[tier] = 0 if not q else self._batch_timers[tier]
        return batch

    def ready_batches(self) -> List[int]:
        """Return tier numbers that have enough transactions or have waited long enough."""
        ready = []
        now = time.time()
        for tier in [1, 2, 3]:
            q = self.queues[tier]
            if not q:
                continue
            wait = self.batch_waits[tier] / 1000.0
            if len(q) >= self.batch_sizes[tier]:
                ready.append(tier)
            elif wait > 0 and self._batch_timers[tier] > 0:
                elapsed = now - self._batch_timers[tier]
                if elapsed >= wait:
                    ready.append(tier)
            elif tier == 1 and len(q) > 0:
                ready.append(tier)
        return ready

    def queue_depth(self, tier: int) -> int:
        return len(self.queues.get(tier, deque()))

    def queue_depths(self) -> tuple[int, int, int]:
        return (
            len(self.queues[1]),
            len(self.queues[2]),
            len(self.queues[3]),
        )

    def stats(self) -> dict:
        return {
            f"tier{t}": QueueStats(
                size=len(self.queues[t]),
                max_batch=self.batch_sizes[t],
                batch_wait_ms=self.batch_waits[t],
            )
            for t in [1, 2, 3]
        }
