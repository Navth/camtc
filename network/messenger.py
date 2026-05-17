"""Inter-node messaging with simulated WAN latency."""
import asyncio
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Message:
    sender: int
    recipient: int
    msg_type: str
    payload: Any
    timestamp: float = field(default_factory=time.time)
    deliver_at: float = 0.0


class Messenger:
    """Simulates network communication between nodes with configurable WAN delay."""

    def __init__(
        self,
        n_nodes: int,
        delay_min_ms: int = 20,
        delay_max_ms: int = 200,
        seed: int = 42,
    ):
        self.n_nodes = n_nodes
        self.delay_min = delay_min_ms / 1000.0
        self.delay_max = delay_max_ms / 1000.0
        self.rng = random.Random(seed)
        self._queues: Dict[int, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._inflight: List[Message] = []
        self._handlers: Dict[int, Dict[str, Callable]] = defaultdict(dict)
        self._running = False
        self._stats = {"sent": 0, "delivered": 0, "dropped": 0}

    def register_handler(self, node_id: int, msg_type: str, handler: Callable):
        self._handlers[node_id][msg_type] = handler

    def get_delay(self) -> float:
        return self.rng.uniform(self.delay_min, self.delay_max)

    async def send(self, sender: int, recipient: int, msg_type: str, payload: Any):
        delay = self.get_delay()
        msg = Message(
            sender=sender,
            recipient=recipient,
            msg_type=msg_type,
            payload=payload,
            deliver_at=time.time() + delay,
        )
        self._inflight.append(msg)
        self._stats["sent"] += 1

    async def broadcast(self, sender: int, msg_type: str, payload: Any, exclude: Optional[set] = None):
        tasks = []
        for rid in range(self.n_nodes):
            if rid == sender or (exclude and rid in exclude):
                continue
            tasks.append(self.send(sender, rid, msg_type, payload))
        await asyncio.gather(*tasks)

    async def run_delivery_loop(self):
        self._running = True
        while self._running:
            now = time.time()
            delivered = []
            remaining = []
            for msg in self._inflight:
                if now >= msg.deliver_at:
                    delivered.append(msg)
                else:
                    remaining.append(msg)
            self._inflight = remaining

            for msg in delivered:
                handlers = self._handlers.get(msg.recipient, {})
                handler = handlers.get(msg.msg_type)
                if handler:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(msg)
                        else:
                            handler(msg)
                    except Exception:
                        pass
                self._stats["delivered"] += 1

            await asyncio.sleep(0.001)

    def stop(self):
        self._running = False

    def stats(self) -> dict:
        return dict(self._stats)
