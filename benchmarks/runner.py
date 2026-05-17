"""Benchmark runner — compares CAMTC against baseline protocols."""
import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import List, Dict

from ..core.transaction import Transaction
from ..core.block import Block
from .workload import WorkloadGenerator
from .baselines.protocols import PBFTBaseline, HotStuffBaseline, TendermintBaseline


@dataclass
class BenchmarkResult:
    protocol: str
    n_tx: int
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    tps: float
    total_time_s: float


class BenchmarkRunner:
    """Runs benchmarks comparing CAMTC with baseline protocols."""

    def __init__(self, n_nodes: int = 10, seed: int = 42):
        self.n_nodes = n_nodes
        self.seed = seed
        self.results: List[BenchmarkResult] = []

    def run_baseline(
        self,
        protocol_name: str,
        txs: List[Transaction],
        batch_size: int = 10,
        delay_ms: float = 100,
    ) -> BenchmarkResult:
        rng = random.Random(self.seed)
        protocols = {
            "PBFT": PBFTBaseline(self.n_nodes, self.seed),
            "HotStuff": HotStuffBaseline(self.n_nodes, self.seed),
            "Tendermint": TendermintBaseline(self.n_nodes, self.seed),
        }
        protocol = protocols[protocol_name]

        start_time = time.time()
        latencies = []

        for i in range(0, len(txs), batch_size):
            batch = txs[i:i + batch_size]
            injected_delay = rng.uniform(20, 200)
            result = protocol.process_batch(batch, delay_ms=injected_delay)
            for tx in batch:
                lat = tx.latency_ms
                if lat > 0:
                    latencies.append(lat)

        total_time = time.time() - start_time

        if not latencies:
            latencies = [0]

        latencies.sort()
        n = len(latencies)
        result = BenchmarkResult(
            protocol=protocol_name,
            n_tx=len(txs),
            mean_latency_ms=sum(latencies) / n,
            p50_latency_ms=latencies[n // 2],
            p95_latency_ms=latencies[int(n * 0.95)] if n > 1 else latencies[0],
            min_latency_ms=latencies[0],
            max_latency_ms=latencies[-1],
            tps=len(txs) / total_time if total_time > 0 else 0,
            total_time_s=total_time,
        )
        self.results.append(result)
        return result

    def run_all_baselines(
        self,
        n_tx: int = 10000,
        tps_target: int = 50,
    ) -> List[BenchmarkResult]:
        gen = WorkloadGenerator(seed=self.seed)
        txs = gen.generate_batch(n_tx)

        results = []
        for proto in ["PBFT", "HotStuff", "Tendermint"]:
            r = self.run_baseline(proto, txs, batch_size=10, delay_ms=100)
            results.append(r)
        return results

    def to_dict(self) -> List[dict]:
        return [
            {
                "protocol": r.protocol,
                "n_tx": r.n_tx,
                "mean_latency_ms": round(r.mean_latency_ms, 1),
                "p50_latency_ms": round(r.p50_latency_ms, 1),
                "p95_latency_ms": round(r.p95_latency_ms, 1),
                "tps": round(r.tps, 1),
            }
            for r in self.results
        ]
