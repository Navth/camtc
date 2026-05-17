"""Full validator node — integrates all CAMTC components."""
import asyncio
import time
from typing import Dict, List, Optional, Callable

from ..config.settings import Settings
from ..core.transaction import Transaction, TransactionMeta
from ..core.block import Block
from ..core.ledger import Ledger
from ..core.mempool import TieredMempool
from ..consensus.pbft import PBFTEngine, TieredConsensus, ConsensusMessage
from ..consensus.vrf_election import VRFLeaderElection
from ..consensus.reputation import ReputationManager
from ..ml.priority_net import PriorityNet
from ..ml.rl_agent import RLAgent
from ..crypto.signatures import generate_keypair, sign, verify, vk_to_bytes


class ValidatorNode:
    """A single CAMTC validator node."""

    def __init__(self, node_id: int, settings: Settings, priority_net: Optional[PriorityNet] = None):
        self.node_id = node_id
        self.settings = settings
        self.is_running = False

        # Cryptographic identity
        self.sk, self.vk = generate_keypair(seed=node_id.to_bytes(32, "big"))
        self.sk_bytes = bytes(self.sk)
        self.vk_bytes = vk_to_bytes(self.vk)

        # Core components
        self.ledger = Ledger(node_id)
        self.mempool = TieredMempool(
            tier1_batch=settings.tier1.max_batch, tier1_wait_ms=settings.tier1.batch_wait_ms,
            tier2_batch=settings.tier2.max_batch, tier2_wait_ms=settings.tier2.batch_wait_ms,
            tier3_batch=settings.tier3.max_batch, tier3_wait_ms=settings.tier3.batch_wait_ms,
        )

        # Consensus
        all_ids = list(range(settings.n_validators))
        self.consensus = TieredConsensus(
            tier1_committee=all_ids[:settings.tier1.committee_size],
            tier2_committee=all_ids[:settings.tier2.committee_size],
            tier3_committee=all_ids[:settings.tier3.committee_size],
            tier1_quorum=settings.tier1.quorum_fraction,
            tier2_quorum=settings.tier2.quorum_fraction,
            tier3_quorum=settings.tier3.quorum_fraction,
        )

        # VRF election
        self.vrf_election = VRFLeaderElection(settings.n_validators)

        # Reputation
        self.reputation = ReputationManager(settings.n_validators)

        # ML models
        self.priority_net = priority_net
        self.rl_agent = RLAgent()

        # Network
        self.messenger = None

        # Metrics
        self._processed_tx = 0
        self._epoch = 0
        self._last_commit_time = 0

        # Callbacks for external monitoring
        self.on_commit: Optional[Callable] = None
        self.on_tx_received: Optional[Callable] = None

    def set_messenger(self, messenger):
        self.messenger = messenger

    def score_transaction(self, tx: Transaction) -> float:
        if self.priority_net is None:
            C = tx.meta.criticality
            S = max(tx.meta.urgency, tx.meta.latency_sensitivity)
            R = 0.5
            K = tx.meta.regulatory_class
            return 0.40 * C + 0.30 * S + 0.10 * R + 0.20 * K
        return self.priority_net.predict(tx.meta.to_feature_vector())

    def route_transaction(self, tx: Transaction) -> int:
        theta1, theta2 = self.rl_agent.get_thresholds()
        if tx.priority_score > theta1:
            return 1
        elif tx.priority_score > theta2:
            return 2
        return 3

    def receive_transaction(self, tx: Transaction):
        score = self.score_transaction(tx)
        tx.priority_score = score
        tx.tier = self.route_transaction(tx)
        tx.sender_vk = self.vk_bytes
        self.mempool.enqueue(tx)
        self._processed_tx += 1
        if self.on_tx_received:
            self.on_tx_received(tx)

    def create_block(self, tier: int, txs: List[Transaction]) -> Block:
        self._epoch += 1
        return Block(
            height=0,  # assigned on ledger append
            epoch=self._epoch,
            tier=tier,
            transactions=txs,
            prev_hash=self.ledger.last_block_hash(),
            proposer_vk=self.vk_bytes,
        )

    async def propose(self, tier: int) -> Optional[Block]:
        txs = self.mempool.dequeue_batch(tier)
        if not txs:
            return None

        block = self.create_block(tier, txs)
        engine = self.consensus.get_engine(tier)

        # Simulate PBFT phases locally (in full deployment, messages go through network)
        engine.start_proposal(block, self.node_id)

        # Simulate Prepare phase — all committee members vote
        committee = engine.committee
        n_active = len(committee)
        if tier == 1:
            # Check fallback
            engine.check_fallback(n_active)

        for cid in committee:
            if cid == self.node_id:
                continue
            msg = ConsensusMessage(
                msg_type="prepare",
                epoch=engine.epoch,
                tier=tier,
                sender_id=cid,
                block_hash=block.hash(),
            )
            result = engine.receive_prepare(msg)
            if result is None and engine.phase.name == "COMMITTED":
                break

        if engine.phase.name == "COMMIT" and engine.phase.name != "COMMITTED":
            for cid in committee:
                if cid == self.node_id:
                    continue
                msg = ConsensusMessage(
                    msg_type="commit",
                    epoch=engine.epoch,
                    tier=tier,
                    sender_id=cid,
                    block_hash=block.hash(),
                )
                committed = engine.receive_commit(msg)
                if committed:
                    break

        if engine.phase.name == "COMMITTED" and engine.committed_blocks:
            committed_block = engine.committed_blocks[-1]
            self.ledger.append(committed_block)
            self._last_commit_time = time.time()

            # Update reputation
            self.reputation.update(self.node_id, "correct_proposal")

            # Update RL agent
            self.rl_agent.adapt(
                self.mempool.queue_depths(),
                tier1_latency_ms=0.0,  # would be computed from actual metrics
            )

            if self.on_commit:
                self.on_commit(committed_block, tier)

            return committed_block

        return None

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "running": self.is_running,
            "ledger": self.ledger.to_dict(),
            "mempool": {f"tier{t}": q for t, q in zip([1,2,3], self.mempool.queue_depths())},
            "consensus": self.consensus.to_dict(),
            "reputation": {self.node_id: self.reputation.to_dict()[self.node_id]},
            "processed_tx": self._processed_tx,
            "epoch": self._epoch,
        }
