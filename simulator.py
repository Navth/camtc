"""CAMTC Simulator — orchestrates the entire system end-to-end."""
import asyncio
import random
import time
import threading
from typing import Dict, List, Optional

from .config.settings import Settings
from .core.transaction import Transaction, TransactionMeta
from .core.block import Block
from .network.node import ValidatorNode
from .network.messenger import Messenger
from .ml.priority_net import PriorityNet, train_priority_net, save_model, load_model
from .ml.generate_data import generate_dataset
from .ml.rl_agent import RLAgent
from .anchor.ethereum_anchor import EthereumAnchorSimulator
from .benchmarks.runner import BenchmarkRunner


class CAMTCSimulator:
    """Full CAMTC simulation environment."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.nodes: List[ValidatorNode] = []
        self.messenger: Optional[Messenger] = None
        self.anchor = EthereumAnchorSimulator(async_mode=True)
        self.benchmark_runner = BenchmarkRunner(
            n_nodes=self.settings.n_validators,
            seed=self.settings.seed,
        )

        self.priority_net: Optional[PriorityNet] = None
        self.rl_agent = RLAgent()

        self._running = False
        self._benchmark_running = False
        self._benchmark_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.EventLoop] = None

        # Metrics
        self._total_tx = 0
        self._total_blocks = 0
        self._start_time = time.time()
        self._latencies: Dict[int, List[float]] = {1: [], 2: [], 3: []}
        self._byzantine_nodes: set = set()
        self._offline_nodes: set = set()

        self._init_nodes()

    def _init_nodes(self):
        for i in range(self.settings.n_validators):
            node = ValidatorNode(i, self.settings, priority_net=self.priority_net)
            node.on_commit = self._on_block_committed
            self.nodes.append(node)

    def train_priority_net(self, epochs: int = 200) -> dict:
        features, labels, types = generate_dataset(
            n=self.settings.dnn_train_size, seed=self.settings.seed
        )
        model, metrics = train_priority_net(
            features, labels,
            hidden_dim=self.settings.dnn_hidden_size,
            epochs=epochs,
            lr=self.settings.dnn_lr,
            seed=self.settings.seed,
        )
        self.priority_net = model

        # Update all nodes with the trained model
        for node in self.nodes:
            node.priority_net = model

        return {
            "status": "trained",
            "mse": round(metrics["final_val_mse"], 6),
            "accuracy": round(metrics["tier_accuracy"], 4),
            "epochs": epochs,
        }

    def train_rl_agent(self, steps: int = 5000) -> None:
        self.rl_agent.train(total_timesteps=steps)
        for node in self.nodes:
            node.rl_agent.model = self.rl_agent.model

    def submit_transaction(self, tx: Transaction) -> Transaction:
        if not self._running:
            self._running = True
            self._start_time = time.time()

        # Route through node 0 (primary gateway)
        primary = self.nodes[0]
        primary.receive_transaction(tx)
        self._total_tx += 1

        # Process through consensus
        self._process_pending()

        return tx

    def _process_pending(self):
        primary = self.nodes[0]
        for tier in [1, 2, 3]:
            ready = primary.mempool.ready_batches()
            # Also force-run if queue has items (sim mode: don't wait for timers)
            if tier in ready or primary.mempool.queue_depth(tier) > 0:
                self._run_consensus(tier)

    def _run_consensus(self, tier: int):
        primary = self.nodes[0]

        # VRF leader election
        all_ids = list(range(self.settings.n_validators))
        active = [i for i in all_ids if i not in self._offline_nodes]
        committee = active[:self._get_committee_size(tier)]

        # Select leader via VRF-weighted selection
        vscores = {i: primary.reputation.get_vscore(i) for i in committee}
        leader = primary.vrf_election.elect(
            {i: n.sk_bytes for i, n in enumerate(self.nodes) if i in committee},
            {i: n.vk_bytes for i, n in enumerate(self.nodes) if i in committee},
            primary.ledger.last_block_hash(),
            primary._epoch + 1,
            tier,
            vscores,
            tier_load=primary.mempool.queue_depth(tier) / max(primary.mempool.batch_sizes[tier], 1),
        )

        if leader is None:
            leader_id = committee[0] if committee else 0
        else:
            leader_id = leader[0]

        # Always use primary (node 0) mempool for batch assembly in simulation
        txs = primary.mempool.dequeue_batch(tier)
        if not txs:
            return

        block = primary.create_block(tier, txs)
        engine = primary.consensus.get_engine(tier)

        # Simulate Byzantine behavior
        n_byz = len([i for i in self._byzantine_nodes if i in committee])

        # Start proposal
        prev_committed = len(engine.committed_blocks)
        engine.start_proposal(block, leader_id)

        # Simulate prepare votes from committee
        for cid in committee:
            if cid in self._byzantine_nodes:
                continue  # Byzantine nodes may not vote
            if cid == leader_id:
                continue

            msg = type('Msg', (), {
                'epoch': engine.epoch,
                'tier': tier,
                'sender_id': cid,
                'block_hash': block.hash(),
                'block': block,
            })()
            result = engine.receive_prepare(msg)
            if result is None and engine.phase.name == "COMMITTED":
                break

        # Simulate commit phase if needed
        if engine.phase.name == "COMMIT":
            for cid in committee:
                if cid in self._byzantine_nodes:
                    continue
                if cid == leader_id:
                    continue
                msg = type('Msg', (), {
                    'epoch': engine.epoch,
                    'tier': tier,
                    'sender_id': cid,
                    'block_hash': block.hash(),
                })()
                committed = engine.receive_commit(msg)
                if committed:
                    break

        if len(engine.committed_blocks) > prev_committed:
            committed_block = engine.committed_blocks[-1]

            # Replicate to all nodes
            for node in self.nodes:
                if node.node_id != leader_id:
                    node.ledger.append(Block(
                        height=0,
                        epoch=committed_block.epoch,
                        tier=tier,
                        transactions=committed_block.transactions,
                        prev_hash=node.ledger.last_block_hash(),
                        proposer_vk=committed_block.proposer_vk,
                    ))

            self._total_blocks += 1

            # Anchor to Ethereum
            if tier in [1, 3]:  # Anchor Tier-1 and Tier-3 as per spec
                self.anchor.anchor_block(committed_block)

            # Record latencies
            now = time.time()
            for tx in committed_block.transactions:
                tx.committed_at = now
                lat = (now - tx.timestamp) * 1000
                self._latencies[tier].append(lat)

            # Update reputation
            primary.reputation.update(leader_id, "correct_proposal")

            # Update RL agent
            self.rl_agent.adapt(
                primary.mempool.queue_depths(),
                self._get_tier1_latency(),
            )

    def _get_committee_size(self, tier: int) -> int:
        sizes = {1: self.settings.tier1.committee_size,
                 2: self.settings.tier2.committee_size,
                 3: self.settings.tier3.committee_size}
        return sizes.get(tier, 10)

    def _on_block_committed(self, block: Block, tier: int):
        pass

    def _get_tier1_latency(self) -> float:
        lats = self._latencies.get(1, [])
        return sum(lats) / len(lats) if lats else 0.0

    def start_benchmark(self, n_tx: int = 10000, tps: int = 50):
        self._running = True
        self._start_time = time.time()
        self._benchmark_running = True

        # Generate workload
        rng = random.Random(self.settings.seed)
        gen = __import__("camtc.benchmarks.workload", fromlist=["WorkloadGenerator"]).WorkloadGenerator(
            seed=self.settings.seed
        )

        batch_size = max(1, tps // 10)
        txs = gen.generate_batch(n_tx)

        tier1_count = 0
        tier2_count = 0
        tier3_count = 0

        start_time = time.time()

        for i in range(0, n_tx, batch_size):
            batch = txs[i:i + batch_size]
            for tx in batch:
                primary = self.nodes[0]
                primary.receive_transaction(tx)
                self._total_tx += 1

            self._process_pending()

        # Process remaining
        for _ in range(20):
            self._process_pending()

        self._benchmark_running = False
        elapsed = time.time() - start_time

    def inject_byzantine(self, n_faulty: int = 1):
        available = [i for i in range(self.settings.n_validators) if i not in self._byzantine_nodes]
        for i in range(min(n_faulty, len(available))):
            self._byzantine_nodes.add(available[i])

    def trigger_fallback(self, n_offline: int = 2):
        available = [i for i in range(self.settings.n_validators) if i not in self._offline_nodes]
        for i in range(min(n_offline, len(available))):
            node_id = available[i]
            self._offline_nodes.add(node_id)

        # Update Tier-1 engine fallback state
        engine = self.nodes[0].consensus.get_engine(1)
        active = self.settings.n_validators - len(self._offline_nodes)
        engine.check_fallback(active)

    def reset(self):
        self._running = False
        self._benchmark_running = False
        self._total_tx = 0
        self._total_blocks = 0
        self._latencies = {1: [], 2: [], 3: []}
        self._byzantine_nodes.clear()
        self._offline_nodes.clear()
        self.anchor = EthereumAnchorSimulator(async_mode=True)
        self._init_nodes_fresh()

    def _init_nodes_fresh(self):
        self.nodes.clear()
        self._init_nodes()

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "benchmark_running": self._benchmark_running,
            "n_validators": self.settings.n_validators,
            "total_tx": self._total_tx,
            "total_blocks": self._total_blocks,
        }

    def get_metrics(self) -> dict:
        elapsed = time.time() - self._start_time if self._running else 0
        tps = self._total_tx / elapsed if elapsed > 0 else 0

        primary = self.nodes[0] if self.nodes else None
        thresholds = "0.85 / 0.60"
        if primary:
            t1, t2 = primary.rl_agent.get_thresholds()
            thresholds = f"{t1:.2f} / {t2:.2f}"

        return {
            "total_tx": self._total_tx,
            "total_blocks": self._total_blocks,
            "tps": round(tps, 1),
            "epoch": primary._epoch if primary else 0,
            "thresholds": thresholds,
            "byzantine_nodes": list(self._byzantine_nodes),
            "offline_nodes": list(self._offline_nodes),
        }

    def get_latency_stats(self) -> dict:
        stats = {}
        for tier in [1, 2, 3]:
            lats = self._latencies.get(tier, [])
            if lats:
                sorted_lats = sorted(lats)
                n = len(sorted_lats)
                stats[f"tier{tier}_mean"] = sum(lats) / n
                stats[f"tier{tier}_p50"] = sorted_lats[n // 2]
                stats[f"tier{tier}_p95"] = sorted_lats[int(n * 0.95)] if n > 1 else sorted_lats[0]
                stats[f"tier{tier}_min"] = sorted_lats[0]
                stats[f"tier{tier}_max"] = sorted_lats[-1]
            else:
                stats[f"tier{tier}_mean"] = 0
        return stats

    def benchmark_status(self) -> dict:
        return {
            "running": self._benchmark_running,
            "results": self.benchmark_runner.to_dict(),
            "latency_stats": self.get_latency_stats(),
        }
