"""Transaction workload generator for benchmarks."""
import random
import time
from typing import List, Tuple

from ..core.transaction import Transaction, TransactionMeta, Domain
from ..ml.generate_data import TRANSACTION_PROFILES, DOMAIN_WEIGHTS


class WorkloadGenerator:
    """Generates synthetic transaction workloads for benchmarking."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def generate_one(self) -> Transaction:
        domain_list = list(DOMAIN_WEIGHTS.keys())
        domain_weights = [DOMAIN_WEIGHTS[d] for d in domain_list]
        domain = self.rng.choices(domain_list, weights=domain_weights, k=1)[0]

        types_for_domain = [
            t for t, p in TRANSACTION_PROFILES.items() if p["domain"] == domain
        ]
        sem_type = self.rng.choice(types_for_domain)
        profile = TRANSACTION_PROFILES[sem_type]

        meta = TransactionMeta(
            domain=domain,
            semantic_type=sem_type,
            urgency=self._sample(profile["urgency"]),
            economic_value=self._sample(profile["value"]),
            submitter_reputation=self._sample(profile["reputation"]),
            latency_sensitivity=self._sample(profile["latency"]),
            regulatory_class=self._sample(profile["regulatory"]),
        )
        return Transaction(meta=meta, timestamp=time.time())

    def generate_batch(self, n: int) -> List[Transaction]:
        return [self.generate_one() for _ in range(n)]

    def _sample(self, range_tuple: Tuple[float, float]) -> float:
        return range_tuple[0] + (range_tuple[1] - range_tuple[0]) * self.rng.random()

    async def generate_stream(self, n: int, tps: int = 50):
        """Yield transactions at the specified rate."""
        import asyncio
        interval = 1.0 / tps
        for i in range(n):
            yield self.generate_one()
            if i < n - 1:
                await asyncio.sleep(interval)
